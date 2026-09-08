#!/usr/bin/env bash
# Runs once, on the first initialisation of the postgres volume, by the
# official image's docker-entrypoint. Creates the n8n database beside the
# ledger and enables pgvector on the ledger database. Re-running the stack
# against an existing volume skips this directory entirely, which is the
# documented behaviour of the image and the reason every statement below is
# also safe to run by hand.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
SELECT 'CREATE DATABASE n8n'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n')\gexec
SQL
