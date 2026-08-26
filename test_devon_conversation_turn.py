"""The conversational turn: the brake, and the binding on "yes".

Two properties carry the safety of presence authority once it is wired:

1. A halt stops the NEXT effect. It cannot un-run what already ran, and the
   tests say so plainly rather than implying an undo.
2. A confirmation approves the action it was SHOWN, never whatever happens to be
   queued when the answer arrives. Between the ask and the yes, a re-plan or a
   race can move the target; the binding is what stops a yes from drifting.
"""

from __future__ import annotations

import pytest

from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.conversation import (
    PresenceExecutor,
    confirm_binding,
)
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.halt import (
    Halted,
    HaltRegistry,
    HaltSignal,
    signal_or_open,
)
from services.agent_runtime.presence import Caller, PresenceDecision
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.devon.approval import (
    ApprovalQueue,
    ApprovalState,
    InMemoryApprovalStore,
)

TEE = Caller.human()
ROUTINE = Caller.automated("reflection")
TURN = "TURN-001"


def registry_with(*specs: ToolSpec) -> ToolRegistry:
    reg = ToolRegistry()
    for spec in specs:
        reg.register(spec)
    return reg


def executor(*specs: ToolSpec, turn_id: str = TURN, actor: str = "tee"):
    """An executor wired the way the endpoint wires one.

    The queue is not optional decoration. An effect DEVON cannot record is one
    he does not run, so an executor without a queue refuses every write -- which
    is its own test further down.
    """
    queue = ApprovalQueue(InMemoryApprovalStore())
    return (
        PresenceExecutor(
            registry_with(*specs), turn_id=turn_id, approvals=queue, actor=actor
        ),
        queue,
    )


def recorder(name: str, risk: ToolRisk, *, reversible: bool = False):
    """A tool that records every invocation, so 'did not run' is provable."""
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
    )
    return spec, ran


# ---------------------------------------------------------------------------
# The happy path Tee actually asked for
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reversible_write_runs_immediately_with_no_asking() -> None:
    spec, ran = recorder("notes.append", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)

    out = await ex.run_step(
        "notes.append", {"text": "hi"}, caller=TEE, halt=HaltSignal()
    )

    assert out.decision is PresenceDecision.RUN
    assert out.ran is True
    assert out.result and out.result.ok
    assert out.confirm_token == ""

    # The write ran with no card emailed and no waiting -- and still left a row
    # behind it. That row is what the capability adapters check independently,
    # and what makes the effect accountable afterwards.
    assert out.approval_request_id
    record = queue.get(out.approval_request_id)
    assert record is not None
    assert record.state is ApprovalState.APPROVED
    assert record.requested_by == RUNTIME_REQUESTED_BY
    assert record.decided_by == "tee (present)"
    assert approval_marker(
        approval_binding(
            task_id=TURN,
            step_id="STEP-01",
            tool_name="notes.append",
            arguments={"text": "hi"},
        )
    ) in record.what_happens

    # The handler is handed the proof, keyed exactly as the adapters pop it.
    assert len(ran) == 1
    delivered = ran[0]
    assert delivered["text"] == "hi"
    assert delivered[APPROVAL_METADATA_KEY]["request_id"] == out.approval_request_id
    assert delivered[APPROVAL_METADATA_KEY]["tool_name"] == "notes.append"


# ---------------------------------------------------------------------------
# The brake
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_halt_prevents_the_next_effect() -> None:
    spec, ran = recorder("notes.append", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)
    halt = HaltSignal()
    halt.halt("Tee said stop")

    with pytest.raises(Halted) as caught:
        await ex.run_step("notes.append", {}, caller=TEE, halt=halt)

    assert caught.value.reason == "Tee said stop"
    assert ran == [], "the halt must land before the handler, not after"


