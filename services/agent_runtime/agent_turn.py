"""One conversational turn: DEVON answers, and acts while answering.

Until Build 15 DEVON had a mouth and hands that were never wired together.
Talking to him convened the council, which deliberates beautifully and cannot
touch a tool. Asking him to DO something created a task whose plan froze at
creation and then waited on an emailed card. There was no single loop where he
answers you and acts inside the same exchange, and that gap is the whole
distance between what the estate had and what Tee asked for.

This is that loop. It is deliberately iterative rather than plan-then-execute:
a conversation cannot freeze its plan at the first message, because the second
tool result routinely changes what the third call should be.

Three properties hold it together:

- **Authority comes from the transport, never the transcript.** The Caller is
  handed in by the endpoint that authenticated a human. Nothing the model emits
  can manufacture presence, so a turn cannot talk itself into permissions.
- **The brake is checked between every step**, and again inside the executor
  immediately before any effect. A halt stops the next action; it never claims
  to undo the last.
- **The loop is bounded.** Every iteration costs a provider call, so a model
  that loops on itself burns Tee's money. `max_steps` caps it and the cap is
  reported as a real outcome rather than a silent stop.

Wire format: the provider has no native tool-use, so the same JSON-mode
discipline the planner uses applies here. Each reply is one object, either
`{"say": "..."}` to answer or `{"tool": ..., "arguments": {...}}` to act.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from services.agent_runtime.conversation import PresenceExecutor
from services.agent_runtime.halt import Halted, HaltSignal
from services.agent_runtime.presence import Caller, PresenceDecision
from services.agent_runtime.tools import ToolRegistry
from services.intelligence.providers.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderError,
    extract_json,
)

logger = logging.getLogger(__name__)

MAX_TURN_STEPS = 8
"""Tool calls allowed in one turn before the loop stops and says so.

