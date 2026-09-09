"""The enrichment call site: proof that a suggestion reaches the filing plan.

DCD-07, raised by the 2026-09-02 agent audit, was that
`services/intelligence/enrichment.py` and `app/services/intelligence.py` held a
whole enrichment lane that nothing called. The code was covered by sixteen tests
and none of them proved a capture had ever been tagged, because none of them
went through a caller.

WHY THIS FILE EXISTS AND WHY IT LOOKS LIKE THIS

The offline lane sets ENRICHMENT_PROVIDER=mock, and under the mock provider the
entire suite stays green with `suggest_area` replaced by `return None`. So a
green run proves nothing about this wiring unless a test drives a provider that
actually answers and then checks the answer arrived in the plan. That is
`test_a_supplied_area_reaches_the_filing_plan`, and its negative control is
`test_without_a_suggestion_the_same_capture_declines`: the same words, no
provider, no Area.

Every provider here is a real `CerebrasProvider` over an httpx MockTransport,
the pattern `test_devon_cerebras.py` established. Nothing reaches the network,
and nothing reaches a database either, so this file belongs in the standalone
job's list.
"""

import asyncio
import json
import logging
from datetime import date, datetime, timezone

import httpx
import pytest
from sqlalchemy.exc import DBAPIError

from app.services import capture_enrichment
from app.services.capture_enrichment import (
    NON_ENRICHING_PROVIDERS,
    enrichment_is_configured,
    suggest_area,
)
from app.services.knowledge_loop import _plan_from, _utterance_for
from app.services.provider_usage import ProviderSpendCapExceeded
from services.devon.assistant import FIXED_AREA_INTENTS, Devon
from services.devon.commands import ALL_INTENTS, Kind
from services.intelligence.enrichment import DECLINE_TOKEN
from services.intelligence.providers import CerebrasProvider
from services.intelligence.providers.cerebras_provider import DEFAULT_MODEL

#: Deliberately signal free. `resolve_area` declines on it, so any Area on a
#: plan built from it can only have come from the suggestion. Measured, not
#: assumed: see test_the_payload_carries_no_keyword_signal.
NEUTRAL = "the zzz qqq widget"


@pytest.fixture(autouse=True)
def _no_cached_provider():
    """`get_enrichment_provider` is lru_cached over settings.

    A test that changes ENRICHMENT_PROVIDER and then calls into the factory
    would otherwise be served the provider built by whichever test ran first,
    and the failure would look like a wiring bug rather than a cache.
    """
    from app.services.intelligence import get_enrichment_provider

    get_enrichment_provider.cache_clear()
    yield
    get_enrichment_provider.cache_clear()


def _provider(content: str, *, calls: list | None = None) -> CerebrasProvider:
    """A real provider whose socket is an httpx MockTransport."""

    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": DEFAULT_MODEL,
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 20},
            },
        )

    return CerebrasProvider(api_key="test-key", transport=httpx.MockTransport(handler))


