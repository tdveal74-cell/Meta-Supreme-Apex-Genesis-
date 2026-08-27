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

Two things an adversarial pass on 2026-08-26 forced into this file.

First, the binding alone was never enough at the capability boundary. DEVON's
real tools -- github, the operator shell -- do not trust runtime metadata; each
one recomputes the binding and then demands an APPROVED approval-queue record
raised by the runtime. Presence supplied none, so every genuine write returned
"runtime approval metadata is missing" and the whole presence path executed
reads and nothing else. The fix is not to teach the adapters a second way in.
It is to make presence produce the thing they already check: when a present
human's authority rules an effect may run, this executor RAISES the card and
rules on it in the same breath, server side, with the same binding the adapter
will recompute. One door, and every effect leaves a queue row behind it. That is
the receipt half of Tee's ruling, kept honestly rather than asserted.

Second, arguments arrive from a model. Anything the model writes into them is
model output, including a forged `_devon_runtime_approval` block, so the key is
stripped on the way in before anything looks at it. A tool call cannot carry its
own permission slip.
"""

from __future__ import annotations

import hashlib
import hmac
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.halt import Halted, HaltSignal
from services.agent_runtime.presence import (
    Caller,
    PresenceDecision,
    confirm_reason,
    decide,
)
from services.agent_runtime.tools import (
    ToolRegistry,
    ToolResult,
    ToolSpec,
    unknown_argument_error,
    unknown_arguments,
)
from services.devon.approval import ApprovalQueue

CONFIRM_BINDING_PREFIX = "DEVON-PRESENCE-CONFIRM:"

MAX_ARGUMENT_DIGEST = 1200
"""How much of the arguments the approval row quotes. The row is a receipt a
human reads, not a payload store, and the binding -- which is computed over the
FULL arguments -- is what the capability boundary verifies."""

MAX_ARGUMENT_VALUE_DIGEST = 120
"""How much of any ONE argument value the row quotes.

The first cut of this quoted `repr(args)` and cut the whole string at a fixed
length. Argument order is the model's, preserved end to end from its own JSON,
so a long first value pushed every later key past the cut: a `github.write_file`
with 700 characters of `content` first produced a row that never said which
repository, path, or branch it wrote to. The binding still covered the full
arguments, so nothing unsafe ran, but the receipt a human reads afterwards
described the wrong thing by omission -- and a receipt that omits the target is
the failure this whole layer exists to prevent.

Per-value truncation with sorted keys fixes it: every key name survives, every
value is bounded, and the model cannot choose what gets dropped."""


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


def _argument_digest(args: Dict[str, Any]) -> str:
    """A row a human can act on, whatever the model put in the arguments.

    Keys sorted so the order is ours and not the model's, each value bounded
    separately so no single long value can crowd the others out, and the key
    names listed in full if the whole thing still has to be cut. The reader
    always learns WHICH fields were involved even when a value is elided.
    """
    if not args:
        return "{}"

    rendered = []
    for key in sorted(args, key=str):
        text = repr(args[key])
        if len(text) > MAX_ARGUMENT_VALUE_DIGEST:
            dropped = len(text) - MAX_ARGUMENT_VALUE_DIGEST
            text = f"{text[:MAX_ARGUMENT_VALUE_DIGEST]}... (+{dropped} chars)"
        rendered.append(f"{key!r}: {text}")

    digest = "{" + ", ".join(rendered) + "}"
    if len(digest) <= MAX_ARGUMENT_DIGEST:
        return digest
    names = ", ".join(repr(key) for key in sorted(args, key=str))
    return f"{digest[:MAX_ARGUMENT_DIGEST]}... (truncated; all keys: {names})"


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
    awaiting_confirmation: bool = False
    """This call stopped to ask, and is waiting on an answer.

    Stated rather than inferred from `decision is CONFIRM and not ran`. That
    inference was wrong for a confirmed call that then failed for some other
    reason -- it re-asked a question Tee had already answered.
    """
    approval_request_id: str = ""
    """The queue row this effect was authorised by, when there is one."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "decision": self.decision.value,
            "ran": self.ran,
            "result": self.result.to_dict() if self.result else None,
            "detail": self.detail,
            "confirm_token": self.confirm_token,
            "awaiting_confirmation": self.awaiting_confirmation,
            "approval_request_id": self.approval_request_id,
        }