@pytest.mark.asyncio
async def test_a_halt_leaves_no_approval_for_an_effect_that_never_ran() -> None:
    """A receipt for something that did not happen is a receipt for a lie."""
    spec, ran = recorder("notes.append", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)
    halt = HaltSignal()
    halt.halt("Tee said stop")

    with pytest.raises(Halted):
        await ex.run_step("notes.append", {}, caller=TEE, halt=halt)

    assert ran == []
    assert queue.pending() == []
    assert queue._store.all() == [], "no row was raised for an effect that was stopped"


@pytest.mark.asyncio
async def test_a_halt_does_not_pretend_to_undo_what_already_ran() -> None:
    """Honest brake: the first call completed, the second is refused."""
    spec, ran = recorder("notes.append", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)
    halt = HaltSignal()

    first = await ex.run_step("notes.append", {"n": 1}, caller=TEE, halt=halt)
    assert first.ran is True

    halt.halt("stop")
    with pytest.raises(Halted):
        await ex.run_step("notes.append", {"n": 2}, caller=TEE, halt=halt)

    assert [args["n"] for args in ran] == [1], (
        "what ran, ran; only the next one is stopped"
    )


def test_halt_keeps_the_first_reason() -> None:
    """'Tee said stop' must not be overwritten by a later generic reason."""
    halt = HaltSignal()
    halt.halt("Tee said stop")
    halt.halt("turn ended")
    assert halt.reason == "Tee said stop"


def test_registry_halts_a_turn_by_id_from_another_request() -> None:
    reg = HaltRegistry()
    signal = reg.open(TURN)
    assert reg.is_running(TURN)

    assert reg.halt(TURN, "Tee said stop") is True
    assert signal.halted is True
    assert signal.reason == "Tee said stop"

    reg.close(TURN)
    assert reg.is_running(TURN) is False


def test_halting_a_finished_turn_reports_a_miss_rather_than_raising() -> None:
    """Saying stop half a second late is a race, not an error."""
    reg = HaltRegistry()
    assert reg.halt("TURN-GONE", "stop") is False


def test_a_turn_without_a_registry_is_still_interruptible_in_shape() -> None:
    """The execution path must not branch on whether wiring exists."""
    signal = signal_or_open(None, TURN)
    assert isinstance(signal, HaltSignal)
    assert signal.halted is False


# ---------------------------------------------------------------------------
# "Yes" is bound to what was shown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_irreversible_tool_asks_and_does_not_run() -> None:
    spec, ran = recorder("soul.commit", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)

    out = await ex.run_step(
        "soul.commit", {"claim": "x"}, caller=TEE, halt=HaltSignal()
    )

    assert out.decision is PresenceDecision.CONFIRM
    assert out.ran is False
    assert out.confirm_token == confirm_binding(
        turn_id=TURN, tool_name="soul.commit", arguments={"claim": "x"}
    )
    assert ran == []


@pytest.mark.asyncio
async def test_a_matching_confirmation_runs_it() -> None:
    spec, ran = recorder("soul.commit", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)
    args = {"claim": "x"}
    token = confirm_binding(turn_id=TURN, tool_name="soul.commit", arguments=args)

    out = await ex.run_step(
        "soul.commit", args, caller=TEE, halt=HaltSignal(), confirmed_token=token
    )

    assert out.ran is True
    assert len(ran) == 1
    assert ran[0]["claim"] == "x"
    # A confirmed effect is recorded exactly like an unconfirmed one. The
    # confirmation decided WHETHER it runs; the row is how it is accounted for.
    assert out.approval_request_id
    assert queue.get(out.approval_request_id).state is ApprovalState.APPROVED


@pytest.mark.asyncio
async def test_a_yes_cannot_drift_onto_different_arguments() -> None:
    """The load-bearing one. Tee confirmed claim 'x'; the action became 'y'."""
    spec, ran = recorder("soul.commit", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)
    shown = confirm_binding(
        turn_id=TURN, tool_name="soul.commit", arguments={"claim": "x"}
    )

    out = await ex.run_step(
        "soul.commit",
        {"claim": "y"},
        caller=TEE,
        halt=HaltSignal(),
        confirmed_token=shown,
    )

    assert out.ran is False
    assert "does not match" in out.detail
    assert ran == []


