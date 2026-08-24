#!/usr/bin/env bash
#
# Start DEVON. One command, from nothing to a console in your browser.
#
#   ./start-devon.sh
#
# It does every step for you and stops with a plain explanation if one fails:
#
#   1. Finds Python
#   2. Installs the Python packages into a private folder (.venv)
#   3. Finds a database, or starts one with Docker if you have none
#   4. Writes your settings file and asks for the Pinecone key once
#   5. Creates the database tables
#   6. Starts the API
#   7. Prints the console link and the token to paste
#
# Safe to run again. It reuses the database, the .venv, and the .env you
# already have, so a second run repeats nothing and breaks nothing.

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

PG_CONTAINER="devon-pg"
PG_PASSWORD="devon-local-only"
PG_DB="meta_supreme"
PG_PORT="5432"
API_PORT="8000"
CONSOLE_EMAIL="console@devon-local.example.com"
CONSOLE_PASSWORD="devon-console-local-password"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
step() { printf "\n\033[38;5;173m[%s/7]\033[0m %s\n" "$1" "$2"; }
ok()   { printf "      \033[38;5;79m*%s\033[0m %s\n" "" "$1"; }
warn() { printf "      \033[38;5;179m!%s\033[0m %s\n" "" "$1"; }
die()  { printf "\n\033[38;5;203mStopped.\033[0m %s\n\n" "$1"; exit 1; }

printf "\n"
bold "DEVON starter"
printf "Bringing up the database, the API, and the console.\n"

# ---------------------------------------------------------------------------
step 1 "Finding Python"
# ---------------------------------------------------------------------------
PY=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || die \
"Python is not installed. Get Python 3.11 or newer from https://python.org/downloads
On Windows, tick 'Add Python to PATH' during the install. Then run this again."
ok "$($PY --version 2>&1)"

# ---------------------------------------------------------------------------
step 2 "Installing the Python packages"
# ---------------------------------------------------------------------------
if [ ! -d .venv ]; then
  $PY -m venv .venv || die \
"Could not create the .venv folder. On Debian or Ubuntu you may need:
  sudo apt install python3-venv"
  ok "Created .venv"
else
  ok ".venv already exists"
fi

VENV_PY=".venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY=".venv/Scripts/python.exe"   # Windows layout
[ -x "$VENV_PY" ] || die "The .venv folder looks broken. Delete it and run this again."

printf "      installing, a minute or so the first time\n"
"$VENV_PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1
"$VENV_PY" -m pip install --quiet -r requirements.txt || die \
"Package install failed. The reason is printed above. A second run usually
clears a network blip."
ok "Packages ready"

# ---------------------------------------------------------------------------
step 3 "Finding a database"
# ---------------------------------------------------------------------------
db_reachable() {
  "$VENV_PY" - "$1" "$2" <<'PYEOF' 2>/dev/null
import socket, sys
s = socket.socket()
s.settimeout(1.5)
try:
    s.connect((sys.argv[1], int(sys.argv[2])))
    sys.exit(0)
except Exception:
    sys.exit(1)
finally:
    s.close()
PYEOF
}

if db_reachable localhost "$PG_PORT"; then
  ok "A database is already listening on port $PG_PORT, using it"
  printf "      If it needs a different password than the default, press Ctrl+C,\n"
  printf "      set DATABASE_URL yourself in .env, and run this again.\n"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
    docker start "$PG_CONTAINER" >/dev/null 2>&1
    ok "Restarted the database container"
  else
    docker run -d --name "$PG_CONTAINER" \
      -e POSTGRES_PASSWORD="$PG_PASSWORD" \
      -e POSTGRES_DB="$PG_DB" \
      -p "$PG_PORT:5432" \
      pgvector/pgvector:pg16 >/dev/null 2>&1 \
      || die "Could not start the database container. If something else is using
port $PG_PORT, stop it, or change PG_PORT at the top of this script."
    ok "Started a new database container"
  fi
  printf "      waiting for it"
  for _ in $(seq 1 45); do
    db_reachable localhost "$PG_PORT" && break
    printf "."; sleep 1
  done
  printf "\n"
  db_reachable localhost "$PG_PORT" || die \
"The database did not come up. See what it says with:  docker logs $PG_CONTAINER"
  sleep 3
  ok "Database ready"