class _Raises(CerebrasProvider):
    """A provider whose `complete` raises something enrich_capture does not catch."""

    def __init__(self, exc: BaseException) -> None:
        super().__init__(
            api_key="test-key",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        self._exc = exc
        self.calls = 0

    async def complete(self, request):  # type: ignore[override]
        self.calls += 1
        raise self._exc


# -- the payload the rest of the file leans on -----------------------------


def test_the_payload_carries_no_keyword_signal():
    """If this ever classifies, every Area assertion below stops proving anything."""
    plan = Devon().ask(f"remember {NEUTRAL}").plan
    assert plan is not None
    assert plan.area is None, f"{NEUTRAL!r} now classifies as {plan.area}"
    assert plan.area_provenance == "declined, no signal"


# -- the load bearing pair -------------------------------------------------


@pytest.mark.asyncio
async def test_a_supplied_area_reaches_the_filing_plan():
    """End to end: prose in, provider asked, Area on the plan.

    This is the test DCD-07 was missing. It starts from the phrasing the
    knowledge loop actually receives, which does not parse as a capture on its
    own, and follows it through utterance selection, the provider call and the
    trust ladder to a filed Area.
    """
    calls: list = []
    provider = _provider(json.dumps({"area": "ACX", "summary": "a widget note"}), calls=calls)

    utterance = _utterance_for(NEUTRAL)
    assert utterance == f"remember {NEUTRAL}"

    result = await suggest_area(utterance, provider=provider)
    assert result is not None
    assert result.area_label == "ACX"
    assert result.summary == "a widget note"

    plan = _plan_from(utterance, suggested_area=result.area_label)
    assert plan is not None
    assert plan.area == "ACX"
    assert plan.area_provenance == "supplied and validated"

    # The provider was asked about the words that were filed, not the raw text.
    assert len(calls) == 1
    assert NEUTRAL in json.dumps(calls[0])


def test_without_a_suggestion_the_same_capture_declines():
    """The negative control for the test above.

    Without it, that test would pass on a build where the Area came from
    anywhere at all.
    """
    plan = _plan_from(_utterance_for(NEUTRAL), suggested_area=None)
    assert plan is not None
    assert plan.area is None
    assert plan.area_provenance == "declined, no signal"


def test_prose_is_prefixed_before_it_is_tagged():
    """The knowledge loop is fed prose, and prose parses as nothing.

    Tagging the raw text would return None from `area_suggestion_text` for the
    whole lane, so the wiring would read as done while never once running. The
    guard is that the prefixed form has something to tag and the raw form does
    not.
    """
    assert Devon().ask(NEUTRAL).plan is None
    assert Devon().area_suggestion_text(NEUTRAL) is None
    assert Devon().area_suggestion_text(_utterance_for(NEUTRAL)) == NEUTRAL


def test_an_utterance_that_already_files_is_not_rewritten():
    assert _utterance_for(f"remember {NEUTRAL}") == f"remember {NEUTRAL}"


def test_nothing_to_file_selects_no_utterance():
    """"remember" alone carries no payload, and prefixing it again changes nothing."""
    assert _utterance_for("remember") is None
    assert _plan_from(None) is None


# -- what is worth asking about --------------------------------------------


@pytest.mark.asyncio
async def test_a_query_spends_nothing():
    provider = _Raises(AssertionError("a query must not reach a provider"))
    assert await suggest_area("what is on my plate today", provider=provider) is None
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_an_intent_that_fixes_its_own_area_spends_nothing():
    provider = _Raises(AssertionError("episode_idea must not reach a provider"))
    assert await suggest_area(f"new episode idea {NEUTRAL}", provider=provider) is None
    assert provider.calls == 0


@pytest.mark.parametrize("name", sorted(FIXED_AREA_INTENTS))
def test_every_fixed_area_intent_really_fixes_its_area(name):
    """Half one of the drift guard on FIXED_AREA_INTENTS.

    The constant is a list of names because the handlers pass force_area inside
    a call expression and there is nothing to introspect. A name listed here
    that no longer forces an Area would silently stop a lane being enriched.
    """
    intent = next((i for i in ALL_INTENTS if i.name == name), None)
    assert intent is not None, f"{name} is not an intent any more"
    assert intent.kind is Kind.CAPTURE
    plan = Devon().ask(f"{intent.phrases[0]} {NEUTRAL}").plan
    assert plan is not None
    assert plan.area_provenance == "fixed by intent"


@pytest.mark.parametrize(
    "name", sorted(i.name for i in ALL_INTENTS if i.kind is Kind.CAPTURE)
)
def test_a_call_is_spent_exactly_when_the_answer_would_be_read(name):
    """Half two, and the stronger half.

    For every capture intent: a suggestion is asked for if and only if the plan
    would actually consult one. A new capture intent that forces its Area and is
    not added to FIXED_AREA_INTENTS fails here, and so does a name left in the
    set after its handler stopped forcing.
    """
    intent = next(i for i in ALL_INTENTS if i.name == name)
    utterance = f"{intent.phrases[0]} {NEUTRAL}"
    devon = Devon()
    asked = devon.area_suggestion_text(utterance)
    plan = devon.ask(utterance, suggested_area="ACX").plan

    if asked is None:
        # Nothing was spent, so nothing may depend on an answer.
        assert plan is None or plan.area_provenance != "supplied and validated", (
            f"{name} files from a suggestion it never asks for"
        )
        assert name in FIXED_AREA_INTENTS or not intent.takes_payload
    else:
        assert plan is not None, f"{name} spends a provider call and files nothing"
        assert plan.area == "ACX"
        assert plan.area_provenance == "supplied and validated", (
            f"{name} asks for a suggestion and then ignores it"
        )


# -- the gate --------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_mock_lane_asks_nobody(monkeypatch):
    """The offline lane must behave exactly as it did before this wiring landed.

    The mock provider fabricates a value per declared JSON key without reading
    the capture, so its Area is discarded on the next line. Asking it would buy
    nothing and spend a metered call and two database round trips.
    """
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "mock")
    assert not enrichment_is_configured()
    assert await suggest_area(f"remember {NEUTRAL}") is None


