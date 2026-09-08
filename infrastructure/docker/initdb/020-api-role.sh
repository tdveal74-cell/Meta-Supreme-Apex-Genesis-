#!/usr/bin/env bash
# Creates the API's runtime role on the first initialisation of the postgres
# volume. The SQL lives in sql/api-role.sql so the test suite can run the
# same statements against the test database and prove the role's limits;
# the sql/ subfolder is not auto-executed by the image, this script is.
set -euo pipefail

: "${API_DB_PASSWORD:?API_DB_PASSWORD must be set for the devon_api role}"

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v api_password="$API_DB_PASSWORD" \
    -v target_database="$POSTGRES_DB" \
    -v owner_role="$POSTGRES_USER" \
    -f /docker-entrypoint-initdb.d/sql/api-role.sql
