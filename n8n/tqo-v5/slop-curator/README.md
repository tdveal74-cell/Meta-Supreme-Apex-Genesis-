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

## October 19 continuation: tested candidate and ChatGPT handoff

### 90-point n8n candidate (NOT ACTIVE)

`tqo90_workflow_candidate.mjs` transforms a clone of the **pinned** 274-node V5 workflow in memory. It intentionally does not mutate the pinned live export, call the n8n API, or modify the active workflow.

- `Script Gate: Quality` reads Show Context: Script; **TQO 90**, NCO **70**.
- `QC Doctor Gate` is based on the previously tested compliance mirror; **TQO 90**, NCO **70**.
- The candidate tests execute both actual patched node bodies with synthetic rows: 89 fails the TQO score floor, and even a score of 90 or 100 **stays on HOLD** until the signed review adapter is wired; NCO's existing 69/70 boundary remains unchanged. They verify that only those two node bodies change.
- These checks cover the score boundary and the provisional fail-closed hold **only**. The current QC code reads a text score-history line, not an authenticated final-draft hash. Do not deploy this candidate without the additional signed review intake and a final-text Doctor score. A manually changed Airtable status can bypass today's script gate and must not bypass the downstream receipt requirement.

### Review handoff (NO PAID MODEL CALL FROM n8n)

`chatgpt_review_handoff.mjs` provides two pure functions:

1. `prepareChatgptReviewHandoff`: freezes a TQO script together with its SHA-256, versioned voice card, Script Doctor rubric, and approved-source references; returns `AWAITING_CHATGPT_REVIEW`.
2. `verifySignedChatgptReview`: requires an HMAC-SHA256-signed independent verifier return for the **same exact script and packet**; then invokes the staged curator 90-point gate. Invalid/missing secrets or signatures, changed drafts, absent evidence and below-90 reviews stay `HOLD`. Passing can reach only `READY_FOR_EXISTING_GATES`, never `RELEASE_ELIGIBLE`.

**Critical:** The signer is not implemented here. Only an authorized trusted host can sign after independently reading the actual ChatGPT Slop Curator findings, re-running Script Doctor on the final text, and validating source provenance. Never sign directly from the model output, never accept a signature supplied by a draft writer, never store the signing secret in GitHub, ChatGPT, a prompt, or an Airtable record. The test secret is a synthetic fixture. This code does not supply access to installed ChatGPT Skills from n8n.

### Safe activation plan

1. Pin and read back the current n8n V5 export. Confirm existing source provenance and quality reporting; abort on any live drift.
2. Install the handoff as an explicit **manual review** task with a durable pending state, not a hidden model-to-model call.
3. Implement a trusted verifier/signing boundary and a zero-spend intake that checks packet hash, independent evidence, Script Doctor and curator receipts. Bind accepted receipts to the final stored script SHA-256, not row ID or timestamp.
4. Put that trusted receipt check in BOTH the script lane and the downstream QC lane, before any status promotion. Validate manual status changes cannot evade this check.
5. Generate a candidate export from the readback version, prove the 89/90 and 69/70 cases, compare original and candidate node IDs/connections/credentials, and run compliance and source-gate suites.
6. Separately approve any live deployment after the new signed handoff is complete. Run read-only/no-spend test traffic, read back the deployed workflow, and keep a rollback export.
7. Human approval remains mandatory. This PR does not authorize narration, rendering, thumbnails, distribution, payments or publication.

**No automatic deployment or publication should occur while the signer and final-text wiring are absent.**

### Offline operator command (staged)

The new `review_handoff_cli.mjs` can create a private, non-overwriting review packet file from a JSON input containing the final script, voice/rubric IDs and source references. It prints **only** the packet ID and SHA-256, never script text. `verify` needs `TQO_REVIEW_SIGNING_SECRET` supplied by an authorized host at runtime and prints a safe HOLD/READY result without any script text. No `sign` operation exists in this CLI.

```sh
node n8n/tqo-v5/slop-curator/review_handoff_cli.mjs prepare final-input.json private-review-packet.json
node n8n/tqo-v5/slop-curator/review_handoff_cli.mjs verify private-review-packet.json trusted-signed-return.json
```

The second command **does not pass** unless an authorized signer has already returned a valid attestation and the signing key is securely injected. Never run `verify` from an untrusted workflow that can control the HMAC key, and never treat an unsigned ChatGPT reply as an approved receipt. Do not copy private review packets into public logs or issues.
