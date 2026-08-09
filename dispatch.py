"""
Cron entrypoint for the schedule dispatcher.

    python -m app.cli.dispatch

Exit codes are for the cron wrapper's benefit, not decoration:

    0  work done, or nothing due, or another dispatcher held the lock
    1  the batch itself failed (database unreachable, unexpected error)

Individual workflows that fail to dispatch do not fail the batch — one
tenant's broken workflow must not stop everyone else's schedule. They are
logged and counted in the report; a nonzero `failed` with exit 0 is the
signal to look at the logs.

Suggested cron (every minute; the dispatcher is cheap when nothing is due):

    * * * * * cd /srv/app && python -m app.cli.dispatch >> /var/log/dispatch.log 2>&1
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.services.dispatcher import dispatch_due

logger = logging.getLogger("app.cli.dispatch")


async def _main() -> int:
    setup_logging()
    try:
        async with AsyncSessionLocal() as session:
            report = await dispatch_due(session)
            await session.commit()
    except Exception:
        logger.exception("dispatch batch failed")
        return 1

    logger.info("dispatch: %s", report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
