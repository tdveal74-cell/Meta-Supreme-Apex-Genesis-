"""An argument a tool does not read must not be silently dropped.

Found on 2026-08-27 while proving the capability adapters against their real
backends rather than against mocks. `operator.command` was handed
`{"command": "echo", "args": ["adapter-proof-marker"]}`, ran a bare `echo`,
returned ok with empty output, and said nothing about the ignored key. It looked
exactly like a working tool call. Had the proof stopped at the green tick it
would have reported a capability that had done nothing.

The silent drop is a nuisance. The governance consequence is the real defect:
the approval binding is computed over the whole argument dict, so the card and
the queue row carry `args: ["adapter-proof-marker"]` while the process runs
something else entirely. "Approve what you see" holds only while every key the
human reads is a key the adapter honours, and a model inventing plausible-looking
parameters is ordinary behaviour, not an attack.

Both invocation paths are covered here, because there are two and they do not
share a call site: `ToolRegistry.execute` serves the durable agent-task lane and
`PresenceExecutor.run_step` serves the conversation.
"""

from __future__ import annotations

import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.conversation import PresenceExecutor
from services.agent_runtime.governance import APPROVAL_METADATA_KEY
from services.agent_runtime.halt import HaltRegistry, signal_or_open
from services.agent_runtime.presence import Caller, PresenceDecision
from services.agent_runtime.tools import (
    ToolRegistry,
    ToolResult,
    ToolSpec,
    unknown_arguments,
)
from services.devon.approval import ApprovalQueue, InMemoryApprovalStore

TEE = Caller.human()
TURN = "TURN-ARGS-001"


def recorder(
    name: str,
    risk: ToolRisk,
    parameters: tuple,
    *,
    reversible: bool = True,
):
    """A tool that records what actually reached it, so 'did not run' is provable."""
    ran: list = []

    def handler(args):
        ran.append(dict(args))
        return ToolResult(ok=True, output=f"{name} ran")

    spec = ToolSpec(
        name=name,
        description=name,
        risk=risk,
        handler=handler,
        reversible=reversible,
        parameters=parameters,
    )
    return spec, ran


def executor(*specs: ToolSpec):
    registry = ToolRegistry()
    for spec in specs:
        registry.register(spec)
    store = InMemoryApprovalStore()
    queue = ApprovalQueue(store)
    return (
        PresenceExecutor(registry, turn_id=TURN, approvals=queue, actor="tee"),
        store,
    )


def rows(store: InMemoryApprovalStore) -> int:
    """Every approval record, not just the pending ones.

    `store.pending()` is the only public reader and it filters to PENDING, which
    would report empty for exactly the record this test is trying to catch:
    presence mints a card and rules on it in one call stack, so a minted row is
    already APPROVED by the time anyone could look.
    """
    return len(store._records)


async def run(ex, tool: str, arguments: dict):
    return await ex.run_step(
        tool,
        arguments,
        caller=TEE,
        halt=signal_or_open(HaltRegistry(), TURN),
    )


# ---------------------------------------------------------------------------
# The tripwire: nothing ships without declaring its surface
# ---------------------------------------------------------------------------


def test_every_shipped_tool_declares_the_arguments_it_reads() -> None:
    """An empty `parameters` disables the check, so no shipped tool may have one.

    This is the test that keeps the fix alive. The validator treats an
    undeclared surface as unchecked, which is right for the ad-hoc ToolSpecs
    that tests build by the dozen and wrong for anything DEVON actually hands
    out. Without this, a new adapter added next month reintroduces the silent
    drop and every other test still passes.
    """
    from app.services.agent_tasks import build_tool_registry

    undeclared = [
        described["name"]
        for described in build_tool_registry().describe()
        if not described["parameters"]
    ]
    assert undeclared == [], (
        "these registered tools accept anything and silently drop what they do "
        f"not read: {undeclared}"
    )


