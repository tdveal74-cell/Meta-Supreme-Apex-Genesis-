-- The runtime role for the API. Run by 020-api-role.sh on first init with
-- :'api_password' bound, and by test_live_state_ledger_provenance.py against
-- the test database to prove what the role can and cannot do.
--
-- The migrations run as the database owner in the compose stack's one-shot
-- migrate service. The API itself connects as this role, which can read and
-- write every table the owner creates and nothing more: no CREATE on the
-- schema (so no scratch table with a trigger that deletes at depth 2), no
-- TRUNCATE, no ownership (so no DISABLE TRIGGER), no superuser (so no
-- session_replication_role). The ledger triggers refuse the rest.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'devon_api') THEN
        EXECUTE format('CREATE ROLE devon_api LOGIN PASSWORD %L', :'api_password');
    ELSE
        EXECUTE format('ALTER ROLE devon_api WITH LOGIN PASSWORD %L', :'api_password');
    END IF;
END
$$;

GRANT CONNECT ON DATABASE :"target_database" TO devon_api;
GRANT USAGE ON SCHEMA public TO devon_api;
REVOKE CREATE ON SCHEMA public FROM devon_api;

-- Tables the owner has already created, and every table it creates later
-- (each migration runs as the owner, so the default privileges apply).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO devon_api;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO devon_api;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO devon_api;
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO devon_api;
