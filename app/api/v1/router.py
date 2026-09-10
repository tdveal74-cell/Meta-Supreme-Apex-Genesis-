"""
API v1 Router - aggregates all module routers.
"""

from fastapi import APIRouter

from app.api.v1 import (
    agent_expansion,
    agent_tasks,
    agents,
    auth,
    conversations,
    decisions,
    devon,
    devon_editforge,
    health,
    intelligence,
    knowledge,
    knowledge_fkr,
    knowledge_graph,
    ledger,
    memory,
    operator,
    operator_shell,
    projects,
    soul,
    usage,
    workflows,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(agents.router)
api_router.include_router(conversations.router)
api_router.include_router(intelligence.router)
# BEFORE knowledge.router, deliberately. app/api/v1/knowledge.py declares
# GET /knowledge/{item_id}, which matches the literal segment "graph", and FastAPI
# resolves across included routers in registration order. Measured both ways against
# a real TestClient: graph first returns the edge payload, graph last returns 404
# "Knowledge item not found". test_knowledge_graph.py asserts this order and also
# demonstrates the shadowing, so the ordering is proved rather than commented.
api_router.include_router(knowledge_graph.router)
api_router.include_router(knowledge.router)
api_router.include_router(knowledge_fkr.router)
api_router.include_router(memory.router)
api_router.include_router(usage.router)
api_router.include_router(decisions.router)
api_router.include_router(workflows.router)
api_router.include_router(devon.router)
api_router.include_router(devon_editforge.router)
api_router.include_router(operator.router)
api_router.include_router(operator_shell.router)
api_router.include_router(agent_tasks.router)
api_router.include_router(agent_expansion.router)
api_router.include_router(soul.router)
api_router.include_router(ledger.router)
