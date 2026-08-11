# Restore full monorepo from Google Drive

**Authoritative archive:** `Meta Supreme Apex Genesis Workflows 11.zip`  
Drive file id: `1eWNfCGBAaVIWCi7Aiqr8DLoHGtnj8-k5`

This GitHub repo holds the monorepo **layout + offline surface**. The complete
Phase 5 source tree (all `apps/api` modules, tests, web pages, services) is in
that zip (~336 KB).

## One-shot restore on Linux / Chromebook

```bash
# 1) Download Workflows 11 from Drive into Linux files, then:
cd ~
unzip -o "Meta Supreme Apex Genesis Workflows 11.zip"

# 2) Overlay into your clone (or use the unzipped tree directly)
cd meta-supreme-apex-genesis
cp apps/api/.env.example apps/api/.env
# edit SECRET_KEY if desired

# 3) Full stack
docker compose -f infrastructure/docker/docker-compose.yml up -d --build

# or:
# make install && alembic upgrade head && make up
```

## Verify

- http://localhost:3000 — web
- http://localhost:8000/api/docs — API
- `make test` — backend suite (expects DB)

## Offline (already in this repo)

```bash
make standalone
make test-offline
```

## Why two layers?

GitHub previously held a **flattened** snapshot. Workflows 11 is the real
`apps/` + `services/` + `database/` tree with Alembic and workflows. Prefer the
zip for full `make test` / Docker; keep this repo for offline API + docs.