class PresenceExecutor:
    """Runs one tool call under presence authority.

    Deliberately does not ask anything itself. When a call needs confirming it
    returns a CONFIRM outcome carrying the token, and the conversation surfaces
    the question and carries the answer back. Keeping the asking outside means
    this object never blocks, never owns a transport, and stays testable without
    one.

    `approvals` is what makes the difference between a demo and DEVON's actual
    tools. Without a queue this executor still runs reads and any adapter that
    does not check, which is exactly the shape the gauntlet caught pretending to
    work. With one, an effect that presence has ruled on gets a real APPROVED
    row bound to its exact arguments, which is what github, the operator shell,
    and every other guarded adapter verify independently before they act.
    """

    def __init__(
        self,
        tools: ToolRegistry,
        *,
        turn_id: str,
        approvals: Optional[ApprovalQueue] = None,
        actor: str = "",
    ) -> None:
        self.tools = tools
        self.turn_id = (turn_id or "").strip()
        if not self.turn_id:
            raise ValueError("turn id is required: confirmations are bound to it")
        self.approvals = approvals
        self.actor = (actor or "").strip()

    async def run_step(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        *,
        caller: Caller,
        halt: HaltSignal,
        step_id: str = "STEP-01",
        confirmed_token: str = "",
    ) -> StepOutcome:
        # Arguments come from a model. A `_devon_runtime_approval` block sitting
        # in them is model output wearing the shape of a permission slip, so it
        # is dropped before the decision, before the binding, and before the
        # handler -- never merged, never inspected.
        args = {
            key: value
            for key, value in dict(arguments or {}).items()
            if key != APPROVAL_METADATA_KEY
        }
        spec: ToolSpec = self.tools.require(tool_name)

        # Before the verdict, before the binding, before any row is minted. An
        # argument the adapter will not read must not appear on a card the human
        # reads, because the card would then describe an action the process is
        # not going to take.
        unknown = unknown_arguments(spec, args)
        if unknown:
            message = unknown_argument_error(spec, unknown)
            return StepOutcome(
                tool=spec.name,
                decision=PresenceDecision.REFUSE,
                ran=False,
                result=ToolResult(ok=False, error=message),
                detail=message,
                arguments=args,
            )

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
                    detail=(
                        f"{spec.name} {confirm_reason(spec)}; confirm to run it"
                    ),
                    confirm_token=token,
                    arguments=args,
                    awaiting_confirmation=True,
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
                    awaiting_confirmation=True,
                )

        # Checked here as well as immediately before the handler. A stop that
        # arrived while a previous slow tool was running should not first mint an
        # approval for an effect it is about to cancel: an APPROVED row for
        # something that never ran is a receipt for a lie.
        halt.check()

        # Presence has ruled. Record the ruling before acting on it, so the
        # capability boundary has something of its own to check and so the effect
        # leaves a row behind whatever happens next.
        execution_args = args
        request_id = ""
        if spec.approval_required:
            authorised, failure = self._authorise(spec, args, step_id=step_id)
            if failure is not None:
                return StepOutcome(
                    tool=spec.name,
                    decision=verdict,
                    ran=False,
                    result=failure,
                    detail=failure.error or "could not record this effect",
                    arguments=args,
                )
            execution_args, request_id = authorised

        # Immediately before execution, so a halt that landed during the
        # authorisation above still stops this one.
        halt.check()

        result = await self._invoke(spec, execution_args)
        return StepOutcome(
            tool=spec.name,
            decision=verdict,
            ran=True,
            result=result,
            detail="ran" if result.ok else (result.error or "tool reported failure"),
            arguments=args,
            approval_request_id=request_id,
        )

    def _authorise(
        self,
        spec: ToolSpec,
        args: Dict[str, Any],
        *,
        step_id: str,
    ) -> tuple:
        """Turn a presence ruling into the record the adapters already demand.

        The card is raised and decided here, server side, in one call stack. The
        single-use token never leaves this method: the human authority it stands
        for was established by the transport before the turn began, and re-asking
        for it in an inbox is precisely the friction Tee's ruling removed.

        What survives is the row -- APPROVED, attributed to the human who was
        present, carrying the binding marker over these exact arguments. That is
        both the receipt and the thing `require_approved_runtime_binding`
        recomputes independently a moment later.

        Returns (execution_arguments, request_id) or (None, failure). A queue
        that cannot record the effect fails the step: an effect DEVON cannot
        account for is one he does not run.
        """
        if self.approvals is None:
            return (
                None,
                ToolResult(
                    ok=False,
                    error=(
                        f"{spec.name} needs an approval record and this "
                        "conversation has no approval queue wired"
                    ),
                ),
            )

        clean_step = (step_id or "").strip() or "STEP-01"
        binding = approval_binding(
            task_id=self.turn_id,
            step_id=clean_step,
            tool_name=spec.name,
            arguments=args,
        )
        digest = _argument_digest(args)
        who = self.actor or "Tee"

        try:
            record, token = self.approvals.request(
                title=f"DEVON live turn: {spec.name}",
                what_happens=(
                    f"Run tool `{spec.name}` with arguments {digest} during live "
                    f"conversation turn `{self.turn_id}` ({clean_step}). "
                    f"Authorised by presence: {who} was in the conversation and "
                    f"asked for it. {approval_marker(binding)}"
                ),
                requested_by=RUNTIME_REQUESTED_BY,
                area="Conversation",
                reversible=spec.reversible,
                blast_radius=spec.blast_radius,
            )
            ruling = self.approvals.decide(
                record.request_id,
                token,
                "approve",
                decided_by=f"{who} (present)",
            )
        except Exception as exc:  # noqa: BLE001 - a queue outage stops the effect
            return (
                None,
                ToolResult(
                    ok=False,
                    error=(
                        f"could not record this effect, so it did not run: "
                        f"{type(exc).__name__}"
                    ),
                ),
            )

        if not ruling.approved:
            return (
                None,
                ToolResult(
                    ok=False,
                    error=f"the approval record did not take: {ruling.message}",
                ),
            )

        execution_args = dict(args)
        execution_args[APPROVAL_METADATA_KEY] = {
            "request_id": record.request_id,
            "binding": binding,
            "task_id": self.turn_id,
            "step_id": clean_step,
            "tool_name": spec.name,
        }
        return (execution_args, record.request_id), None

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
