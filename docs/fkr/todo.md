# Federated Knowledge Retrieval System - Task Checklist

**Design locked:** 2026-08-14  
**Plan:** `docs/fkr/plan.md`  
**Spec:** `docs/fkr/design-spec.md`  
**Gauntlet:** `docs/fkr/GAUNTLET.md`

## Phase 1: Foundation
- [ ] Task 1: Alembic migration for narrow-waist evolution
- [ ] Task 2: Update SQLAlchemy models

### Checkpoint: Foundation
- [ ] Migration + models applied; existing knowledge paths still work
- [ ] Human review before proceeding

## Phase 2: Core Retrieval (Stage 4)
- [ ] Task 3: Pure RRF function + unit tests
- [ ] Task 4: hybrid_retrieve service

### Checkpoint: Core Retrieval
- [ ] hybrid_retrieve works end-to-end on seeded data
- [ ] Human review

## Phase 3: Ingestion Path (Stages 1-3)
- [ ] Task 5: Distillation helper
- [ ] Task 6: Evolved ingest pipeline + FastAPI /ingest

### Checkpoint: Ingestion
- [ ] Can ingest a document and immediately retrieve it via hybrid path
- [ ] Human review

## Phase 4: Synthesis and Query Surface (Stage 5)
- [ ] Task 7: Re-ranker + synthesize_with_governance
- [ ] Task 8: FastAPI /query endpoint

### Checkpoint: Full Pipeline
- [ ] End-to-end ingest to hybrid to synthesize with citations works
- [ ] All tests green
- [ ] Human review of sample answers

## Phase 5: Hardening and Docs
- [ ] Task 9: Test suite expansion + regression protection
- [ ] Task 10: Documentation and operator notes

## Final Checkpoint
- [ ] Full five-stage pipeline verified against locked design
- [ ] Explicit authorization obtained before production deploy or connector activation
