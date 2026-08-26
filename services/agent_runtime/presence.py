"""Presence authority: who is standing behind a tool call, and what that buys.

DEVON's approval queue was built for an ABSENT human. It emails a card, waits up
to 72 hours, and expires. That is the right instrument when nobody is watching
and the wrong one when Tee is sitting in the conversation: asking a present human
to go tap an email is friction with no safety in it, because the person the card
exists to reach is already here.

So presence collapses the gate into the conversation rather than removing it.
Ruled by Tee on 2026-08-26: in a live human turn his message IS the approval.

What presence buys, and what it does not:

- READ runs immediately. It always did.
- A REVERSIBLE write runs immediately when a human is present. No card, no email,
  no wait. This is the friction that goes.
- An IRREVERSIBLE action still stops - but inline, in the same breath, answered
  in the conversation rather than in an inbox twenty minutes later.
- BLOCKED never runs, present or not. A governance refusal is not a permission
  question and no amount of authority reaches it.

The load-bearing rule is the one about who counts as present. Presence is a
property of the CALLER, established by the transport that authenticated a live
human, and it must never be inferable from message content. A scheduled routine,
the daily reflection, a webhook, or any other absent-human caller gets
`Caller.automated()` and falls back to the card exactly as before. That is what
keeps the reflection able to want things without being able to do them, and it
is why this module takes a Caller object rather than a boolean flag: a bool is
one typo away from an LLM turning its own output into consent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolSpec


class PresenceDecision(str, Enum):
    """What the runtime may do with one tool call, right now."""

    RUN = "run"
    """Execute immediately. No card, no inline question."""

    CONFIRM = "confirm"
    """Stop and ask, inline, inside this turn. A present human answers in words."""

    CARD = "card"
    """Raise the approval card and stop. The absent-human path, unchanged."""

    REFUSE = "refuse"
    """Never, by any authority. Blocked tools only."""


#: Tools that ask even when Tee is standing right there.
#:
#: Not because he cannot be trusted with them - because HE ALREADY GOT BURNED BY
#: ONE. On 2026-08-25 a mis-tapped approval card put a smoke record into
#: devon-soul; undoing it took unpublishing the committer, deleting the record by
#: exact id, and marking the row REVERTED. The risk this list guards is not Tee
#: changing his mind, it is a model proposing something plausible while wearing
#: his authority, on a store where a bad write is expensive and hard to see later.
#:
#: Keep this list SHORT and specific. Every name added here is friction Tee feels
#: on every turn, so a tool belongs here only when a mistake is genuinely hard to
#: walk back. Reversible damage does not qualify.
#:
#: As of 2026-08-26 none of these names is a registered runtime tool: the soul
#: write surface is an n8n workflow behind the approval queue, not something
#: `build_tool_registry` hands out. So this list is currently forward-looking,
#: which is the state in which a guard quietly rots. Two tests in
#: `test_devon_presence_authority.py` are the tripwires: one fails the day any
#: name here becomes registered, and one fails if a write is registered on a
#: guarded surface (`soul.`, `subconscious.`, `secrets.`, `credentials.`) under a
#: name this list does not already know. Matching is exact, so `soul.append`
#: would buy itself silence without anyone deciding to.
ALWAYS_CONFIRM_TOOLS: FrozenSet[str] = frozenset(
    {
        # Writes into the two soul indexes: DEVON's experience and Tee's rulings.
        "soul.commit",
        "soul.write",
        "subconscious.write",
        # Anything that changes who can act as DEVON.
        "secrets.write",
        "credentials.write",
    }
)


@dataclass(frozen=True)
class Caller:
    """Who is asking, and whether a human is live on the other end.

    Build this from the transport, never from model output or request body
    content. `present` means: a human authenticated on this connection and is
    reading the stream this turn - close enough to answer a question in the next
    few seconds.
    """

    kind: str
    present: bool = False
    actor: str = ""

    @classmethod
    def human(cls, actor: str = "tee") -> "Caller":
        """A live human turn: the conversational surface with an authenticated user."""
        return cls(kind="human", present=True, actor=actor or "tee")

    @classmethod
    def automated(cls, kind: str = "automation") -> "Caller":
        """A routine, the reflection, a scheduler, a webhook. Nobody is watching."""
        return cls(kind=kind or "automation", present=False, actor="")


def confirm_reason(
    spec: ToolSpec,
    *,
    always_confirm: Optional[FrozenSet[str]] = None,
) -> str:
    """Why a CONFIRM was ruled, in words that are true of THIS tool.

    Two different rules produce CONFIRM and they mean different things. A tool
    named in ALWAYS_CONFIRM_TOOLS is guarded because its surface is expensive to
    get wrong, and such a tool may well be reversible -- the list matches on name
    precisely so a mislabelled adapter cannot buy itself silence. A tool that
    reaches CONFIRM by the HIGH_IMPACT-and-not-reversible rule genuinely cannot
    be walked back.

    Telling Tee "this cannot be undone" about something that can is a small lie,
    and a gate that lies about why it is stopping him teaches him to stop reading
    it. So the question says which one it is.
    """
    confirm_set = ALWAYS_CONFIRM_TOOLS if always_confirm is None else always_confirm
    if spec.name in confirm_set:
        return "writes somewhere a mistake is expensive to walk back"
    return "cannot be undone"


def decide(
    spec: ToolSpec,
    caller: Caller,
    *,
    always_confirm: Optional[FrozenSet[str]] = None,
) -> PresenceDecision:
    """Rule one tool call.

    Deterministic and side-effect free: the same spec and caller always give the
    same answer, and nothing here executes, logs, or asks. The runtime acts on
    the returned decision.
    """
    confirm_set = ALWAYS_CONFIRM_TOOLS if always_confirm is None else always_confirm

    # A blocked tool is a refusal, not a permission question. Checked first so no
    # caller, present or absent, can reach past it.
    if spec.risk is ToolRisk.BLOCKED:
        return PresenceDecision.REFUSE

    if spec.risk is ToolRisk.READ:
        return PresenceDecision.RUN

    # From here down the tool writes or has blast radius.
    if not caller.present:
        # Nobody is watching. This is exactly what the card was built for.
        return PresenceDecision.CARD

    if spec.name in confirm_set:
        return PresenceDecision.CONFIRM

    # High impact that cannot be walked back earns a question even from a present
    # human, without needing to be named above: "irreversible" is the property
    # that matters, and an adapter declaring it should not also have to remember
    # to add itself to a list.
    if spec.risk is ToolRisk.HIGH_IMPACT and not spec.reversible:
        return PresenceDecision.CONFIRM

    # A reversible write with a human present. This is the friction that goes:
    # his word in the conversation is the ruling.
    return PresenceDecision.RUN