def test_the_declared_surface_is_published_to_the_model() -> None:
    """The model picks arguments from this list; hiding it invites invention."""
    from app.services.agent_tasks import build_tool_registry

    described = {d["name"]: d for d in build_tool_registry().describe()}
    assert described["operator.command"]["parameters"] == [
        "command",
        "cwd",
        "timeout_seconds",
    ]
    assert "args" not in described["operator.command"]["parameters"]


# ---------------------------------------------------------------------------
# The exact shape that passed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_argument_shape_that_silently_passed_is_now_refused() -> None:
    """Verbatim reproduction of the 2026-08-27 false pass."""
    spec, ran = recorder(
        "operator.command", ToolRisk.HIGH_IMPACT, ("command", "cwd", "timeout_seconds")
    )
    ex, _store = executor(spec)

    outcome = await run(
        ex, "operator.command", {"command": "echo", "args": ["adapter-proof-marker"]}
    )

    assert not outcome.ran
    assert ran == [], "the handler ran on arguments the caller did not get"
    assert "does not accept: args" in outcome.detail
    assert "command, cwd, timeout_seconds" in outcome.detail


@pytest.mark.asyncio
async def test_refusal_lands_before_any_approval_row_is_minted() -> None:
    """The governance property, and the reason this is not merely a nicety.

    An APPROVED row naming arguments the process was never going to honour is a
    receipt for something that did not happen. The check therefore sits ahead of
    the binding and ahead of `_authorise`, not merely ahead of the handler.
    """
    spec, ran = recorder(
        "github.write_file",
        ToolRisk.WRITE,
        # Reversible so the positive control below runs without a confirmation.
        # Irreversibility is irrelevant here: the argument check sits ahead of
        # the presence verdict entirely.
        ("repository", "path", "content", "message", "branch"),
        reversible=True,
    )
    ex, store = executor(spec)

    outcome = await run(
        ex,
        "github.write_file",
        {
            "repository": "tdveal74-cell/Meta-Supreme-Apex-Genesis-",
            "path": "README.md",
            "content": "x",
            "message": "m",
            "branch": "main",
            "force": True,
        },
    )

    assert not outcome.ran
    assert ran == []
    assert outcome.decision is PresenceDecision.REFUSE
    assert outcome.approval_request_id == ""
    assert rows(store) == 0, "a refused call left an approval record behind"
    assert "force" in outcome.detail

    # Positive control: the same tool, same executor, arguments it actually
    # reads. Without this the assertion above would also pass if presence had
    # stopped minting rows altogether.
    good = await run(
        ex,
        "github.write_file",
        {
            "repository": "tdveal74-cell/Meta-Supreme-Apex-Genesis-",
            "path": "README.md",
            "content": "x",
            "message": "m",
            "branch": "main",
        },
    )
    assert good.ran
    assert good.approval_request_id != ""
    assert rows(store) == 1


@pytest.mark.asyncio
async def test_a_refused_call_reports_a_failure_not_a_success() -> None:
    """The false pass returned ok. This one must not."""
    spec, _ran = recorder("browser.fetch", ToolRisk.READ, ("url",))
    ex, _store = executor(spec)

    outcome = await run(
        ex, "browser.fetch", {"url": "https://api.github.com", "method": "POST"}
    )

    assert outcome.result is not None
    assert outcome.result.ok is False
    assert "method" in outcome.result.error


# ---------------------------------------------------------------------------
# The other invocation path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_durable_lane_refuses_unknown_arguments_too() -> None:
    """`ToolRegistry.execute` is a separate call site and needs its own guard."""
    spec, ran = recorder("runtime.schedule_goal", ToolRisk.WRITE, ("goal", "owner_id"))
    registry = ToolRegistry()
    registry.register(spec)

    result = await registry.execute(
        "runtime.schedule_goal", {"goal": "ship it", "when": "tomorrow"}
    )

    assert result.ok is False
    assert ran == []
    assert "does not accept: when" in result.error


