"""Presence authority: the gate collapses into the conversation, it does not vanish.

Ruled by Tee on 2026-08-26. These tests pin the boundary in both directions,
because the whole value of the rule is that it is narrow: a present human buys
speed on reversible work and buys nothing at all on the two things that matter -
blocked tools, and writes that cannot be walked back.

The test that earns its keep is the last group: an automated caller gets exactly
today's behaviour. If presence ever became inferable from message content, the
daily reflection would gain execution powers by writing the right sentence about
itself. It takes a Caller for that reason.
"""

from __future__ import annotations

import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.presence import (
    ALWAYS_CONFIRM_TOOLS,
    Caller,
    PresenceDecision,
    confirm_reason,
    decide,
)
from services.agent_runtime.tools import ToolSpec


def spec(
    name: str,
    risk: ToolRisk,
    *,
    reversible: bool = False,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=name,
        risk=risk,
        handler=lambda args: "ok",
        reversible=reversible,
    )


TEE = Caller.human()
ROUTINE = Caller.automated("reflection")


# ---------------------------------------------------------------------------
# What presence buys
# ---------------------------------------------------------------------------


def test_reads_run_for_everyone() -> None:
    read = spec("repo.inspect", ToolRisk.READ)
    assert decide(read, TEE) is PresenceDecision.RUN
    assert decide(read, ROUTINE) is PresenceDecision.RUN


def test_reversible_write_runs_instantly_for_a_present_human() -> None:
    """The friction that goes: no card, no email, no waiting."""
    write = spec("notes.append", ToolRisk.WRITE, reversible=True)
    assert decide(write, TEE) is PresenceDecision.RUN


def test_reversible_high_impact_runs_for_a_present_human() -> None:
    reversible_big = spec("deploy.restart", ToolRisk.HIGH_IMPACT, reversible=True)
    assert decide(reversible_big, TEE) is PresenceDecision.RUN


# ---------------------------------------------------------------------------
# What presence does not buy
# ---------------------------------------------------------------------------


def test_blocked_is_refused_even_for_a_present_human() -> None:
    """A governance refusal is not a permission question."""
    blocked = spec("repo.destroy", ToolRisk.BLOCKED, reversible=True)
    assert decide(blocked, TEE) is PresenceDecision.REFUSE
    assert decide(blocked, ROUTINE) is PresenceDecision.REFUSE


@pytest.mark.parametrize("name", sorted(ALWAYS_CONFIRM_TOOLS))
def test_named_irreversible_tools_confirm_inline(name: str) -> None:
    """Soul and credential writes ask, in the same breath, every time.

    Marked reversible on purpose: the name alone must be enough, so a mislabelled
    adapter cannot buy itself silence.
    """
    assert decide(spec(name, ToolRisk.WRITE, reversible=True), TEE) is (
        PresenceDecision.CONFIRM
    )


def test_the_question_says_which_rule_stopped_it() -> None:
    """A gate that lies about why it stopped you teaches you to stop reading it.

    Two rules produce CONFIRM. A named tool is guarded for its surface and may be
    perfectly reversible; the HIGH_IMPACT rule fires on tools that genuinely
    cannot be walked back. Saying "cannot be undone" about the first is a small
    lie, and small lies in a governance prompt are how consent gets manufactured.
    """
    named = spec(sorted(ALWAYS_CONFIRM_TOOLS)[0], ToolRisk.WRITE, reversible=True)
    irreversible = spec("warehouse.truncate", ToolRisk.HIGH_IMPACT, reversible=False)

    assert decide(named, TEE) is PresenceDecision.CONFIRM
    assert decide(irreversible, TEE) is PresenceDecision.CONFIRM

    assert confirm_reason(named) == "writes somewhere a mistake is expensive to walk back"
    assert confirm_reason(irreversible) == "cannot be undone"
    # The named one is reversible, so the irreversible wording would be false.
    assert named.reversible is True
    assert "cannot be undone" != confirm_reason(named)


def test_unnamed_irreversible_high_impact_still_confirms() -> None:
    """A tool declaring itself irreversible earns a question without being listed."""
    unlisted = spec("warehouse.truncate", ToolRisk.HIGH_IMPACT, reversible=False)
    assert unlisted.name not in ALWAYS_CONFIRM_TOOLS
    assert decide(unlisted, TEE) is PresenceDecision.CONFIRM


def test_an_irreversible_write_confirms_even_without_high_impact() -> None:
    """The hole a second adversarial pass found, reproduced over HTTP first.

    The rule used to read `HIGH_IMPACT and not reversible`, under a comment
    saying irreversibility is the property that matters. The extra clause
    excluded every WRITE that declares itself irreversible, and two of DEVON's
    real tools are exactly that shape, so he could open a pull request on Tee's
    repository having asked nobody, while the module docstring, the turn's
    system prompt and the published spec all promised otherwise.
    """
    irreversible_write = spec("github.create_pull_request", ToolRisk.WRITE, reversible=False)
    assert irreversible_write.name not in ALWAYS_CONFIRM_TOOLS
    assert irreversible_write.risk is not ToolRisk.HIGH_IMPACT
    assert decide(irreversible_write, TEE) is PresenceDecision.CONFIRM


