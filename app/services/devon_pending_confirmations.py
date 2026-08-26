"""Process-local store of inline confirmations DEVON is waiting on.

Same scope, and the same honest limitation, as the halt registry next door: one
store per API process. A handle minted by one worker is unknown to another, so
under multiple replicas a confirmation could be offered by one process and
answered at another, where it would simply not be found.

That failure is in the safe direction and stays legible: an unrecognised handle
is refused, DEVON asks again, and nothing runs on a yes he cannot match. The
estate runs a single replica today (Railway `multiRegionConfig: ams,
numReplicas: 1`); moving this to Redis is the fix when it scales out, and the
`offer`/`claim` contract does not change when it does.

Kept separate from the approval queue on purpose. The queue is the durable
72-hour instrument for a human who is not here. This is a question asked of
someone reading the stream right now, and it should lapse when he stops reading.
"""

from __future__ import annotations

from functools import lru_cache

from services.agent_runtime.pending import PendingConfirmationRegistry


@lru_cache(maxsize=1)
def get_pending_confirmations() -> PendingConfirmationRegistry:
    """The one store for this process."""
    return PendingConfirmationRegistry()
