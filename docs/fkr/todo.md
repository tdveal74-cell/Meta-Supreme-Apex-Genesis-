# Federated Knowledge Retrieval System - Task Checklist

**Design locked:** 2026-08-14
**Gauntlet:** `docs/fkr/GAUNTLET.md`
**Phase 1 status:** `docs/fkr/PHASE1_STATUS.md`

## Phase 1: Foundation
- [x] Task 1: Alembic migration for narrow-waist evolution (source written; not applied)
- [x] Task 2: Update SQLAlchemy models (source written; dual path)

### Checkpoint: Foundation
- [ ] Migration + models applied on Docker Postgres
- [ ] Existing knowledge tests pass
- [ ] Human review before Phase 2

## Phase 2: Core Retrieval (Stage 4)
- [x] Task 3: Pure RRF function + unit tests (source written)
- [ ] Task 4: hybrid_retrieve service

### Checkpoint: Core Retrieval
- [ ] hybrid_retrieve works end-to-end on seeded data
- [ ] Human review

## Phase 3: Ingestion Path (Stages 1-3)
- [ ] Task 5: Distillation helper
- [ ] Task 6: Evolved ingest pipeline + FastAPI /ingest

## Phase 4: Synthesis and Query Surface (Stage 5)
- [ ] Task 7: Re-ranker + synthesize_with_governance
- [ ] Task 8: FastAPI /query endpoint

## Phase 5: Hardening and Docs
- [ ] Task 9: Test suite expansion + regression protection
- [ ] Task 10: Documentation and operator notes

## Final Checkpoint
- [ ] Full five-stage pipeline verified against locked design
- [ ] Explicit authorization obtained before production deploy or connector activation
