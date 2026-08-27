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

Four properties hold it together:

- **Authority comes from the transport, never the transcript.** The Caller is
  handed in by the endpoint that authenticated a human. Nothing the model emits
  can manufacture presence, so a turn cannot talk itself into permissions.
- **The brake is checked between every step**, and again inside the executor
  immediately before any effect. A halt stops the next action; it never claims
  to undo the last.
- **The loop is bounded.** Every iteration costs a provider call, so a model
  that loops on itself burns Tee's money. `max_steps` caps it and the cap is
  reported as a real outcome rather than a silent stop.
- **A confirmation resumes the turn; it never replays it.** The first cut of
  this loop ended the turn on a question and expected the whole turn to be
  driven again with a token attached. An adversarial pass on 2026-08-26 watched
  that re-run every step that preceded the question -- `browser.navigate` fired
  twice for one "yes" -- because "re-ask the model from the top" and "do the one
  thing he agreed to" are not the same instruction. So the question carries its
  observations out, and the answer carries them back in: on resume the confirmed
  call runs, and only then does the model get asked what to do next.

Wire format: the provider has no native tool-use, so the same JSON-mode
discipline the planner uses applies here. Each reply is one object, either
`{"say": "..."}` to answer or `{"tool": ..., "arguments": {...}}` to act.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from services.agent_runtime.contracts import COUNCIL_TOOL_NAME
from services.agent_runtime.conversation import (
    PresenceExecutor,
    StepOutcome,
    confirm_binding,
)
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

PER_TURN_TOOL_BUDGET: Dict[str, int] = {
    COUNCIL_TOOL_NAME: 1,
}
"""Tools whose single call costs far more than one provider round trip.

`max_steps` bounds how many times the LOOP calls the provider; it says nothing
about what one tool does internally. The council convenes a panel and can spend
well over a hundred completions inside a single `council.consult`, which the
step counter cannot see and the stream does not show. A model that decides
deliberation is the answer could therefore consult eight times in one turn and
spend more than most days of DEVON's operation.

The cap is per turn and deliberately one: a second opinion from the same panel
on the same question is not new information. Hitting it is reported to the model
as an observation rather than silently swallowed, so it reroutes instead of
retrying."""


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

    def to_dict(self) -> Dict[str, str]:
        return {"tool": self.tool, "outcome": self.outcome}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        return cls(
            tool=str(data.get("tool") or ""),
            outcome=str(data.get("outcome") or ""),
        )

    @classmethod
    def from_result(cls, tool: str, ok: bool, body: str) -> "Observation":
        """The one place a tool result becomes something the model reads.

        A failure keeps its FAILED prefix and is cut shorter than a success: the
        model needs to know a call failed and roughly why, and a long stack trace
        crowds out the work that did succeed.
        """
        text = body or ""
        return cls(tool=tool, outcome=(text[:1000] if ok else f"FAILED: {text[:500]}"))


