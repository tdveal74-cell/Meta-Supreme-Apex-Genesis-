"""DEVON now runs the goals it records, and neither owner sees the other's.

WHY THIS FILE EXISTS

Until 2026-09-10 a scheduled agent goal was recorded durably and never ran.
`materialize_due_schedules` had one caller, the manual HTTP route, and the cron
the API image ships drove only the Workflow lane. The capability was complete,
tested and unreachable, which is the shape every door in this estate has had.

The runner in app/services/agent_scheduler.py closes it, and the hard part is
not the cron line. `materialize_due_schedules` is owner scoped and a cron has no
owner, so the runner has to enumerate owners itself. Get that wrong in the
obvious way, by materializing across owners in one call or by inventing a system
owner id, and one account's scheduled goal becomes a task in another account's
list. `test_two_owners_due_goals_never_cross` is the proof that it does not, run
with two real users and two real schedules rather than argued from the code.

The second thing under test is the honesty of the report, because this lane logs
into a file nobody reads. A failure must not be able to look like an idle night.
The pure half of that lives in test_devon_scheduler_report_honesty.py; here it is
checked against a real failure, injected into the real runner.

DATABASE: the runner commits per owner through its own sessions, so the fixtures
below commit their users and schedules first. `_clean_tables` truncates
afterwards as it does for every other database test in the suite.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from sqlalchemy import text

from app.core.tenant_context import current_tenant_id
from app.db.session import AsyncSessionLocal
from app.services import agent_scheduler
from app.services.agent_scheduler import materialize_due_agent_schedules
from app.services.agent_tasks import agent_tasks_service
from app.services.hermes_expansion_persistence import HermesExpansionRepository
from services.agent_runtime.contracts import TaskState
from services.agent_runtime.expansion import ScheduleState
from services.agent_runtime.scheduler_report import (
    STATE_COMPLETE,
    STATE_NOTHING_DUE,
    STATE_PARTIAL,
)

REPO = HermesExpansionRepository()
ROOT = Path(__file__).resolve().parent


async def _owner(db) -> str:
    """A real user row. owner_id on agent_schedules carries a users FK."""
    owner_id = str(uuid.uuid4())
    await db.execute(
        text(
            "INSERT INTO users (id, email, password_hash, is_active, is_verified)"
            " VALUES (CAST(:id AS uuid), :email, :pw, TRUE, TRUE)"
        ),
        {"id": owner_id, "email": f"runner-{owner_id}@example.com", "pw": "x"},
    )
    return owner_id


async def _schedule(db, owner_id: str, goal: str, *, seconds: int = -60) -> str:
    """A schedule due `seconds` from now. Negative is already due."""
    item = await REPO.create_schedule(
        db,
        owner_id=owner_id,
        goal=goal,
        run_at=datetime.now(timezone.utc) + timedelta(seconds=seconds),
        context={"probe": goal},
    )
    return item.schedule_id


async def _rows(db) -> List[Dict[str, Any]]:
    """Every schedule row with the owner of the task it points at.

    The uuid columns are cast in SQL. Read raw, asyncpg hands back UUID objects
    while the owner ids these tests hold are strings, and `UUID(x) == x` is
    False, so an owner comparison would fail for the wrong reason.
    """
    result = await db.execute(
        text(
            "SELECT s.schedule_id, s.owner_id::text AS schedule_owner, s.goal,"
            "       s.state, s.task_id, t.owner_id::text AS task_owner,"
            "       t.goal AS task_goal, t.state AS task_state,"
            "       t.payload AS task_payload"
            "  FROM agent_schedules s"
            "  LEFT JOIN agent_tasks t ON t.id = s.task_id"
            " ORDER BY s.goal"
        )
    )
    return [dict(row) for row in result.mappings().all()]


@pytest.fixture
async def two_owners(db_session) -> Tuple[str, str]:
    """Two committed users. Committed because the runner reads its own sessions."""
    first = await _owner(db_session)
    second = await _owner(db_session)
    await db_session.commit()
    return first, second


# ---------------------------------------------------------------------------
# The door: a due goal now becomes a task without anybody posting a route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_runner_materializes_a_due_goal_with_no_http_request(
    db_session, two_owners
) -> None:
    owner, _other = two_owners
    schedule_id = await _schedule(db_session, owner, "Nightly estate check")
    await db_session.commit()

    report = await materialize_due_agent_schedules(db_session)

    assert report.state == STATE_COMPLETE, report.summary()
    assert report.owners_scanned == 1
    assert report.created_total == 1
    assert report.healthy is True

    rows = await _rows(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row["schedule_id"] == schedule_id
    assert row["task_id"], "the schedule was left with no task, so nothing ran it"
    assert row["task_owner"] == owner
    assert row["task_goal"] == "Nightly estate check"


@pytest.mark.asyncio
async def test_the_task_the_runner_creates_is_still_human_gated(
    db_session, two_owners
) -> None:
    """CLAUDE.md: materialize and spawn never auto run effects.

    The runner may create work. It may not perform it. A task that came back
    already running, completed or holding a lease would mean cron executed
    something with no person in the loop.
    """
    owner, _other = two_owners
    await _schedule(db_session, owner, "Post the thing")
    await db_session.commit()

    await materialize_due_agent_schedules(db_session)

    row = (await _rows(db_session))[0]
    assert row["task_state"] == TaskState.PLANNED.value, (
        f"the runner left the task in {row['task_state']!r}; anything past "
        "planned means cron ran it"
    )

    lease = await db_session.execute(
        text(
            "SELECT lease_token, lease_owner, execution_generation, current_step"
            "  FROM agent_tasks WHERE id = :id"
        ),
        {"id": row["task_id"]},
    )
    fenced = lease.mappings().one()
    assert fenced["lease_token"] is None, "an execution lease was taken by cron"
    assert fenced["lease_owner"] is None
    assert fenced["execution_generation"] == 0
    assert fenced["current_step"] == 0

    # No run, no effect intent and no receipt. Those three tables are the record
    # of something having actually happened.
    for table in ("agent_task_runs", "agent_effect_intents", "agent_effect_receipts"):
        count = await db_session.scalar(text(f"SELECT count(*) FROM {table}"))
        assert count == 0, f"{table} has {count} rows after a materialize only pass"


# ---------------------------------------------------------------------------
# The hard part: owner enumeration that cannot leak
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_owners_due_goals_never_cross(db_session, two_owners) -> None:
    """The proof the commission asked for, with two real owners.

    A cron has no owner, so the runner enumerates them. If it enumerated wrongly
    (one call across owners, or a single invented system owner) one of these two
    goals would land in the other account's task list, and that is the failure
    this asserts against directly rather than trusting the call to be scoped.
    """
    first, second = two_owners
    first_schedule = await _schedule(db_session, first, "AAA first owner goal")
    second_schedule = await _schedule(db_session, second, "BBB second owner goal")
    await db_session.commit()

    report = await materialize_due_agent_schedules(db_session)

    assert report.state == STATE_COMPLETE, report.summary()
    assert report.owners_scanned == 2
    assert report.created_total == 2
    assert sorted(item.owner_id for item in report.succeeded) == sorted([first, second])

    rows = {row["schedule_id"]: row for row in await _rows(db_session)}
    assert set(rows) == {first_schedule, second_schedule}

    mine = rows[first_schedule]
    theirs = rows[second_schedule]

    assert mine["task_owner"] == first
    assert theirs["task_owner"] == second
    assert mine["task_id"] != theirs["task_id"]
    assert mine["task_goal"] == "AAA first owner goal"
    assert theirs["task_goal"] == "BBB second owner goal"

    # The owner stamped into the task context is what every approval card and
    # every list query is scoped by, so it has to agree with the row.
    assert mine["task_payload"]["context"]["owner_id"] == first
    assert theirs["task_payload"]["context"]["owner_id"] == second

    # And the same read through the service each owner actually uses: neither
    # owner can see the other's task at all.
    for owner, expected_goal, forbidden_goal in (
        (first, "AAA first owner goal", "BBB second owner goal"),
        (second, "BBB second owner goal", "AAA first owner goal"),
    ):
        visible = await agent_tasks_service.list_tasks(db_session, owner_id=owner)
        goals = [task.goal for task in visible]
        assert goals == [expected_goal], (
            f"owner {owner} sees {goals}; the runner leaked across owners"
        )
        assert forbidden_goal not in goals


@pytest.mark.asyncio
async def test_the_owner_scan_reads_only_what_is_actually_due(
    db_session, two_owners
) -> None:
    """A future goal is not due, and an owner with only future goals is not scanned."""
    now_owner, later_owner = two_owners
    await _schedule(db_session, now_owner, "due now")
    await _schedule(db_session, later_owner, "due in an hour", seconds=3600)
    await db_session.commit()

    owners = await REPO.owners_with_due_schedules(db_session)
    assert owners == [now_owner], (
        f"the scan returned {owners}; an owner whose only goal is in the future "
        "would be charged a planner call for nothing"
    )

    report = await materialize_due_agent_schedules(db_session)
    assert report.owners_scanned == 1
    assert report.created_total == 1

    rows = {row["goal"]: row for row in await _rows(db_session)}
    assert rows["due now"]["task_id"]
    assert rows["due in an hour"]["task_id"] is None
    assert rows["due in an hour"]["state"] == ScheduleState.PENDING.value


@pytest.mark.asyncio
async def test_an_owner_whose_goals_are_all_claimed_is_not_scanned_again(
    db_session, two_owners
) -> None:
    """A second tick must not create a second task for the same schedule."""
    owner, _other = two_owners
    await _schedule(db_session, owner, "Only once")
    await db_session.commit()

    first = await materialize_due_agent_schedules(db_session)
    assert first.created_total == 1

    second = await materialize_due_agent_schedules(db_session)
    assert second.state == STATE_NOTHING_DUE, second.summary()
    assert second.created_total == 0

    count = await db_session.scalar(text("SELECT count(*) FROM agent_tasks"))
    assert count == 1, f"{count} tasks for one schedule after two ticks"


@pytest.mark.asyncio
async def test_nothing_due_is_reported_as_nothing_due(db_session, two_owners) -> None:
    report = await materialize_due_agent_schedules(db_session)
    assert report.state == STATE_NOTHING_DUE
    assert report.owners_scanned == 0
    assert report.created_total == 0
    assert report.healthy is True


# ---------------------------------------------------------------------------
# Spend attribution: the cron must not launder a tenant's planner call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_owners_tenant_is_bound_while_the_goal_is_planned(
    db_session, two_owners, monkeypatch
) -> None:
    """app/core/tenant_context.py's own rule, checked rather than assumed.

    create_task plans through the provider. Unbound, that spend lands on
    SYSTEM_TENANT, which is the estate paying for a tenant's scheduled goal and
    a per account spend cap that never applies to the account that asked.
    """
    first, second = two_owners
    await _schedule(db_session, first, "AAA bound goal")
    await _schedule(db_session, second, "BBB bound goal")
    await db_session.commit()

    seen: List[Tuple[str, str | None]] = []
    real = agent_tasks_service.materialize_due_schedules

    async def watched(db, *, owner_id):
        seen.append((owner_id, current_tenant_id()))
        return await real(db, owner_id=owner_id)

    monkeypatch.setattr(agent_tasks_service, "materialize_due_schedules", watched)

    report = await materialize_due_agent_schedules(db_session)
    assert report.state == STATE_COMPLETE, report.summary()

    assert len(seen) == 2, f"expected one call per owner, got {seen}"
    for owner_id, tenant in seen:
        assert tenant == owner_id, (
            f"the materializer ran for {owner_id} with the tenant bound to "
            f"{tenant!r}; that owner's planner spend is not theirs"
        )

    assert current_tenant_id() is None, "the binding outlived the batch"


# ---------------------------------------------------------------------------
# The negative control's target: a failure may never read as an idle night
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_owners_failure_is_named_and_does_not_silence_the_other(
    db_session, two_owners, monkeypatch
) -> None:
    """The honesty property of this door, against a real injected failure.

    Two owners, one of whom cannot be materialized. Three things must all hold:
    the other owner's goal still becomes a task, the failed owner is named as
    unread rather than counted as zero, and the batch does not report healthy.
    """
    broken, working = two_owners
    broken_schedule = await _schedule(db_session, broken, "AAA broken owner goal")
    working_schedule = await _schedule(db_session, working, "BBB working owner goal")
    await db_session.commit()

    real = agent_tasks_service.materialize_due_schedules

    async def selective(db, *, owner_id):
        if owner_id == broken:
            raise RuntimeError("planner unreachable for this owner")
        return await real(db, owner_id=owner_id)

    monkeypatch.setattr(agent_tasks_service, "materialize_due_schedules", selective)

    report = await materialize_due_agent_schedules(db_session)

    assert report.state == STATE_PARTIAL, report.summary()
    assert report.healthy is False, (
        "a batch that left an owner unread reported healthy, so dispatch.py "
        "would exit 0 and the failure would never surface"
    )
    assert report.unresolved_owners == [broken]
    assert report.created_total == 1, (
        "the working owner's goal was not materialized, so one owner's failure "
        "stopped everyone else's schedule"
    )

    failure = report.failed[0]
    assert failure.created is None, (
        "the failed owner carries a created count; a rolled back owner created "
        "nothing and its due schedules are unread, which is not the same as zero"
    )
    assert "planner unreachable" in failure.error

    sentence = report.summary()
    assert broken in sentence
    assert "unread" in sentence
    assert "nothing to materialize" not in sentence, (
        "the summary of a partial failure reads like an idle night"
    )

    rows = {row["schedule_id"]: row for row in await _rows(db_session)}
    assert rows[working_schedule]["task_id"], "the healthy owner was collateral"
    assert rows[working_schedule]["task_owner"] == working
    assert rows[broken_schedule]["task_id"] is None
    assert rows[broken_schedule]["state"] != ScheduleState.RUNNING.value, (
        "the failed owner's schedule was left claiming a task it never got"
    )


@pytest.mark.asyncio
async def test_a_failed_owner_is_deferred_so_the_next_tick_does_not_re_plan_it(
    db_session, monkeypatch
) -> None:
    """The cost containment, measured across three real ticks.

    WHAT THIS IS ABOUT. `materialize_due_schedules` calls `create_task`, which
    plans through the provider BEFORE anything can fail. Nothing advanced a
    failed owner's rows, so the same rows were due again on the next tick and the
    plan was spent again. An adversary measured it on 2026-09-10: three ticks,
    three planner calls, zero tasks committed, the row still due with task_id
    NULL. On the documented `* * * * *` cron that is 1,440 provider calls a day
    for one broken schedule, forever.

    app/services/dispatcher.py:143 already had the rule and says so in its own
    comment. This asserts the schedule lane now follows it.
    """
    owner = await _owner(db_session)
    schedule_id = await _schedule(db_session, owner, "poison pill")
    await db_session.commit()

    real = agent_tasks_service.materialize_due_schedules
    calls: List[str] = []

    async def counted(db, *, owner_id):
        calls.append(owner_id)
        # Raise AFTER the real call has planned, which is the expensive shape.
        await real(db, owner_id=owner_id)
        raise RuntimeError("attach failed after the plan was spent")

    monkeypatch.setattr(agent_tasks_service, "materialize_due_schedules", counted)

    first = await materialize_due_agent_schedules(db_session)
    assert first.healthy is False, first.summary()
    assert len(calls) == 1, calls
    outcome = first.failed[0]
    assert outcome.deferred_until, (
        "the failed owner was not deferred, so the next tick re-plans the same "
        "rows and the report says nothing about it"
    )
    assert first.spinning_owners == [], (
        f"a deferred owner is being reported as spinning: {first.summary()}"
    )

    # Two more ticks. The rows are no longer due, so the owner is not even
    # enumerated and the planner is not called again.
    second = await materialize_due_agent_schedules(db_session)
    third = await materialize_due_agent_schedules(db_session)
    assert len(calls) == 1, (
        f"the planner was called {len(calls)} times across three ticks ({calls}). "
        "One broken schedule is spending a plan every tick"
    )
    assert second.state == STATE_NOTHING_DUE, second.summary()
    assert third.state == STATE_NOTHING_DUE, third.summary()

    rows = {row["schedule_id"]: row for row in await _rows(db_session)}
    row = rows[schedule_id]
    assert row["task_id"] is None, "a failed materialization attached a task"
    moved = await db_session.execute(
        text(
            "SELECT run_at, failure_reason FROM agent_schedules"
            " WHERE schedule_id = :sid"
        ),
        {"sid": schedule_id},
    )
    run_at, reason = moved.one()
    assert run_at > datetime.now(timezone.utc), (
        f"run_at is {run_at}, still in the past, so the row is due again now"
    )
    assert "attach failed after the plan was spent" in reason, (
        "the row was moved and does not say why, so an operator sees a goal "
        "silently sliding into the future"
    )
    # The goal is not lost: it comes back one backoff window later.
    assert run_at < datetime.now(timezone.utc) + timedelta(hours=1), (
        f"the deferral pushed the goal to {run_at}, which reads as dropped "
        "rather than retried"
    )


@pytest.mark.asyncio
async def test_an_owner_whose_deferral_cannot_land_is_named_as_spinning(
    db_session, monkeypatch
) -> None:
    """A deferral that fails must not be reported as one that worked.

    The whole point of the field is that a reader can tell "costed" from
    "unbounded". If a failed deferral read as a successful one, the report would
    be quietly claiming a containment that is not there.
    """
    owner = await _owner(db_session)
    await _schedule(db_session, owner, "undeferrable")
    await db_session.commit()

    async def broken_materialize(db, *, owner_id):
        raise RuntimeError("planner unreachable")

    async def broken_defer(db, **kwargs):
        raise RuntimeError("the deferral update itself failed")

    monkeypatch.setattr(
        agent_tasks_service, "materialize_due_schedules", broken_materialize
    )
    monkeypatch.setattr(
        agent_scheduler._repo, "defer_due_schedules", broken_defer
    )

    report = await materialize_due_agent_schedules(db_session)
    assert report.healthy is False
    assert report.failed[0].deferred_until == "", (
        "a deferral that raised was recorded as a deferral that landed"
    )
    assert report.spinning_owners == [owner]
    assert "NOT deferred" in report.summary(), report.summary()
    assert "planner unreachable" in report.failed[0].error, (
        "the deferral failure replaced the original reason, so the real cause is "
        "gone from the log"
    )


@pytest.mark.asyncio
async def test_a_failed_owner_scan_is_not_reported_as_an_empty_store(
    db_session, two_owners, monkeypatch
) -> None:
    """The scan itself failing is the worst case: it looks like a quiet estate."""
    owner, _other = two_owners
    await _schedule(db_session, owner, "unreadable goal")
    await db_session.commit()

    async def broken_scan(db, **kwargs):
        raise RuntimeError("agent_schedules unreadable")

    monkeypatch.setattr(
        agent_scheduler._repo, "owners_with_due_schedules", broken_scan
    )

    report = await materialize_due_agent_schedules(db_session)

    assert report.state != STATE_NOTHING_DUE
    assert report.healthy is False
    assert report.created_total is None, (
        "a scan that never ran reported a count; 0 there is an invented number"
    )
    assert report.owners_scanned is None
    assert "agent_schedules unreadable" in report.summary()
    assert "nothing to materialize" not in report.summary()

    rows = await _rows(db_session)
    assert rows[0]["task_id"] is None, "work happened despite the scan failing"


# ---------------------------------------------------------------------------
# The lock, and the lane it must not share
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_second_runner_backs_off_without_claiming_it_read_anything(
    db_session, two_owners
) -> None:
    """Two runners overlapping must not both plan the same goal."""
    owner, _other = two_owners
    await _schedule(db_session, owner, "Contended goal")
    await db_session.commit()

    async with AsyncSessionLocal() as holder:
        held = await holder.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": 0x5F1D16}
        )
        assert held is True, "could not take the runner's lock to simulate a rival"
        try:
            report = await materialize_due_agent_schedules(db_session)
        finally:
            await holder.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": 0x5F1D16}
            )

    assert report.locked_out is True
    assert report.created_total is None, (
        "a locked out runner read nothing, so it has no count to report"
    )
    assert report.healthy is True, "another runner holding the lock is not a failure"

    rows = await _rows(db_session)
    assert rows[0]["task_id"] is None

    # And the lock is released for the next tick.
    again = await materialize_due_agent_schedules(db_session)
    assert again.locked_out is False
    assert again.created_total == 1


@pytest.mark.asyncio
async def test_the_workflow_lane_lock_does_not_lock_this_lane_out(
    db_session, two_owners
) -> None:
    """The two lanes share dispatch.py and must not share the advisory key.

    Sharing it would mean a workflow batch holding its lock blocks the schedule
    lane for the whole tick, which is a door reopening quietly.
    """
    from app.services.agent_scheduler import _ADVISORY_LOCK_KEY as SCHEDULE_KEY
    from app.services.dispatcher import _ADVISORY_LOCK_KEY as WORKFLOW_KEY

    assert WORKFLOW_KEY != SCHEDULE_KEY

    owner, _other = two_owners
    await _schedule(db_session, owner, "Runs beside a workflow batch")
    await db_session.commit()

    async with AsyncSessionLocal() as holder:
        held = await holder.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": WORKFLOW_KEY}
        )
        assert held is True
        try:
            report = await materialize_due_agent_schedules(db_session)
        finally:
            await holder.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": WORKFLOW_KEY}
            )

    assert report.locked_out is False
    assert report.created_total == 1


# ---------------------------------------------------------------------------
# The catalog, in the direction test_devon_scheduler_honesty.py leaves open
# ---------------------------------------------------------------------------


def test_the_matrix_names_a_runner_that_exists_on_disk() -> None:
    """A named runner has to point at something a reader can open.

    test_devon_scheduler_honesty.py couples the NAME to the ast call graph and
    the FLAG to the deployment's SCHEDULER_TICK_INSTALLED. This closes the half
    neither covers: the name has to resolve to a module on disk that really calls
    the materializer, and dispatch.py has to really call that module.

    Note what this test does NOT assert any more. It required runs_goals True on
    the strength of the runner existing, and an adversary showed on 2026-09-10
    that the two are different facts: the live Railway project carried this image
    and scheduled nothing, so a runner existed and no goal could fire. The flag
    is now a deployment reading, so it is False in CI and in any deployment that
    has not set the variable, and that is the honest answer rather than a
    regression.
    """
    expansion = agent_tasks_service.tool_catalog()["expansion"]
    assert isinstance(expansion, dict)
    status = expansion["scheduler_status"]
    assert isinstance(status, dict)

    assert status["records_goals"] is True
    assert status["runner_in_image"] is True, (
        "the runner is in this image and the matrix does not say so"
    )

    runner = status["runner"]
    assert isinstance(runner, str) and runner.strip(), (
        "the matrix claims a runner and does not say what it is"
    )
    assert "agent_scheduler" in runner
    assert "dispatch.py" in runner

    module = ROOT / "app" / "services" / "agent_scheduler.py"
    assert module.is_file(), f"the named runner {runner!r} is not at {module}"
    source = module.read_text(encoding="utf-8")
    assert "materialize_due_agent_schedules" in source
    assert "materialize_due_schedules" in source, (
        "the named runner does not call the materializer, so it is not a runner"
    )

    entrypoint = (ROOT / "dispatch.py").read_text(encoding="utf-8")
    assert "materialize_due_agent_schedules" in entrypoint, (
        "the matrix names dispatch.py as the runner and dispatch.py does not "
        "call it, which is the original dishonest green in a new place"
    )

    detail = status["detail"]
    assert isinstance(detail, str) and len(detail.strip()) >= 40
    # The gate has to be stated in BOTH branches, because the dock renders this
    # verbatim and the branch a reader sees depends on their deployment.
    assert "human gated" in detail or "executes nothing" in detail, (
        "the dock renders this verbatim; a runner that does not say the task it "
        "creates is still gated invites the reader to assume cron executes it"
    )


def test_nothing_in_this_repository_asserts_the_tick_is_scheduled() -> None:
    """The default has to stay the one that claims nothing.

    A default of True would put every deployment that never heard of the flag
    into a green Scheduler tile, which is the defect this whole split exists to
    prevent. Read from the file rather than from the settings object, so a
    committed change to the default is caught even if the environment overrides
    it here.
    """
    config = (ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    assert "SCHEDULER_TICK_INSTALLED: bool = False" in config, (
        "SCHEDULER_TICK_INSTALLED no longer defaults to False in "
        "app/core/config.py. A deployment that never set it would then claim its "
        "recorded goals fire"
    )
    for name in (".env.example", "railway.json", "railway.toml"):
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for truthy in ("SCHEDULER_TICK_INSTALLED=1", "SCHEDULER_TICK_INSTALLED=true"):
            assert truthy not in text.lower().replace("true", "true"), (
                f"{name} sets the tick flag on, which makes an operator statement "
                "about a real deployment on behalf of every reader who copies it"
            )


def test_the_cron_entrypoint_still_ships_in_the_api_image() -> None:
    """The runner is only real if the image that runs cron contains it.

    dispatch.py is copied explicitly; app/ is copied wholesale, which is what
    carries app/services/agent_scheduler.py. Read from the Dockerfile rather
    than assumed, because the whole door was a call graph nobody checked.
    """
    dockerfile = (
        ROOT / "infrastructure" / "docker" / "Dockerfile.api"
    ).read_text(encoding="utf-8")
    assert "COPY dispatch.py ./dispatch.py" in dockerfile
    assert "COPY app/ ./app/" in dockerfile
    assert "COPY services/ ./services/" in dockerfile, (
        "services/agent_runtime/scheduler_report.py has to be in the image too"
    )
