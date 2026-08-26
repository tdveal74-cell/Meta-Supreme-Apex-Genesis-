"""
Synthesizer — combines Council contributions into one clear response.

Synthesis priority order (fixed, from the platform blueprint):
    1. Accuracy
    2. Strategic value
    3. Practical execution
    4. Risk awareness
    5. User objectives

Transparency rules:
- Disagreements between agents are surfaced, never averaged away.
- If model-driven synthesis fails, a deterministic structured fallback
  assembles the agents' actual outputs verbatim — clearly flagged with
  synthesis_mode="fallback". Nothing is ever fabricated.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, List

from services.agents.executor import AgentResult
from services.intelligence.providers import (
    REQUIRED_KEYS_MARKER,
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderError,
    extract_json,
)

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM = (
    "You are the synthesis layer of an Intelligence Operating System. "
    "Several specialized Council agents have analyzed the user's request. "
    "Your job is to combine their contributions into one clear, useful "
    "response for a human decision-maker.\n\n"
    "Synthesis priority order (strict):\n"
    "1. Accuracy — never state something the contributions do not support.\n"
    "2. Strategic value — what matters most for the user's goals.\n"
    "3. Practical execution — what the user can actually do next.\n"
    "4. Risk awareness — what could go wrong, proportionally stated.\n"
    "5. User objectives — framed around what the user is trying to achieve.\n\n"
    "Rules:\n"
    "- Surface disagreements between agents explicitly; never average them away.\n"
    "- Recommend; do not decide. The human makes the final decision.\n"
    "- Plain language, calm tone, no hype, no filler.\n"
    "- If the contributions are weak or incomplete, say so honestly.\n\n"
    "--- Output contract ---\n"
    "Respond with a single JSON object containing exactly these keys.\n"
    f"{REQUIRED_KEYS_MARKER} response, recommended_actions, points_of_agreement, "
    "points_of_tension, confidence\n"
    "- response: the synthesized answer (markdown allowed, no headings deeper than ###)\n"
    "- recommended_actions: JSON array of concrete next steps (may be empty)\n"
    "- points_of_agreement: JSON array — where agents converged\n"
    "- points_of_tension: JSON array — where agents disagreed or flagged risk\n"
    "- confidence: number 0-1 reflecting overall evidence strength\n"
    "- No markdown fences, no text outside the JSON object."
)


@dataclass
class SynthesisOutput:
    """Result of the synthesis stage."""

    response: str
    recommended_actions: List[str] = field(default_factory=list)
    points_of_agreement: List[str] = field(default_factory=list)
    points_of_tension: List[str] = field(default_factory=list)
    confidence: float = 0.0
    synthesis_mode: str = "model"  # "model" | "fallback"
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""


class Synthesizer:
    """Produces the final Council response from individual contributions."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        max_tokens: int = 2000,
        temperature: float = 0.2,
        model: str | None = None,  # synthesis-tier override; None → provider default
        persona: str = "",  # optional voice; applies to the response text only
    ):
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.model = model
        self.persona = (persona or "").strip()

    def _system_prompt(self) -> str:
        if not self.persona:
            return _SYNTHESIS_SYSTEM
        # The persona shapes voice, never substance: it is appended after the
        # contract so the accuracy rules and required JSON keys stay intact.
        return (
            _SYNTHESIS_SYSTEM
            + "\n\nVoice (apply to the `response` text only; never weaken the "
            "accuracy rules or alter the JSON contract):\n"
            + self.persona
        )

    async def synthesize(
        self,
        *,
        message: str,
        intent: str,
        results: List[AgentResult],
    ) -> SynthesisOutput:
        completed = [r for r in results if r.status == "completed" and r.content]
        failed = [r for r in results if r.status != "completed"]

        request = CompletionRequest(
            system=self._system_prompt(),
            messages=[
                ChatMessage(role="user", content=self._build_prompt(message, intent, completed, failed))
            ],
            model=self.model,  # None → provider default
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            json_mode=True,
            metadata={"stage": "synthesis"},
        )

        try:
            response = await self.provider.complete(request)
            parsed = extract_json(response.text)
            return SynthesisOutput(
                response=str(parsed.get("response", "")).strip()
                or self._fallback_text(completed, failed),
                recommended_actions=_as_str_list(parsed.get("recommended_actions")),
                points_of_agreement=_as_str_list(parsed.get("points_of_agreement")),
                points_of_tension=_as_str_list(parsed.get("points_of_tension")),
                confidence=_clamp(parsed.get("confidence")),
                synthesis_mode="model",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=response.model,
                provider=response.provider,
            )
        except (ProviderError, ValueError) as exc:
            logger.error("synthesis failed, using structured fallback: %s", exc)
            return self._fallback(completed, failed)

    # ------------------------------------------------------------------ #

    def _build_prompt(
        self,
        message: str,
        intent: str,
        completed: List[AgentResult],
        failed: List[AgentResult],
    ) -> str:
        contributions = [
            {
                "agent": r.agent_slug,
                "confidence": r.confidence,
                "contribution": r.content,
            }
            for r in completed
        ]
        sections = [
            f"User request:\n{message}",
            f"Detected intent: {intent}",
            "Council contributions (JSON):\n"
            + json.dumps(contributions, ensure_ascii=False, indent=2),
        ]
        if failed:
            sections.append(
                "Agents that failed to contribute (be transparent about this "
                "if it weakens the answer): "
                + ", ".join(f"{r.agent_slug} ({r.error})" for r in failed)
            )
        return "\n\n".join(sections)

    def _fallback(
        self, completed: List[AgentResult], failed: List[AgentResult]
    ) -> SynthesisOutput:
        """Deterministic assembly of real agent outputs. Never fabricates."""
        confidences = [r.confidence for r in completed] or [0.0]
        return SynthesisOutput(
            response=self._fallback_text(completed, failed),
            recommended_actions=[],
            points_of_agreement=[],
            points_of_tension=[],
            confidence=min(confidences),
            synthesis_mode="fallback",
            provider=self.provider.name,
        )

    @staticmethod
    def _fallback_text(completed: List[AgentResult], failed: List[AgentResult]) -> str:
        if not completed:
            return (
                "The Council could not produce a synthesized response for this "
                "request. No agent contributions were available."
            )
        parts = [
            "Model-driven synthesis was unavailable for this request. "
            "Below are the individual Council contributions, unmodified:"
        ]
        for r in completed:
            parts.append(
                f"\n### {r.agent_name} (confidence {r.confidence:.0%})\n"
                + json.dumps(r.content, ensure_ascii=False, indent=2)
            )
        if failed:
            parts.append(
                "\nAgents unable to contribute: "
                + ", ".join(r.agent_slug for r in failed)
            )
        return "\n".join(parts)


def _as_str_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
