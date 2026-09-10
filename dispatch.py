"""
Cron entrypoint for the two schedule lanes.

    python dispatch.py

Two lanes, in this order, each in its own session so neither can roll the other
back:

1. **Scheduled workflows.** `app/services/dispatcher.dispatch_due` selects
   Workflow rows whose `next_run_at` has passed and starts a run.
2. **Recorded agent goals.** `app/services/agent_scheduler` turns due
   `agent_schedules` rows into durable agent tasks, once per owner.

Lane 2 arrived on 2026-09-10 and it closed a door. Before it, DEVON recorded
scheduled goals and never ran them: `materialize_due_schedules` had one caller,
the manual HTTP route, and this file drove only lane 1, so a due goal sat inert
forever and nothing failed. The two lanes read alike and are not the same
scheduler, which is exactly why the second one was missing for so long.

Lane 2 creates tasks and never runs them. Execution stays behind
POST /api/v1/agent-tasks/{task_id}/run, so a materialized goal is a planned task
waiting on a person, not an effect that fired from cron.

Exit codes are for the cron wrapper's benefit, not decoration:

    0  work done, or nothing due, or another dispatcher held the lock
    1  a lane itself failed (database unreachable, unexpected error), the agent
       schedule lane could not read what was due, OR an individual owner in that
       lane was left unread

THE TWO LANES DIFFER ON THAT LAST LINE, and this docstring said otherwise until
2026-09-10, when an adversary read the code against the prose:

* Lane 1: an individual workflow that fails to dispatch does NOT fail the batch.
  `dispatch_due` counts it and the lane exits 0, so a nonzero `failed` with exit
  0 is the signal to look at the logs.
* Lane 2: an individual owner left unread DOES fail the batch. `partial` is not
  `healthy`, so the exit code is 1. Reproduced: one owner created 1 and one
  failed gives state `partial`, healthy False, exit 1.

Exit 1 is the honest behaviour for lane 2 and it is deliberate. An owner whose
goals were rolled back has goals nobody read, and nothing else would surface
that. The sentence that claimed otherwise was the error, and an operator wiring
alerting off it would have believed exit 1 meant the lane itself had died.

One tenant's broken schedule still must not STOP everyone else's, and it does
not: lane 2 materializes every other owner first and only then reports. What it
will not do is stay quiet about the one it could not reach. A failed owner's due
rows are also pushed forward by
`app/services/agent_scheduler._FAILURE_BACKOFF`, so a permanently broken schedule
costs one plan per backoff window rather than one per tick, and the summary names
any owner whose deferral did not land.

An agent schedule lane that could not read the store at all is different from
one that found nothing due, and both exit differently from a batch that read it
and left somebody out: `ScheduleRunReport.state` names all six cases and
`healthy` collapses them to the exit code, so "nothing due" can never be the way
a broken scan reads.

Suggested cron (every minute; both lanes are cheap when nothing is due):

    * * * * * cd /app && python dispatch.py >> /var/log/dispatch.log 2>&1
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.agent_scheduler import materialize_due_agent_schedules
from app.services.dispatcher import dispatch_due

logger = logging.getLogger("app.cli.dispatch")


async def _dispatch_workflows() -> int:
    """Lane 1. Returns the exit code this lane contributes."""
    try:
        async with AsyncSessionLocal() as session:
            report = await dispatch_due(session)
            await session.commit()
    except Exception:
        logger.exception("dispatch batch failed")
        return 1

    logger.info("dispatch: %s", report.summary())
    return 0


async def _materialize_agent_schedules() -> int:
    """Lane 2. Returns the exit code this lane contributes.

    Its own session: a workflow lane that failed has already been logged and
    must not stop recorded goals from being materialized, and a schedule lane
    that fails must not roll back a workflow run that started.
    """
    try:
        async with AsyncSessionLocal() as session:
            report = await materialize_due_agent_schedules(session)
            await session.commit()
    except Exception:
        logger.exception("agent schedule batch failed")
        return 1

    logger.info("agent schedules: %s", report.summary())
    # `healthy` is False when the scan failed or an owner was left unread, and
    # the summary already says which. Exiting 0 there would make a silent
    # failure look like a quiet estate, which is the whole reason this lane
    # exists.
    return 0 if report.healthy else 1


async def _main() -> int:
    setup_logging()
    workflows = await _dispatch_workflows()
    schedules = await _materialize_agent_schedules()
    return 1 if (workflows or schedules) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
