# CLAUDE.md

Project memory for Meta Supreme Apex Genesis. Read this first, then load the
`steward` skill before touching CI or a PR.

## What this is

An intelligence operating system, not a chatbot. A FastAPI service under
`app/` and `services/`, a Next.js workspace under `apps/web` and
`packages/ui`, PostgreSQL 16 with pgvector, Alembic migrations under
`database/`. Agents recommend, humans decide: every WRITE or HIGH_IMPACT tool
call is human gated.

Orientation docs, in the order worth reading them: `README.md`,
`ARCHITECTURE.md`, `RUNBOOK.md`, `OPERATING.md`, `docs/devon/DEVON.md`.
The `docs/devon/SYS_OPS_*` files are the dated status record; the newest one
on a topic supersedes the older ones.

## Environment

The SessionStart hook (`.claude/hooks/session-start.sh`) runs on Claude Code
on the web and prepares everything below, so in a web session it is already
done. On a local machine the hook exits immediately and you do it yourself.

```bash
python3 -m pip install -r requirements.txt   # add --ignore-installed if the
                                             # Debian PyYAML shim blocks it
pnpm install --frozen-lockfile
export DEFAULT_AI_PROVIDER=mock EMBEDDING_PROVIDER=mock ENVIRONMENT=test
export PYTHONPATH=$PWD:$PWD/apps/api
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/meta_supreme
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/meta_supreme_test
```

The cluster lives at `/var/lib/pgtest`, not at the empty Debian skeleton in
`/var/lib/postgresql/16/main`. It does not survive a container restart:

```bash
su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/pgtest -l /tmp/pg.log start"
```

`ConnectionRefused` in the middle of a run is the cluster going away, not a
test failure. It shows up as a hundred or more collection ERRORs.

## Reproducing CI

CI is six jobs. Five are in `.github/workflows/ci.yml`
(`standalone` then `container` and `engine` then `api`, plus `dependency-audit`
on every push). The sixth is `.github/workflows/web-ci.yml`, path filtered to
the web workspace, so a run of Python-only PRs makes CI look like five.
`ruff check .` runs at the end of the api job, not as a job of its own.

The standalone job runs with **no** `PYTHONPATH` and no database. An import
that only resolves under the test path passes locally and fails there, so
reproduce it exactly:

```bash
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -c "import standalone_api"
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q \
  test_billing.py test_definition.py test_providers.py test_schedule.py \
  test_workflow_engine.py test_devon_hermes_expansion.py \
  test_devon_hermes_durable_followon.py test_devon_learning_loop.py \
  test_devon_operating_layer.py test_devon_editforge_execution.py

python3 -m pytest -q --tb=short          # full api suite, needs the database
python3 -m ruff check .
pnpm --filter @meta-supreme/web typecheck && pnpm --filter @meta-supreme/web build
```

The dependency audit lane needs a tool the pinned closure does not carry, and
installing it can perturb that closure, so the hook leaves it out. Reproduce it
on demand, in a throwaway environment when you can:

```bash
python3 -m pip install pip-audit
python3 -m pip_audit -r requirements.txt --progress-spinner off
python3 -m pip_audit -r deploy/soul/requirements.txt --progress-spinner off
pnpm audit --audit-level=moderate
```

`pytest ... | tail` and `tsc ... | tail` report tail's exit code. A run with
154 errors exits 0 through a pipe. Redirect to a file and check `$?`.

ESLint is not configured here. `next lint` drops into its interactive setup and
exits non-zero, which looks like a lint failure and is not one.

The full failure catalogue with root causes lives in the `steward` skill.
Check it before inventing a new theory.

## Invariants that never get relaxed to make CI green

- `services/devon` stays effect free
- WRITE and HIGH_IMPACT tools require human approval
- Orphan effect intents refuse automatic retry; the intent commits durably
  before the adapter runs
- Receipts commit atomically with the lease fenced result
- Skill promotion is human gated; proposals dedupe by goal slug
- Materialize and spawn never auto run effects
- `deploy/soul/main.py` has no mutating routes. The one permitted non-GET is
  `POST /api/v1/soul/conflict-search`, which is a read only recall query, and
  it is allowlisted explicitly in `test_deploy_soul.py`
- No em or en dashes in `services/devon/*.py` or `docs/devon/*.md`.
  `test_devon_integrity.py` enforces it. Restructure the sentence, do not swap
  the punctuation

## Adding a migration

A new migration touches three places in `ci.yml`, not two: the two `for f in
001... ; do test -s` existence loops, and the `assert revision == "<head>"`
inside the Python heredoc of the "Fresh Alembic deploy" step. It also touches
two lists in `conftest.py`: `_INCREMENTAL_SCHEMAS` and `_DATA_TABLES`, where FK
order matters. Miss either list and every test touching the new tables fails
with `relation "agent_..." does not exist`.

Confirm the current head with `alembic heads`, never from a doc.

## Ship discipline

Small PRs on the designated branch, draft first, full local validation before
every push. Merge only with Tee's explicit authorization. After a designated
branch's PR merges, restart the branch from `origin/main` under the same name.
Close an arc with a dated `docs/devon/SYS_OPS_*` status doc and a DEVON thread
log receipt.

A handover's "CI green" is a claim, not a fact. Check the Actions history for
the claimed head SHA before building on it. A green Vercel preview is not
production; load the `deploy-readback` skill before saying any surface is live.

## Skills in this repository

`.claude/skills/` carries four: `steward` (CI and PR conventions, load it for
anything touching either), `deploy-readback` (what the production surfaces are
actually serving), `estate-reconcile` (checking records against the live
estate), `devon-learning-lane` (the Build 12 learning lane and the n8n house
conventions).

`.claude/settings.json` also pins three community plugins through the
`meta-supreme-pinned` marketplace in `.claude-plugin/marketplace.json`. Each
machine installs them once:

```bash
claude plugin install agentic-guardrails@meta-supreme-pinned
claude plugin install backend-security-skills@meta-supreme-pinned
claude plugin install test-generator@meta-supreme-pinned
```

Remove any `@claude-community` copy of the same name, which would otherwise
load beside the pinned one and win.