@dataclass(frozen=True)
class ResumedStep:
    """The call Tee confirmed, plus the work that led up to it.

    Handed in by the transport after it has spent a stored confirmation handle.
    Nothing here is taken from the request body: `tool` and `arguments` are what
    the loop itself proposed and the server remembered, which is what stops a
    confirmation from becoming a way to name an arbitrary tool call.
    """

    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    observations: List[Observation] = field(default_factory=list)
    spent: Dict[str, int] = field(default_factory=dict)
    """What the per-turn tool budget had already consumed before the question.

    Without this the budget resets on resume and is not a per-turn budget at
    all: consult, propose something irreversible, say yes, consult again. Two
    panels under one turn id, and nothing in the stream showing it."""
    steps_used: int = 0
    """Tool calls already made this turn, so resuming does not grant a fresh
    allowance on top of the one already spent."""


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
        resume: Optional[ResumedStep] = None,
    ) -> AsyncIterator[TurnEvent]:
        clean = (message or "").strip()
        if not clean:
            yield TurnEvent("error", {"message": "empty message"})
            return

        observations: List[Observation] = list(resume.observations) if resume else []
        spent: Dict[str, int] = dict(resume.spent) if resume else {}
        steps_used = resume.steps_used if resume else 0
        system = self._system(caller)

        yield TurnEvent("turn_started", {"turn_id": self.executor.turn_id})

        if resume is not None:
            # Tee answered a question. Do the thing he answered, and nothing
            # else: the steps before it already ran, and their results are
            # carried in `observations` rather than earned a second time.
            yield TurnEvent(
                "turn_resumed",
                {"turn_id": self.executor.turn_id, "tool": resume.tool},
            )
            token = confirm_binding(
                turn_id=self.executor.turn_id,
                tool_name=resume.tool,
                arguments=resume.arguments,
            )
            try:
                outcome = await self.executor.run_step(
                    resume.tool,
                    resume.arguments,
                    caller=caller,
                    halt=halt,
                    step_id=self._step_id(observations),
                    confirmed_token=token,
                )
            except Halted as stop:
                yield TurnEvent("halted", {"reason": stop.reason})
                return
            except KeyError:
                yield TurnEvent(
                    "error",
                    {"message": "the confirmed tool is no longer registered"},
                )
                return

            # Deliberately NOT counted again. The main loop charges a step when
            # a tool call is proposed, and this call was proposed on the leg that
            # stopped to ask -- `resume.steps_used` already includes it. Charging
            # it a second time would quietly cost the resumed turn a step it had
            # not spent.
            events, stop_here = self._absorb(outcome, observations, spent, steps_used)
            for event in events:
                yield event
            if stop_here:
                return

        remaining = max(0, self.max_steps - steps_used)
        for _step in range(remaining):
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

            budget = PER_TURN_TOOL_BUDGET.get(tool_name)
            if budget is not None:
                used = spent.get(tool_name, 0)
                if used >= budget:
                    detail = (
                        f"{tool_name} has already been used {used} time(s) this "
                        f"turn, which is its limit; answer from what you have or "
                        "use a cheaper tool"
                    )
                    yield TurnEvent(
                        "tool_capped", {"tool": tool_name, "limit": budget, "detail": detail}
                    )
                    observations.append(Observation(tool=tool_name, outcome=detail))
                    continue
                spent[tool_name] = used + 1

            steps_used += 1
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
                    step_id=self._step_id(observations),
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

            events, stop_here = self._absorb(outcome, observations, spent, steps_used)
            for event in events:
                yield event
            if stop_here:
                return

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

    @staticmethod
    def _step_id(observations: Sequence[Observation]) -> str:
        """A stable identity for the step about to run.

        Numbered from the work already done, so a resumed turn keeps counting
        where it left off instead of restarting at one. The approval binding
        includes this, which is what stops two identical calls in one turn from
        sharing a single authorisation.
        """
        return f"STEP-{len(observations) + 1:02d}"

    def _absorb(
        self,
        outcome: StepOutcome,
        observations: List[Observation],
        spent: Dict[str, int],
        steps_used: int,
    ) -> tuple:
        """Turn one step outcome into events, and say whether the turn ends here.

        Pure: it appends to `observations` and returns events for the caller to
        yield. Keeping it out of the generator is what lets the first step of a
        resumed turn and the Nth step of a fresh one share exactly one code path.
        """
        events: List[TurnEvent] = []

        if outcome.awaiting_confirmation:
            events.append(
                TurnEvent(
                    "needs_confirmation",
                    {
                        "turn_id": self.executor.turn_id,
                        "tool": outcome.tool,
                        "arguments": outcome.arguments,
                        "detail": outcome.detail,
                        # Carried so the transport can remember the question
                        # exactly as asked, without reconstructing it from the
                        # events it happened to forward. The counters ride along
                        # for the same reason: a budget the resume does not
                        # inherit is not a per-turn budget.
                        "observations": [obs.to_dict() for obs in observations],
                        "spent": dict(spent),
                        "steps_used": steps_used,
                    },
                )
            )
            return events, True

        if outcome.decision is PresenceDecision.REFUSE:
            events.append(
                TurnEvent("refused", {"tool": outcome.tool, "detail": outcome.detail})
            )
            # The turn continues after a refusal, so what the model is told here
            # decides whether it can correct itself. A fixed "blocked by policy"
            # was fine while refusal only ever meant a BLOCKED tool; it is not
            # fine now that a malformed argument list also lands here, because
            # the model would retry the same call or abandon a task it could
            # have fixed by renaming one key.
            observations.append(
                Observation(
                    tool=outcome.tool,
                    outcome=f"refused: {outcome.detail or 'blocked by policy'}",
                )
            )
            return events, False

        if outcome.decision is PresenceDecision.CARD:
            events.append(
                TurnEvent("card_required", {"tool": outcome.tool, "detail": outcome.detail})
            )
            return events, True

        result = outcome.result
        ok = bool(result and result.ok)
        body = (result.output if result else "") or (result.error if result else "")
        data: Dict[str, Any] = {
            "tool": outcome.tool,
            "ok": ok,
            "output": (body or "")[:2000],
        }
        if outcome.approval_request_id:
            # The receipt half of presence authority: every effect names the row
            # that authorised it, in the stream, while Tee is watching.
            data["approval_request_id"] = outcome.approval_request_id
        events.append(TurnEvent("tool_result", data))
        observations.append(Observation.from_result(outcome.tool, ok, body or ""))
        return events, False

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
