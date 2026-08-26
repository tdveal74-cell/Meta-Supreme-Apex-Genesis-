"""The conversational turn: DEVON answering and acting in one exchange.

This is the loop that runs tools while Tee is talking, so its boundaries matter
more than its happy path. The tests that earn their keep are the ones proving
what the loop CANNOT be talked into: manufacturing its own presence, spending
one confirmation twice, running past a stop, or looping on Tee's money forever.
"""

from __future__ import annotations

import json
from typing import List

import pytest

from services.agent_runtime.agent_turn import MAX_TURN_STEPS, AgentTurn
from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.conversation import PresenceExecutor, confirm_binding
from services.agent_runtime.halt import HaltSignal
from services.agent_runtime.presence import Caller
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderError,
    TokenUsage,
)

TURN = "TURN-42"
TEE = Caller.human()
ROUTINE = Caller.automated("reflection")


def say(text: str) -> str:
    return json.dumps({"say": text})


def call(tool: str, **arguments) -> str:
    return json.dumps({"tool": tool, "arguments": arguments, "why": "because"})


class Scripted(AIProvider):
    name = "scripted-turn"

    def __init__(self, *replies: str) -> None:
        super().__init__(default_model="scripted-turn", max_retries=0)
        self._replies = list(replies)
        self.requests: List[CompletionRequest] = []

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if not self._replies:
            raise AssertionError("the loop asked for more replies than scripted")
        return CompletionResponse(
            text=self._replies.pop(0),
            usage=TokenUsage(),
            model="scripted-turn",
            provider=self.name,
        )


class Dead(AIProvider):
    name = "dead-turn"

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        del request
        raise ProviderError("upstream is down", provider=self.name)

    def __init__(self) -> None:
        super().__init__(default_model="dead-turn", max_retries=0)


def build(*replies: str, tools: ToolRegistry = None) -> tuple:
    reg = tools if tools is not None else default_tools()[0]
    provider = Scripted(*replies)
    turn = AgentTurn(
        provider=provider,
        tools=reg,
        executor=PresenceExecutor(reg, turn_id=TURN),
    )
    return turn, provider


def default_tools():
    ran: List[str] = []

    def read_handler(args):
        ran.append("ledger.read")
        return ToolResult(ok=True, output="8 jobs, all terminal")

    def write_handler(args):
        ran.append("notes.append")
        return ToolResult(ok=True, output="noted")

    def soul_handler(args):
        ran.append("soul.commit")
        return ToolResult(ok=True, output="committed")

    reg = ToolRegistry()
    reg.register(ToolSpec("ledger.read", "read", ToolRisk.READ, read_handler))
    reg.register(
        ToolSpec("notes.append", "write", ToolRisk.WRITE, write_handler, reversible=True)
    )
    reg.register(
        ToolSpec("soul.commit", "soul", ToolRisk.WRITE, soul_handler, reversible=True)
    )
    reg.register(
        ToolSpec("repo.destroy", "blocked", ToolRisk.BLOCKED, lambda a: ran.append("BAD"))
    )
    return reg, ran


async def collect(turn, *args, **kwargs) -> List[dict]:
    return [e.to_dict() async for e in turn.run(*args, **kwargs)]


def types_of(events) -> List[str]:
    return [e["type"] for e in events]


# ---------------------------------------------------------------------------
# Answering, and acting while answering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_plain_question_is_answered_without_touching_a_tool() -> None:
    reg, ran = default_tools()
    turn, provider = build(say("Everything is quiet."), tools=reg)

    events = await collect(turn, "how are things?", caller=TEE, halt=HaltSignal())

    assert types_of(events) == ["turn_started", "answer"]
    assert events[-1]["text"] == "Everything is quiet."
    assert ran == []
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_a_read_runs_immediately_and_its_result_reaches_the_answer() -> None:
    reg, ran = default_tools()
    turn, provider = build(
        call("ledger.read"), say("8 jobs, all terminal."), tools=reg
    )

    events = await collect(turn, "what is stuck?", caller=TEE, halt=HaltSignal())

    assert types_of(events) == ["turn_started", "tool_started", "tool_result", "answer"]
    assert ran == ["ledger.read"]
    # The observation was fed back, labelled as tool output rather than as Tee.
    second = provider.requests[1].messages[-1].content
    assert "TOOL RESULTS SO FAR" in second
    assert "not Tee" in second
    assert "8 jobs, all terminal" in second


