"""The runner for recorded agent goals. Before this module there was none.

WHAT WAS WRONG

DEVON recorded scheduled goals and never ran them. `agent_schedules` rows were
written durably by POST /api/v1/agent-expansion/schedules, and the only thing
that turns one into a task,
`DurableAgentTaskService.materialize_due_schedules`, had exactly one caller: the
manual route at app/api/v1/agent_expansion.py:87. The cron the API image ships
(infrastructure/docker/Dockerfile.api, `python dispatch.py`) drives
`app/services/dispatcher.dispatch_due`, which selects Workflow rows and never
touches agent_schedules. So a due goal sat inert forever and nothing failed.
This module is the missing half, and dispatch.py now runs it beside the
workflow lane.

WHY A COMPLETE OWNER SCAN AND NOT A SYSTEM OWNER

`materialize_due_schedules` is owner scoped, and a cron has no owner. Inventing
one is the wrong answer twice over: a literal placeholder id matches no row, and
anything that materialized across owners in a single call would put one
account's goal into another account's task list. The runner therefore asks the
schedule table which owners actually have a due row
(`HermesExpansionRepository.owners_with_due_schedules`) and calls the existing
owner scoped materializer once per owner, with that owner's id. Cross owner
leakage is impossible by construction rather than by care, and
test_devon_agent_scheduler_runner.py proves it with two owners.

WHY THIS RESPECTS THE HUMAN GATE

Materializing creates a durable agent task and nothing else.
`DurableAgentTaskService.create_task` plans and saves; the executor is
`run_until_blocked`, a different method, reachable only from
POST /api/v1/agent-tasks/{task_id}/run. Read of both on 2026-09-10: `create_task`
never calls it. So the runner turns a recorded goal into a planned, human gated
task, which is what CLAUDE.md's "Materialize and spawn never auto run effects"
requires, and it is strictly less than the workflow lane beside it already does
(`dispatch_due` executes the run).

WHY EACH OWNER GETS ITS OWN SESSION AND ITS OWN TENANT BINDING

dispatch.py's rule is that one tenant's broken schedule must not stop everyone
else's. A shared session cannot deliver that: one owner's IntegrityError poisons
the transaction for every owner after it, which the workflow dispatcher handles
by ending the whole batch. A session per owner means a failure rolls back that
owner alone and the owners already done stay committed.

The tenant binding is the same law app/core/tenant_context.py states in its own
docstring: a lane that knows its owner outside a request binds it itself.
`create_task` plans through the provider, and unbound that planning is spent
under SYSTEM_TENANT, which is the estate paying for a tenant's scheduled goal
and a per account spend cap that never applies to the account that asked.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import bind_tenant, reset_tenant
from app.db.session import AsyncSessionLocal
from app.services.agent_tasks import agent_tasks_service
from app.services.hermes_expansion_persistence import HermesExpansionRepository
from services.agent_runtime.scheduler_report import OwnerOutcome, ScheduleRunReport

logger = logging.getLogger(__name__)

#: A lane of its own. app/services/dispatcher.py holds 0x5F1D15 for the whole
#: of its batch, and sharing that key would let the workflow lane lock the
#: schedule lane out for the entire tick, and the other way round.
_ADVISORY_LOCK_KEY = 0x5F1D16

#: Owners per batch. A cap rather than a page: the next tick picks up whatever
#: this one did not reach, exactly as _MAX_PER_BATCH does for workflows.
_MAX_OWNERS_PER_BATCH = 200

#: How far forward a failed owner's due rows are pushed before they are tried
#: again.
#:
#: WHY THIS NUMBER EXISTS AT ALL. Without it a failed owner is due again on the
#: next tick, and `materialize_due_schedules` calls `create_task`, which plans
#: through the provider BEFORE the failure happens. An adversary measured three
#: consecutive real ticks with `attach_task` raising after the plan: three
#: planner calls, zero tasks committed, the row still `due` with `task_id` NULL.
#: On the documented `* * * * *` cron that is 1,440 provider calls a day for one
#: broken schedule, forever, each tick exiting 1.
#:
#: app/services/dispatcher.py:143 already had this rule for the workflow lane and
#: states it in its own comment. 15 minutes turns 1,440 wasted plans a day into
#: 96, keeps a transient failure (a lock, a provider blip) recovering within a
#: quarter hour, and is short enough that a person watching does not think the
#: goal was dropped. It is a containment, not a retry policy: nothing here counts
#: attempts, so a permanently broken schedule costs 96 plans a day until somebody
#: looks. Making that bounded needs an attempts column and a migration, which is
#: a bigger change than this door.
_FAILURE_BACKOFF = timedelta(minutes=15)

_repo = HermesExpansionRepository()

SessionFactory = Callable[[], AsyncSession]


async def _try_lock(db: AsyncSession) -> bool:
    return bool(
        await db.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
        )
    )


async def _unlock(db: AsyncSession) -> None:
    await db.execute(
        text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY}
    )


def _reason(err: BaseException) -> str:
    """A non-empty failure reason, always. OwnerOutcome refuses an empty one."""
    detail = str(err).strip()
    name = type(err).__name__
    return f"{name}: {detail}"[:500] if detail else name


async def _defer_owner(
    owner_id: str, factory: SessionFactory, moment: datetime, reason: str
) -> str:
    """Push a failed owner's due rows forward. Returns the new time, or "".

    Its own session, because the owner's was rolled back. Never raises: a
    deferral that cannot land is reported as an absent deferral, which is the
    state the report calls spinning, rather than as a second failure that would
    hide the first.
    """
    until = moment + _FAILURE_BACKOFF
    try:
        async with factory() as session:
            moved = await _repo.defer_due_schedules(
                session,
                owner_id=owner_id,
                until=until,
                reason=reason,
                now=moment,
            )
            await session.commit()
    except Exception:
        logger.exception(
            "agent schedule runner could not defer owner %s, so the next tick "
            "will re-plan the same rows",
            owner_id,
        )
        return ""
    if not moved:
        # Nothing matched the predicate any more, so there is nothing to spin on
        # and nothing to report as deferred either.
        return ""
    logger.warning(
        "agent schedule runner deferred %s due row(s) for owner %s to %s after a "
        "failure, so the next tick does not re-plan them",
        moved,
        owner_id,
        until.isoformat(),
    )
    return until.isoformat()


async def _materialize_for_owner(
    owner_id: str, factory: SessionFactory, moment: datetime
) -> OwnerOutcome:
    """One owner, one transaction, one tenant binding.

    Returns an outcome instead of raising, so the batch continues. A failure
    carries its reason and no count: the owner's due schedules were rolled back
    unread, which is not the same as the owner having none.

    A failure also DEFERS that owner's due rows, on a session of its own. See
    `_FAILURE_BACKOFF` for why: without it the next tick re-plans the same rows
    and the plan is spent before the failure recurs.
    """
    tenant = bind_tenant(owner_id)
    try:
        async with factory() as session:
            try:
                created = await agent_tasks_service.materialize_due_schedules(
                    session, owner_id=owner_id
                )
                await session.commit()
            except Exception as err:  # one owner must not end the batch
                await session.rollback()
                logger.exception(
                    "agent schedule materialization failed for owner %s", owner_id
                )
                reason = _reason(err)
                deferred = await _defer_owner(owner_id, factory, moment, reason)
                return OwnerOutcome(
                    owner_id=owner_id, error=reason, deferred_until=deferred
                )
            return OwnerOutcome(owner_id=owner_id, created=len(created))
    except Exception as err:  # the session itself could not open
        logger.exception(
            "agent schedule materialization could not open a session for owner %s",
            owner_id,
        )
        reason = _reason(err)
        # No deferral attempt here: the factory just failed to produce a session,
        # so a second call to it would almost certainly fail too, and the report
        # naming this owner as spinning is the honest answer.
        return OwnerOutcome(owner_id=owner_id, error=reason)
    finally:
        reset_tenant(tenant)


async def materialize_due_agent_schedules(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
    limit: int = _MAX_OWNERS_PER_BATCH,
    session_factory: Optional[SessionFactory] = None,
) -> ScheduleRunReport:
    """Turn every owner's due recorded goals into durable, human gated tasks.

    `db` is used for the advisory lock and the read only owner scan. The work
    itself runs on a session per owner from `session_factory`, defaulting to
    AsyncSessionLocal, so the caller's transaction is never the thing that
    commits another account's task.

    Never raises for a failure it can attribute. The returned report says which
    owners were left unread and why, and `report.healthy` is False whenever any
    were, so the cron wrapper can exit nonzero instead of logging a comfortable
    line.

    `now` REACHES THE OWNER SCAN AND THE DEFERRAL, NOT THE MATERIALIZER.
    `materialize_due_schedules` takes no clock and `due_schedules` calls
    `_utcnow()` itself, so passing a future `now` enumerates owners the
    materializer then finds nothing due for, and the report reads "N owner(s)
    with due schedules, 0 task(s) materialized". Confusing rather than false, and
    harmless in production because dispatch.py never passes it. Stated here
    rather than left for a reader to discover, per an adversary's note on
    2026-09-10; threading the clock the rest of the way is a change to the
    materializer's signature and belongs with that module.
    """
    moment = now or datetime.now(timezone.utc)
    factory: SessionFactory = session_factory or AsyncSessionLocal

    if not await _try_lock(db):
        report = ScheduleRunReport(locked_out=True)
        logger.info("agent schedule runner: %s", report.summary())
        return report

    try:
        try:
            owners = await _repo.owners_with_due_schedules(
                db, now=moment, limit=limit
            )
        except Exception as err:  # reported, never rendered as empty
            logger.exception("agent schedule owner scan failed")
            report = ScheduleRunReport(scan_error=_reason(err))
            logger.error("agent schedule runner: %s", report.summary())
            return report

        outcomes: List[OwnerOutcome] = []
        for owner_id in owners:
            outcomes.append(await _materialize_for_owner(owner_id, factory, moment))

        report = ScheduleRunReport(outcomes=outcomes)
        if report.healthy:
            logger.info("agent schedule runner: %s", report.summary())
        else:
            logger.error("agent schedule runner: %s", report.summary())
        return report
    finally:
        await _unlock(db)
