"""
Dispatcher and orphan-sweep integration tests.

The dispatcher's job is narrow and its failure modes are expensive: firing a
workflow twice, firing six times after an outage, firing one whose gate is
still open, or letting one tenant's malformed cadence stop everyone else's
schedule. Each of those has a test here.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.models.workflow import Workflow, WorkflowRun
from app.services.dispatcher import compute_next_run_at, dispatch_due
from app.services.maintenance import sweep_orphaned_runs

READ_ONLY_STEPS = [
    {"id": "recall", "type": "knowledge_search", "config": {"query": "market intel"}}
]

EFFECT_STEPS = READ_ONLY_STEPS + [
    {"id": "remember", "type": "memory_write", "config": {"content": "noted"}}
]


def scheduled(cadence="daily:07:00", steps=None):
    return {
        "version": 1,
        "trigger": {"type": "schedule", "config": {"cadence": cadence}},
        "steps": steps or READ_ONLY_STEPS,
    }


async def _user_id(db):
    return await db.scalar(text("SELECT id FROM users LIMIT 1"))


async def _make_workflow(db, *, definition, status="active", next_run_at=None, name="W"):
    workflow = Workflow(
        owner_id=await _user_id(db),
        name=name,
        definition=definition,
        status=status,
        meta={},
        next_run_at=next_run_at,
    )
    db.add(workflow)
    await db.flush()
    return workflow


# ---------------------------------------------------------------------------
# next_run_at
# ---------------------------------------------------------------------------


async def test_manual_workflows_never_get_a_slot(db_session, auth_headers):
    workflow = await _make_workflow(
        db_session,
        definition={
            "version": 1,
            "trigger": {"type": "manual", "config": {}},
            "steps": READ_ONLY_STEPS,
        },
    )
    assert compute_next_run_at(workflow, now=datetime.now(timezone.utc)) is None


async def test_an_unparseable_cadence_yields_no_slot_instead_of_raising(
    db_session, auth_headers
):
    """Pre-5.1 validation accepted any non-empty string; those rows still exist."""
    workflow = await _make_workflow(
        db_session, definition=scheduled(cadence="every other tuesday")
    )
    assert compute_next_run_at(workflow, now=datetime.now(timezone.utc)) is None


async def test_a_valid_cadence_yields_a_future_slot(db_session, auth_headers):
    workflow = await _make_workflow(db_session, definition=scheduled())
    now = datetime.now(timezone.utc)
    assert compute_next_run_at(workflow, now=now) > now


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def test_a_due_workflow_starts_a_run(db_session, auth_headers):
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(
        db_session, definition=scheduled(), next_run_at=now - timedelta(minutes=1)
    )
    report = await dispatch_due(db_session, now=now)

    assert len(report.started) == 1
    run = (
        await db_session.execute(
            select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
        )
    ).scalar_one()
    assert run.trigger == "schedule"
    assert run.meta["idempotency_key"].startswith("schedule:")


async def test_a_workflow_not_yet_due_is_left_alone(db_session, auth_headers):
    now = datetime.now(timezone.utc)
    await _make_workflow(
        db_session, definition=scheduled(), next_run_at=now + timedelta(hours=1)
    )
    report = await dispatch_due(db_session, now=now)
    assert report.started == []


async def test_paused_and_draft_workflows_are_not_dispatched(db_session, auth_headers):
    now = datetime.now(timezone.utc)
    for status in ("paused", "draft", "archived"):
        await _make_workflow(
            db_session,
            definition=scheduled(),
            status=status,
            next_run_at=now - timedelta(minutes=1),
            name=f"W-{status}",
        )
    report = await dispatch_due(db_session, now=now)
    assert report.started == []


async def test_dispatch_advances_the_slot_so_it_does_not_refire(
    db_session, auth_headers
):
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(
        db_session,
        definition=scheduled(cadence="hourly:00"),
        next_run_at=now - timedelta(minutes=1),
    )
    await dispatch_due(db_session, now=now)
    assert workflow.next_run_at > now
    assert workflow.last_fired_at == now

    second = await dispatch_due(db_session, now=now)
    assert second.started == [], "the same slot fired twice"


async def test_a_six_hour_outage_fires_once_not_six_times(db_session, auth_headers):
    """Catch-up policy: skip the backlog deliberately."""
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(
        db_session,
        definition=scheduled(cadence="hourly:00"),
        next_run_at=now - timedelta(hours=6),
    )
    report = await dispatch_due(db_session, now=now)

    assert len(report.started) == 1
    assert workflow.next_run_at > now, "next slot is computed from now, not the backlog"

    runs = (
        await db_session.execute(
            select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
        )
    ).scalars().all()
    assert len(runs) == 1


async def test_a_workflow_with_an_open_gate_is_skipped(db_session, auth_headers):
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(
        db_session,
        definition=scheduled(steps=EFFECT_STEPS),
        next_run_at=now - timedelta(minutes=1),
    )
    first = await dispatch_due(db_session, now=now)
    assert len(first.started) == 1

    run = (
        await db_session.execute(
            select(WorkflowRun).where(WorkflowRun.workflow_id == workflow.id)
        )
    ).scalar_one()
    assert run.status == "awaiting_approval", "the effect step must have paused"

    workflow.next_run_at = now - timedelta(seconds=1)
    await db_session.flush()
    second = await dispatch_due(db_session, now=now)

    assert second.started == []
    assert workflow.id in second.skipped


async def test_one_broken_workflow_does_not_stop_the_batch(db_session, auth_headers):
    """Multi-tenant blast radius: a malformed cadence is one tenant's problem."""
    now = datetime.now(timezone.utc)
    await _make_workflow(
        db_session,
        definition=scheduled(cadence="nonsense"),
        next_run_at=now - timedelta(minutes=1),
        name="broken",
    )
    await _make_workflow(
        db_session,
        definition=scheduled(),
        next_run_at=now - timedelta(minutes=1),
        name="healthy",
    )
    report = await dispatch_due(db_session, now=now)

    assert len(report.started) == 1
    assert len(report.skipped) == 1


