"""Memory services.

Empty stub. Not durable memory. Not Live. Not a 2nd-brain store.
Platform memory CRUD lives in app.api.v1.memory (Postgres, lexical).
Hermes expansion defaults (InMemoryScheduleStore, SkillProposalStore,
InMemoryLearningStore) are process-local and not durable.
"""