def test_the_gate_names_the_provider_rather_than_a_flag(monkeypatch):
    """Setting ENRICHMENT_PROVIDER to a real provider is what turns tagging on.

    That is the sentence docs/devon/DEVON.md carries, so it is asserted here
    rather than described there and hoped for.
    """
    assert "mock" in NON_ENRICHING_PROVIDERS
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "cerebras")
    assert enrichment_is_configured()


@pytest.mark.asyncio
async def test_a_provider_that_cannot_be_built_loses_no_capture(monkeypatch):
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "cerebras")
    import app.services.intelligence as intelligence

    def boom():
        raise RuntimeError("no key")

    monkeypatch.setattr(intelligence, "get_enrichment_provider", boom)
    assert await suggest_area(f"remember {NEUTRAL}") is None


# -- failure is never a lost capture ---------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        ConnectionRefusedError("no route to the provider"),
        DBAPIError("SELECT 1", {}, Exception("the cap check could not read")),
        ProviderSpendCapExceeded(
            tenant_id="t",
            cap=1,
            used=2,
            day=date(2026, 9, 9),
            resets_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        ),
    ],
    ids=["socket", "database", "spend-cap"],
)
async def test_enrichment_failure_degrades_to_no_suggestion(exc):
    """`enrich_capture` handles ProviderError itself. Nothing else does.

    The metered wrapper raises outside that family: ProviderSpendCapExceeded is
    an AppError, the cap check and the usage record are database round trips,
    and a socket error can arrive unwrapped. A capture must file through all of
    it, so the guard at the call site is broad and this proves it.
    """
    provider = _Raises(exc)
    assert await suggest_area(f"remember {NEUTRAL}", provider=provider) is None
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_a_cancelled_request_stays_cancelled():
    """CancelledError is a BaseException and must not be swallowed as a failure.

    A broad `except Exception` is correct here and a broad `except BaseException`
    would not be: it would turn a client that hung up into a capture that files.
    """
    provider = _Raises(asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await suggest_area(f"remember {NEUTRAL}", provider=provider)


# -- the model is allowed to say no ----------------------------------------


@pytest.mark.asyncio
async def test_a_declining_model_is_not_an_invented_area():
    provider = _provider(json.dumps({"area": DECLINE_TOKEN, "summary": "nothing here"}))
    result = await suggest_area(f"remember {NEUTRAL}", provider=provider)
    assert result is not None
    assert result.area_label is None
    assert result.declined is True
    assert _plan_from(_utterance_for(NEUTRAL), suggested_area=result.area_label).area is None


@pytest.mark.asyncio
async def test_an_area_outside_the_nine_is_discarded_not_filed():
    provider = _provider(json.dumps({"area": "Crypto", "summary": "a widget note"}))
    result = await suggest_area(f"remember {NEUTRAL}", provider=provider)
    assert result is not None
    assert result.model_suggested_area == "Crypto"
    assert result.area_label is None
    assert "rejected" in result.area_provenance

# -- what a fresh critic found on 2026-09-09 -------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["Mock", "MOCK", " mock ", "mock\n"])
async def test_the_gate_normalises_the_provider_name_the_way_the_factory_does(
    monkeypatch, name
):
    """F3. `create_provider` lowercases and strips; the gate must agree.

    With `ENRICHMENT_PROVIDER=Mock` the unnormalised gate said enrich, the
    factory built a MockProvider anyway, and every capture spent a metered call
    and a cap check on an answer discarded on the next line.
    """
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", name)
    assert not enrichment_is_configured(), f"{name!r} passed the gate"
    assert await suggest_area(f"remember {NEUTRAL}") is None


@pytest.mark.asyncio
async def test_the_offline_lane_does_not_even_parse(monkeypatch):
    """F5. The gate is asked before the parse, not after.

    `parse` on 4000 characters that match no intent runs the full fuzzy pass,
    measured at 276 ms of blocking CPU. On the lane that will never call a
    provider, that must cost nothing at all.
    """
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "mock")

    def explode(_text):
        raise AssertionError("the offline lane parsed the utterance")

    monkeypatch.setattr(capture_enrichment._DEVON, "area_suggestion_text", explode)
    assert await suggest_area(f"remember {NEUTRAL}") is None


