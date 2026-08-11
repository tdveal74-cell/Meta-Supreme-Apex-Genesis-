# Restore Meta Supreme (authoritative)

GitHub `main` is a **working partial** of the monorepo. The complete tree is:

1. **Drive:** [Meta-Supreme-Apex-Genesis-BUILD.zip](https://drive.google.com/file/d/1cjSiMO-JypICuDcIxCP_0WWFfNeHv2gW/view) (209 files)
2. **Drive:** Meta Supreme Apex Genesis Workflows 11.zip (Phase 5 source)

```bash
cd ~
unzip -o Meta-Supreme-Apex-Genesis-BUILD.zip -d meta-supreme-apex-genesis
cd meta-supreme-apex-genesis
cp apps/api/.env.example apps/api/.env
docker compose -f infrastructure/docker/docker-compose.yml up -d --build
# Web :3000 · API :8000/api/docs
```

Offline: `make standalone` / `make test-offline` when Makefile targets exist in the unzipped tree.

Do not treat the flattened root-level Python files on GitHub as the only layout — prefer `apps/`, `services/`, `database/` from the BUILD zip.
