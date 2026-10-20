# Universal 90: Trusted review integration and closure runbook

**Date:** 2026-10-20. **Owner:** Tee. **Status:** staged/partly tested, not deployed. No private signing key, live signatory identity, or approval is created by this document.

## What is verified

- The policy source on PR #377 sets 90/100 for formal ecosystem quality acceptance. The staged V5 and DEVON bot candidate patchers use authenticated live-capture hashes and do not import into production.
- DEVON runtime readback on srv1936199 previously returned **QUALITY_THRESHOLD 99**, despite a staged source value of 90; it must not be described as deployed.
- On 2026-10-20 the offline `secure_review_intake.mjs` checks passed **2/2** with disposable Ed25519 test keys on srv1936193. A passing 90 remains `READY_FOR_EXISTING_GATES`, never `RELEASE_ELIGIBLE`. Temporary source copies were deleted after the test.
- The public-key verifier requires separate author, editorial-reviewer and evidence-verifier identities, score 90+, no hard or critical failures, source evidence and TSWS/ACX canon checks.
- The stricter intake also requires the precise final script/artifact text, a protected trust registry with permitted brand and policy, enabled unrevoked issuer key, time validity and a recent signed receipt.

These are offline assertions. Synthetic signatures do **not** establish independently verified source truth, reviewer authority, deployment or actual release eligibility.

## Trusted production architecture (required before enabling any candidate)

1. **Producer (n8n/DEVON):** after the *last* expansion or edit, materialize the immutable final artifact, compute SHA-256 from actual bytes, and reference versioned brand rules, rubric, canon and source evidence. Do not ask a model to invent the hash.
2. **Editorial reviewer (independent reviewer):** read the exact final artifact, inspect voice and brand-specific rules, and record a score/clear or revise verdict. A 90 meets only the numerical floor. The reviewer must not be the producer or evidence verifier.
3. **Evidence and canon verifier (different authenticated principal):** check each claim against source snapshots, recheck consent and required story canon, authenticate the editorial review, and issue a detached Ed25519 receipt for the exact packet. Its private key must live **outside n8n and the writer's execution environment**. Signing a model's self-reported boolean is not independent verification.
4. **Consumer (trusted verifier endpoint):** load a pre-approved public-key trust registry from protected host configuration; reject revoked/expired/unlisted keys and incorrect brand scope. Never take a trust registry, key, policy version, `verified=true`, or evidence-confirmed flag from a mutable n8n data row as authority. Require exact live final bytes and fresh signed receipt.
5. **n8n quality gates:** accept only the authenticated consumer's result, independently recomputed final artifact hash and hard gate results. No direct `Scripted` status edit, `WAIVED` value or stale Doctor score can bypass these checks. Keep a read-only record of the decision and return `HOLD` on missing API, timeout, bad signature or stale revision.
6. **Release and paid operations:** still require separate owner approval, consent and platform disclosure, and a no-spend acceptance test with readback before enabling publishing or generation.

**Important dependency:** The current `secure_review_intake.mjs` is a pure verifier. A caller-provided `trustRegistry` is safe **only if loaded by a protected independent consumer**, not from the workflow request. The protected consumer host, source-checking issuer, provisioning/revocation workflow and actual final-artifact storage binding do not yet exist here.

## Negative scenarios required for runtime acceptance

- **Score:** 89/100 fails; 90/100 meets the numeric threshold but cannot release by itself.
- **Artifact:** one changed byte or post-Doctor expansion makes old receipt invalid.
- **Evidence:** omitted source quote, missing source snapshot, unsupported personal test, expired evidence or changed evidence reference causes HOLD.
- **TSWS/ACX:** changed canon revision, missing consent, locked-line drift or an unresolved immersion-breaking P0 causes HOLD regardless of score.
- **Independence:** writer-issued/synthetic/self-signed receipt or same writer/editor/evidence-verifier identity fails.
- **Key trust:** unknown, revoked, disabled, out-of-scope, expired or rotated key fails.
- **Operational bypass:** direct data-table status `Scripted`, `QC Verdict=WAIVED`, direct publisher invocation, retry, and stale cached result all fail without valid receipt.
- **Network failure:** reviewer unavailable/timeouts produce HOLD with no spend.

## Live deployment sequence, requiring Tee's separate authorization

1. Resolve the independent signer and its authenticated source/canon checks; register a public trust anchor under least privilege and protect revocation updates.
2. Verify the signed intake using **current** data-table and final-artifact storage, and run negative tests against the actual transport and brand routing.
3. Re-export each active workflow, compare IDs/credentials/connection shapes against its documented fingerprint and fail on drift. Preserve rollback exports.
4. Deploy versioned routing changes on an inactive test workflow; no generation credentials or publishing outputs.
5. Run no-spend end-to-end 89/90, stale-hash, evidence and WAIVED bypass tests; require a different verifier to reproduce findings.
6. Present exact changes and a rollback plan for authenticated approval before altering active workflows.
7. Following approval, read back active workflow bodies and DEVON runtime, verify current SHA and effective quality score, and record a closure receipt for each lane under issue #380.

**Do not close issue #380** without every live lane's before/after state, independent review receipt, negative tests, no-spend verification and human authorization. Source CI green is necessary but not sufficient.