@pytest.mark.asyncio
async def test_the_summary_never_reaches_an_info_log(caplog, monkeypatch):
    """F2. A critic read a card number and a medical detail out of the INFO log.

    The model quotes the capture inside its own summary, and four of the nine
    Areas are Health, Money, Family and Learning. What stays at INFO is enough
    to answer "is this lane running and is it any good" and none of it is the
    capture.
    """
    secret = "amex 3782822463 10005 and the biopsy on Tuesday"
    provider = _provider(json.dumps({"area": "Money", "summary": secret}))
    with caplog.at_level(logging.INFO, logger="app.services.capture_enrichment"):
        result = await suggest_area(f"remember {NEUTRAL}", provider=provider)
    assert result is not None and result.summary == secret

    info = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert info, "the lane logged nothing at INFO, so it cannot be read at all"
    rendered = " ".join(r.getMessage() for r in info)
    assert secret not in rendered, rendered
    assert "3782822463" not in rendered
    # The operational half must still be there, or the fix traded one blind
    # spot for another.
    assert "Money" in rendered
    assert "provider=cerebras" in rendered
    assert "tokens=" in rendered


def test_the_status_reading_says_what_it_does_and_does_not_know(monkeypatch):
    """F4. A lane that can stop running silently is what DCD-07 was."""
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "mock")
    reading = capture_enrichment.status()
    assert reading["enrichment_provider"] == "mock"
    assert reading["enrichment_configured"] is False
    assert "provider_built" in reading
    # The reading must not imply a working key, because it has not seen one.
    assert "not a working key" in reading["note"]


@pytest.mark.asyncio
async def test_a_built_provider_is_recorded_so_a_reader_can_tell(monkeypatch):
    monkeypatch.setattr(capture_enrichment, "_provider_built", False)
    monkeypatch.setattr(capture_enrichment.settings, "ENRICHMENT_PROVIDER", "cerebras")
    import app.services.intelligence as intelligence

    provider = _provider(json.dumps({"area": "ACX", "summary": "a note"}))
    monkeypatch.setattr(intelligence, "get_enrichment_provider", lambda: provider)
    assert capture_enrichment.status()["provider_built"] is False
    result = await suggest_area(f"remember {NEUTRAL}")
    assert result is not None and result.area_label == "ACX"
    assert capture_enrichment.status()["provider_built"] is True

