# Getting Started — Meta Supreme Apex Genesis

This guide gets a local development environment running for **Phase 1 (Foundation)**.

## Prerequisites

- Node.js 20+
- pnpm 9+ (recommended) or npm
- Python 3.11+
- Docker & Docker Compose
- Git

## 1. Clone & Install

```bash
git clone <repository-url>
cd meta-supreme-apex-genesis

# Frontend workspace
pnpm install

# Backend
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ../..
```

## 2. Environment

Copy example env files:

```bash
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
cp infrastructure/docker/.env.example infrastructure/docker/.env
```

Edit `apps/api/.env` and set a strong `SECRET_KEY` (generate with `openssl rand -hex 32`).

## 3. Start Infrastructure

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

This starts:

- PostgreSQL 16 + pgvector (port 5432)
- API service (port 8000) with hot reload
- Web service (port 3000) with hot reload

The initial schema is automatically applied on first database start via the mounted `001_initial_schema.sql`.

## 4. Verify

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/api/v1/health

## 5. Manual Backend (without Docker for API)

```bash
cd apps/api
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Current Phase 1 Status

| Capability              | Status      |
|-------------------------|-------------|
| Repository structure    | Complete    |
| Frontend shell + design | Complete    |
| Database schema         | Complete    |
| Authentication (JWT)    | Complete    |
| User models             | Complete    |
| Health endpoints        | Complete    |
| AI Council registry     | Complete    |
| Executive Controller    | Skeleton    |
| Knowledge / Memory      | Pending (Phase 3+) |
| Live agent execution    | Pending (Phase 2/4) |

## Next Steps (Phase 2)

1. Wire real AI provider abstraction
2. Implement Executive Controller agent routing + synthesis
3. Add conversation and message persistence
4. Protect frontend routes and connect login form to `/api/v1/auth/login`

See `ARCHITECTURE.md` and the master blueprint for the full roadmap.
