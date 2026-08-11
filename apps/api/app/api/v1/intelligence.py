"""
Intelligence endpoints — direct access to the Executive Controller.

POST /intelligence/ask runs a one-shot Council request without creating a
conversation (nothing is persisted).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.security.deps import CurrentUser
from app.services.intelligence import build_controller, get_provider
from services.agents.registry import AGENT_REGISTRY
from services.intelligence import ContextPacket, CouncilExecutionError
from services.intelligence.providers import ProviderConfigError, ProviderError

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=32_000)
    agents: Optional[List[str]] = Field(
        None, description="Explicit agent slugs to consult (overrides intent routing)."
    )
    full_council: bool = Field(
        False, description="Activate all nine Council agents."
    )


class AskContribution(BaseModel):
    agent_slug: str
    agent_name: str
    status: str
    content: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    latency_ms: int = 0
    error: Optional[str] = None


class AskResponse(BaseModel):
    request_id: str
    response: str
    intent: str
    intent_source: str
    agents_consulted: List[str]
    contributions: List[AskContribution]
    recommended_actions: List[str]
    points_of_agreement: List[str]
    points_of_tension: List[str]
    confidence: float
    synthesis_mode: str
    provider: str
    model: str
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int


class IntelligenceStatus(BaseModel):
    provider: str
    model: str
    simulated: bool
    parallel_execution: bool
    agents_available: int


@router.get("/status", response_model=IntelligenceStatus)
async def intelligence_status(current_user: CurrentUser):
    try:
        provider = get_provider()
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI provider is not configured: {exc}",
        ) from exc
    return IntelligenceStatus(
        provider=provider.name,
        model=provider.default_model,
        simulated=provider.name == "mock",
        parallel_execution=settings.COUNCIL_PARALLEL_EXECUTION,
        agents_available=len(AGENT_REGISTRY),
    )


@router.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest, current_user: CurrentUser):
    if payload.agents:
        unknown = [slug for slug in payload.agents if slug not in AGENT_REGISTRY]
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown agent slugs: {', '.join(unknown)}",
            )

    context = ContextPacket(
        user_id=current_user.id,
        message=payload.message,
        requested_agents=payload.agents or [],
        full_council=payload.full_council,
    )

    try:
        controller = build_controller()
        result = await controller.run(context)
    except ProviderConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI provider is not configured: {exc}",
        ) from exc
    except CouncilExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The Council could not process this request: {exc}",
        ) from exc
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {exc}",
        ) from exc

    return AskResponse(
        request_id=result.request_id,
        response=result.final_response,
        intent=result.intent.value,
        intent_source=result.intent_source,
        agents_consulted=result.agents_consulted,
        contributions=[
            AskContribution(
                agent_slug=c.agent_slug,
                agent_name=c.agent_name,
                status=c.status,
                content=c.content,
                confidence=c.confidence,
                latency_ms=c.latency_ms,
                error=c.error,
            )
            for c in result.contributions
        ],
        recommended_actions=result.recommended_actions,
        points_of_agreement=result.points_of_agreement,
        points_of_tension=result.points_of_tension,
        confidence=result.confidence,
        synthesis_mode=result.synthesis_mode,
        provider=result.provider,
        model=result.model,
        total_input_tokens=result.total_input_tokens,
        total_output_tokens=result.total_output_tokens,
        total_latency_ms=result.total_latency_ms,
    )
