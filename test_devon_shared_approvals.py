"""Regression coverage for DEVON's PostgreSQL shared approval authority."""

import asyncio
import hashlib
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from app.services.devon_approval_store import (
    PostgresApprovalStore,
    build_approval_queue,
)
from services.devon.approval import ApprovalQueue, ApprovalState, RefusalReason


def _dsn() -> str:
    value = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme_test",
    )
    return value.replace("postgresql+asyncpg://", "postgresql://")


def _queue() -> ApprovalQueue:
    return ApprovalQueue(PostgresApprovalStore(_dsn(), connect_timeout_seconds=3))


def _request(queue: ApprovalQueue):
    return queue.request(
        title="Deploy verified DEVON change",
        what_happens="Merges one verified change after Tee rules on it.",
        requested_by="DEVON Agent Runtime",
        area="Systems",
        reversible=False,
        blast_radius="one repository target branch",
    )


@pytest.mark.asyncio
async def test_pending_request_survives_queue_reconstruction(_clean_tables):
    first = _queue()
    record, token = await asyncio.to_thread(_request, first)

    # A new store and queue model a new worker/process consulting the same DB.
    second = _queue()
    seen = await asyncio.to_thread(second.get, record.request_id)
    assert seen is not None
    assert seen.state is ApprovalState.PENDING
    assert seen.what_happens == record.what_happens

    ruled = await asyncio.to_thread(
        second.decide,
        record.request_id,
        token,
        "approve",
        "Tee",
    )
    assert ruled.approved is True

    # The original worker reads the authoritative decision back from PostgreSQL.
    read_back = await asyncio.to_thread(first.get, record.request_id)
    assert read_back is not None
    assert read_back.state is ApprovalState.APPROVED
    assert read_back.decided_by == "Tee"


@pytest.mark.asyncio
async def test_two_workers_cannot_both_win_the_same_ruling(_clean_tables):
    first = _queue()
    second = _queue()
    record, token = await asyncio.to_thread(_request, first)

    approve, refuse = await asyncio.gather(
        asyncio.to_thread(first.decide, record.request_id, token, "approve", "Tee-A"),
        asyncio.to_thread(second.decide, record.request_id, token, "refuse", "Tee-B"),
    )

    winners = [result for result in (approve, refuse) if result.ok]
    losers = [result for result in (approve, refuse) if not result.ok]
    assert len(winners) == 1
    assert len(losers) == 1
    assert losers[0].reason is RefusalReason.ALREADY_DECIDED

    final = await asyncio.to_thread(_queue().get, record.request_id)
    assert final is not None
    assert final.state is winners[0].state
    assert final.state in {ApprovalState.APPROVED, ApprovalState.REFUSED}


@pytest.mark.asyncio
async def test_plaintext_token_is_never_persisted(_clean_tables):
    queue = _queue()
    record, token = await asyncio.to_thread(_request, queue)

    def read_hash() -> str:
        with psycopg.connect(_dsn()) as conn:
            row = conn.execute(
                "SELECT token_hash FROM devon_approvals WHERE request_id = %s",
                (record.request_id,),
            ).fetchone()
            assert row is not None
            return str(row[0])

    stored_hash = await asyncio.to_thread(read_hash)
    assert stored_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert token not in stored_hash


@pytest.mark.asyncio
async def test_expiry_is_durable_across_workers(_clean_tables):
    first = _queue()
    record, token = await asyncio.to_thread(_request, first)
    later = datetime.now(timezone.utc) + timedelta(hours=73)

    result = await asyncio.to_thread(
        _queue().decide,
        record.request_id,
        token,
        "approve",
        "Tee",
        later,
    )
    assert result.ok is False
    assert result.reason is RefusalReason.EXPIRED

    persisted = await asyncio.to_thread(_queue().get, record.request_id)
    assert persisted is not None
    assert persisted.state is ApprovalState.EXPIRED
    assert persisted.decided_at is not None


@pytest.mark.asyncio
async def test_pending_listing_durably_sweeps_overdue_rows(_clean_tables):
    queue = _queue()
    record, _ = await asyncio.to_thread(_request, queue)

    def force_expired() -> None:
        with psycopg.connect(_dsn()) as conn:
            conn.execute(
                "UPDATE devon_approvals "
                "SET created_at = NOW() - INTERVAL '2 hours', "
                "expires_at = NOW() - INTERVAL '1 minute' "
                "WHERE request_id = %s",
                (record.request_id,),
            )

    await asyncio.to_thread(force_expired)
    pending = await asyncio.to_thread(_queue().pending)
    assert all(item.request_id != record.request_id for item in pending)

    durable = await asyncio.to_thread(_queue().get, record.request_id)
    assert durable is not None
    assert durable.state is ApprovalState.EXPIRED


@pytest.mark.asyncio
async def test_devon_api_reports_shared_durable_state_without_token_recovery(client):
    response = await client.get("/api/v1/devon/approvals")
    assert response.status_code == 200, response.text
    storage = response.json()["storage"]
    assert storage == {
        "backend": "postgres",
        "shared": True,
        "state_durable": True,
        "plaintext_tokens_persisted": False,
        "token_recoverable": False,
    }


@pytest.mark.asyncio
async def test_devon_identity_reports_shared_durable_approval_state(client):
    response = await client.get("/api/v1/devon")
    assert response.status_code == 200, response.text
    assert response.json()["approval_storage"] == {
        "backend": "postgres",
        "shared": True,
        "state_durable": True,
        "plaintext_tokens_persisted": False,
        "token_recoverable": False,
    }


def test_memory_backend_must_be_explicit():
    queue = build_approval_queue(mode="memory")
    assert queue.storage_backend == "memory"


def test_unknown_backend_fails_closed():
    with pytest.raises(ValueError, match="DEVON_APPROVAL_STORE"):
        build_approval_queue(mode="redis")
