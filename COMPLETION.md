# Meta Supreme Apex Genesis — Completion

## Restored from Drive

**Archive:** `Meta Supreme Apex Genesis Workflows 11.zip`  
**Layout:** full monorepo (`apps/`, `services/`, `database/`, `infrastructure/`)

## Surfaces

| Mode | Command | Needs |
|------|---------|--------|
| Full stack | `make up` | Docker + Postgres |
| API local | `make api` | venv + DATABASE_URL |
| Offline flagship | `make standalone` | pip only |
| Tests (full) | `make test` | DB |
| Tests (offline) | `make test-offline` | none |

## Non-negotiables

1. Not a chatbot — multi-agent Council + synthesis only
2. Humans decide; agents recommend
3. Automation never commits effects unattended
4. Memory is transparent, editable, deletable
5. Simulated output is always labeled simulated
