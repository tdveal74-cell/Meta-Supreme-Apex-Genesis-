"""Process-local halt registry for live DEVON turns.

One registry per API process, so a "stop" arriving on one request can reach a
turn running on another. That scope is a real limitation and is stated rather
than hidden: with more than one worker or replica, a stop only reaches turns on
the process that receives it.

That is acceptable for now because the estate runs a single replica (Railway
`multiRegionConfig: ams, numReplicas: 1`) and because the failure mode is safe
in the right direction -- a missed stop reports False and Tee is told the turn
was not found, rather than being told it stopped when it did not. Moving this
to Redis or the database is the fix when the service scales out, and the
`halt()` contract does not change when it does.
"""

from __future__ import annotations

from functools import lru_cache

from services.agent_runtime.halt import HaltRegistry


@lru_cache(maxsize=1)
def get_halt_registry() -> HaltRegistry:
    """The one registry for this process."""
    return HaltRegistry()
