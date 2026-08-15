# Handover: Federated Knowledge Retrieval System (Cerebras-style)

**Date:** 2026-08-14
**Status:** Design locked. Implementation plan written. Awaiting explicit authorization to begin code.
**Owner:** Tee
**Target repo:** Meta-Supreme-Apex-Genesis- (tdveal74-cell)
**Working style:** Evolve-in-place inside the existing monorepo
**Gauntlet:** `docs/fkr/GAUNTLET.md` (overall product score ~28 until implementation)

---

## 1. What This Is

A production-grade Federated Knowledge Retrieval System modeled on the Cerebras Knowledge architecture, built for Tee operational environment (Meta Supreme + EditForge + TSWS + Devon + n8n + GitHub + Drive + Notion).

Five stages:

1. **Ingestion Engine** - connector / payload intake
2. **Contextual Distillation** - LLM strips noise and produces searchable structured text
3. **Unified Single-Table Storage** - PostgreSQL + pgvector, HNSW (cosine), ACL tokens, full-text
4. **Hybrid 4-Signal Retrieval** - Dense + Sparse/BM25 + IDF/fluff + Exponential Age-Decay, fused by RRF (k=60)
5. **Synthesis and Governance** - cross-encoder re-rank, final ACL gate, cited answer

---

## 2. Key Decisions (Locked)

| Decision | Choice |
|----------|--------|
| Location | **A** - inside Meta-Supreme-Apex-Genesis- monorepo |
| Approach | **1** - evolve existing `knowledge_items` + `embeddings` tables (narrow waist on `embeddings`) |
| Database | Existing Meta Supreme Docker Postgres + pgvector (1536 dims) |
| ACL model | Denormalized `owner_id` + `acl_tokens TEXT[]` (empty = inherit ownership only) |
| Fusion | Reciprocal Rank Fusion, **k = 60** |
| Distillation | Mandatory before embedding for new content |
| Write path | Single endpoint `POST /api/v1/knowledge/ingest` for all future connectors |
| Pure-semantic path | Kept alive (existing `search_knowledge` continues to work) |

---

## 3. Artifacts in this repo

| Artifact | Path |
|----------|------|
| Design Spec (locked) | `docs/fkr/design-spec.md` |
| Implementation Plan | `docs/fkr/plan.md` |
| Task Checklist | `docs/fkr/todo.md` |
| Gauntlet law | `docs/fkr/GAUNTLET.md` |
| This Handover | `docs/fkr/HANDOVER.md` |

---

## 4. Current State (honest)

- Design fully reviewed section-by-section and locked.
- Formal design document and plan written.
- **No code has been written.**
- **No migration has been applied.**
- Gauntlet overall product score: **~28** (design-complete only).

---

## 5. Constraints (non-negotiable)

- Reads flow. Writes wait.
- No Drive / Notion / Canon / n8n / production writes without current-session explicit authorization.
- Prefer propose, review, authorize before any side-effect.
- Keep pure-semantic path alive until callers are migrated.
- Mock providers must remain clearly labelled.
- No em dashes in deliverables.

---

## 6. Immediate Next Actions (when authorized)

1. Authorize the plan (or request changes).
2. Start **Phase 1 / Task 1** - write the Alembic migration (propose the file, wait for approval before applying or committing).
3. Proceed task-by-task with human checkpoints after each phase.

Suggested authorization phrases:
- authorize plan
- start Phase 1
- begin Task 1

---

**End of Handover**
Generated 2026-08-14. Design is locked. Implementation has not started. Gauntlet standard applies.
