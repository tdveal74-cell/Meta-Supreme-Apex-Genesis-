"""Smoke tests for Hermes expansion wiring."""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.models.agent_runtime import AgentScheduleRecord, AgentSkillProposalRecord


def test_expansion_router_paths_registered() -> None:
    # FastAPI >= 0.141 includes routers lazily, so api_router.routes no longer
    # carries concrete paths. The OpenAPI schema always does, on every version.
    app = FastAPI()
    app.include_router(api_router)
    paths = set(app.openapi()["paths"])
    assert any("/agent-expansion/schedules" in path for path in paths)
    assert any("/agent-expansion/skill-proposals" in path for path in paths)


def test_schedule_and_proposal_models_map_to_schema_tables() -> None:
    assert AgentScheduleRecord.__tablename__ == "agent_schedules"
    assert AgentSkillProposalRecord.__tablename__ == "agent_skill_proposals"