@pytest.mark.asyncio
async def test_a_reversible_write_runs_with_no_card_and_no_asking() -> None:
    reg, ran = default_tools()
    turn, _ = build(call("notes.append", text="hi"), say("Noted."), tools=reg)

    events = await collect(turn, "note that", caller=TEE, halt=HaltSignal())

    assert "tool_result" in types_of(events)
    assert ran == ["notes.append"]


# ---------------------------------------------------------------------------
# What the loop cannot be talked into
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_irreversible_tool_stops_the_turn_and_asks() -> None:
    reg, ran = default_tools()
    turn, _ = build(call("soul.commit", claim="x"), tools=reg)

    events = await collect(turn, "remember that", caller=TEE, halt=HaltSignal())

    assert types_of(events)[-1] == "needs_confirmation"
    ask = events[-1]
    assert ask["tool"] == "soul.commit"
    assert ask["confirm_token"] == confirm_binding(
        turn_id=TURN, tool_name="soul.commit", arguments={"claim": "x"}
    )
    assert ran == [], "the turn must end at the question, not run and then ask"


@pytest.mark.asyncio
async def test_a_confirmation_is_spent_once_and_cannot_authorise_a_second_effect() -> None:
    """The load-bearing one: a single yes must not become a blank cheque."""
    reg, ran = default_tools()
    args = {"claim": "x"}
    token = confirm_binding(turn_id=TURN, tool_name="soul.commit", arguments=args)
    turn, _ = build(
        call("soul.commit", **args),  # runs on the supplied token
        call("soul.commit", claim="y"),  # must NOT ride the same yes
        tools=reg,
    )

    events = await collect(
        turn, "do it", caller=TEE, halt=HaltSignal(), confirmed_token=token
    )

    assert ran == ["soul.commit"], "only the confirmed call may run"
    assert types_of(events)[-1] == "needs_confirmation"
    assert events[-1]["arguments"] == {"claim": "y"}


@pytest.mark.asyncio
async def test_a_blocked_tool_is_refused_and_the_loop_is_told() -> None:
    reg, ran = default_tools()
    turn, _ = build(call("repo.destroy"), say("I cannot do that."), tools=reg)

    events = await collect(turn, "wipe it", caller=TEE, halt=HaltSignal())

    assert "refused" in types_of(events)
    assert types_of(events)[-1] == "answer"
    assert "BAD" not in ran


@pytest.mark.asyncio
async def test_an_absent_caller_is_sent_to_the_card_and_the_turn_ends() -> None:
    """The reflection may want things. It may not do them."""
    reg, ran = default_tools()
    turn, _ = build(call("notes.append", text="x"), tools=reg)

    events = await collect(turn, "note it", caller=ROUTINE, halt=HaltSignal())

    assert types_of(events)[-1] == "card_required"
    assert ran == []


@pytest.mark.asyncio
async def test_presence_in_the_prompt_is_stated_not_asked() -> None:
    """The model is told the verdict; it never supplies it."""
    reg, _ = default_tools()
    turn, provider = build(say("ok"), tools=reg)
    await collect(turn, "hi", caller=ROUTINE, halt=HaltSignal())

    system = provider.requests[0].system
    assert "Presence for this turn: automation" in system
    assert "You do not decide whether Tee is present" in system


# ---------------------------------------------------------------------------
# The brake
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_halt_before_the_turn_stops_it_immediately() -> None:
    reg, ran = default_tools()
    turn, provider = build(call("notes.append"), tools=reg)
    halt = HaltSignal()
    halt.halt("Tee said stop")

    events = await collect(turn, "go", caller=TEE, halt=halt)

    assert types_of(events) == ["turn_started", "halted"]
    assert events[-1]["reason"] == "Tee said stop"
    assert ran == []
    assert provider.requests == [], "a stopped turn must not even pay for a call"