Eight is chosen to be generous for real work (read four tables, compare, act)
and still bounded, because each step is a paid provider round trip.
"""

TURN_CONTRACT = (
    '{"say": "what you want to tell Tee"} '
    'OR {"tool": "exact.tool.name", "arguments": {}, "why": "one short clause"}'
)


@dataclass
class TurnEvent:
    """One thing worth telling Tee about, as it happens."""

    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, **self.data}


@dataclass
class Observation:
    """What a tool call produced, in the form the model sees next iteration."""

    tool: str
    outcome: str

    def as_line(self) -> str:
        return f"{self.tool} -> {self.outcome}"


class AgentTurn:
    """Runs one exchange and yields events as it goes.

    Owns no transport and no database. The endpoint feeds it a Caller and a
    HaltSignal and forwards its events; that keeps every property below
    testable against a scripted provider with no server running.
    """

    def __init__(
        self,
        *,
        provider: AIProvider,
        tools: ToolRegistry,
        executor: PresenceExecutor,
        model: Optional[str] = None,
        max_steps: int = MAX_TURN_STEPS,
    ) -> None:
        self.provider = provider
        self.tools = tools
        self.executor = executor
        self.model = model
        self.max_steps = max(1, min(int(max_steps), MAX_TURN_STEPS))

    # -- prompt ------------------------------------------------------------

    def _system(self, caller: Caller) -> str:
        catalog = json.dumps(self.tools.describe(), ensure_ascii=False)
        return (
            "You are DEVON, Tee's second brain and executive control plane. "
            "You are in a live conversation with him: answer like a colleague "
            "who is already doing the work, not like a form. "
            "Reply with ONE JSON object and nothing else, in exactly this "
            f"shape: {TURN_CONTRACT} "
            "Use a tool when the answer depends on something you can look up "
            "or do; otherwise just say it. Never invent a tool name; the "
            f"available tools are: {catalog} "
            "Read tools run immediately. Writes run immediately too while Tee "
            "is present, EXCEPT ones that cannot be undone, which will come "
            "back to you as needing his confirmation. Blocked tools are "
            "refused no matter who asks, so do not select one. "
            "You do not decide whether Tee is present; that is established "
            "before you are called. "
            f"Presence for this turn: {'live human' if caller.present else 'automation'}."
        )

    def _messages(
        self,
        history: Sequence[ChatMessage],
        message: str,
        observations: Sequence[Observation],
    ) -> List[ChatMessage]:
        msgs = list(history)
        msgs.append(ChatMessage(role="user", content=message))
        if observations:
            # Observations are labelled as tool output, not as Tee speaking, so
            # a tool that echoes text cannot impersonate him.
            lines = "\n".join(obs.as_line() for obs in observations)
            msgs.append(
                ChatMessage(
                    role="user",
                    content=(
                        "TOOL RESULTS SO FAR (these are tool output, not Tee):\n"
                        f"{lines}\n"
                        "Continue: either call another tool or answer him."
                    ),
                )
            )
        return msgs

    # -- the loop ----------------------------------------------------------

    async def run(
        self,
        message: str,
        *,
        caller: Caller,
        halt: HaltSignal,
        history: Optional[Sequence[ChatMessage]] = None,
        confirmed_token: str = "",
    ) -> AsyncIterator[TurnEvent]:
        clean = (message or "").strip()
        if not clean:
            yield TurnEvent("error", {"message": "empty message"})
            return

        observations: List[Observation] = []
        system = self._system(caller)
        # A confirmation answers the FIRST tool call of this turn and is spent
        # once, so a single yes can never authorise a second effect.
        pending_token = (confirmed_token or "").strip()

        yield TurnEvent("turn_started", {"turn_id": self.executor.turn_id})

        for _step in range(self.max_steps):
            if halt.halted:
                yield TurnEvent("halted", {"reason": halt.reason})
                return

            try:
                reply = await self._ask(system, history or [], clean, observations)
            except ProviderError as exc:
                logger.error("agent turn provider failure: %s", type(exc).__name__)
                yield TurnEvent(
                    "error", {"message": "the intelligence provider did not answer"}
                )
                return
            except ValueError:
                # Unparseable JSON. The planner earns a repair attempt because a
                # plan is expensive to redo; a conversation is cheaper to simply
                # answer again, so this fails visibly instead of silently
                # burning another call.
                yield TurnEvent(
                    "error",
                    {"message": "DEVON did not reply in a usable shape; ask again"},
                )
                return

            say = reply.get("say")
            tool_name = str(reply.get("tool") or "").strip()

            if not tool_name:
                text = str(say or "").strip()
                if not text:
                    yield TurnEvent(
                        "error", {"message": "DEVON replied with neither words nor an action"}
                    )
                    return
                yield TurnEvent("answer", {"text": text})
                return

            arguments = reply.get("arguments")
            if not isinstance(arguments, dict):
                arguments = {}

            yield TurnEvent(
                "tool_started",
                {"tool": tool_name, "why": str(reply.get("why") or "").strip()},
            )

            try:
                outcome = await self.executor.run_step(
                    tool_name,
                    arguments,
                    caller=caller,
                    halt=halt,
                    confirmed_token=pending_token,
                )
            except Halted as stop:
                yield TurnEvent("halted", {"reason": stop.reason})
                return
            except KeyError:
                # An invented tool name. Tell the model so it can correct itself
                # rather than ending the turn on a model typo.
                observations.append(
                    Observation(tool=tool_name, outcome="no such tool; do not use that name")
                )
                yield TurnEvent("tool_unknown", {"tool": tool_name})
                continue
            finally:
                pending_token = ""

            if outcome.decision is PresenceDecision.CONFIRM and not outcome.ran:
                yield TurnEvent(
                    "needs_confirmation",
                    {
                        "tool": outcome.tool,
                        "arguments": outcome.arguments,
                        "confirm_token": outcome.confirm_token,
                        "detail": outcome.detail,
                    },
                )
                return

            if outcome.decision is PresenceDecision.REFUSE:
                yield TurnEvent("refused", {"tool": outcome.tool, "detail": outcome.detail})
                observations.append(
                    Observation(tool=outcome.tool, outcome="refused: blocked by policy")
                )
                continue

            if outcome.decision is PresenceDecision.CARD:
                yield TurnEvent("card_required", {"tool": outcome.tool, "detail": outcome.detail})
                return

            result = outcome.result
            ok = bool(result and result.ok)
            body = (result.output if result else "") or (result.error if result else "")
            yield TurnEvent(
                "tool_result",
                {"tool": outcome.tool, "ok": ok, "output": body[:2000]},
            )
            observations.append(
                Observation(
                    tool=outcome.tool,
                    outcome=(body[:1000] if ok else f"FAILED: {body[:500]}"),
                )
            )

        # Fell out of the loop with work still queued. Say so plainly: a silent
        # stop here would look like an answer.
        yield TurnEvent(
            "step_limit",
            {
                "steps": self.max_steps,
                "message": (
                    f"stopped after {self.max_steps} tool calls without reaching "
                    "an answer; ask again more narrowly"
                ),
            },
        )

    async def _ask(
        self,
        system: str,
        history: Sequence[ChatMessage],
        message: str,
        observations: Sequence[Observation],
    ) -> Dict[str, Any]:
        response = await self.provider.complete(
            CompletionRequest(
                system=system,
                messages=self._messages(history, message, observations),
                model=self.model,
                max_tokens=1500,
                temperature=0.2,
                json_mode=True,
                metadata={"component": "devon-agent-turn"},
            )
        )
        return extract_json(response.text)
