"""The enrichment lane end to end, through the two routes that carry it.

`test_devon_capture_enrichment.py` proves the call site works in isolation and
runs with no database, which is what puts it in the standalone job. This file
proves the two callers actually reach it, which needs the API and the ledger.

The distinction matters because the isolated file stays green on a build where
`propose` never calls `suggest_area` at all. That was the exact shape of DCD-07:
sixteen passing tests around a function nothing invoked.

Nothing here reaches the network. The provider is a real `CerebrasProvider` over
an httpx MockTransport, and `get_enrichment_provider` is replaced so the metered
wrapper and its spend cap stay out of the way. ENRICHMENT_PROVIDER is set to
cerebras for the duration, because the offline default deliberately asks nobody.
"""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import text as sql_text

from app.services import capture_enrichment
from services.intelligence.providers import CerebrasProvider
from services.intelligence.providers.cerebras_provider import DEFAULT_MODEL

#: Signal free, so an Area on the plan can only have come from the model.
NEUTRAL = "the zzz qqq widget"


@pytest.fixture
def enricher(monkeypatch):
    """Turn the lane on, and hand it a provider that answers ACX.

    Returns the list of request bodies the provider saw, so a test can assert
    both that a call happened and that it was about the right words.
    """
    seen: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": DEFAULT_MODEL,
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"area": "ACX", "summary": "a widget note"}
                            )
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 30, "completion_tokens": 20},
            },
        )

    provider = CerebrasProvider(api_key="test-key", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "cerebras")

    import app.services.intelligence as intelligence

    # Held before the patch: monkeypatch restores the attribute on teardown, and
    # the plain function put in its place has no cache to clear. The factory is
    # lru_cached over settings, so a provider built while ENRICHMENT_PROVIDER was
    # something else would outlive this fixture and answer the next test.
    factory = intelligence.get_enrichment_provider
    factory.cache_clear()
    monkeypatch.setattr(intelligence, "get_enrichment_provider", lambda: provider)
    yield seen
    factory.cache_clear()


async def _plan_created(db_session, request_id: str) -> dict:
    """The PLAN_CREATED payload the loop wrote for this approval request."""
    rows = await db_session.execute(
        sql_text("SELECT payload FROM events WHERE name = 'PLAN_CREATED'")
    )
    for (payload,) in rows.all():
        if str(payload.get("approval_request_id") or "") == request_id:
            return payload
    raise AssertionError(f"no PLAN_CREATED for {request_id}")


async def test_propose_tags_prose_that_does_not_parse_as_a_capture(
    client, auth_headers, db_session, enricher
):
    """The knowledge loop's real input is prose, and prose parses as nothing.

    So the lane only works if `propose` prefixes before it tags. This is the
    test that goes red if it tags the raw text instead: the provider would be
    asked about an utterance DEVON does not understand, `area_suggestion_text`
    would return None, and no call would be made at all.
    """
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": NEUTRAL},
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()

    assert len(enricher) == 1, "propose did not reach the enrichment provider"
    assert NEUTRAL in json.dumps(enricher[0])

    assert body["plan"]["area"] == "ACX"
    assert body["plan"]["area_provenance"] == "supplied and validated"
    assert body["plan"]["executed"] is False

    payload = await _plan_created(db_session, body["approval"]["request_id"])
    assert payload["enrichment"]["area"] == "ACX"
    assert payload["enrichment"]["summary"] == "a widget note"
    assert payload["enrichment"]["model_suggested_area"] == "ACX"
    assert payload["enrichment"]["provider"] == "cerebras"


async def test_an_area_the_caller_supplied_spends_no_call(
    client, auth_headers, enricher
):
    """A caller who names the Area has outranked anything a model could infer."""
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": NEUTRAL, "area": "Systems"},
    )
    assert proposed.status_code == 201, proposed.text
    assert enricher == [], "an Area was supplied and a provider was asked anyway"


