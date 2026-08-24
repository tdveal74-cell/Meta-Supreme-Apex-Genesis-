"""
Model package.

Every model module is imported here, and that is load bearing rather than
tidiness. SQLAlchemy resolves `relationship("Organization", ...)` by name at
mapper configuration time, so a model class that no module ever imports is
never registered and the lookup fails.

`User.owned_organizations` referenced `Organization`, `app/models/organization.py`
defined it, and nothing imported it. `configure_mappers()` raised
InvalidRequestError, so every database backed test failed at fixture setup
before running a single assertion. Importing the package now registers the
whole set.

Keep this list complete. A new model module that is not listed here works
until something references it by name, then fails at runtime rather than at
import, which is the expensive way to find out.
"""

from app.models.agent import Agent, AgentRun
from app.models.agent_runtime import (
    AgentEffectIntentRecord,
    AgentEffectReceiptRecord,
    AgentRuntimeMemory,
    AgentRuntimeSkill,
    AgentTaskCheckpointRecord,
    AgentTaskRecord,
    AgentTaskRunRecord,
)
from app.models.conversation import Conversation, Message
from app.models.decision import Decision
from app.models.knowledge import Embedding, KnowledgeItem
from app.models.memory import Memory
from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.models.workflow import Workflow, WorkflowRun

__all__ = [
    "Agent",
    "AgentRun",
    "AgentEffectIntentRecord",
    "AgentEffectReceiptRecord",
    "AgentRuntimeMemory",
    "AgentRuntimeSkill",
    "AgentTaskCheckpointRecord",
    "AgentTaskRecord",
    "AgentTaskRunRecord",
    "Conversation",
    "Decision",
    "Embedding",
    "KnowledgeItem",
    "Memory",
    "Message",
    "Organization",
    "OrganizationMember",
    "Project",
    "User",
    "Workflow",
    "WorkflowRun",
]
