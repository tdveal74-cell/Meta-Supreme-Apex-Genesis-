"""
Agent Executor — turns registry definitions into executable agents.

Given an AgentDefinition and a task, the executor builds the agent's prompt
(system instructions + council ground rules + declared output contract),
calls the configured AI provider, and validates that the output matches the
agent's declared `output_format`.

Honesty rules (non-negotiable):
- An agent that cannot produce valid structured output FAILS EXPLICITLY.
  The executor never fabricates content on the agent's behalf.
- Confidence is self-reported by the agent and clamped to [0, 1].
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.agents.registry import AgentDefinition
from services.intelligence.providers import (
    REQUIRED_KEYS_MARKER,
    AIProvider,
    ChatMessage,
    CompletionRequest,
    ProviderError,
    extract_json,
)

logger = logging.getLogger(__name__)

# Shared ground rules appended to every agent's system prompt.
_COUNCIL_GROUND_RULES = (
    "\n\n--- Council ground rules ---\n"
    "You are one voice on an AI Council inside an Intelligence Operating "
    "System. Other specialized agents will also analyze this request, and a "
    "synthesis step will combine all contributions.\n"
    "- Stay strictly within your role; do not answer for other agents.\n"
    "- Never invent facts. If information is missing, say so explicitly.\n"
    "- Flag uncertainty honestly. Overconfidence corrupts the synthesis.\n"
    "- Humans make the final decisions. You recommend; you never decide.\n"
    "- Be concise and information-dense. No filler, no hype."
)


@dataclass
class AgentTask:
    """Everything an agent needs to produce its contribution."""

    message: str
    intent: str = "general"
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    retrieved_knowledge: List[Dict[str, Any]] = field(default_factory=list)
    retrieved_memories: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Outcome of a single agent execution."""

    agent_slug: str
    agent_name: str
    status: str  # "completed" | "failed"
    content: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    model: str = ""
    provider: str = ""
    error: Optional[str] = None
    round: int = 1  # deliberation round that produced this result


