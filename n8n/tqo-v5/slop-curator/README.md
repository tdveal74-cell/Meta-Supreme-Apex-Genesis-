# TQO Slop Curator preflight (staged, not deployed)

**Ruling, 2026-10-19:** The Quiet Operator acceptance threshold is **90/100**, replacing the earlier 99/100 ambition for TQO scripts. This ruling does **not** change The Shadow We Share's separate, locked 99/100 gate or NCO Forge's existing thresholds.

## Objective

Review The Quiet Operator's script for generic AI-writing patterns *without* deleting the writer's cadence or fabricating personal experience, then submit the exact final script to the existing Script Doctor, deterministic Sources Gate, Script Gate: Quality, originality checks, QC and authenticated human review. Passing the curator must never automatically publish or purchase narration, video or image generation.

The installed Slop Curator Skill route for this request is:
`slop-audit -> voice-preserving-edit -> slop-pattern-repair -> strict-human-output (TQO rules only) -> slop-quality-gate`.
Default Slop Curator quality guidance is not the controlling number: TQO has explicitly requested 90.

## Current repository mismatch

The Oct 19 read of `n8n/tqo-v5/exports/qEkGOUsNyVaRAmm6_active.json` found `Script Gate: Quality` with `DOCTOR_FLOOR = 70`. The existing patched `n8n/tqo-v5/compliance/qc_doctor_gate.js` also has `DOCTOR_FLOOR = 70`. **Both** must use TQO-specific 90 when actually wired. Do not change the NCO floor inadvertently and do not touch TSWS's 99 gate.

Important: `Script: Short After Doctor?` can trigger `Expand After Doctor`, producing a final script that differs from the text the Doctor scored. A final-script 90/100 receipt must be tied to the actual output of `Script: Final Text`. Rerun the Doctor when expansion changes the text; never bind an earlier score to new wording.

Existing mirror/export consistency is covered by `n8n/tqo-v5/compliance/compliance.test.mjs` and `replacements.json`. Patch both mechanisms together, add 89/90 boundary tests, and verify mirror equality before any live workflow deployment. This staging branch intentionally leaves the active export and the pinned compliance mirror unchanged.

## Testable preflight

`tqo_curator_gate.mjs` is an offline, fail-closed decision helper. Run its tests with:

```sh
node --test n8n/tqo-v5/slop-curator/tqo_curator_gate.test.mjs
```

It requires:
1. Exact final script and its **trusted SHA-256**, computed in orchestration, not hallucinated by an LLM
2. A Slop Curator assessment attached to that hash, with numeric score >= 90, `PASS`, no hard failures, and explicit factual/voice/constraint verification
3. A Script Doctor assessment of that exact hash, with numeric score >= 90 and `PASS` or `REPAIRED`
4. A **separate** verified provenance receipt for the same final draft
5. Local TQO hard-style check for banned terms, retired audit CTA, em/en dashes, and semicolons

Repetitive binary reframes are **review flags**, not automatically forbidden occurrences. The validator never edits the script. It returns only `HOLD` or `READY_FOR_EXISTING_GATES`, never release approval.

**Trust boundary:** The helper now recomputes SHA-256 against the exact script bytes it receives; a syntactically valid but incorrect hash is a HOLD. The `editorial`, `scriptDoctor`, and `evidenceReceipt` objects are still supplied inputs, **not authenticated assertions**. In particular, `evidenceReceipt.verified: true` must be populated only by a trusted provenance-verifier adapter, never from an LLM response or a publisher-supplied flag. Do not connect this module to live release routing without implementing that trust boundary.

**Observed offline test:** 2026-10-19, on `srv1936199`, the branch copies of the gate and tests passed 8/8 using `node --test`. CI now runs the same test as a required `standalone` step on this PR. This is isolated preflight evidence only, not proof of live n8n wiring or of model evaluation quality.

The editorial fields are *reported judgments*, not deterministic proof of authorship or factual correctness. The source receipt and existing mechanical checks are independent. A model-assigned score can be wrong: run a second judge or human inspection for disputed findings; retain the evidence rather than silently overriding hard failures.

## Integration order, not yet executed

1. Freeze the input, approved sources, TQO voice card, and existing Script Doctor rubric with version IDs
2. Run Slop Curator audit, minimal edit, and final gate; keep original text and diff
3. Compute the final SHA-256 in trusted code; ensure all reports are explicitly bound to that hash
4. Re-score the **final** text with Script Doctor, especially after any length-expansion node
5. Apply the TQO-only 90 point floor in both script and downstream QC nodes, without weakening the existing Sources Gate, originality gate or human approval
6. Run held-out tests: 89 fails, 90 passes only when other criteria pass, stale hashes fail, missing sources fail, NCO and TSWS remain unchanged
7. Compare proposed workflow against the pinned export, deploy only after review, run a no-spend smoke check and read back the active version

**Not yet done:** The Slop Curator Plugin is available to ChatGPT, but this file does not give n8n permission or an API to call it. The automatic evaluator/adapter and actual n8n wiring require their own implemented transport and verified receipt generation. No changes to live n8n, publication, credit spend, human approval, or existing scripts have been made by this staged addition.