else
  die \
"No database found on port $PG_PORT, and Docker is not available to start one.

Pick whichever is easier:
  a) Install Docker Desktop from https://docker.com/products/docker-desktop
     open it, wait until it says Running, then run this script again.
  b) If you already have PostgreSQL somewhere, put its address in .env as
     DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME
     then run this script again."
fi

# ---------------------------------------------------------------------------
step 4 "Your settings"
# ---------------------------------------------------------------------------
if [ -f .env ]; then
  ok ".env already exists, leaving your settings alone"
else
  cat > .env <<ENVEOF
# DEVON local settings. Private: git ignores this file, and it never belongs
# in Drive. Secrets do not live in the vault.

DATABASE_URL=postgresql+asyncpg://postgres:$PG_PASSWORD@localhost:$PG_PORT/$PG_DB

# The soul layer: recall from tee-soul-layer (your rulings) and devon-soul.
SOUL_RECALL_ENABLED=true
PINECONE_API_KEY=

# DEVON voice and enrichment use Cerebras (measured 42ms lane, gpt-oss-120b).
# Paste your Cerebras Cloud key. Without it the process fails loudly rather
# than silently falling back to a different provider.
DEFAULT_AI_PROVIDER=cerebras
ENRICHMENT_PROVIDER=cerebras
CEREBRAS_MODEL=gpt-oss-120b
CEREBRAS_API_KEY=
ENVEOF
  ok "Wrote .env (Cerebras is the default voice and enrichment provider)"
fi

if grep -q '^PINECONE_API_KEY=$' .env 2>/dev/null; then
  printf "\n      DEVON needs your Pinecone key to recall from the soul layer.\n"
  printf "      Find it at https://app.pinecone.io under API Keys.\n"
  printf "      Paste it and press Enter, or just press Enter to skip for now.\n\n"
  printf "      Pinecone key: "
  read -r PINECONE_INPUT || PINECONE_INPUT=""
  if [ -n "${PINECONE_INPUT:-}" ]; then
    "$VENV_PY" - "$PINECONE_INPUT" <<'PYEOF'
import pathlib, sys
key = sys.argv[1].strip()
p = pathlib.Path(".env")
p.write_text(p.read_text().replace("PINECONE_API_KEY=", "PINECONE_API_KEY=" + key, 1))
PYEOF
    ok "Saved to .env"
  else
    warn "Skipped. Everything else still runs; recall will say it is switched off."
  fi
fi

if grep -q '^CEREBRAS_API_KEY=$' .env 2>/dev/null; then
  printf "\n      DEVON voice is set to Cerebras. Paste your Cerebras Cloud key.\n"
  printf "      Find it at https://cloud.cerebras.ai under API Keys.\n"
  printf "      Paste it and press Enter, or press Enter to leave unset (live calls will fail closed).\n\n"
  printf "      Cerebras key: "
  read -r CEREBRAS_INPUT || CEREBRAS_INPUT=""
  if [ -n "${CEREBRAS_INPUT:-}" ]; then
    "$VENV_PY" - "$CEREBRAS_INPUT" <<'PYEOF'
import pathlib, sys
key = sys.argv[1].strip()
p = pathlib.Path(".env")
p.write_text(p.read_text().replace("CEREBRAS_API_KEY=", "CEREBRAS_API_KEY=" + key, 1))
PYEOF
    ok "Saved Cerebras key to .env"
  else
    warn "Skipped. DEFAULT_AI_PROVIDER=cerebras will refuse until the key is set."
  fi
fi

# ---------------------------------------------------------------------------
step 5 "Creating the database tables"
# ---------------------------------------------------------------------------
"$VENV_PY" - <<'PYEOF'
import asyncio, pathlib, re, sys

