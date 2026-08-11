# Build — Meta Supreme Apex Genesis

## Verified offline (this environment)

```text
agents: oracle, analyst, strategist, architect, engineer,
        guardian, creator, librarian, skeptic
effect steps: decision_draft, export, memory_write
WorkflowDefinition.empty() → ok
```

## Full monorepo source

**Google Drive:** `Meta Supreme Apex Genesis Workflows 11.zip`  
https://drive.google.com/file/d/1eWNfCGBAaVIWCi7Aiqr8DLoHGtnj8-k5/view

```bash
cd ~
unzip -o "Meta Supreme Apex Genesis Workflows 11.zip"
cd meta-supreme-apex-genesis
cp apps/api/.env.example apps/api/.env

# Postgres + API + Web
docker compose -f infrastructure/docker/docker-compose.yml up -d --build

# or
make install && alembic upgrade head && make up && make test
```

## Flagship visual

See `docs/FLAGSHIP_SPEC.md` — Navy / Amber / Surface only.

## Phase

`0.1.0` / Phase 5 workflows · mock provider default · human-final gates
