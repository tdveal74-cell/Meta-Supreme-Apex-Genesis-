"""Fix PR 8 from the DEVON and Hermes audit, H8: the knowledge-loop commit.

The approval was spent on the approval store's own connection before any
ledger row was durable, and the Pinecone and n8n effects ran in between.
A failure after the spend left a spent approval, a fired webhook and no
ledger row; the retry was refused as already spent with nothing to show
why. The ledger rows are durable before the spend now, everything after
the spend runs inside a failure recorder that leaves ACTION_FAILED on the
intent, the refusal of a spent approval names the intent and its terminal
event, and commits of one request are serialized on the intent.

The fresh critic on the first cut found the recorder wired to a path
production cannot reach (the connectors swallow their own errors) while
the ledger writes after the effect ran outside it. The failing write these
tests use is the receipt, the one a database can refuse.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.api.v1.soul import _loop_error
from app.services import knowledge_loop as loop_module
from app.services.knowledge_loop import KnowledgeLoop, KnowledgeLoopRefused
from app.services.live_state_ledger import LedgerConflict, ledger
from services.devon.approval import ApprovalState

RULING_KEY = "test-ruling-key-not-a-jwt"
LEGIT = "Lesson: the ledger row is the receipt, not the chat."


@pytest.fixture(autouse=True)
def _ruling_key_env(monkeypatch):
    monkeypatch.setenv("DEVON_RULING_KEY", RULING_KEY)


def _ruled(auth_headers):
    return {**auth_headers, "X-Devon-Ruling-Key": RULING_KEY}


async def _approved(client, auth_headers, text_: str = LEGIT):
    proposed = await client.post(
        "/api/v1/soul/propose", headers=auth_headers, json={"text": text_}
    )
    assert proposed.status_code == 201, proposed.text
    body = proposed.json()
    intent_id = body["intent_id"]
    request_id = body["approval"]["request_id"]
    approved = await client.post(
        "/api/v1/soul/approve",
        headers=_ruled(auth_headers),
        json={"request_id": request_id, "token": body["approval"]["token"]},
    )
    assert approved.status_code == 200, approved.text
    return intent_id, request_id


async def _owner_id(db_session, email: str = "council-tester@example.com") -> str:
    row = await db_session.execute(
        text("SELECT id FROM users WHERE email = :email"), {"email": email}
    )
    return str(row.scalar_one())


async def _events(db_session, owner_id: str, intent_id: str) -> list:
    opened = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    return list(opened["events"])


async def _event_names(db_session, owner_id: str, intent_id: str) -> list:
    return [event["name"] for event in await _events(db_session, owner_id, intent_id)]


async def _commit(client, auth_headers, request_id: str):
    return await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )


async def _locked_receipt(*args, **kwargs):
    raise RuntimeError("receipt table locked")


async def test_a_failed_ledger_write_after_the_spend_leaves_a_trace(
    client, auth_headers, db_session, monkeypatch
):
    """The audit's run on the path production can reach: the receipt write
    fails after the approval is spent."""
    intent_id, request_id = await _approved(client, auth_headers)
    owner_id = await _owner_id(db_session)

    monkeypatch.setattr(ledger, "issue_receipt", _locked_receipt)
    failed = await _commit(client, auth_headers, request_id)
    assert failed.status_code == 502, failed.text
    assert "ACTION_FAILED" in failed.text
    assert intent_id in failed.text

    events = await _events(db_session, owner_id, intent_id)
    names = [event["name"] for event in events]
    assert names.count("ACTION_STARTED") == 1
    assert "ARTIFACT_CREATED" in names
    assert names.count("ACTION_FAILED") == 1
    assert "ACTION_COMPLETED" not in names, "the uncommitted completion was rolled back"
    trace = next(event for event in events if event["name"] == "ACTION_FAILED")["payload"]
    assert trace["consumed"] is True
    assert "receipt table locked" in trace["error"]
    assert trace["approval_request_id"] == request_id
    assert loop_module._queue().get(request_id).state is ApprovalState.CONSUMED

    again = await _commit(client, auth_headers, request_id)
    assert again.status_code == 403, again.text
    assert "already spent" in again.text
    assert intent_id in again.text
    assert "ACTION_FAILED" in again.text and "receipt table locked" in again.text


async def test_a_refusing_connector_is_a_completed_capture(
    client, auth_headers, db_session, monkeypatch
):
    """n8n unreachable after the spend: the capture completes, the refusal is
    on ACTION_COMPLETED and in the response, and nothing is marked failed.
    The artifact was durable before the spend; a failed webhook is not a
    failed capture."""
    intent_id, request_id = await _approved(client, auth_headers)
    owner_id = await _owner_id(db_session)

    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://127.0.0.1:9")
    done = await _commit(client, auth_headers, request_id)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["executed"] is True
    assert body["n8n"]["routed"] is False
    assert "n8n route failed" in body["n8n"]["reason"]

    events = await _events(db_session, owner_id, intent_id)
    names = [event["name"] for event in events]
    assert "ACTION_FAILED" not in names
    assert names.count("ACTION_COMPLETED") == 1
    completed = next(event for event in events if event["name"] == "ACTION_COMPLETED")["payload"]
    assert completed["approval_request_id"] == request_id
    assert completed["consumed"] is True
    assert completed["n8n_routed"] is False
    assert completed["n8n"]["routed"] is False
    assert "n8n route failed" in completed["n8n"]["reason"]
    assert "127.0.0.1:9" not in completed["n8n"]["reason"], "the webhook URL stays out of the ledger"
    assert loop_module._queue().get(request_id).state is ApprovalState.CONSUMED

    again = await _commit(client, auth_headers, request_id)
    assert again.status_code == 403, again.text
    assert "ACTION_COMPLETED" in again.text and "Nothing to retry" in again.text


async def test_a_lost_trace_still_names_the_gap_on_retry(
    client, auth_headers, db_session, monkeypatch
):
    """The recorder itself fails: the 502 says the trace could not be written,
    and the retry names the ACTION_STARTED with no terminal event."""
    intent_id, request_id = await _approved(client, auth_headers)
    owner_id = await _owner_id(db_session)

    async def ledger_down(self, db, **kwargs):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(ledger, "issue_receipt", _locked_receipt)
    monkeypatch.setattr(KnowledgeLoop, "_record_failure", ledger_down)
    failed = await _commit(client, auth_headers, request_id)
    assert failed.status_code == 502, failed.text
    assert "could not be written" in failed.text
    assert "receipt table locked" in failed.text

    names = await _event_names(db_session, owner_id, intent_id)
    assert "ACTION_STARTED" in names
    assert "ACTION_FAILED" not in names and "ACTION_COMPLETED" not in names
    assert loop_module._queue().get(request_id).state is ApprovalState.CONSUMED

    again = await _commit(client, auth_headers, request_id)
    assert again.status_code == 403, again.text
    assert "no ACTION_COMPLETED or ACTION_FAILED" in again.text
    assert intent_id in again.text


async def test_ledger_rows_are_durable_before_the_spend(
    client, auth_headers, db_session, monkeypatch
):
    """The process dies between the ledger rows and the spend: the rows stand,
    the approval is unspent, and the next commit fails closed with the reason."""
    intent_id, request_id = await _approved(client, auth_headers)
    owner_id = await _owner_id(db_session)
    queue = loop_module._queue()
    real_consume = queue.consume

    def dying_consume(*args, **kwargs):
        raise RuntimeError("approval store connection dropped")

    monkeypatch.setattr(queue, "consume", dying_consume)
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        with pytest.raises(RuntimeError, match="connection dropped"):
            await loop_module.knowledge_loop.commit(
                session, owner_id=owner_id, request_id=request_id
            )
        await session.rollback()

    events = await _events(db_session, owner_id, intent_id)
    names = [event["name"] for event in events]
    assert "ACTION_STARTED" in names and "ARTIFACT_CREATED" in names
    assert "ACTION_FAILED" not in names
    started = next(event for event in events if event["name"] == "ACTION_STARTED")["payload"]
    assert "consumed" not in started, "ACTION_STARTED does not claim a spend state"
    assert queue.get(request_id).state is ApprovalState.APPROVED, "nothing was spent"

    monkeypatch.setattr(queue, "consume", real_consume)
    again = await _commit(client, auth_headers, request_id)
    assert again.status_code == 409, again.text
    assert "already started" in again.text
    assert queue.get(request_id).state is ApprovalState.APPROVED


async def test_two_concurrent_commits_run_the_effect_once(client, auth_headers, db_session):
    intent_id, request_id = await _approved(client, auth_headers)
    owner_id = await _owner_id(db_session)
    from app.db.session import AsyncSessionLocal

    async def worker():
        async with AsyncSessionLocal() as session:
            try:
                return await loop_module.knowledge_loop.commit(
                    session, owner_id=owner_id, request_id=request_id
                )
            except KnowledgeLoopRefused as exc:
                await session.rollback()
                return exc

    outcomes = await asyncio.gather(worker(), worker())
    executed = [o for o in outcomes if isinstance(o, dict) and o.get("executed")]
    refused = [o for o in outcomes if isinstance(o, KnowledgeLoopRefused)]
    assert len(executed) == 1 and len(refused) == 1, [type(o).__name__ for o in outcomes]
    assert refused[0].status_code in {403, 409}

    names = await _event_names(db_session, owner_id, intent_id)
    assert names.count("ACTION_STARTED") == 1, names
    assert names.count("ARTIFACT_CREATED") == 1, names
    assert names.count("ACTION_COMPLETED") == 1, names
    assert "ACTION_FAILED" not in names
    assert loop_module._queue().get(request_id).state is ApprovalState.CONSUMED


def test_a_ledger_race_answers_409_not_500():
    """A writer that bypasses the advisory lock (the generic ledger event
    route) turns a race into LedgerConflict; the route maps it to 409."""
    assert _loop_error(LedgerConflict("Another writer appended first")).status_code == 409
