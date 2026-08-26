"""Executing one tool call inside a live conversation.

This is the seam where Tee's ruling of 2026-08-26 becomes behaviour: presence
decides, the brake can stop the next effect, and a confirmation is bound to the
exact action it answered.

The confirmation binding is the part worth reading twice. "Yes" is the most
dangerous word in a conversational agent, because between DEVON asking and Tee
answering the plan can move: a re-plan, a race, a second turn, a model that
re-reads its own transcript and proposes something adjacent. A bare yes would
land on whatever is queued at that moment. So a confirmation carries a token
computed from the turn, the tool, and the arguments -- the same SHA-256 shape
the approval queue already uses for its cards -- and a token that does not match
the action about to run is refused. Tee's yes approves the thing he was shown,
or it approves nothing.
"""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.agent_runtime.halt import Halted, HaltSignal
from services.agent_runtime.presence import Caller, PresenceDecision, decide
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec

CONFIRM_BINDING_PREFIX = "DEVON-PRESENCE-CONFIRM:"


def confirm_binding(
    *,
    turn_id: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> str:
    """The token a confirmation must carry to count.

    Canonical JSON so argument ordering cannot change the token, and the turn id
    so a yes cannot be replayed into a later turn.
    """
    payload = {
        "turn_id": turn_id,
        "tool": tool_name,
        "arguments": arguments,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StepOutcome:
    """What happened to one tool call, and why."""

    tool: str
    decision: PresenceDecision
    ran: bool
    result: Optional[ToolResult] = None
    detail: str = ""
    confirm_token: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "decision": self.decision.value,
            "ran": self.ran,
            "result": self.result.to_dict() if self.result else None,
            "detail": self.detail,
            "confirm_token": self.confirm_token,
        }


class PresenceExecutor:
    """Runs one tool call under presence authority.

    Deliberately does not ask anything itself. When a call needs confirming it
    returns a CONFIRM outcome carrying the token, and the conversation surfaces
    the question and carries the answer back. Keeping the asking outside means
    this object never blocks, never owns a transport, and stays testable without
    one.
    """

    def __init__(
        self,
        tools: ToolRegistry,
        *,
        turn_id: str,
    ) -> None:
        self.tools = tools
        self.turn_id = (turn_id or "").strip()
        if not self.turn_id:
            raise ValueError("turn id is required: confirmations are bound to it")

    async def run_step(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        caller: Caller,
        halt: HaltSignal,
        confirmed_token: str = "",
    ) -> StepOutcome:
        args = dict(arguments or {})
        spec: ToolSpec = self.tools.require(tool_name)
        verdict = decide(spec, caller)
        token = confirm_binding(
            turn_id=self.turn_id, tool_name=spec.name, arguments=args
        )

        if verdict is PresenceDecision.REFUSE:
            return StepOutcome(
                tool=spec.name,
                decision=verdict,
                ran=False,
                detail=f"{spec.name} is blocked; no authority reaches it",
                arguments=args,
            )

        if verdict is PresenceDecision.CARD:
            return StepOutcome(
                tool=spec.name,
                decision=verdict,
                ran=False,
                detail=(
                    f"{spec.name} needs a ruling and nobody is present; "
                    "raise the approval card"
                ),
                arguments=args,
            )

        if verdict is PresenceDecision.CONFIRM:
            supplied = (confirmed_token or "").strip()
            if not supplied:
                return StepOutcome(
                    tool=spec.name,
                    decision=verdict,
                    ran=False,
                    detail=f"{spec.name} cannot be walked back; confirm to run it",
                    confirm_token=token,
                    arguments=args,
                )
            if not hmac.compare_digest(supplied, token):
                # A yes that does not match what was shown approves nothing.
                return StepOutcome(
                    tool=spec.name,
                    decision=verdict,
                    ran=False,
                    detail=(
                        "confirmation does not match this action; "
                        "it was given for something else"
                    ),
                    confirm_token=token,
                    arguments=args,
                )

        # Everything below this line is about to have an effect. The brake is
        # checked here, immediately before execution, so a halt that arrived
        # while a previous slow tool was running still stops this one.
        halt.check()

        result = await self._invoke(spec, args)
        return StepOutcome(
            tool=spec.name,
            decision=verdict,
            ran=True,
            result=result,
            detail="ran" if result.ok else (result.error or "tool reported failure"),
            arguments=args,
        )

    async def _invoke(self, spec: ToolSpec, args: Dict[str, Any]) -> ToolResult:
        """Call the handler, sync or async, and normalise whatever it returns.

        A handler that raises becomes a failed ToolResult rather than an
        exception: one bad adapter should end its own step, not the conversation.
        Halted is re-raised untouched -- a stop Tee asked for is not a tool
        failure and must not be reported as one.
        """
        try:
            outcome = spec.handler(args)
            if inspect.isawaitable(outcome):
                outcome = await outcome
        except Halted:
            raise
        except Exception as exc:  # noqa: BLE001 - one adapter cannot end the turn
            return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")

        if isinstance(outcome, ToolResult):
            return outcome
        if outcome is None:
            return ToolResult(ok=True, output="")
        if isinstance(outcome, str):
            return ToolResult(ok=True, output=outcome)
        if isinstance(outcome, dict):
            return ToolResult(ok=True, output="", metadata=dict(outcome))
        return ToolResult(ok=True, output=str(outcome))
