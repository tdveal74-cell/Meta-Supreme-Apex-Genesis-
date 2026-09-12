#!/usr/bin/env bash
# Runs once, on the first initialisation of the postgres volume, by the
# official image's docker-entrypoint. Enables pgvector on the ledger database
# and, when N8N_DB_PASSWORD is set, creates the n8n role and its own database
# owned by that role, so the executor never holds the ledger owner's
# credential. Re-running the stack against an existing volume skips this
# directory entirely, which is the documented behaviour of the image and the
# reason every statement below is also safe to run by hand.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL

if [ -n "${N8N_DB_PASSWORD:-}" ]; then
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
        -v n8n_password="$N8N_DB_PASSWORD" <<'SQL'
SELECT set_config('devon.n8n_password', :'n8n_password', false);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'n8n') THEN
        EXECUTE format('CREATE ROLE n8n LOGIN PASSWORD %L', current_setting('devon.n8n_password'));
    END IF;
END
$$;
SELECT 'CREATE DATABASE n8n OWNER n8n'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n')\gexec
SQL
else
    echo "N8N_DB_PASSWORD is unset: the n8n role and database were not created (executor profile off)"
fi
