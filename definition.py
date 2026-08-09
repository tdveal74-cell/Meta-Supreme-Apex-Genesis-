"""
Workflow definitions — parse, validate, and classify.

A workflow is a trigger plus an ordered list of steps, stored as JSONB in
`workflows.definition`:

    {
      "version": 1,
      "trigger": {"type": "manual", "config": {}},
      "steps": [
        {"id": "recall",  "type": "knowledge_search",
         "config": {"query": "{{ input }}", "limit": 6}},
        {"id": "council", "type": "council",
         "config": {"prompt": "Assess: {{ input }}\\nPrior material: {{ recall }}",
                    "full_council": true, "deliberate": true}},
        {"id": "remember", "type": "memory_write",
         "config": {"content": "{{ council }}", "importance": 6}},
        {"id": "draft",   "type": "decision_draft",
         "config": {"question": "{{ input }}", "recommendation": "{{ council }}"}}
      ]
    }

Two rules do the load-bearing work here:

1. **Reads flow, effects pause.** `knowledge_search` and `council` only read
   and reason, so they run unattended. `memory_write`, `decision_draft` and
   `export` change state or leave the system, so every run stops in front of
   them until a human approves (see `EFFECT_STEP_TYPES`).
2. **Templates can only look backwards.** `{{ input }}` and `{{ <earlier
   step id> }}` are the only references allowed; a forward or unknown
   reference is rejected at save time rather than resolving to nothing at
   run time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

DEFINITION_VERSION = 1
MAX_STEPS = 12

_STEP_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")

TRIGGER_INPUT_REF = "input"
_STEP_FIELDS = ("summary", "text")


class WorkflowDefinitionError(ValueError):
    """A definition is malformed. Raised at save time, never at run time."""


class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    EVENT = "event"


class StepType(str, Enum):
    KNOWLEDGE_SEARCH = "knowledge_search"
    COUNCIL = "council"
    MEMORY_WRITE = "memory_write"
    DECISION_DRAFT = "decision_draft"
    EXPORT = "export"


#: Steps that change state or leave the system. Every run pauses in front of
#: these for explicit human approval — the platform's core promise is that
#: automation never acts on the user's behalf without being told to.
EFFECT_STEP_TYPES = frozenset(
    {StepType.MEMORY_WRITE, StepType.DECISION_DRAFT, StepType.EXPORT}
)

#: Required non-empty string config keys per step type.
_REQUIRED_TEXT_CONFIG: Dict[StepType, str] = {
    StepType.KNOWLEDGE_SEARCH: "query",
    StepType.COUNCIL: "prompt",
    StepType.MEMORY_WRITE: "content",
    StepType.DECISION_DRAFT: "question",
    StepType.EXPORT: "title",
}


@dataclass(frozen=True)
class WorkflowTrigger:
    type: TriggerType
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def awaiting_dispatcher(self) -> bool:
        """
        True for triggers that describe automatic firing the platform cannot
        yet perform. Schedule and event triggers are stored and validated, but
        no scheduler or event bus dispatches them — runs are started by a
        human until that lands. Reported honestly through the API.
        """
        return self.type is not TriggerType.MANUAL

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type.value, "config": dict(self.config)}


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    type: StepType
    config: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_effect(self) -> bool:
        return self.type in EFFECT_STEP_TYPES

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "type": self.type.value, "config": dict(self.config)}


@dataclass(frozen=True)
class WorkflowDefinition:
    trigger: WorkflowTrigger
    steps: List[WorkflowStep]
    version: int = DEFINITION_VERSION

    @property
    def effect_steps(self) -> List[WorkflowStep]:
        return [s for s in self.steps if s.is_effect]

    def step(self, step_id: str) -> Optional[WorkflowStep]:
        return next((s for s in self.steps if s.id == step_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "trigger": self.trigger.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(
        cls, raw: Any, *, max_steps: int = MAX_STEPS
    ) -> "WorkflowDefinition":
        """Validate and parse a stored/incoming definition. Raises on any defect."""
        if not isinstance(raw, Mapping):
            raise WorkflowDefinitionError("Definition must be an object")

        version = raw.get("version", DEFINITION_VERSION)
        if version != DEFINITION_VERSION:
            raise WorkflowDefinitionError(
                f"Unsupported definition version {version!r} "
                f"(this build understands {DEFINITION_VERSION})"
            )

        trigger = _parse_trigger(raw.get("trigger"))
        steps = _parse_steps(raw.get("steps"), max_steps=max_steps)
        _validate_references(steps)
        return cls(trigger=trigger, steps=steps, version=DEFINITION_VERSION)

    @classmethod
    def empty(cls) -> "WorkflowDefinition":
        """A draft skeleton: manual trigger, no steps (never runnable)."""
        return cls(trigger=WorkflowTrigger(TriggerType.MANUAL), steps=[])


def _parse_trigger(raw: Any) -> WorkflowTrigger:
    if raw is None:
        return WorkflowTrigger(TriggerType.MANUAL)
    if not isinstance(raw, Mapping):
        raise WorkflowDefinitionError("Trigger must be an object")

    raw_type = raw.get("type", TriggerType.MANUAL.value)
    try:
        trigger_type = TriggerType(raw_type)
    except ValueError:
        allowed = ", ".join(t.value for t in TriggerType)
        raise WorkflowDefinitionError(
            f"Unknown trigger type {raw_type!r} (expected one of: {allowed})"
        ) from None

    config = raw.get("config") or {}
    if not isinstance(config, Mapping):
        raise WorkflowDefinitionError("Trigger config must be an object")

    if trigger_type is TriggerType.SCHEDULE and not str(config.get("cadence", "")).strip():
        raise WorkflowDefinitionError("Schedule triggers need a `cadence` in config")
    if trigger_type is TriggerType.EVENT and not str(config.get("event", "")).strip():
        raise WorkflowDefinitionError("Event triggers need an `event` name in config")

    return WorkflowTrigger(type=trigger_type, config=dict(config))


def _parse_steps(raw: Any, *, max_steps: int) -> List[WorkflowStep]:
    if raw is None:
        return []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise WorkflowDefinitionError("Steps must be a list")
    if len(raw) > max_steps:
        raise WorkflowDefinitionError(
            f"A workflow may hold at most {max_steps} steps (got {len(raw)})"
        )

    steps: List[WorkflowStep] = []
    seen: set = set()
    for position, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise WorkflowDefinitionError(f"Step {position + 1} must be an object")

        step_id = str(entry.get("id", "")).strip()
        if not _STEP_ID_RE.match(step_id):
            raise WorkflowDefinitionError(
                f"Step {position + 1} needs an id matching [a-z][a-z0-9_]* "
                f"(got {step_id!r})"
            )
        if step_id in seen:
            raise WorkflowDefinitionError(f"Duplicate step id {step_id!r}")
        seen.add(step_id)

        raw_type = entry.get("type")
        try:
            step_type = StepType(raw_type)
        except ValueError:
            allowed = ", ".join(t.value for t in StepType)
            raise WorkflowDefinitionError(
                f"Step {step_id!r}: unknown type {raw_type!r} "
                f"(expected one of: {allowed})"
            ) from None

        config = entry.get("config") or {}
        if not isinstance(config, Mapping):
            raise WorkflowDefinitionError(f"Step {step_id!r}: config must be an object")

        required = _REQUIRED_TEXT_CONFIG[step_type]
        if not str(config.get(required, "")).strip():
            raise WorkflowDefinitionError(
                f"Step {step_id!r} ({step_type.value}) requires a non-empty "
                f"`{required}`"
            )
        _validate_step_config(step_id, step_type, config)
        steps.append(WorkflowStep(id=step_id, type=step_type, config=dict(config)))

    return steps


def _validate_step_config(
    step_id: str, step_type: StepType, config: Mapping[str, Any]
) -> None:
    if step_type is StepType.KNOWLEDGE_SEARCH:
        limit = config.get("limit", 5)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
            raise WorkflowDefinitionError(
                f"Step {step_id!r}: `limit` must be an integer between 1 and 20"
            )

    elif step_type is StepType.COUNCIL:
        agents = config.get("agents", [])
        if not isinstance(agents, Sequence) or isinstance(agents, (str, bytes)):
            raise WorkflowDefinitionError(f"Step {step_id!r}: `agents` must be a list")
        if not all(isinstance(a, str) and a.strip() for a in agents):
            raise WorkflowDefinitionError(
                f"Step {step_id!r}: `agents` must contain agent slugs"
            )
        for flag in ("full_council", "deliberate"):
            if flag in config and not isinstance(config[flag], bool):
                raise WorkflowDefinitionError(
                    f"Step {step_id!r}: `{flag}` must be true or false"
                )

    elif step_type is StepType.MEMORY_WRITE:
        importance = config.get("importance", 5)
        if (
            not isinstance(importance, int)
            or isinstance(importance, bool)
            or not 1 <= importance <= 10
        ):
            raise WorkflowDefinitionError(
                f"Step {step_id!r}: `importance` must be an integer between 1 and 10"
            )
        memory_type = config.get("memory_type", "context")
        if memory_type not in {
            "preference",
            "context",
            "decision",
            "lesson",
            "pattern",
            "other",
        }:
            raise WorkflowDefinitionError(
                f"Step {step_id!r}: unsupported memory_type {memory_type!r}"
            )

    elif step_type is StepType.DECISION_DRAFT:
        options = config.get("options", [])
        if not isinstance(options, Sequence) or isinstance(options, (str, bytes)):
            raise WorkflowDefinitionError(f"Step {step_id!r}: `options` must be a list")
        if len(options) > 20:
            raise WorkflowDefinitionError(
                f"Step {step_id!r}: at most 20 options may be drafted"
            )


def _validate_references(steps: Sequence[WorkflowStep]) -> None:
    """
    Every `{{ … }}` reference must resolve to the trigger input or to an
    *earlier* step. Caught here so a workflow cannot be saved with a
    placeholder that would silently render as nothing.
    """
    available: set = {TRIGGER_INPUT_REF}
    for step in steps:
        for reference in _references_in(step.config):
            head, _, tail = reference.partition(".")
            if head not in available:
                raise WorkflowDefinitionError(
                    f"Step {step.id!r} references {{{{ {reference} }}}}, which is "
                    f"not available yet — reference `input` or an earlier step id"
                )
            if tail and tail not in _STEP_FIELDS:
                raise WorkflowDefinitionError(
                    f"Step {step.id!r}: unknown field {tail!r} on {head!r} "
                    f"(expected one of: {', '.join(_STEP_FIELDS)})"
                )
            if tail and head == TRIGGER_INPUT_REF:
                raise WorkflowDefinitionError(
                    f"Step {step.id!r}: `input` has no fields — use {{{{ input }}}}"
                )
        available.add(step.id)


def _references_in(value: Any) -> List[str]:
    if isinstance(value, str):
        return _PLACEHOLDER_RE.findall(value)
    if isinstance(value, Mapping):
        found: List[str] = []
        for nested in value.values():
            found.extend(_references_in(nested))
        return found
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        found = []
        for nested in value:
            found.extend(_references_in(nested))
        return found
    return []


def render_template(
    value: Any,
    *,
    trigger_input: str = "",
    results: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Any:
    """
    Substitute `{{ input }}` / `{{ step_id[.summary|.text] }}` throughout a
    config value (strings, lists, and nested objects). Unresolved references
    render as an empty string — validation at save time is what prevents them
    from occurring.
    """
    results = results or {}

    if isinstance(value, str):

        def _substitute(match: "re.Match[str]") -> str:
            head, _, tail = match.group(1).partition(".")
            if head == TRIGGER_INPUT_REF:
                return trigger_input
            record = results.get(head) or {}
            return str(record.get(tail or "summary", "") or "")

        return _PLACEHOLDER_RE.sub(_substitute, value)

    if isinstance(value, Mapping):
        return {
            key: render_template(nested, trigger_input=trigger_input, results=results)
            for key, nested in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            render_template(nested, trigger_input=trigger_input, results=results)
            for nested in value
        ]

    return value
