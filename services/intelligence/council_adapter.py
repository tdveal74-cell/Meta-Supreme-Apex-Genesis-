"""Council capability adapter for DEVON Agent Runtime.

`council.consult` gives a gated job a voice to ask before it acts: the
nine-seat Council deliberates (`ExecutiveController.run`) and its synthesis
lands as an ordinary read observation. Nothing executes on its advice — the
runtime's own risk gates still decide what needs a human — but the latest
council observation is what the approval card later carries, so a human
ruling on an effectful step can see what the Council actually said.

Modeled on `services/browser/agent_adapter.py`: a thin class that registers
one ToolSpec and keeps every failure inside the ToolResult.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from services.agent_runtime.contracts import COUNCIL_TOOL_NAME, ToolRisk
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolSpec
from services.intelligence.executive_controller import (
    ContextPacket,
    CouncilExecutionError,
    ExecutiveController,
)
from services.intelligence.providers.base import AIProvider, ProviderError

#: The Council answers to the runtime, not to a person; the packet still
#: needs a user identity, so it names the caller honestly.
COUNCIL_USER_ID = "devon-agent-runtime"


class CouncilCapabilityAdapter:
    """Read-only consultation over the nine-seat Council."""

    name = "council"

    def __init__(
        self,
        provider_factory: Callable[[], AIProvider],
        *,
        max_concurrency: int = 3,
    ) -> None:
        # A factory rather than a provider: the app layer resolves the live
        # provider per call, and a fresh ExecutiveController per consultation
        # keeps request ids one-to-one with observations.
        self._provider_factory = provider_factory
        self._max_concurrency = max_concurrency

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name=COUNCIL_TOOL_NAME,
                description=(
                    "Consult the nine-seat Council about a question before "
                    "acting. Read-only deliberation: the synthesis is context "
                    "for the plan and the approval card, never a command."
                ),
                risk=ToolRisk.READ,
                handler=self._consult,
                reversible=True,
                blast_radius="provider tokens only; no external effect",
            )
        )

    async def _consult(self, arguments: Dict[str, Any]) -> ToolResult:
        question = str(arguments.get("question") or "").strip()
        if not question:
            return ToolResult(False, error="question is required")
        requested = arguments.get("agents") or []
        if not isinstance(requested, list):
            return ToolResult(False, error="agents must be a list of registry slugs")

        controller = ExecutiveController(
            self._provider_factory(),
            max_concurrency=self._max_concurrency,
        )
        packet = ContextPacket(
            user_id=COUNCIL_USER_ID,
            message=question,
            requested_agents=[str(slug) for slug in requested],
            full_council=bool(arguments.get("full_council")),
            deliberate=bool(arguments.get("deliberate")),
        )
        try:
            synthesis = await controller.run(packet)
        except (CouncilExecutionError, ProviderError) as exc:
            return ToolResult(False, error=f"council consultation failed: {exc}")

        return ToolResult(
            True,
            output=synthesis.final_response,
            metadata={
                "request_id": synthesis.request_id,
                "intent": synthesis.intent.value,
                "agents_consulted": list(synthesis.agents_consulted),
                "confidence": synthesis.confidence,
                "recommended_actions": list(synthesis.recommended_actions),
                "points_of_agreement": list(synthesis.points_of_agreement),
                "points_of_tension": list(synthesis.points_of_tension),
                "synthesis_mode": synthesis.synthesis_mode,
                "deliberation_rounds": synthesis.deliberation_rounds,
                "provider": synthesis.provider,
                "model": synthesis.model,
                "contributions": [
                    {
                        "agent": item.agent_slug,
                        "status": item.status,
                        "confidence": item.confidence,
                        "round": item.round,
                    }
                    for item in synthesis.contributions
                ],
                "provider_receipt_id": f"council-{synthesis.request_id}",
            },
        )