async def test_the_chat_command_route_tags_a_capture(client, auth_headers, enricher):
    answered = await client.post(
        "/api/v1/devon/command",
        headers=auth_headers,
        json={"text": f"remember {NEUTRAL}"},
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert len(enricher) == 1, "the command route did not reach the provider"
    assert body["plan"]["area"] == "ACX"
    assert body["plan"]["area_provenance"] == "supplied and validated"


async def test_the_chat_command_route_spends_nothing_on_a_query(
    client, auth_headers, enricher
):
    answered = await client.post(
        "/api/v1/devon/command",
        headers=auth_headers,
        json={"text": "what is on my plate today"},
    )
    assert answered.status_code == 200, answered.text
    assert enricher == [], "a query reached the enrichment provider"


async def test_the_offline_default_asks_nobody(client, auth_headers, monkeypatch):
    """No fixture here on purpose: this is the lane CI actually runs.

    ENRICHMENT_PROVIDER=mock is the offline default, and a capture must still
    file exactly as it did before this wiring existed. If the gate ever moves,
    every provider-backed test in the suite starts making calls and this is what
    says so.
    """
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "mock")
    answered = await client.post(
        "/api/v1/devon/command",
        headers=auth_headers,
        json={"text": "remember the vespera cold open needs work"},
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["plan"]["area"] == "Podcast"
    assert answered.json()["plan"]["area_provenance"] == "keyword classification"

# -- F1: a bad byte in the model's summary must not cost the capture -------


@pytest.fixture
def dirty_enricher(monkeypatch):
    """A provider whose summary carries a NUL, which jsonb cannot store.

    Found by a fresh critic on 2026-09-09 driving the live route: the block went
    straight into a hash chained jsonb payload, `provenance.check_payload`
    refused it, `append_event` refused, propose answered 409 and the capture was
    lost. `_clean_summary` collapses whitespace and truncates; it removes
    neither a NUL nor a lone surrogate.
    """

    import app.services.intelligence as intelligence

    # Held before any patch, for the same reason the `enricher` fixture above
    # holds it: monkeypatch restores the attribute on teardown and the plain
    # function put in its place has no cache to clear.
    factory = intelligence.get_enrichment_provider

    def make(summary: str):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "model": DEFAULT_MODEL,
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"area": "ACX", "summary": summary})
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 20},
                },
            )

        provider = CerebrasProvider(
            api_key="test-key", transport=httpx.MockTransport(handler)
        )
        monkeypatch.setattr(
            capture_enrichment.settings, "ENRICHMENT_PROVIDER", "cerebras"
        )
        factory.cache_clear()
        monkeypatch.setattr(intelligence, "get_enrichment_provider", lambda: provider)
        return provider

    yield make
    factory.cache_clear()


@pytest.mark.parametrize(
    "summary",
    ["a widget \u0000 note", "a widget \ud800 note"],
    ids=["nul", "lone-surrogate"],
)
async def test_a_summary_the_ledger_refuses_still_files_the_capture(
    client, auth_headers, db_session, dirty_enricher, summary
):
    """The capture is what matters. The audit note is not worth losing it for."""
    dirty_enricher(summary)
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": NEUTRAL},
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()

    # The Area the model supplied still made it through: only the note was lost.
    assert body["plan"]["area"] == "ACX"
    assert body["plan"]["area_provenance"] == "supplied and validated"

    payload = await _plan_created(db_session, body["approval"]["request_id"])
    assert payload["enrichment"] is None, "a payload the ledger refuses was stored"


async def test_a_clean_summary_is_still_kept_whole(
    client, auth_headers, db_session, dirty_enricher
):
    """The negative control for the pair above.

    Without it, dropping every enrichment block unconditionally would pass them.
    """
    dirty_enricher("a widget note")
    proposed = await client.post(
        "/api/v1/soul/propose",
        headers=auth_headers,
        json={"text": NEUTRAL},
    )
    assert proposed.status_code == 201, proposed.text
    payload = await _plan_created(db_session, proposed.json()["approval"]["request_id"])
    assert payload["enrichment"]["summary"] == "a widget note"
    assert payload["enrichment"]["area"] == "ACX"

