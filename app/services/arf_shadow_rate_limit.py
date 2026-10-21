"""Shared ARF diagnostic budget: 30/minute refill, five-request burst.

The theoretical next arrival time is equivalent to a five-token bucket
refilling one token every two seconds. PostgreSQL serializes the conditional
upsert per authenticated owner. No process-local allowance exists.

Security accounting commits on a separate short transaction before evidence
is read, so a later 404, 409, cancellation or request rollback cannot refund
an admitted diagnostic. This module never edits tasks, approvals or evidence.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import AsyncSessionLocal


class ShadowRateLimitExceeded(RuntimeError):
    """The authenticated account exhausted its shared diagnostic budget."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("ARF diagnostic request limit reached")


class ShadowRateLimitUnavailable(RuntimeError):
    """No diagnostic is permitted without successful budget accounting."""


# Five immediate requests schedule slots at +2, +4, +6, +8 and +10 seconds.
# A sixth must wait until the stored slot is within eight seconds of DB time.
# ON CONFLICT evaluates its predicate against the locked current row, not a
# previously fetched application snapshot. clock_timestamp(), unlike NOW(),
# is not frozen at transaction start while a contender waits for that lock.
_ACQUIRE = text("""
    INSERT INTO arf_shadow_rate_limits (owner_id, next_slot_at)
    VALUES (CAST(:owner AS uuid), clock_timestamp() + INTERVAL '2 seconds')
    ON CONFLICT (owner_id) DO UPDATE
    SET next_slot_at = GREATEST(arf_shadow_rate_limits.next_slot_at, clock_timestamp())
                       + INTERVAL '2 seconds'
    WHERE arf_shadow_rate_limits.next_slot_at <= clock_timestamp() + INTERVAL '8 seconds'
    RETURNING owner_id
""")
_RETRY_AFTER = text("""
    SELECT GREATEST(1, CEIL(EXTRACT(EPOCH FROM
        (next_slot_at - clock_timestamp() - INTERVAL '8 seconds'))))::bigint
    FROM arf_shadow_rate_limits WHERE owner_id = CAST(:owner AS uuid)
""")


async def consume_shadow_budget(owner_id: str) -> None:
    """Admit one diagnostic or refuse closed; caller supplies authenticated ID.

    The owned row and burst survive worker restarts and are shared by all API
    workers using this database. Account deletion removes only its own row.
    Disabling ARF does not clear budgets. No request field configures limits.
    """
    try:
        owner = str(UUID(owner_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ShadowRateLimitUnavailable("ARF diagnostic limiter unavailable") from exc
    retry_after = None
    try:
        # Includes connection acquisition, row-lock wait, execution and commit.
        async with asyncio.timeout(2.0):
            async with AsyncSessionLocal() as db:
                async with db.begin():
                    await db.execute(text("SET LOCAL lock_timeout = '500ms'"))
                    await db.execute(text("SET LOCAL statement_timeout = '1500ms'"))
                    admitted = (await db.execute(_ACQUIRE, {"owner": owner})).first()
                    if admitted is None:
                        retry_after = (await db.execute(_RETRY_AFTER, {"owner": owner})).scalar_one()
    except (SQLAlchemyError, TimeoutError, OSError) as exc:
        # A missing migration, exhausted pool, DB outage or timed-out lock is
        # not permission to bypass protection. Never expose underlying errors.
        raise ShadowRateLimitUnavailable("ARF diagnostic limiter unavailable") from exc
    if retry_after is not None:
        raise ShadowRateLimitExceeded(int(retry_after))
