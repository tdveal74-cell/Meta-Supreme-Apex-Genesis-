"""
Maintenance — reconciling state the process model cannot guarantee.

A workflow run executes inside the HTTP request that started it. When that
process dies mid-run — deploy, OOM kill, node eviction — the row is left
saying `running` with nothing alive to finish it. Nothing else in the system
will ever correct it.

This sweep is the correction. It is deliberately narrow: it changes a status
and writes a reason, and it touches nothing else.

**Why this is safe.** An effect step cannot have committed without a matching
`approvals` entry, which is written in the same transaction as the effect. So
a run killed mid-flight has either fully committed an approved effect or done
nothing — there is no half-written state to repair. Marking it `failed` loses
no work that was not already lost with the process.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import WorkflowRun

logger = logging.getLogger(__name__)

#: `RunStatus` (services layer) carries only the statuses the *engine* can
#: return — it never sees a run mid-flight. "running" is an app-layer
#: transient, written as a literal by `start_run`, so it is one here too.
_RUNNING = "running"
_FAILED = "failed"

_SWEEP_REASON = (
    "Marked failed by the startup sweep: the process running this workflow "
    "ended before the run finished. No unapproved effect can have committed."
)


async def sweep_orphaned_runs(db: AsyncSession, *, older_than_minutes: int) -> int:
    """
    Fail runs stuck in `running` past the threshold. Returns the count.

    The threshold matters: a council step against a live provider legitimately
    takes minutes, and sweeping a run that is genuinely in flight would mark a
    healthy run as failed while it continues to execute. `older_than_minutes`
    must exceed the longest plausible run — hence a 30-minute default rather
    than a tidier-looking 5.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)

    doomed = (
        (
            await db.execute(
                select(WorkflowRun.id).where(
                    WorkflowRun.status == _RUNNING,
                    WorkflowRun.started_at < cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    if not doomed:
        return 0

    await db.execute(
        update(WorkflowRun)
        .where(WorkflowRun.id.in_(doomed))
        .values(
            status=_FAILED,
            error_message=_SWEEP_REASON,
            completed_at=datetime.now(timezone.utc),
        )
    )
    # Logged at warning, with ids: a nonzero count means a process died, and
    # that is worth noticing even though the sweep handled it.
    logger.warning(
        "swept %d orphaned workflow run(s) older than %dm: %s",
        len(doomed),
        older_than_minutes,
        ", ".join(doomed),
    )
    return len(doomed)
