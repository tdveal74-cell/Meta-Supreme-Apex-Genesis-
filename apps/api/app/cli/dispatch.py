"""
Cron entrypoint for the schedule dispatcher.

    python -m app.cli.dispatch
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
