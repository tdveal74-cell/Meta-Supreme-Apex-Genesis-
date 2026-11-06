"""One authenticated, bounded Presence completion, accounted by the API."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.security.deps import CurrentUser
from app.services.presence import complete_presence
from services.intelligence.presence import PRESENCE_MAX_PROMPT_CHARS

router = APIRouter(prefix="/presence", tags=["Presence"])


class PresenceCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=PRESENCE_MAX_PROMPT_CHARS, pattern=r"\S")
    provider: Literal["mock", "gemini", "cerebras", "anthropic", "openai"]



@router.post("/complete")
async def complete(body: PresenceCompletionRequest, user: CurrentUser):
    response = await complete_presence(
        owner_id=str(user.id), provider_name=body.provider, prompt=body.text
    )
    return {
        "text": response.text,
        "provider": response.provider,
        "model": response.model,
        "usage": response.usage.as_dict(),
        "usage_recorded": True,
    }
