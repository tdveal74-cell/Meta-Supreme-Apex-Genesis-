"""
Mock AI provider — deterministic, keyless, zero-cost.

Purpose
-------
- Lets the entire platform run end-to-end (development, CI, demos) with no
  API keys and no network access.
- Produces *clearly labeled* simulated output. It never pretends to be real
  intelligence: every response carries `provider="mock"` so the API and UI
  can surface "simulated" transparently.

Behavior
--------
- Deterministic: identical requests produce identical responses.
- If the prompt declares a structured contract via the line
  `REQUIRED_JSON_KEYS: key1, key2, ...` (the convention used by the agent
  executor and synthesizer), the mock returns a JSON object with exactly
  those keys and plausible deterministic values.
- Tests may inject a custom `responder` for full control.
"""

from __future__ import annotations

import json
import re
from typing import Callable, List, Optional

from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)

# Machine-readable contract marker shared with prompt builders.
REQUIRED_KEYS_MARKER = "REQUIRED_JSON_KEYS:"

# Keys are declared on a single line; match must not spill past the newline.
_KEYS_RE = re.compile(re.escape(REQUIRED_KEYS_MARKER) + r"[ \t]*([a-zA-Z0-9_, \t]+)")

# Keys that should be numeric / list-valued for a realistic shape.
_NUMERIC_KEYS = {"confidence", "strength_of_claim", "severity"}
_LIST_HINTS = (
    "s",  # plural heuristic fallback, checked last
)
_ALWAYS_LIST_KEYS = {
    "implications", "findings", "patterns", "gaps", "options", "tradeoffs",
    "risks", "mitigations", "steps", "dependencies", "recommendations",
    "assumptions", "challenges", "alternatives", "key_points", "connections",
    "retrieval_tips", "tech_choices", "recommended_actions", "agents_consulted",
    "points_of_agreement", "points_of_tension", "scalability_notes",
}


def _topic_of(request: CompletionRequest) -> str:
    """Derive a short deterministic topic string from the last user message."""
    for message in reversed(request.messages):
        if message.role == "user" and message.content.strip():
            topic = " ".join(message.content.split())
            return topic[:96] + ("…" if len(topic) > 96 else "")
    return "the current request"


def _declared_keys(request: CompletionRequest) -> Optional[List[str]]:
    """Find a REQUIRED_JSON_KEYS contract in the system prompt or messages."""
    corpus = (request.system or "") + "\n" + "\n".join(m.content for m in request.messages)
    match = _KEYS_RE.search(corpus)
    if not match:
        return None
    keys = [k.strip() for k in match.group(1).split(",") if k.strip()]
    return keys or None


def _value_for(key: str, topic: str) -> object:
    if key in _NUMERIC_KEYS:
        return 0.6
    if key in _ALWAYS_LIST_KEYS:
        return [
            f"Simulated {key.replace('_', ' ')} item 1 for: {topic}",
            f"Simulated {key.replace('_', ' ')} item 2 for: {topic}",
        ]
    return f"Simulated {key.replace('_', ' ')} for: {topic}"


class MockProvider(AIProvider):
    """Deterministic offline provider for development and tests."""

    name = "mock"

    def __init__(
        self,
        *,
        default_model: str = "mock-council-v1",
        timeout_seconds: float = 5.0,
        max_retries: int = 0,
        responder: Optional[Callable[[CompletionRequest], str]] = None,
    ) -> None:
        super().__init__(
            default_model=default_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self._responder = responder

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        if self._responder is not None:
            text = self._responder(request)
        else:
            text = self._default_response(request)

        input_chars = len(request.system or "") + sum(len(m.content) for m in request.messages)
        usage = TokenUsage(
            input_tokens=max(1, input_chars // 4),
            output_tokens=max(1, len(text) // 4),
        )
        return CompletionResponse(
            text=text,
            usage=usage,
            model=self.resolve_model(request),
            provider=self.name,
            finish_reason="stop",
        )

    def _default_response(self, request: CompletionRequest) -> str:
        topic = _topic_of(request)
        keys = _declared_keys(request)

        if request.json_mode and request.metadata.get("component") == "devon-agent-planner":
            planned = self._planner_response(request)
            if planned is not None:
                return planned

        if request.json_mode and request.metadata.get("component") == "devon-agent-turn":
            return self._turn_response(request)

        if request.json_mode and keys:
            payload = {key: _value_for(key, topic) for key in keys}
            return json.dumps(payload, ensure_ascii=False)

        if request.json_mode:
            return json.dumps(
                {"response": f"Simulated response for: {topic}", "confidence": 0.6},
                ensure_ascii=False,
            )

        return (
            f"Simulated response for: {topic}\n\n"
            "This output was produced by the offline mock provider. Configure a "
            "real AI provider (Anthropic or OpenAI) to receive live intelligence."
        )

    @staticmethod
    def _turn_response(request: CompletionRequest) -> str:
        """An answer in the conversational turn's contract.

        Without this the mock replies in its generic
        `{"response": ..., "confidence": ...}` shape, which carries neither
        `say` nor `tool` -- so every turn under the offline provider ended on
        "DEVON replied with neither words nor an action" and the whole
        conversational surface was dead in CI and in any mock deployment.

        Deliberately always an answer and never a tool call. A provider that
        invents effects because it is offline is a far worse failure than one
        that declines to act, and the tool paths are exercised by tests that
        script a provider on purpose.
        """
        return json.dumps(
            {
                "say": (
                    f"Simulated answer for: {_topic_of(request)}. This is the "
                    "offline mock provider; configure a real AI provider to get "
                    "live intelligence."
                )
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _planner_response(request: CompletionRequest) -> Optional[str]:
        """A valid single-step plan for the DEVON agent planner.

        The planner validates tool names against its registry, so the step must
        name a tool from the request's own catalog. Prefers a read tool; never
        selects a blocked one. Returns None when the payload is not the
        planner's contract so the generic shape still answers.
        """
        try:
            payload = json.loads(request.messages[-1].content)
            catalog = payload["tools"]
            goal = str(payload.get("goal") or "the goal")
        except (ValueError, KeyError, IndexError, TypeError):
            return None
        usable = [t for t in catalog if t.get("risk") != "blocked" and t.get("name")]
        if not usable:
            return None
        tool = next((t for t in usable if t.get("risk") == "read"), usable[0])
        return json.dumps(
            {
                "steps": [
                    {
                        "title": f"Simulated step for: {goal[:80]}",
                        "tool": tool["name"],
                        "arguments": {},
                        "reason": "offline mock plan",
                        "expected_outcome": "deterministic mock observation",
                    }
                ],
                "completion_criteria": ["mock step executed"],
            },
            ensure_ascii=False,
        )
