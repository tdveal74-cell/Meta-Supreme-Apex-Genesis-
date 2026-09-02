"""Fix PR 8 from the DEVON and Hermes audit, H8: the knowledge-loop commit.

The approval was spent on the approval store's own connection before any
ledger row was durable, and the Pinecone and n8n effects ran in between.
A failure after the spend left a spent approval, a fired webhook and no
ledger row; the retry was refused as already spent with nothing to show
why. The ledger rows are durable before the spend now, a failed effect
leaves ACTION_FAILED on the intent, and commits of one request are
serialized on the intent.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.services import knowledge_loop as loop_module
from app.services.knowledge_loop import KnowledgeLoop, KnowledgeLoopRefused
from app.services.live_state_ledger import ledger
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


async def _event_names(db_session, owner_id: str, intent_id: str) -> list:
    opened = await ledger.read_intent(db_session, owner_id=owner_id, intent_id=intent_id)
    return [event["name"] for event in opened["events"]]


async def test_a_failed_effect_after_the_spend_leaves_a_ledger_trace(
    client, auth_headers, db_session, monkeypatch
):
    """The audit's run: the effect fails after the approval is spent."""
    intent_id, request_id = await _approved(client, auth_headers)
    owner_id = await _owner_id(db_session)

    async def broken_router(self, candidate, filing_plan):
        raise RuntimeError("n8n webhook refused the connection")

    monkeypatch.setattr(KnowledgeLoop, "_maybe_route_n8n", broken_router)
    failed = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert failed.status_code == 502, failed.text
    assert "ACTION_FAILED" in failed.text

    names = await _event_names(db_session, owner_id, intent_id)
    assert names.count("ACTION_STARTED") == 1
    assert "ARTIFACT_CREATED" in names
    assert names.count("ACTION_FAILED") == 1
    assert "ACTION_COMPLETED" not in names
    assert loop_module._queue().get(request_id).state is ApprovalState.CONSUMED

    again = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
    assert again.status_code == 403, again.text
    assert "spent" in again.text.lower()


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

    names = await _event_names(db_session, owner_id, intent_id)
    assert "ACTION_STARTED" in names and "ARTIFACT_CREATED" in names
    assert "ACTION_FAILED" not in names
    assert queue.get(request_id).state is ApprovalState.APPROVED, "nothing was spent"

    monkeypatch.setattr(queue, "consume", real_consume)
    again = await client.post(
        "/api/v1/soul/commit", headers=auth_headers, json={"request_id": request_id}
    )
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
