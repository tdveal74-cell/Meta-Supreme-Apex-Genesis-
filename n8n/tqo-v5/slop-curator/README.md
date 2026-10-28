# TQO Slop Curator preflight (staged, not deployed)

**Superseding ruling, 2026-10-19:** Tee requires **90/100 acceptance across the entire ecosystem**, including TQO, NCO Forge, TSWS, ACX, EditForge, WhatBroke and DEVON. Previous 99/100 TSWS and 70/80/99 numerical acceptance floors are superseded for new quality assessments. See `docs/devon/SYS_POLICY_ecosystem-quality-90_2026-10-19.md`. Canon, provenance, hard blockers and authenticated approval are unchanged.

## Objective

Review The Quiet Operator's script for generic AI-writing patterns *without* deleting the writer's cadence or fabricating personal experience, then submit the exact final script to the existing Script Doctor, deterministic Sources Gate, Script Gate: Quality, originality checks, QC and authenticated human review. Passing the curator must never automatically publish or purchase narration, video or image generation.

The installed Slop Curator Skill route for this request is:
`slop-audit -> voice-preserving-edit -> slop-pattern-repair -> strict-human-output (TQO rules only) -> slop-quality-gate`.
Default Slop Curator quality guidance is not the controlling number: the ecosystem-wide acceptance floor is 90.

## Current repository mismatch

The Oct 19 pinned V5 export contained **70** in Script Gate, **80** in Parse QC, and TSWS-specific **99** in the historical QC gate. The staged candidate sets **90** in all three quality checks for all brands, and blocks the OS 28 publishing gate until signed final-text review. It uses the updated compliance QC and publish mirrors. Its signed-review hold remains active until independently verified evidence is wired.

Important: `Script: Short After Doctor?` can trigger `Expand After Doctor`, producing a final script that differs from the text the Doctor scored. A final-script 90/100 receipt must be tied to the actual output of `Script: Final Text`. Rerun the Doctor when expansion changes the text; never bind an earlier score to new wording.

Mirror/export consistency is covered by `n8n/tqo-v5/compliance/compliance.test.mjs` and `replacements.json`. The pinned original export is unchanged; the compliance mirror and corresponding replacement ledger **are updated together** in this staging PR. Verify equality, test 89/90 across brands, and read back live state before any deployment.

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
5. Apply the universal 90 point floor in Script Doctor, Parse QC and downstream QC nodes, without weakening the existing Sources Gate, originality gate or human approval
6. Run held-out tests: 89 fails for every brand, 90 meets only the score floor, stale hashes and missing sources fail; NCO and TSWS retain canon and human approval requirements
7. Compare proposed workflow against the pinned export, deploy only after review, run a no-spend smoke check and read back the active version

**Not yet done:** The Slop Curator Plugin is available to ChatGPT, but this file does not give n8n permission or an API to call it. The automatic evaluator/adapter and actual n8n wiring require their own implemented transport and verified receipt generation. No changes to live n8n, publication, credit spend, human approval, or existing scripts have been made by this staged addition.

## October 19 continuation: tested candidate and ChatGPT handoff

### 90-point n8n candidate (NOT ACTIVE)

`tqo90_workflow_candidate.mjs` (legacy filename, now `buildUniversal90Candidate`) no longer patches anything. The 90 floors are live in the re-exported V5 workflow, and on 2026-10-28 the owner ruled "Drop the AI review from the publish gate", so no signed AI review receipt is required and nothing is held for a pending review adapter. The function asserts that the four live node bodies still carry the 90 anchors, throws on drift, and returns the export unchanged. It does not call the n8n API.

- `Script Gate: Quality`: script doctor floor **90** for TQO and NCO; a 90 clears with no receipt.
- `Parse QC + Set Verdict`: **90** for the episode QC score.
- `QC Doctor Gate`: **90** for every scored scope; a doctor line of 90 or more reaches `READY_FOR_HUMAN_REVIEW` with no receipt, and a doctor score under 90 holds.
- `OS 28: Publish Gate`: QC **90** with no `WAIVED` bypass, and the human approval must read `approved:<sha256 of the script>`.
- Candidate tests execute all four live node bodies with synthetic rows. **89 does not clear**; **90 clears** with the script hash approval and no AI receipt.
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
5. Generate a candidate export from the readback version, prove 89/90 boundaries for all brands, compare original and candidate node IDs/connections/credentials, and run compliance and source-gate suites.
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

**Universal applicability:** The TQO Slop Curator reviewer packet and banned-word lint stay TQO-specific. The score is universally 90, but other brands need their own approved voice, canon, source and verifier adapters before live use. Do not apply TQO-specific vocabulary bans to TSWS, NCO or ACX.
