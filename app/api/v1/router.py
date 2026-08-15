"""
API v1 Router - aggregates all module routers.
"""

from fastapi import APIRouter

from app.api.v1 import (
    agents,
    auth,
    conversations,
    decisions,
    health,
    intelligence,
    knowledge,
    knowledge_fkr,
    memory,
    projects,
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
