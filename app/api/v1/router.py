"""
API v1 Router - aggregates all module routers.
"""

from fastapi import APIRouter

from app.api.v1 import (
    agent_tasks,
    agents,
    auth,
    conversations,
    decisions,
    devon,
    health,
    intelligence,
    knowledge,
    knowledge_fkr,
    memory,
    operator,
    projects,
    soul,
    workflows,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(agents.router)
api_router.include_router(conversations.router)
api_router.include_router(intelligence.router)
api_router.include_router(knowledge.router)
api_router.include_router(knowledge_fkr.router)
api_router.include_router(memory.router)
api_router.include_router(decisions.router)
api_router.include_router(workflows.router)
api_router.include_router(devon.router)
api_router.include_router(operator.router)
api_router.include_router(agent_tasks.router)
api_router.include_router(soul.router)
