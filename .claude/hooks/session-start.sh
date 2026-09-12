#!/usr/bin/env bash
# SessionStart hook: make a Claude Code on the web session able to reproduce
# CI locally without any manual setup.
#
# CI is six jobs (see .claude/skills/steward/SKILL.md). This hook prepares the
# four things they need: the pinned Python closure, the locked pnpm workspace,
# a PostgreSQL 16 + pgvector cluster, and the environment variables the api and
# engine jobs run under.
#
# Local machines are left alone: it exits immediately unless CLAUDE_CODE_REMOTE
# is set. It is idempotent, non-interactive, and the database stage is best
# effort so a session always starts even when apt or initdb is unavailable.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 1

PGBIN=/usr/lib/postgresql/16/bin
PGDATA=/var/lib/pgtest

say() { printf '[session-start] %s\n' "$*"; }
warn() { printf '[session-start] WARNING: %s\n' "$*" >&2; }

# 1. Python: the exact pinned, hashed closure Railway builds from.
#    The Debian PyYAML has no RECORD file, so pip cannot uninstall it to make
#    room for the pinned 6.0.3. --ignore-installed steps over that shim; the
#    plain install is tried first so pip keeps its normal bookkeeping when the
#    container is already clean.
say "installing pinned Python requirements"
if ! python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt; then
  warn "plain pip install failed (usually the Debian PyYAML shim); retrying with --ignore-installed"
  python3 -m pip install --quiet --disable-pip-version-check --ignore-installed -r requirements.txt \
    || warn "pip install failed; the Python suites will not run"
fi

# 2. Node: the locked workspace the Web CI job installs.
if command -v pnpm >/dev/null 2>&1; then
  say "installing locked pnpm workspace"
  pnpm install --frozen-lockfile --silent \
    || pnpm install --silent \
    || warn "pnpm install failed; apps/web typecheck and build will not run"
else
  warn "pnpm not on PATH; skipping the web workspace"
fi

# 3. PostgreSQL 16 + pgvector, matching the api job's service container.
#    Every step here is best effort: a session without a database still runs
#    the standalone, engine-adjacent, and web lanes.
setup_postgres() {
  [ -x "$PGBIN/initdb" ] || { warn "PostgreSQL 16 is not installed; skipping the database"; return 0; }

  if ! ls /usr/lib/postgresql/16/lib/ 2>/dev/null | grep -qi vector; then
    say "installing postgresql-16-pgvector"
    apt-get install -y --no-install-recommends postgresql-16-pgvector >/dev/null 2>&1 \
      || { apt-get update -qq >/dev/null 2>&1 && apt-get install -y --no-install-recommends postgresql-16-pgvector >/dev/null 2>&1; } \
      || { warn "could not install pgvector; the api suite will fail on CREATE EXTENSION vector"; return 0; }
  fi

  # /var/lib/postgresql/16/main is the empty Debian skeleton. The cluster the
  # suite uses lives at $PGDATA and is created here.
  if [ ! -s "$PGDATA/PG_VERSION" ]; then
    say "initialising the PostgreSQL cluster at $PGDATA"
    install -d -o postgres -g postgres "$PGDATA" || { warn "could not create $PGDATA"; return 0; }
    su postgres -c "$PGBIN/initdb -D $PGDATA -U postgres --auth=trust" >/dev/null 2>&1 \
      || { warn "initdb failed"; return 0; }
  fi

  if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    say "starting PostgreSQL"
    su postgres -c "$PGBIN/pg_ctl -D $PGDATA -l /tmp/pg.log -o '-c listen_addresses=127.0.0.1 -p 5432' -w start" >/dev/null 2>&1 \
      || { warn "pg_ctl start failed; see /tmp/pg.log"; return 0; }
  fi

  for db in meta_supreme meta_supreme_test; do
    if ! psql -h 127.0.0.1 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" 2>/dev/null | grep -q 1; then
      psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE $db" >/dev/null 2>&1 \
        || { warn "could not create $db"; continue; }
    fi
    psql -h 127.0.0.1 -U postgres -d "$db" -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null 2>&1 \
      || warn "could not create the vector extension in $db"
  done
  say "PostgreSQL ready on 127.0.0.1:5432 (meta_supreme, meta_supreme_test)"
}
setup_postgres

# 4. The environment the api and engine jobs run under. Note that the
#    standalone job runs with NO PYTHONPATH: reproduce it with
#    `env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL ...`.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export DEFAULT_AI_PROVIDER=mock"
    echo "export EMBEDDING_PROVIDER=mock"
    echo "export ENVIRONMENT=test"
    echo "export PYTHONPATH=$ROOT:$ROOT/apps/api"
    echo "export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/meta_supreme"
    echo "export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/meta_supreme_test"
  } >> "$CLAUDE_ENV_FILE"
  say "wrote the CI environment to CLAUDE_ENV_FILE"
fi

say "done"
