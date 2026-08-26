"""Confirmations that survive the gap between DEVON asking and Tee answering.

Build 15 shipped a confirmation token computed as a hash of the turn id, the
tool, and the arguments. An adversarial pass on 2026-08-26 found that shape
broken in two independent ways, and both are the reason this module exists.

The first defect was fatal and simple: the turn id went into the token but never
came back out of the API, so no honest client could ever produce a matching
confirmation. Every "yes" was refused with a message that read like a tampering
alert.

The second defect survives fixing the first, and is the interesting one. A hash
of public inputs is not a secret. Any caller who knows the turn id, the tool
name, and the arguments can compute a valid token for an action DEVON never
proposed -- which turns a confirmation into a direct tool-invocation API for
anything the front end (or anything that got into the front end) cares to name.
Presence authority says Tee's word is the ruling; it does not say a cross-site
script wearing his session is Tee.

So a confirmation is no longer something the client can compute. It is something
the SERVER remembers: a random handle pointing at the exact call that was shown,
held here with the observations that led to it. The client echoes the handle and
nothing else. Three properties fall out of that:

- A confirmation cannot name an action DEVON did not propose, because the action
  is stored, not supplied.
- Answering yes RESUMES the turn instead of restarting it. The old shape re-drove
  the whole turn, re-running every read and every reversible write that preceded
  the question; the verifier watched `browser.navigate` run twice for one
  confirmation. Here the stored observations carry that work forward and only the
  confirmed step runs.
- A handle is single use and short lived. Claiming one removes it, so a replayed
  yes finds nothing.

Deliberately in memory, and deliberately not the approval queue. An inline
confirmation is a question asked of someone who is reading the stream right now:
if the process restarts, or he walks away for twenty minutes, the right outcome
is that the question lapses and he is asked again -- not that a stale yes lands
on an effect later. The 72-hour durable instrument for an absent human already
exists, and this is not it.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

CONFIRMATION_TTL_SECONDS = 900
"""Fifteen minutes. Long enough to read a question and answer it, short enough
that a yes cannot land on a conversation Tee has left."""

MAX_PENDING = 512
"""Backstop against unbounded growth if offers vastly outpace answers."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PendingConfirmation:
    """One irreversible call, held exactly as it was shown to Tee."""

    handle: str
    turn_id: str
    owner: str
    """The conversation this was offered in. A handle is not portable."""
    actor: str
    """The authenticated user it was offered to."""
    tool: str
    arguments: Dict[str, Any]
    observations: Tuple[Tuple[str, str], ...]
    """(tool, outcome) pairs from the steps that already ran this turn."""
    message: str
    """The message that started the turn, so the resumed loop keeps its thread."""
    spent: Tuple[Tuple[str, int], ...] = ()
    """Per-turn tool budget already consumed before the question.

    Carried because a resumed leg builds a fresh AgentTurn, and a budget that
    resets on resume is not a per-turn budget at all: consult, propose something
    irreversible, get a yes, consult again."""
    steps_used: int = 0
    """Tool calls already made, so a resumed turn does not get a fresh allowance."""
    created_at: datetime = field(default_factory=_now)
    expires_at: datetime = field(
        default_factory=lambda: _now() + timedelta(seconds=CONFIRMATION_TTL_SECONDS)
    )

    def is_expired(self, at: Optional[datetime] = None) -> bool:
        return (at or _now()) >= self.expires_at


class PendingConfirmationRegistry:
    """Process-local store of questions DEVON is waiting on an answer to.

    Locked, because the offer and the answer arrive on genuinely concurrent
    requests. Process-local for the same reason the halt registry is: both are
    handles to work running in THIS worker, and a handle that reached a different
    worker would point at nothing anyway.
    """

    def __init__(self) -> None:
        self._pending: Dict[str, PendingConfirmation] = {}
        self._lock = RLock()

    def offer(
        self,
        *,
        turn_id: str,
        owner: str,
        actor: str,
        tool: str,
        arguments: Optional[Dict[str, Any]] = None,
        observations: Tuple[Tuple[str, str], ...] = (),
        message: str = "",
        spent: Tuple[Tuple[str, int], ...] = (),
        steps_used: int = 0,
    ) -> PendingConfirmation:
        """Remember a question. Returns the record whose handle the client echoes."""
        clean_turn = (turn_id or "").strip()
        clean_owner = (owner or "").strip()
        clean_tool = (tool or "").strip()
        if not clean_turn or not clean_owner or not clean_tool:
            raise ValueError("a pending confirmation needs a turn, an owner, and a tool")

        record = PendingConfirmation(
            handle=f"CONFIRM-{secrets.token_urlsafe(24)}",
            turn_id=clean_turn,
            owner=clean_owner,
            actor=(actor or "").strip(),
            tool=clean_tool,
            arguments=dict(arguments or {}),
            observations=tuple(observations),
            message=message or "",
            spent=tuple(spent),
            steps_used=max(0, int(steps_used)),
        )
        with self._lock:
            self._prune_locked()
            self._pending[record.handle] = record
        return record

    def claim(
        self,
        handle: Optional[str],
        *,
        owner: str,
        actor: str,
    ) -> Optional[PendingConfirmation]:
        """Spend a handle. Returns None for anything that does not cleanly match.

        Every failure looks the same from outside -- unknown handle, wrong
        conversation, wrong user, expired -- because distinguishing them would
        turn this into an oracle for which confirmations are outstanding. The
        record is removed on success, so a yes is single use.
        """
        key = (handle or "").strip()
        if not key:
            return None
        with self._lock:
            record = self._pending.get(key)
            if record is None:
                return None
            if record.is_expired():
                self._pending.pop(key, None)
                return None
            if record.owner != (owner or "").strip():
                return None
            if record.actor != (actor or "").strip():
                return None
            self._pending.pop(key, None)
            return record

    def discard(self, handle: Optional[str]) -> None:
        """Forget a handle without spending it. Safe to call twice."""
        key = (handle or "").strip()
        if not key:
            return
        with self._lock:
            self._pending.pop(key, None)

    @property
    def outstanding(self) -> int:
        with self._lock:
            self._prune_locked()
            return len(self._pending)

    def _prune_locked(self) -> None:
        now = _now()
        dead = [h for h, r in self._pending.items() if r.is_expired(now)]
        for handle in dead:
            self._pending.pop(handle, None)
        if len(self._pending) <= MAX_PENDING:
            return
        # Oldest first. Losing the stalest question is better than growing without
        # bound, and the client is told to ask again rather than left waiting.
        ordered: List[Tuple[str, PendingConfirmation]] = sorted(
            self._pending.items(), key=lambda item: item[1].created_at
        )
        for handle, _record in ordered[: len(self._pending) - MAX_PENDING]:
            self._pending.pop(handle, None)
