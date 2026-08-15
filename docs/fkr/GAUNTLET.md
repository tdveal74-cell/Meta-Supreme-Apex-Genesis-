# Gauntlet Law - Federated Knowledge Retrieval (FKR)

**Status:** Operating law  
**Stream:** Meta-Supreme-Apex-Genesis- (evolve-in-place knowledge subsystem)  
**Date:** 2026-08-14

## The rule

1. **Flagship is the floor.** Honesty marks, labelled mocks, human gates, closed claims.
2. **99 gauntlet is mandatory.** Design locked is not shipped. Shipped means verified pipeline under operator use.
3. **Never fabricate.** Unverified beats invention. A claim that retrieval works is itself a finding that must be checked.
4. **Rulings beat rules.** Tee decides production deploy, connector activation, and any write to Drive / Notion / n8n / live base.
5. **Reads flow. Writes wait.** Propose migration and code. Do not apply or push side effects without current-session authorization.
6. **No em dashes** in deliverables.
7. **Pure-semantic path stays alive** until callers are migrated. Mock providers stay labelled.

## What FKR is

Five-stage Cerebras-style knowledge system inside Meta Supreme:

1. Ingestion  
2. Contextual distillation  
3. Unified storage (Postgres + pgvector, narrow waist on embeddings)  
4. Hybrid 4-signal retrieval (dense + sparse/BM25 + IDF/fluff + age-decay), RRF k=60  
5. Synthesis and governance (re-rank, ACL gate, cited answer)

## Living scores (honest)

| Surface | Score | Note |
|---------|-------|------|
| Design spec (locked) | ~94 | Section-reviewed, decisions recorded |
| Implementation plan | ~92 | Phased, human checkpoints |
| Task checklist | ~90 | Clear acceptance criteria |
| Code / migrations | **0** | None written |
| Hybrid retrieve | **0** | Not built |
| Ingest path | **0** | Not built |
| Synthesis / citations | **0** | Not built |
| Live connector writes | **0** | Explicitly blocked until authorized |
| **Overall (product)** | **~28** | Design-complete, implementation not started |

## Path to 99

| Gate | Required |
|------|----------|
| Phase 1 | Alembic + models; existing knowledge tests still pass |
| Phase 2 | RRF unit tests + hybrid_retrieve on seeded data |
| Phase 3 | Distill + ingest; retrieve same doc immediately |
| Phase 4 | Re-rank + synthesize with citations; sample answers reviewed by Tee |
| Phase 5 | Regression suite + operator notes |
| Production | Explicit Tee authorization before deploy or connector activation |

## Pass condition

Would Tee trust FKR answers over opening Drive and Notion himself, with citations he can verify, under his ACL, without fabricated history?

If no, continue the loop.

## Standing constraints

- Target repo only: `Meta-Supreme-Apex-Genesis-`
- Live base / Drive / Notion / n8n: no writes without current-session explicit OK
- Empty `acl_tokens` must preserve current ownership behaviour
- Back-fill is additive, not a big-bang rewrite
