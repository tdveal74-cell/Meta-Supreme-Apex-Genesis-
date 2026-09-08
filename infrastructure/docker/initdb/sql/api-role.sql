-- The runtime role for the API: created here, granted in
-- database/grants/devon_api.sql after every migration. Run by
-- 020-api-role.sh on first init with :'api_password', :"target_database"
-- and :"owner_role" bound, and by test_live_state_ledger_provenance.py
-- against the test database to prove what the role can and cannot do.
--
-- What this file takes away is the point. No CREATE on the schema and no
-- TEMP on the database, so the role can create no table, temporary or not,
-- and therefore no trigger of its own to delete from inside. No ownership,
-- so no DISABLE TRIGGER. No superuser, so no session_replication_role. The
-- third gauntlet of 2026-09-08 deleted a receipted history through a
-- temporary table's trigger because TEMP is granted to PUBLIC by default;
-- it is revoked here from PUBLIC for the whole database.

-- psql interpolates :'api_password' in a plain statement and never inside a
-- dollar quoted body, so the password goes in through a session setting.
SELECT set_config('devon.api_password', :'api_password', false);

DO $$
DECLARE
    pw TEXT := current_setting('devon.api_password');
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'devon_api') THEN
        EXECUTE format('CREATE ROLE devon_api LOGIN PASSWORD %L', pw);
    ELSE
        EXECUTE format('ALTER ROLE devon_api WITH LOGIN PASSWORD %L', pw);
    END IF;
END
$$;

GRANT CONNECT ON DATABASE :"target_database" TO devon_api;
REVOKE TEMP ON DATABASE :"target_database" FROM PUBLIC;
REVOKE TEMP ON DATABASE :"target_database" FROM devon_api;
GRANT USAGE ON SCHEMA public TO devon_api;
REVOKE CREATE ON SCHEMA public FROM devon_api;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
