"""
The company layer's read surface: the six business functions and the
Operations and Finance scoreboard.

Both routes are GET and mutate nothing. The scoreboard reads the same spend
ledger and cap setting that /usage reads. Revenue has no source connected, so
it is reported as not measured rather than as zero.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.security.deps import CurrentUser
from app.services.provider_usage import read_usage, utc_today
from services.company.functions import list_functions
from services.company.scoreboard import build_scoreboard

router = APIRouter(prefix="/company", tags=["Company"])


class FunctionOut(BaseModel):
    slug: str
    function: str
    mission: str
    key_tools: List[str]
    outcome: str
    max_impact: str
    status: str
    built_in: Optional[str]
    build_order: int
    notes: List[str]


class ScoreboardOut(BaseModel):
    date: str
    target_monthly_usd: int
    revenue_month_usd: Optional[float]
    revenue_measured: bool
    gap_to_target_usd: Optional[float]
    pct_of_target: Optional[float]
    spend_calls_today: int
    spend_tokens_today: int
    spend_cap_tokens: Optional[int]
    spend_headroom_tokens: Optional[int]
    cap_pct_used: Optional[float]
    notes: List[str]


@router.get("/functions", response_model=List[FunctionOut], summary="The six business functions")
async def read_functions() -> List[FunctionOut]:
    return [
        FunctionOut(
            slug=f.slug,
            function=f.function,
            mission=f.mission,
            key_tools=list(f.key_tools),
            outcome=f.outcome,
            max_impact=f.max_impact.value,
            status=f.status.value,
            built_in=f.built_in,
            build_order=f.build_order,
            notes=list(f.notes),
        )
        for f in list_functions()
    ]


@router.get("/scoreboard", response_model=ScoreboardOut, summary="Ops and Finance scoreboard")
async def read_scoreboard(current_user: CurrentUser) -> ScoreboardOut:
    day = utc_today()
    usage = await read_usage(str(current_user.id), day)
    cap = int(settings.PROVIDER_DAILY_TOKEN_CAP or 0)
    board = build_scoreboard(
        revenue_month_usd=None,
        calls_today=usage.calls,
        tokens_today=usage.total_tokens,
        cap_tokens=cap if cap > 0 else None,
    )
    return ScoreboardOut(date=day.isoformat(), notes=list(board.notes), **{
        k: getattr(board, k) for k in ScoreboardOut.model_fields if k not in ("date", "notes")
    })
