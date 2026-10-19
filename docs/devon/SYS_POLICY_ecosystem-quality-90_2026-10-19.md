# Ecosystem Quality Acceptance: Universal 90/100 (Ruling 2026-10-19)

**Owner:** Tee. **Status:** authoritative quality-floor ruling, staged source implementation. **No claim of live deployment.**

Tee superseded all earlier brand-specific numeric quality acceptance floors with **90 out of 100**, effective as the governing policy for new reviews and future production changes.

## In scope

- **The Quiet Operator (TQO):** scripts, video/editorial output, Script Doctor, Slop Curator, QC and other scored deliverables
- **NCO Forge:** scripts, videos, QC and derivative content
- **The Shadow We Share (TSWS):** scripts, dialogue, continuity, visuals, shot QC, animation/editing, episode acceptance; previous numeric 99/100 floor superseded
- **ACX:** script, visual and editorial acceptance
- **EditForge / EditForge Digital:** software deliverables, media output, tools, manuals and product QC
- **WhatBroke:** troubleshooting articles, software/product outputs, editorial and verification
- **DEVON / Meta Supreme X:** cross-model audits and qualifying quality assessments
- **Other ecosystem brands and future work:** same scored acceptance floor unless Tee explicitly changes it

For a **0-100 quality or acceptance score**: **89 = FAIL/REVISE/HOLD**; **90 = meets the numeric floor only**; 90-100 can advance to the next existing gate if all other requirements pass. Never round 89 up. Missing scores fail closed; unsupported decimal or string coercion cannot create a pass.

## Never change these when applying the 90 score ruling

1. **Hard constraints remain hard:** canon, locked text/shot rules, voice, brand isolation, evidence/source provenance, factual integrity, required disclosures, critical/high defect blockers, security and accessibility requirements.
2. **Human approval and publication are separate:** no quality score automatically authorizes spending, generation, merging, deploying, publishing or charging a payment method.
3. **Scores must belong to exact final artifacts:** trusted SHA-256 of finalized content, freshness after edits/expansions, independently verified evidence, reviewer identity and rubric/version.
4. **No mechanical cross-brand voice editing:** TQO banned words are NOT automatically banned for TSWS or NCO Forge. Each project's canon and voice rules remain specific.
5. **Do not reinterpret unrelated numbers:** rhythm/similarity heuristic scores, API confidence, VAD thresholds, benchmark targets, frame time limits, word counts, costs and statistical percentages are not acceptance scores just because they use numeric thresholds.
6. **Do not rewrite historical decisions or previously locked artifacts.** Preserve the original record and attach a superseding quality-policy version for new review.

## Implementation inventory and migration

| Area | Old floor | Target | State at this PR |
|---|---:|---:|---|
| DEVON cross-model audit (root and soul source mirrors) | 99 | **90** | source changed, not deployed |
| TQO Slop Curator gate | 90 | **90** | staged fail-closed, no live adapter |
| Shared n8n V5 Script Gate: Quality (TQO/NCO) | 70 | **90** | three-node offline candidate only |
| Shared n8n V5 Parse QC + Set Verdict (TQO/NCO) | 80 | **90** | three-node offline candidate only |
| Shared V5 QC Doctor Gate | 70 doctor / 85 episode / 99 TSWS special | **90 for every scored scope** | compliance mirror and replacement ledger updated; candidate holds pending trusted final-text review |
| TSWS editorial/visual/manual QC not in the shared V5 runtime | 99 historically | **90** | policy ruling, must be propagated to each separate runtime/rubric after inventory |
| ACX, EditForge, WhatBroke and other independent workflows | various/unknown | **90** | policy ruling, runtime changes not assumed |

## Verification and activation

- The pinned, previously exported V5 workflow is deliberately unchanged in Git history.
- The updated offline candidate patches the **three** production-facing score bodies in a clone and **blocks all brands** from advancing through these paths until a trusted exact-final-script review/verifier is implemented.
- The compliance mirror is reconstructed with pinned `replacements.json` and verified by `compliance.test.mjs` including brand-specific 89/90 checks.
- DEVON source and deploy mirrors remain byte-identical; independent verification evidence and hashes are still necessary.
- The ChatGPT packet/handoff CLI is currently TQO-specific. Its **90 number** is universal, but **other brand-specific reviewer adapters are not yet implemented**. Do not counterfeit or auto-sign a receipt to bypass this gap.
- Promotion requires CI success on the **latest head**, an authorized live workflow readback, migration/rollback snapshot, no-spend test, and explicit human approval for deployment. A passing score alone never releases content.

This document supersedes prior numeric threshold rulings only. All other canon and operational rulings remain intact.