# ---------------------------------------------------------------------------
# What must still get through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_declared_arguments_reach_the_handler_unchanged() -> None:
    spec, ran = recorder("operator.read", ToolRisk.READ, ("command", "cwd", "timeout_seconds"))
    ex, _store = executor(spec)

    outcome = await run(
        ex, "operator.read", {"command": "git status", "timeout_seconds": 30}
    )

    assert outcome.ran
    assert ran == [{"command": "git status", "timeout_seconds": 30}]


@pytest.mark.asyncio
async def test_a_partial_argument_set_is_fine() -> None:
    """Declaring a surface names what is allowed, not what is required."""
    spec, ran = recorder("github.read_file", ToolRisk.READ, ("repository", "path", "ref"))
    ex, _store = executor(spec)

    outcome = await run(ex, "github.read_file", {"repository": "o/r", "path": "README.md"})

    assert outcome.ran
    assert ran == [{"repository": "o/r", "path": "README.md"}]


def test_the_approval_metadata_key_is_never_an_unknown_argument() -> None:
    """The executor injects it after the check; the adapters pop it off.

    If this were treated as unknown, every governed write would refuse itself at
    the capability boundary.
    """
    spec = ToolSpec(
        name="github.write_file",
        description="w",
        risk=ToolRisk.WRITE,
        handler=lambda args: "ok",
        parameters=("repository", "path"),
    )
    assert unknown_arguments(spec, {"repository": "o/r", APPROVAL_METADATA_KEY: {}}) == ()


def test_an_undeclared_spec_is_unchecked_and_that_is_deliberate() -> None:
    """Documents the escape hatch the tripwire above exists to police."""
    spec = ToolSpec(
        name="test.only",
        description="t",
        risk=ToolRisk.READ,
        handler=lambda args: "ok",
    )
    assert unknown_arguments(spec, {"anything": 1, "at": "all"}) == ()


# ---------------------------------------------------------------------------
# browser.navigate says what it did not do
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_navigate_does_not_report_a_page_it_never_loaded() -> None:
    """It opens no browser. Its own output used to read like a completed visit.

    "Navigation recorded for https://..." is the kind of sentence a model reads
    as done and then answers questions about the page from nothing. The tool is
    kept because it is the estate's only registered reversible WRITE reaching a
    real adapter, which several presence tests depend on; what changed is that
    it now states plainly that no page was read.
    """
    from services.browser.agent_adapter import BrowserCapabilityAdapter

    queue = ApprovalQueue(InMemoryApprovalStore())
    registry = ToolRegistry()
    BrowserCapabilityAdapter(queue).register(registry)

    ex = PresenceExecutor(registry, turn_id=TURN, approvals=queue, actor="tee")
    outcome = await ex.run_step(
        "browser.navigate",
        {"url": "https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-"},
        caller=TEE,
        halt=signal_or_open(HaltRegistry(), TURN),
    )

    assert outcome.ran
    assert outcome.result is not None and outcome.result.ok
    body = outcome.result.output
    assert "No browser session was opened" in body
    assert "no page was loaded" in body
    assert outcome.result.metadata is not None
    assert outcome.result.metadata["visited"] is False


@pytest.mark.asyncio
async def test_the_model_is_told_which_argument_was_wrong() -> None:
    """A refusal the model cannot act on is a dead end rather than a correction.

    The turn does not stop on a refusal, so this observation is the model's only
    chance to fix the call. If it says nothing but "blocked by policy" the model
    retries the same arguments or abandons a task that one renamed key would
    have fixed.
    """
    from services.agent_runtime.agent_turn import Observation  # noqa: F401

    spec, _ran = recorder("operator.command", ToolRisk.HIGH_IMPACT, ("command",))
    ex, _store = executor(spec)

    outcome = await run(ex, "operator.command", {"command": "echo hi", "args": ["hi"]})

    observed = f"refused: {outcome.detail}"
    assert "args" in observed
    assert "It reads only: command" in observed