class AgentExecutor:
    """Executes a single Council agent against the configured provider."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        history_limit: int = 10,
    ) -> None:
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.history_limit = history_limit

    # ------------------------------------------------------------------ #

    async def execute(
        self,
        agent: AgentDefinition,
        task: AgentTask,
        *,
        round_number: int = 1,
        peer_contributions: Optional[List[Dict[str, Any]]] = None,
        own_round1: Optional[Dict[str, Any]] = None,
    ) -> AgentResult:
        """
        Run one agent. Returns a completed or explicitly failed result.

        Round 2 (deliberation): `peer_contributions` carries the other
        agents' round-1 output and `own_round1` the agent's own, so the
        agent can revise with full Council context.
        """
        started = time.monotonic()
        user_prompt = self._build_user_prompt(
            agent,
            task,
            round_number=round_number,
            peer_contributions=peer_contributions,
            own_round1=own_round1,
        )
        request = CompletionRequest(
            system=self._build_system_prompt(agent),
            messages=[ChatMessage(role="user", content=user_prompt)],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            json_mode=True,
            metadata={"agent": agent.slug, "round": round_number},
        )

        try:
            response = await self.provider.complete(request)
        except ProviderError as exc:
            logger.error("agent=%s provider failure: %s", agent.slug, exc)
            return self._failed(agent, started, f"Provider error: {exc}")

        content, parse_error = self._parse_content(response.text)

        if content is None:
            # One corrective retry: ask the model to repair its own output.
            repair = CompletionRequest(
                system=request.system,
                messages=[
                    ChatMessage(role="user", content=user_prompt),
                    ChatMessage(role="assistant", content=response.text),
                    ChatMessage(
                        role="user",
                        content=(
                            "Your previous reply was not a valid JSON object "
                            f"({parse_error}). Reply again with ONLY the corrected "
                            "single JSON object, nothing else."
                        ),
                    ),
                ],
                max_tokens=self.max_tokens,
                temperature=0.0,
                json_mode=True,
                metadata={"agent": agent.slug, "repair": True, "round": round_number},
            )
            try:
                retry_response = await self.provider.complete(repair)
            except ProviderError as exc:
                return self._failed(
                    agent, started, f"Provider error on repair attempt: {exc}",
                    round_number=round_number,
                )

            content, parse_error = self._parse_content(retry_response.text)
            if content is None:
                return self._failed(
                    agent,
                    started,
                    f"Agent output did not match its declared format: {parse_error}",
                    input_tokens=response.usage.input_tokens + retry_response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens + retry_response.usage.output_tokens,
                    round_number=round_number,
                )
            response.usage.input_tokens += retry_response.usage.input_tokens
            response.usage.output_tokens += retry_response.usage.output_tokens

        confidence = _clamp_confidence(content.get("confidence"))
        return AgentResult(
            agent_slug=agent.slug,
            agent_name=agent.name,
            status="completed",
            content=content,
            confidence=confidence,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
            model=response.model,
            provider=response.provider,
            round=round_number,
        )

    # ------------------------------------------------------------------ #

    def _build_system_prompt(self, agent: AgentDefinition) -> str:
        fields = list(agent.output_format.get("fields", []))
        if "confidence" not in fields:
            fields.append("confidence")

        contract = (
            "\n\n--- Output contract ---\n"
            "Respond with a single JSON object containing exactly these keys.\n"
            f"{REQUIRED_KEYS_MARKER} {', '.join(fields)}\n"
            "- confidence: a number between 0 and 1 — your honest confidence "
            "in this contribution.\n"
            "- Use JSON arrays for keys that naturally hold multiple items.\n"
            "- No markdown fences, no text outside the JSON object."
        )

        limitations = ""
        if agent.limitations:
            limitations = "\n\nYour limitations (respect them):\n" + "\n".join(
                f"- {item}" for item in agent.limitations
            )

        return agent.system_instructions + limitations + _COUNCIL_GROUND_RULES + contract

    def _build_user_prompt(
        self,
        agent: AgentDefinition,
        task: AgentTask,
        *,
        round_number: int = 1,
        peer_contributions: Optional[List[Dict[str, Any]]] = None,
        own_round1: Optional[Dict[str, Any]] = None,
    ) -> str:
        sections: List[str] = []

        history = task.conversation_history[-self.history_limit :]
        if history:
            lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history]
            sections.append("Recent conversation:\n" + "\n".join(lines))

        if task.retrieved_knowledge:
            sections.append(
                "Retrieved knowledge:\n"
                + json.dumps(task.retrieved_knowledge, ensure_ascii=False, indent=2)
            )
        if task.retrieved_memories:
            sections.append(
                "Relevant memories:\n"
                + json.dumps(task.retrieved_memories, ensure_ascii=False, indent=2)
            )

        sections.append(f"Detected intent: {task.intent}")
        sections.append(
            f"Request for analysis (as the {agent.name}):\n{task.message}"
        )

        if round_number >= 2:
            deliberation = [
                "--- Council deliberation (round 2) ---",
                "Round-1 contributions from your fellow Council members:",
                json.dumps(peer_contributions or [], ensure_ascii=False, indent=2),
            ]
            if own_round1 is not None:
                deliberation += [
                    "Your own round-1 contribution:",
                    json.dumps(own_round1, ensure_ascii=False, indent=2),
                ]
            deliberation.append(
                "Revise your contribution in light of the full Council's round-1 "
                "output: strengthen what holds, correct what your peers refuted, "
                "and name real disagreements rather than smoothing them over. "
                "Update your confidence honestly. Reply with the same single "
                "JSON object contract as before."
            )
            sections.append("\n".join(deliberation))

        return "\n\n".join(sections)

    @staticmethod
    def _parse_content(text: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        try:
            return extract_json(text), None
        except ValueError as exc:
            return None, str(exc)

    @staticmethod
    def _failed(
        agent: AgentDefinition,
        started: float,
        error: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        round_number: int = 1,
    ) -> AgentResult:
        return AgentResult(
            agent_slug=agent.slug,
            agent_name=agent.name,
            status="failed",
            error=error,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
            round=round_number,
        )


def _clamp_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
