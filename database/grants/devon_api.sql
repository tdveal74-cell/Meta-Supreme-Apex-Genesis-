-- What the API's runtime role may do to the tables that exist. Applied by
-- database/grants/apply_devon_api.py as the owner after every migration
-- (the compose stack's migrate service), and by the test suite against the
-- test database. Re-runnable.
--
-- DELETE is granted only where the application deletes: workflows and their
-- runs, memories, knowledge items and their embeddings, agent tasks and the
-- rows that hang off them, and runtime memories. It is never granted on
-- users, intents, events or receipts, so the owner cascade, which is the one
-- door through the ledger's append-only triggers, is not a door this role
-- can open. Tables added by a later migration get SELECT, INSERT and UPDATE
-- through the default privileges and no DELETE until a line is added here;
-- a new delete path then fails loudly with "permission denied" rather than
-- quietly widening what the role can erase.
--
-- alembic_version is the owner's bookkeeping. The role may read it and
-- nothing else, so it cannot wedge the next migration.

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO devon_api;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO devon_api;
REVOKE DELETE ON ALL TABLES IN SCHEMA public FROM devon_api;

GRANT DELETE ON
    workflows,
    workflow_runs,
    memories,
    knowledge_items,
    embeddings,
    agent_tasks,
    agent_task_runs,
    agent_task_checkpoints,
    agent_effect_intents,
    agent_effect_receipts,
    agent_subagent_links,
    agent_runtime_memories
TO devon_api;

-- alembic_version exists on every database the Alembic chain built and on
-- none the SQL scripts built (the test fixture), so the revoke is guarded.
DO $$
BEGIN
    IF to_regclass('public.alembic_version') IS NOT NULL THEN
        EXECUTE 'REVOKE ALL ON alembic_version FROM devon_api';
        EXECUTE 'GRANT SELECT ON alembic_version TO devon_api';
    END IF;
END
$$;

ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO devon_api;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO devon_api;
