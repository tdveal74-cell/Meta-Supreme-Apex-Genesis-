# Universal 90/100 — TSWS source and rubric crosswalk

**Date:** 2026-10-19. **Scope:** Connected Google Drive source inspection and repository-level staging only. **Status:** Evidence inventory; no Drive document edited, no canon changed, no production script or QC workflow updated.

## Most relevant source files read

| Source | Drive reference | Role / condition |
|---|---|---|
| Series Bible v2.16 (2026-10-18) | [Current series bible](https://drive.google.com/file/d/1gsReJ_sPSrWIt-PB4uOZnWLmQNNaoPQ3/view) | Current authoritative story/canon context, still preserving the Utterance Release Gate and locked text |
| TSWS Script Doctor skill | [Skill document](https://drive.google.com/file/d/1Gg4qGBDOIXGYsKHYOcQnmpdFqGPNOumJ/view) | Diagnostic skill with 1–5 scores for individual voice/character analysis; routes a ship verdict to the dedicated gate |
| TSWS Script Writer skill | [Skill document](https://drive.google.com/file/d/1AnCPbpDsxMic-Doby7xMEqcb7LfLxvQj/view) | Writer/canon/mechanical validation instructions; separate from a 0–100 quality acceptance verdict |
| TSWS Flagship Graph Loop v2.1 | [Graph-loop text](https://drive.google.com/file/d/1x2PSfBxpXbyPc52gfPqpzNJBU-L7YII4/view) | Older 0–18 scored A/B tracks with a historical **15+ / 18** render-eligibility condition and independent G5 integration pass |
| QC and Script Doctor packet (2026-09-30) | [Historical QC packet](https://drive.google.com/file/d/1yam3fq2uyXMbC-wQ-NvZcEZIDXRbpLOq/view) | Explicitly says **99/100** for TSWS composite; historic TQO/NCO 80 and distinct verdict enums; **now superseded only for the numeric acceptance floor** |
| DEVON bot QC prompt v1 (2026-09-23) | [Historical bot prompts](https://drive.google.com/file/d/1D3PghtjBgtR9Os0gCU6EP5g09IfeEc51/view) | Documents older 70 doctor / 80 episode floors; must not be treated as the current active policy |

## Findings and score classifications

**1. A 99/100 final TSWS composite is confirmed in the historical QC packet.**
The new 2026-10-19 user ruling supersedes **that numeric minimum** with **90/100** for new reviews. The same packet's remaining hard requirements survive: valid scoring coverage, no unresolved high/critical or P0/P1, exact final artifact hash, consent, format/canon and independent reviewer, and human release permission. Do not rewrite the historical packet or claim it currently runs live.

**2. The graph loop's 15/18 threshold needs a separate scoring crosswalk.**
The graph loop explicitly marks an intermediate A/B track render-eligible at **15 of 18** plus an integration gate. 15/18 is 83.33%. For any 0–18 score used as a *quality acceptance threshold*, the new 90% floor requires **17 of 18** (16/18 = 88.89%, 17/18 = 94.44%). However, the graph-loop is both an older creative-stage mechanism and a canon-sensitive source. Do not silently change its gates: verify current production ownership, the current canon hierarchy, and whether the intermediate track score is classified as *quality acceptance* before replacing 15 with 17. The separate 90/100 final approval is mandatory regardless.

**3. The Script Doctor's 1–5 diagnostic grades must not be treated as publication scores.**
That skill describes diagnostic rather than final-ship judgments. Preserve the profile-specific diagnostics and the rich TSWS voice canon. The universal 90 rule applies when a review is converted into a formal acceptance result, not by renaming a diagnostic 4/5 grade as an approved 90.

**4. The v2.16 story bible remains unchanged.**
Its locked source/consent/utterance release requirements are non-numeric hard rules. The quality-floor change does not rewrite the locked long-form scripts or the newer micro-drama form.

## Staged code and tests

- `n8n/tqo-v5/slop-curator/scaled_acceptance_floor.mjs` provides a deterministic, integer-only 90% numeric crosswalk for a score explicitly declared to be an **acceptance** score; returns `MEETS_NUMERIC_FLOOR_ONLY`, never SHIP or authorization.
- `scaled_acceptance_floor.test.mjs` checks 89/100, 90/100, 15/18, 16/18, 17/18, missing/non-numeric scores and diagnostic versus acceptance distinctions.
- This module does **not** make a final TSWS score or authenticate canon, scripts, sources or real reviewers. Its output must be combined with TSWS-specific hard canon checks, the independent public-key verification boundary and human approval.

## Live integration still open

1. Identify the current installed TSWS writer/Doctor/Gauntlet skill versions actually invoked by the active render/editorial host; older Drive files may not be the executing source.
2. Record effective gate priorities and the newer v2.16 canon before modifying creative-stage thresholds.
3. Implement the universal **90/100 final acceptance** score and if appropriate **17/18 creative-stage acceptance** on a separately versioned policy overlay, never altering locked source text in place.
4. Prove 89/90, stale hash, unsigned canon, P0/P1 and consent controls with readback and no-spend tests.
5. Obtain an independently signed review receipt and separately approved live deployment before reporting runtime completion.

This audit resolves **source identification**, not production acceptance migration or publication authority.
