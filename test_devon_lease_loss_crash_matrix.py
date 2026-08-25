"""Multi-worker concurrent lease-loss crash matrix.

Adversarial coverage for the two Hermes governance invariants under load:

1. Only the live lease owner can claim an execution and write effect
   intents or receipts; stale workers are fenced out.
2. An effect intent survives the crash of the worker that wrote it, so an
   ambiguous external effect refuses automatic retry instead of silently
   re-executing.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

WORKERS = 6


@pytest.fixture
def configured_operator(monkeypatch, tmp_path):
    from app.api.v1.operator import _bridge

    monkeypatch.setattr(_bridge, "enabled", True)
    monkeypatch.setattr(_bridge, "_operator_key", "test-operator-key")
    monkeypatch.setattr(_bridge, "root", tmp_path.resolve())
    return _bridge


async def _owner_id(db_session) -> str:
    from app.models.user import User

    result = await db_session.execute(
        select(User.id).where(User.email == "council-tester@example.com")
    )
    return str(result.scalar_one())


async def _create_read_task(client, auth_headers, goal: str) -> str:
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": goal,
            "steps": [
                {
                    "title": "Inspect",
                    "tool": "operator.read",
                    "arguments": {"command": "pwd"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["task_id"]


@pytest.mark.asyncio
async def test_concurrent_claims_yield_exactly_one_lease(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    """N workers race acquire_execution; exactly one may win the lease."""
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import AgentTaskRecord
    from app.services.agent_runtime_persistence import (
        AgentTaskRepository,
        TaskExecutionBusy,
    )

    task_id = await _create_read_task(client, auth_headers, "Race the lease claim")
    owner_id = await _owner_id(db_session)
    repo = AgentTaskRepository()

    before = (
        await db_session.execute(
            select(AgentTaskRecord.execution_generation).where(
                AgentTaskRecord.id == task_id
            )
        )
    ).scalar_one()

    async def worker(index: int):
        async with AsyncSessionLocal() as session:
            try:
                claim = await repo.acquire_execution(
                    session,
                    owner_id=owner_id,
                    task_id=task_id,
                    idempotency_key=f"racer-{index}",
                    max_steps=5,
                    lease_owner=f"worker-{index}",
                    lease_seconds=120,
                )
                await session.commit()
                return claim
            except TaskExecutionBusy as exc:
                await session.rollback()
                return exc

    outcomes = await asyncio.gather(*(worker(i) for i in range(WORKERS)))
    winners = [o for o in outcomes if not isinstance(o, TaskExecutionBusy)]
    losers = [o for o in outcomes if isinstance(o, TaskExecutionBusy)]
    assert len(winners) == 1, f"expected one lease owner, got {len(winners)}"
    assert len(losers) == WORKERS - 1

    after = (
        await db_session.execute(
            select(AgentTaskRecord.execution_generation).where(
                AgentTaskRecord.id == task_id
            )
        )
    ).scalar_one()
    assert after == before + 1, "the lease generation must move exactly once"


@pytest.mark.asyncio
async def test_two_workers_race_an_approved_write_step_only_one_effect(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    """The handover headline: two workers race a WRITE step under load.

    Whatever the interleaving, the external effect runs exactly once and
    exactly one intent/receipt pair is recorded.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import (
        AgentEffectIntentRecord,
        AgentEffectReceiptRecord,
    )
    from app.services.agent_runtime_persistence import TaskExecutionBusy
    from app.services.agent_tasks import DurableAgentTaskService

    command = "python -c \"open('race-marker.txt','a').write('x')\""
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Race one approved write effect",
            "steps": [
                {
                    "title": "Write race marker",
                    "tool": "operator.command",
                    "arguments": {"command": command},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    owner_id = await _owner_id(db_session)

    waiting = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers={**auth_headers, "Idempotency-Key": "approval-phase"},
        json={"max_steps": 5},
    )
    assert waiting.status_code == 200, waiting.text
    token = waiting.json()["approval_token"]
    request_id = waiting.json()["task"]["plan"]["steps"][0]["approval_request_id"]

    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": request_id,
            "token": token,
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.status_code == 200, decision.text

    async def worker(index: int):
        service = DurableAgentTaskService()
        async with AsyncSessionLocal() as session:
            try:
                return await service.run_until_blocked(
                    session,
                    owner_id=owner_id,
                    task_id=task_id,
                    max_steps=5,
                    idempotency_key=f"race-worker-{index}",
                )
            except TaskExecutionBusy as exc:
                await session.rollback()
                return exc

    outcomes = await asyncio.gather(worker(1), worker(2))

    # Every worker either completed cleanly or was fenced out as busy.
    for outcome in outcomes:
        assert isinstance(outcome, TaskExecutionBusy) or outcome.result

    marker = configured_operator.root / "race-marker.txt"
    assert marker.read_text() == "x", "the external effect must run exactly once"

    intents = (
        (
            await db_session.execute(
                select(AgentEffectIntentRecord).where(
                    AgentEffectIntentRecord.task_id == task_id
                )
            )
        )
        .scalars()
        .all()
    )
    receipts = (
        (
            await db_session.execute(
                select(AgentEffectReceiptRecord).where(
                    AgentEffectReceiptRecord.task_id == task_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(intents) == 1, "one effect, one durable intent"
    assert len(receipts) == 1, "one effect, one durable receipt"
    assert receipts[0].status == "succeeded"
    assert receipts[0].intent_id == intents[0].intent_id


@pytest.mark.asyncio
async def test_stale_worker_cannot_write_intent_or_receipt_after_takeover(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    """After a lease takeover, the old token and generation are dead keys."""
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import (
        AgentEffectIntentRecord,
        AgentEffectReceiptRecord,
        AgentTaskRecord,
    )
    from app.services.agent_effect_receipts import EffectReceiptRepository
    from app.services.agent_runtime_persistence import AgentTaskRepository
    from services.agent_runtime.contracts import EffectStatus

    task_id = await _create_read_task(client, auth_headers, "Fence a stale writer")
    owner_id = await _owner_id(db_session)
    repo = AgentTaskRepository()
    effects = EffectReceiptRepository()

    async with AsyncSessionLocal() as first_session:
        stale = await repo.acquire_execution(
            first_session,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key="stale-claim",
            max_steps=5,
            lease_owner="worker-stale",
            lease_seconds=15,
        )
        await first_session.commit()

    async with AsyncSessionLocal() as expire_session:
        await expire_session.execute(
            update(AgentTaskRecord)
            .where(AgentTaskRecord.id == task_id)
            .values(lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await expire_session.commit()

    async with AsyncSessionLocal() as takeover_session:
        live = await repo.acquire_execution(
            takeover_session,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key="takeover-claim",
            max_steps=5,
            lease_owner="worker-live",
            lease_seconds=120,
        )
        await takeover_session.commit()
    assert live.execution_generation > stale.execution_generation

    async with AsyncSessionLocal() as stale_intent_session:
        with pytest.raises(RuntimeError, match="effect intent refused"):
            await effects.record_intent(
                stale_intent_session,
                owner_id=owner_id,
                task_id=task_id,
                step_id="STEP-01",
                tool_name="operator.command",
                arguments={"command": "echo stale"},
                idempotency_key="stale-effect",
                lease_token=stale.lease_token,
                execution_generation=stale.execution_generation,
            )
        await stale_intent_session.rollback()

    # A legitimate intent from the live worker, then a stale receipt attempt.
    async with AsyncSessionLocal() as live_intent_session:
        intent = await effects.record_intent(
            live_intent_session,
            owner_id=owner_id,
            task_id=task_id,
            step_id="STEP-01",
            tool_name="operator.command",
            arguments={"command": "echo live"},
            idempotency_key="live-effect",
            lease_token=live.lease_token,
            execution_generation=live.execution_generation,
        )
        await live_intent_session.commit()

    async with AsyncSessionLocal() as stale_receipt_session:
        with pytest.raises(RuntimeError, match="effect receipt refused"):
            await effects.record_receipt(
                stale_receipt_session,
                owner_id=owner_id,
                task_id=task_id,
                intent_id=intent.intent_id,
                status=EffectStatus.SUCCEEDED,
                lease_token=stale.lease_token,
                execution_generation=stale.execution_generation,
            )
        await stale_receipt_session.rollback()

    stale_intents = (
        (
            await db_session.execute(
                select(AgentEffectIntentRecord).where(
                    AgentEffectIntentRecord.task_id == task_id,
                    AgentEffectIntentRecord.lease_token == stale.lease_token,
                )
            )
        )
        .scalars()
        .all()
    )
    stale_receipts = (
        (
            await db_session.execute(
                select(AgentEffectReceiptRecord).where(
                    AgentEffectReceiptRecord.task_id == task_id,
                    AgentEffectReceiptRecord.lease_token == stale.lease_token,
                )
            )
        )
        .scalars()
        .all()
    )
    assert stale_intents == [], "no intent may carry the dead lease token"
    assert stale_receipts == [], "no receipt may carry the dead lease token"


@pytest.mark.asyncio
async def test_crashed_write_leaves_durable_intent_and_next_worker_refuses(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    """The crash window itself: intent committed, worker dies before receipt.

    The durable intent must survive the crashed worker's rollback, and the
    next worker must refuse with ambiguous_external_effect instead of
    silently re-executing the write.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import AgentEffectIntentRecord
    from app.services.agent_effect_receipts import EffectReceiptRepository
    from app.services.agent_runtime_persistence import (
        AgentTaskRepository,
        AmbiguousEffectRefusal,
    )
    from app.services.agent_tasks import DurableAgentTaskService
    from app.services.leased_effect_recorder import LeasedEffectRecorder

    task_id = await _create_read_task(client, auth_headers, "Crash mid-write")
    owner_id = await _owner_id(db_session)
    repo = AgentTaskRepository()

    async with AsyncSessionLocal() as run_session:
        claim = await repo.acquire_execution(
            run_session,
            owner_id=owner_id,
            task_id=task_id,
            idempotency_key="doomed-run",
            max_steps=5,
            lease_owner="worker-doomed",
            lease_seconds=120,
        )
        await run_session.commit()

        recorder = LeasedEffectRecorder(
            db=run_session,
            owner_id=owner_id,
            lease_token=claim.lease_token,
            execution_generation=claim.execution_generation,
            session_factory=AsyncSessionLocal,
        )
        await recorder.begin_effect(
            task_id=task_id,
            step_id="STEP-01",
            tool_name="operator.command",
            arguments={"command": "echo effect"},
            idempotency_key="doomed-effect",
        )
        # The external effect runs here; then the worker dies before its
        # receipt or result can commit.
        await run_session.rollback()

    # Release the crashed worker's lease the way expiry would.
    async def _expire():
        from app.models.agent_runtime import AgentTaskRecord

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(AgentTaskRecord)
                .where(AgentTaskRecord.id == task_id)
                .values(
                    lease_expires_at=datetime.now(timezone.utc)
                    - timedelta(seconds=1)
                )
            )
            await session.commit()

    await _expire()

    surviving = (
        (
            await db_session.execute(
                select(AgentEffectIntentRecord).where(
                    AgentEffectIntentRecord.task_id == task_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(surviving) == 1, "the intent must survive the worker crash"

    orphans = await EffectReceiptRepository().find_orphan_intents(
        db_session, owner_id=owner_id, task_id=task_id
    )
    assert len(orphans) == 1
    assert orphans[0].reason == "ambiguous_external_effect"

    service = DurableAgentTaskService()
    async with AsyncSessionLocal() as next_worker_session:
        with pytest.raises(AmbiguousEffectRefusal, match="ambiguous_external_effect"):
            await service.run_until_blocked(
                next_worker_session,
                owner_id=owner_id,
                task_id=task_id,
                max_steps=5,
                idempotency_key="takeover-run",
            )

    refused = await service.get_task(db_session, owner_id=owner_id, task_id=task_id)
    assert refused is not None
    assert refused.state.value == "failed"
    assert refused.failure_reason == "ambiguous_external_effect"


@pytest.mark.asyncio
async def test_orphan_refusal_holds_under_concurrent_run_attempts(
    client,
    auth_headers,
    db_session,
    configured_operator,
):
    """Load does not open a retry hole: every concurrent attempt refuses."""
    from app.db.session import AsyncSessionLocal
    from app.models.agent_runtime import AgentEffectIntentRecord, AgentTaskRecord
    from app.services.agent_runtime_persistence import (
        AmbiguousEffectRefusal,
        TaskExecutionBusy,
    )
    from app.services.agent_tasks import DurableAgentTaskService

    task_id = await _create_read_task(client, auth_headers, "Orphan under load")
    owner_id = await _owner_id(db_session)

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as seed_session:
        seed_session.add(
            AgentEffectIntentRecord(
                id="EIR-MATRIX-ORPHAN",
                intent_id="INT-MATRIX-ORPHAN",
                task_id=task_id,
                owner_id=owner_id,
                step_id="STEP-01",
                tool_name="operator.command",
                arguments_hash="deadbeef",
                idempotency_key="crashed-effect",
                execution_generation=1,
                lease_token=None,
                created_at=now,
            )
        )
        await seed_session.commit()

    async def worker(index: int):
        service = DurableAgentTaskService()
        async with AsyncSessionLocal() as session:
            try:
                return await service.run_until_blocked(
                    session,
                    owner_id=owner_id,
                    task_id=task_id,
                    max_steps=3,
                    idempotency_key=f"orphan-racer-{index}",
                )
            except (AmbiguousEffectRefusal, TaskExecutionBusy) as exc:
                await session.rollback()
                return exc

    outcomes = await asyncio.gather(*(worker(i) for i in range(WORKERS)))
    assert all(
        isinstance(o, AmbiguousEffectRefusal) for o in outcomes
    ), f"every attempt must refuse; got {[type(o).__name__ for o in outcomes]}"

    row = (
        await db_session.execute(
            select(AgentTaskRecord).where(AgentTaskRecord.id == task_id)
        )
    ).scalar_one()
    assert row.lease_token is None, "no refusal may leave a claimed lease behind"
    assert row.payload["state"] == "failed"
    assert row.payload["failure_reason"] == "ambiguous_external_effect"
