# FKR operator notes

## Endpoints (after router mount)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/knowledge/ingest` | Distill + embed + store (federated) |
| POST | `/api/v1/knowledge/query` | Hybrid retrieve + cited answer |
| POST | `/api/v1/knowledge` | Existing pure ingest (unchanged) |
| POST | `/api/v1/knowledge/search` | Existing pure-semantic search (unchanged) |

## Migration

```bash
alembic upgrade head
```

Revision `004_federated_knowledge_waist` is additive. Apply on Docker Postgres first.

## Honesty

- Mock embeddings and offline distillation are labelled in metadata (`simulated_*`).
- Query refuses to invent sources when no candidates clear ACL.
- Empty `acl_tokens` means ownership-only access.

## Gauntlet

See `docs/fkr/GAUNTLET.md`. Product is not 99 until live migration + pytest + one Tee-reviewed query.