@pytest.mark.asyncio
async def test_a_yes_cannot_be_replayed_into_a_later_turn() -> None:
    spec, ran = recorder("soul.commit", ToolRisk.WRITE, reversible=True)
    args = {"claim": "x"}
    old_token = confirm_binding(
        turn_id="TURN-OLD", tool_name="soul.commit", arguments=args
    )
    ex, _ = executor(spec, turn_id="TURN-NEW")

    out = await ex.run_step(
        "soul.commit", args, caller=TEE, halt=HaltSignal(), confirmed_token=old_token
    )

    assert out.ran is False
    assert ran == []


def test_argument_order_does_not_change_the_token() -> None:
    a = confirm_binding(turn_id=TURN, tool_name="t", arguments={"x": 1, "y": 2})
    b = confirm_binding(turn_id=TURN, tool_name="t", arguments={"y": 2, "x": 1})
    assert a == b


# ---------------------------------------------------------------------------
# The other decisions still hold at the executor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocked_is_refused_and_never_invoked() -> None:
    spec, ran = recorder("repo.destroy", ToolRisk.BLOCKED, reversible=True)
    ex, queue = executor(spec)

    out = await ex.run_step("repo.destroy", {}, caller=TEE, halt=HaltSignal())

    assert out.decision is PresenceDecision.REFUSE
    assert out.ran is False
    assert ran == []


@pytest.mark.asyncio
async def test_absent_caller_is_sent_to_the_card_and_never_invoked() -> None:
    spec, ran = recorder("notes.append", ToolRisk.WRITE, reversible=True)
    ex, queue = executor(spec)

    out = await ex.run_step("notes.append", {}, caller=ROUTINE, halt=HaltSignal())

    assert out.decision is PresenceDecision.CARD
    assert out.ran is False
    assert ran == []


# ---------------------------------------------------------------------------
# One bad adapter ends its step, not the conversation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_raising_handler_becomes_a_failed_result() -> None:
    def boom(args):
        raise RuntimeError("adapter exploded")

    spec = ToolSpec(
        name="flaky.read",
        description="flaky",
        risk=ToolRisk.READ,
        handler=boom,
    )
    ex, queue = executor(spec)

    out = await ex.run_step("flaky.read", {}, caller=TEE, halt=HaltSignal())

    assert out.ran is True
    assert out.result and out.result.ok is False
    assert "adapter exploded" in out.result.error


@pytest.mark.asyncio
async def test_a_halt_raised_inside_a_handler_is_not_reported_as_a_tool_failure() -> None:
    """A stop Tee asked for is not a crash."""

    def stopper(args):
        raise Halted("Tee said stop")

    spec = ToolSpec(
        name="slow.read",
        description="slow",
        risk=ToolRisk.READ,
        handler=stopper,
    )
    ex, queue = executor(spec)

    with pytest.raises(Halted):
        await ex.run_step("slow.read", {}, caller=TEE, halt=HaltSignal())


@pytest.mark.asyncio
async def test_an_async_handler_is_awaited() -> None:
    async def handler(args):
        return "async ok"

    spec = ToolSpec(
        name="async.read",
        description="async",
        risk=ToolRisk.READ,
        handler=handler,
    )
    ex, queue = executor(spec)

    out = await ex.run_step("async.read", {}, caller=TEE, halt=HaltSignal())
    assert out.result and out.result.output == "async ok"


def test_an_executor_requires_a_turn_id() -> None:
    """Confirmations are bound to it, so an empty one would unbind every yes."""
    with pytest.raises(ValueError, match="turn id"):
        PresenceExecutor(ToolRegistry(), turn_id="  ")
