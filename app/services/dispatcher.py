"""
Schedule dispatcher — the thing that fires scheduled workflows.

Invoked by cron (or a Kubernetes CronJob) via `app.cli.dispatch`, never as a
thread inside the API. Three reasons, in order of how much they would hurt:

1. An in-process scheduler fires N times when you run N API replicas.
2. It ties dispatch to API uptime and to the API's deploy cadence.
3. It makes the API's memory and event loop the scheduler's problem too.

Correctness under concurrent dispatchers does not rest on any of that,
though. Every run is created with an idempotency key of
`schedule:{slot_iso}`, and `idx_workflow_runs_idempotency` is UNIQUE — two
dispatchers racing on the same slot cannot both create a run, because the
second insert is refused by the database. The advisory lock below is an
optimisation to avoid wasted provider calls, not the safety mechanism.

**Catch-up policy: fire once, then move on.** A workflow due hourly whose
dispatcher was down for six hours fires once, not six times. Firing six is
almost never what anyone wants — it is a thundering herd of provider calls
for stale slots, and for a workflow with effect steps it is six approval
gates queued behind each other. `next_run_at` is recomputed from *now*, so
the backlog is skipped deliberately and logged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowRun
from app.services.workflows import parse_definition, start_run
from services.workflows import RunStatus, TriggerType
from services.workflows.schedule import CadenceError, next_slot, parse_cadence

logger = logging.getLogger(__name__)

#: One dispatcher at a time, cluster-wide. Arbitrary but fixed — changing it
#: between deploys would let two versions run concurrently.
_ADVISORY_LOCK_KEY = 0x5F1D15
_MAX_PER_BATCH = 100


@dataclass
class DispatchReport:
    started: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    locked_out: bool = False

    def summary(self) -> str:
        if self.locked_out:
            return "another dispatcher holds the lock; nothing attempted"
        return (
            f"{len(self.started)} started, {len(self.skipped)} skipped, "
            f"{len(self.failed)} failed"
        )


async def _try_lock(db: AsyncSession) -> bool:
    from sqlalchemy import text

    return bool(
        await db.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}
        )
    )


async def _unlock(db: AsyncSession) -> None:
    from sqlalchemy import text

    await db.execute(
        text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY}
    )


def compute_next_run_at(workflow: Workflow, *, now: datetime) -> Optional[datetime]:
    """
    The workflow's next firing, or None if it does not fire on a schedule.

    Returns None rather than raising for a cadence this dispatcher cannot
    parse: pre-5.1 validation accepted any non-empty string, so unparseable
    cadences exist in the wild and must not break a save.
    """
    try:
        definition = parse_definition(workflow.definition)
    except Exception:
        return None
    if definition.trigger.type is not TriggerType.SCHEDULE:
        return None
    try:
        cadence = parse_cadence(definition.trigger.config.get("cadence"))
    except CadenceError:
        logger.warning(
            "workflow %s has an unparseable cadence %r; it will not be dispatched",
            workflow.id,
            definition.trigger.config.get("cadence"),
        )
        return None
    return next_slot(cadence, now)


async def dispatch_due(
    db: AsyncSession, *, now: Optional[datetime] = None, limit: int = _MAX_PER_BATCH
) -> DispatchReport:
    """Start a run for every active workflow whose slot has passed."""
    now = now or datetime.now(timezone.utc)
    report = DispatchReport()

    if not await _try_lock(db):
        logger.info("dispatcher lock held elsewhere; exiting without work")
        report.locked_out = True
        return report

    try:
        due = (
            (
                await db.execute(
                    select(Workflow)
                    .where(
                        Workflow.status == "active",
                        Workflow.next_run_at.is_not(None),
                        Workflow.next_run_at <= now,
                    )
                    .order_by(Workflow.next_run_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

        for workflow in due:
            slot = workflow.next_run_at
            # Recomputed from `now`, not from `slot` — this is the catch-up
            # policy in one line. Advanced before the run is attempted so a
            # workflow that fails cannot spin on the same slot every minute.
            workflow.next_run_at = compute_next_run_at(workflow, now=now)
            workflow.last_fired_at = now

            if workflow.next_run_at is None:
                logger.warning(
                    "workflow %s is due but no longer schedulable; clearing", workflow.id
                )
                report.skipped.append(workflow.id)
                await db.flush()
                continue

            # A gate still open means the previous run is unresolved. Firing
            # again would queue a second gate behind it, and the API refuses
            # this anyway — skip quietly and try the next slot.
            blocked = (
                await db.execute(
                    select(WorkflowRun.id)
                    .where(
                        WorkflowRun.workflow_id == workflow.id,
                        WorkflowRun.status == RunStatus.AWAITING_APPROVAL,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if blocked:
                logger.info(
                    "workflow %s skipped: run %s still awaiting approval",
                    workflow.id,
                    blocked,
                )
                report.skipped.append(workflow.id)
                await db.flush()
                continue

            key = f"schedule:{slot.isoformat()}"
            # Checked before inserting, not just caught after: an IntegrityError
            # poisons the transaction, and recovering from it inside a loop
            # would discard every workflow already advanced in this batch.
            already = (
                await db.execute(
                    select(WorkflowRun.id)
                    .where(
                        WorkflowRun.workflow_id == workflow.id,
                        WorkflowRun.meta["idempotency_key"].astext == key,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if already:
                logger.info("workflow %s slot %s already dispatched", workflow.id, key)
                report.skipped.append(workflow.id)
                await db.flush()
                continue

            try:
                # `start_run` reads the trigger from the definition, which is
                # already `schedule` for everything this loop selects.
                run = await start_run(
                    db,
                    workflow=workflow,
                    user_id=workflow.owner_id,
                    trigger_input="",
                )
                run.meta = {**(run.meta or {}), "idempotency_key": key}
                await db.flush()
                report.started.append(run.id)
            except IntegrityError:
                # Lost the race against another dispatcher between the check
                # and the insert. The unique index did its job; the session is
                # now unusable, so end the batch and let the next tick resume.
                await db.rollback()
                logger.info(
                    "workflow %s slot %s taken by another dispatcher; ending batch",
                    workflow.id,
                    key,
                )
                report.skipped.append(workflow.id)
                break
            except Exception:
                logger.exception("workflow %s failed to dispatch", workflow.id)
                report.failed.append(workflow.id)
                await db.flush()
            except Exception:
                logger.exception("workflow %s failed to dispatch", workflow.id)
                report.failed.append(workflow.id)
                await db.flush()

        logger.info("dispatch complete: %s", report.summary())
        return report
    finally:
        await _unlock(db)