env = {}
for line in pathlib.Path(".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

url = env.get("DATABASE_URL", "")
if not url:
    print("      ! No DATABASE_URL in .env")
    sys.exit(1)
dsn = url.replace("postgresql+asyncpg://", "postgresql://")

async def main():
    import asyncpg
    base, _, dbname = dsn.rpartition("/")
    try:
        conn = await asyncpg.connect(dsn)
    except asyncpg.InvalidCatalogNameError:
        admin = await asyncpg.connect(base + "/postgres")
        await admin.execute('CREATE DATABASE "%s"' % dbname)
        await admin.close()
        print("      * Created the %s database" % dbname)
        conn = await asyncpg.connect(dsn)

    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    except Exception as exc:
        print("      ! pgvector is not installed in this database: %s" % exc)
        print("        Vector search will not work. The pgvector/pgvector image has it.")

    for path in sorted(pathlib.Path("database/schemas").glob("*.sql")):
        sql = path.read_text()
        try:
            await conn.execute(sql)
            print("      * %s" % path.name)
        except Exception as exc:
            if "already exists" in str(exc).lower():
                print("      * %s (already applied)" % path.name)
            else:
                applied = failed = 0
                for stmt in [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]:
                    try:
                        await conn.execute(stmt)
                        applied += 1
                    except Exception as inner:
                        if "already exists" in str(inner).lower():
                            applied += 1
                        else:
                            failed += 1
                note = ", %d skipped" % failed if failed else ""
                print("      * %s (%d applied%s)" % (path.name, applied, note))
    await conn.close()

asyncio.run(main())
PYEOF
[ $? -eq 0 ] || die "Could not set up the tables. The reason is just above."

# ---------------------------------------------------------------------------
step 6 "Starting the API"
# ---------------------------------------------------------------------------
HEALTH="http://localhost:$API_PORT/api/v1/health"
if curl -sf "$HEALTH" >/dev/null 2>&1; then
  ok "Already running on port $API_PORT, reusing it"
else
  "$VENV_PY" -m uvicorn app.main:app --port "$API_PORT" > /tmp/devon-api.log 2>&1 &
  API_PID=$!
  printf "      waiting for it to answer"
  for _ in $(seq 1 45); do
    curl -sf "$HEALTH" >/dev/null 2>&1 && break
    if ! kill -0 "$API_PID" 2>/dev/null; then
      printf "\n"
      warn "The API stopped. Its last words:"
      tail -12 /tmp/devon-api.log | sed 's/^/        /'
      die "Full log: /tmp/devon-api.log"
    fi
    printf "."; sleep 1
  done
  printf "\n"
  curl -sf "$HEALTH" >/dev/null 2>&1 || die "The API never answered. Log: /tmp/devon-api.log"
  ok "Running. Leave this window open; closing it stops DEVON."
fi

# ---------------------------------------------------------------------------
step 7 "Your console login"
# ---------------------------------------------------------------------------
if curl -sf -X POST "http://localhost:$API_PORT/api/v1/auth/register" \
     -H 'Content-Type: application/json' \
     -d "{\"email\":\"$CONSOLE_EMAIL\",\"password\":\"$CONSOLE_PASSWORD\",\"full_name\":\"Tee\"}" \
     >/dev/null 2>&1; then
  ok "Created your console account"
else
  ok "Console account already exists"
fi

TOKEN=$(curl -sf -X POST "http://localhost:$API_PORT/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$CONSOLE_EMAIL\",\"password\":\"$CONSOLE_PASSWORD\"}" \
  | "$VENV_PY" -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)

[ -n "$TOKEN" ] || die "Could not get a login token. Log: /tmp/devon-api.log"

SOUL=$(curl -sf "http://localhost:$API_PORT/api/v1/soul/status" \
  -H "Authorization: Bearer $TOKEN" \
  | "$VENV_PY" -c 'import sys,json; print("on" if json.load(sys.stdin).get("enabled") else "off")' 2>/dev/null)

printf "\n"
bold "DEVON is up."
printf "\n"
printf "  Open this:    http://localhost:%s/console\n" "$API_PORT"
printf "  Soul recall:  %s\n" "${SOUL:-unknown}"
printf "  Voice model:  Cerebras (gpt-oss-120b) when CEREBRAS_API_KEY is set\n"
printf "\n"
printf "  In the console, find the Soul Layer panel on the right.\n"
printf "  Leave API empty. Paste this into TOKEN, press SAVE, then TEST:\n"
printf "\n"
printf "  %s\n" "$TOKEN"
printf "\n"
printf "  Then talk to him. Try: what do we already know about the nine areas\n"
printf "\n"
printf "  Done for the day? Close this window. To stop the database too:\n"
printf "    docker stop %s\n" "$PG_CONTAINER"
printf "\n"