@pytest.mark.asyncio
async def test_a_halt_between_steps_stops_before_the_next_tool() -> None:
    reg, ran = default_tools()

    def stopping_read(args):
        ran.append("ledger.read")
        halt.halt("Tee said stop")
        return ToolResult(ok=True, output="read done")

    reg2 = ToolRegistry()
    reg2.register(ToolSpec("ledger.read", "read", ToolRisk.READ, stopping_read))
    reg2.register(
        ToolSpec("notes.append", "w", ToolRisk.WRITE, lambda a: ran.append("notes.append"),
                 reversible=True)
    )
    halt = HaltSignal()
    turn, _ = build(call("ledger.read"), call("notes.append"), tools=reg2)

    events = await collect(turn, "go", caller=TEE, halt=halt)

    assert types_of(events)[-1] == "halted"
    assert ran == ["ledger.read"], "the first ran; the second never started"


# ---------------------------------------------------------------------------
# Bounded, and honest when it gives up
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_loop_is_capped_and_says_so_rather_than_stopping_silently() -> None:
    reg, ran = default_tools()
    turn, provider = build(*([call("ledger.read")] * MAX_TURN_STEPS), tools=reg)

    events = await collect(turn, "loop", caller=TEE, halt=HaltSignal())

    assert types_of(events)[-1] == "step_limit"
    assert events[-1]["steps"] == MAX_TURN_STEPS
    assert len(provider.requests) == MAX_TURN_STEPS
    assert len(ran) == MAX_TURN_STEPS


@pytest.mark.asyncio
async def test_a_tool_failure_feeds_back_instead_of_killing_the_turn() -> None:
    def broken(args):
        raise RuntimeError("adapter exploded")

    reg = ToolRegistry()
    reg.register(ToolSpec("flaky.read", "flaky", ToolRisk.READ, broken))
    turn, provider = build(call("flaky.read"), say("That failed; here is why."), tools=reg)

    events = await collect(turn, "try it", caller=TEE, halt=HaltSignal())

    assert types_of(events) == ["turn_started", "tool_started", "tool_result", "answer"]
    result = [e for e in events if e["type"] == "tool_result"][0]
    assert result["ok"] is False
    assert "FAILED" in provider.requests[1].messages[-1].content


@pytest.mark.asyncio
async def test_an_invented_tool_name_is_corrected_rather_than_ending_the_turn() -> None:
    reg, ran = default_tools()
    turn, _ = build(call("made.up.tool"), say("Sorry, using the real one."), tools=reg)

    events = await collect(turn, "go", caller=TEE, halt=HaltSignal())

    assert "tool_unknown" in types_of(events)
    assert types_of(events)[-1] == "answer"
    assert ran == []


@pytest.mark.asyncio
async def test_a_provider_outage_fails_visibly_without_leaking_its_message() -> None:
    reg, _ = default_tools()
    turn = AgentTurn(
        provider=Dead(), tools=reg, executor=PresenceExecutor(reg, turn_id=TURN)
    )

    events = [e.to_dict() async for e in turn.run("hi", caller=TEE, halt=HaltSignal())]

    assert types_of(events)[-1] == "error"
    assert "down" not in events[-1]["message"]


@pytest.mark.asyncio
async def test_unparseable_json_fails_visibly_and_does_not_burn_another_call() -> None:
    reg, _ = default_tools()
    turn, provider = build("I am not JSON at all.", tools=reg)

    events = await collect(turn, "hi", caller=TEE, halt=HaltSignal())

    assert types_of(events)[-1] == "error"
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_a_reply_with_neither_words_nor_an_action_is_an_error() -> None:
    reg, _ = default_tools()
    turn, _ = build(json.dumps({"say": "   "}), tools=reg)

    events = await collect(turn, "hi", caller=TEE, halt=HaltSignal())

    assert types_of(events)[-1] == "error"


@pytest.mark.asyncio
async def test_an_empty_message_is_refused_before_any_provider_call() -> None:
    reg, _ = default_tools()
    turn, provider = build(say("never reached"), tools=reg)

    events = await collect(turn, "   ", caller=TEE, halt=HaltSignal())

    assert types_of(events) == ["error"]
    assert provider.requests == []