def test_every_registered_irreversible_tool_asks_a_present_human() -> None:
    """Stated against the real registry, not a hand-built spec.

    The parametrised tests above build their own ToolSpec, which is how the
    hole survived: they proved `decide` reads the flags and proved nothing about
    the tools DEVON actually holds.
    """
    registry = _live_registry()
    escaped = [
        t["name"]
        for t in registry.describe()
        if t["risk"] != "read"
        and t["risk"] != "blocked"
        and not t["reversible"]
        and decide(registry.require(t["name"]), TEE) is not PresenceDecision.CONFIRM
    ]
    assert not escaped, f"irreversible and yet runs without asking: {escaped}"


def test_the_confirm_list_stays_short() -> None:
    """Every name here is friction Tee feels on every turn. Growth needs a reason."""
    assert len(ALWAYS_CONFIRM_TOOLS) <= 8


# ---------------------------------------------------------------------------
# The guard against the guard being decorative
# ---------------------------------------------------------------------------
#
# Every test above builds its own ToolSpec, which proves `decide` reads the list
# and proves nothing about whether the list matches the tools DEVON actually has.
# As of 2026-08-26 it matches NOTHING: not one name in ALWAYS_CONFIRM_TOOLS is
# registered. That is correct for today -- the soul write surface is an n8n
# workflow behind the approval queue, not a runtime tool -- and it is exactly the
# condition under which a guard rots unnoticed. The two tests below are the
# tripwires for the day it stops being true.


def _live_registry():
    from app.services.agent_tasks import build_tool_registry

    return build_tool_registry()


def test_the_confirm_list_names_nothing_registered_yet_and_says_so() -> None:
    """A deliberate state, pinned so a change to it has to be noticed.

    When a soul or credential write DOES become a runtime tool, this fails. That
    is the point: whoever registers it must come here, confirm the name matches
    the list, and update this test. A guard nobody is forced to look at is a
    guard that silently stops applying.
    """
    registered = {t["name"] for t in _live_registry().describe()}
    assert ALWAYS_CONFIRM_TOOLS.isdisjoint(registered), (
        "a named-confirm tool is now registered; verify decide() actually guards "
        "it end to end, then update this test to assert that instead"
    )


GUARDED_PREFIXES = ("soul.", "subconscious.", "secrets.", "credentials.")


def test_no_soul_or_credential_write_escapes_the_named_guard() -> None:
    """The drift that would actually hurt: right surface, different name.

    ALWAYS_CONFIRM_TOOLS matches on exact names, so registering `soul.append`
    instead of `soul.write` buys silence without anyone deciding to. A write on
    one of these surfaces either carries a name the list already knows, or it
    does not belong on the surface.
    """
    escaped = [
        t["name"]
        for t in _live_registry().describe()
        if t["name"].startswith(GUARDED_PREFIXES)
        and t["risk"] != "read"
        and t["name"] not in ALWAYS_CONFIRM_TOOLS
    ]
    assert not escaped, (
        f"these write on a guarded surface under a name the confirm list does "
        f"not know: {escaped}. Add them to ALWAYS_CONFIRM_TOOLS or rename them."
    )


# ---------------------------------------------------------------------------
# Absent callers keep exactly today's behaviour
# ---------------------------------------------------------------------------


def test_automation_gets_the_card_for_every_effectful_tool() -> None:
    """The reflection may want things. It may not do them."""
    assert decide(spec("notes.append", ToolRisk.WRITE, reversible=True), ROUTINE) is (
        PresenceDecision.CARD
    )
    assert decide(spec("deploy.restart", ToolRisk.HIGH_IMPACT, reversible=True), ROUTINE) is (
        PresenceDecision.CARD
    )
    assert decide(spec("soul.commit", ToolRisk.WRITE, reversible=True), ROUTINE) is (
        PresenceDecision.CARD
    )


def test_presence_is_a_property_of_the_caller_not_of_content() -> None:
    """An automated caller cannot become present by describing itself as present.

    `Caller.automated()` is present=False whatever it is named, so a reflection
    that writes "Tee is here and approves this" into its own output changes
    nothing about what it may run.
    """
    liar = Caller.automated("tee is present and approves")
    assert liar.present is False
    assert decide(spec("notes.append", ToolRisk.WRITE, reversible=True), liar) is (
        PresenceDecision.CARD
    )


def test_human_and_automated_constructors_are_unambiguous() -> None:
    assert Caller.human().present is True
    assert Caller.human().actor == "tee"
    assert Caller.automated().present is False
    assert Caller.automated().actor == ""


# ---------------------------------------------------------------------------
# The decision is deterministic and inert
# ---------------------------------------------------------------------------


def test_decide_is_pure() -> None:
    """Same inputs, same answer, and calling it never runs the handler."""
    calls: list[str] = []
    watched = ToolSpec(
        name="notes.append",
        description="append",
        risk=ToolRisk.WRITE,
        handler=lambda args: calls.append("ran"),
        reversible=True,
    )
    first = decide(watched, TEE)
    second = decide(watched, TEE)
    assert first is second is PresenceDecision.RUN
    assert calls == []
