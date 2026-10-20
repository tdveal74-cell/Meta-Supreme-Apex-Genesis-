# Universal 90 — production n8n readback and drift-safe candidate
DATE: 2026-10-19
SCOPE: read-only n8n inspection, no-spend offline validation
OWNER: Tee
STATUS: STAGED AND TESTED, NOT DEPLOYED

## Source of truth inspected
- Device: `srv1936193` (n8n container `n8n-n8n-1`), via authorized Desktop Commander.
- Actual live workflow ID: `qEkGOUsNyVaRAmm6`, name `TQO FINAL V5`, **active=true**.
- n8n-reported updatedAt: `2026-10-19T04:02:42.508Z`.
- 274 nodes.
- Two read-only exports yielded byte-identical SHA-256:
  `ec92cddbaa5f2567640d129acfbe926a0f8ddd03df955eac75d0fb8d9e7ef629`.
- Captured live node code SHA-256 values:
  - `Script Gate: Quality`: `6facfceddc5527658592bc36937085f351f964303d66df98eb3885542297338c`
  - `Parse QC + Set Verdict`: `b1bc7bed4875a8b15a4498e8775d41a3e1a1b8ac1dd70579b674def24370c5ee`
  - `QC Doctor Gate`: `399723676ec88e5579310086a5161d2fbcdec602c0efd87eeee8fd13b9ccf568`
  - `OS 28: Publish Gate`: `89ae42797d233a3d01c83df64b1994393c48e3e4c95d02a9b3be53f6feba22e6`

These fingerprints concern the live workflow, **not** the older GitHub export. Do not use the older export as a production replacement.

## Actual live quality-policy differences
| Stage | What was observed in active n8n |
|---|---|
| Script Gate: Quality | TQO 90, NCO 99 |
| Parse QC + Set Verdict | TQO 90, NCO 99 |
| QC Doctor Gate | TSWS < 99 special rejection and episode high/critical marker below 85 |
| OS 28: Publish Gate | Accepts either `SHIP` or manual `WAIVED` as QC evidence |

The historical raw QC Doctor gate builds an episode report without a complete final-script report for its two required scopes. Until independent final-script receipts are integrated, this is an unresolved correctness blocker. A 90-point numeric update does not resolve it.

## Safe, live-specific correction
- `n8n/tqo-v5/slop-curator/live_v5_universal90_candidate.mjs` refuses any live input whose **raw export SHA-256** differs from the pinned readback. It also confirms the workflow ID, update time, active flag, node count and individual gate code hashes.
- It changes exactly four code bodies to a universal 90 score floor and removes the publishing `WAIVED` score escape.
- All four staged gates deliberately hold pending **independently verified final-script receipts**; scoring 100 does not authorize publication.
- The returned candidate is explicitly **inactive**, has **no production workflow ID**, and is named `DRAFT Universal 90 Gates - NOT FOR ACTIVATION`. Source data is not edited.
- Offline host run: **29 assertions passed** using real captured gate bodies, synthetic 89/90/100 inputs for TQO and NCO, receipt-required HOLD behavior and explicit `WAIVED` refusal.
- Verified unchanged: other **270 node JS code bodies**, workflow connections, settings and credential references; four new node bodies parsed.
- All smoke tests are offline. No paid provider calls, workflow imports, activation, published content, or live database writes took place.

## Other live n8n lanes inspected
Read-only exports on the same host:
- `TSWS V9` (`Ht8k7UefOqKhOEHM`), inactive, 72 nodes
- `TSWS 01 — Post-Production Master` (`UoJS8WDZfkVD9AVH`), active, 47 nodes
- `TSWS 06 Repair Orchestration DRAFT` (`BYAMD9YOT2jOb8sg`), inactive, 24 nodes
- `ACX Lane — The Critic` (`EpnWCVTzNlJnkvDk`), inactive, 5 nodes

A limited scan of JavaScript Code-node bodies for explicit numeric 70/80/85/90/99 quality checks returned zero matches in these four. **This does not establish that their narrative prompts, installed Skills or external services have been updated.** They remain unverified for live 90 acceptance.

## Existing nonproduction test workflows inspected
All were inactive and separate from live V5:
- `Tqo90Check261019A`: synthetic gate evaluation
- `Tqo90Hand261019A`: synthetic ChatGPT handoff validation
- `Tqo90Wait261019A`: manual wait/authentication smoke
- `Tqo90Table261019A`: isolated data-table roundtrip
- `Tqo90Draft261019A`: inactive workflow draft with production-like lanes

These represent useful component checks but do not constitute an independently authenticated verifier wired into live production.

## Still required for completion
1. Authorized separate final-script evidence verifier/signer with versioned canon and human-approval receipts, **not** model-controlled `verified=true`.
2. Proven n8n integration after script expansion, and proof direct row-status/WAIVED changes cannot evade quality gating.
3. Runtime inventories and acceptance tests for TSWS, ACX, EditForge, WhatBroke and DEVON independently owned lanes.
4. Compare and re-export active n8n before any patch, reject capture drift, retain rollback, review, approve deployment explicitly, run no-spend smoke, and perform active-state readback.
5. Leave PR #377 draft; track live closure under issue #380.

Historical records and actual workflow artifacts stay untouched.