async def test_a_workflow_whose_cadence_broke_gets_its_slot_cleared(
    db_session, auth_headers
):
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(
        db_session,
        definition=scheduled(cadence="nonsense"),
        next_run_at=now - timedelta(minutes=1),
    )
    await dispatch_due(db_session, now=now)
    assert workflow.next_run_at is None, "it would otherwise be retried every minute"


async def test_the_batch_is_bounded(db_session, auth_headers):
    now = datetime.now(timezone.utc)
    for i in range(4):
        await _make_workflow(
            db_session,
            definition=scheduled(),
            next_run_at=now - timedelta(minutes=1),
            name=f"W{i}",
        )
    report = await dispatch_due(db_session, now=now, limit=2)
    assert len(report.started) == 2


# ---------------------------------------------------------------------------
# Orphan sweep
# ---------------------------------------------------------------------------


async def test_the_sweep_fails_runs_stranded_by_a_dead_process(
    db_session, auth_headers
):
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(db_session, definition=scheduled())
    stale = WorkflowRun(
        workflow_id=workflow.id,
        user_id=workflow.owner_id,
        status="running",
        trigger="schedule",
        step_results=[],
        approvals={},
        meta={},
        started_at=now - timedelta(hours=2),
    )
    db_session.add(stale)
    await db_session.flush()

    assert await sweep_orphaned_runs(db_session, older_than_minutes=30) == 1
    await db_session.refresh(stale)
    assert stale.status == "failed"
    assert "process running this workflow ended" in stale.error_message
    assert stale.completed_at is not None


async def test_the_sweep_leaves_a_run_that_is_genuinely_in_flight(
    db_session, auth_headers
):
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(db_session, definition=scheduled())
    fresh = WorkflowRun(
        workflow_id=workflow.id,
        user_id=workflow.owner_id,
        status="running",
        trigger="manual",
        step_results=[],
        approvals={},
        meta={},
        started_at=now - timedelta(minutes=2),
    )
    db_session.add(fresh)
    await db_session.flush()

    assert await sweep_orphaned_runs(db_session, older_than_minutes=30) == 0
    await db_session.refresh(fresh)
    assert fresh.status == "running"


async def test_the_sweep_never_touches_a_run_waiting_on_a_human(
    db_session, auth_headers
):
    """An open gate is not an orphan, however long it has been sitting there."""
    now = datetime.now(timezone.utc)
    workflow = await _make_workflow(db_session, definition=scheduled(steps=EFFECT_STEPS))
    waiting = WorkflowRun(
        workflow_id=workflow.id,
        user_id=workflow.owner_id,
        status="awaiting_approval",
        trigger="schedule",
        pending_step_id="remember",
        step_results=[],
        approvals={},
        meta={},
        started_at=now - timedelta(days=9),
    )
    db_session.add(waiting)
    await db_session.flush()

    assert await sweep_orphaned_runs(db_session, older_than_minutes=30) == 0
    await db_session.refresh(waiting)
    assert waiting.status == "awaiting_approval"
