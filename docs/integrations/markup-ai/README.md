# Markup AI editorial preflight (draft)

Status: **review only, not deployed**. Owner: DEVON editorial quality workflow.
Last reviewed: 2026-10-19.

## Purpose

A separate, non-authoritative content-checking layer for TQO and, later, other brands. It does not publish, approve, spend, change n8n workflows or certify factual truth.

Source of truth: approved research receipts and current brand rulings, then the existing Script Doctor, QC, disclosure, rights and authenticated human approval. Markup AI is not a replacement for any existing gate.

## Current blocker

The Markup AI connection returns HTTP 403: `Authentication token is not associated with an organization`. This was reproduced on organization-config discovery on 2026-10-19. No actual Markup AI review/profile configuration has been verified. An authorized organization member must connect/reauthorize the account before a live pilot.

## TQO first

Use `TQO_RULES.md` as a proposed voice/terminology/style configuration. Exact Markup AI profile and guide identifiers must be discovered after authentication, not guessed.

Proposed fixed review agents (subject to organization entitlements): `brand_voice`, `terminology`, `sentence_clarity`, `ai_voice_detector`, `generic_claims`, `source_authority`, `style_agent`. Store the exact requested/completed agent sets, warnings, issue ranges, source receipt IDs, content SHA-256, rule version and human-review state.

Advisory statuses: `NOT_RUN`, `INCOMPLETE`, `EDITORIAL_ISSUES`, `EDITORIAL_CLEAR`. A missing or failed agent, missing expected profile or response warning is INCOMPLETE. A clean result means editorial clear ONLY, never release eligible.

## Quality threshold reconciliation required

Tee ruled **TQO Script Doctor >=90/100 on 2026-10-19**. TSWS remains **>=99/100**. The checked-in `n8n/tqo-v5/compliance/qc_doctor_gate.js` was read on 2026-10-19 and still contained `DOCTOR_FLOOR = 70`. This is an unresolved repo-versus-ruling mismatch. It is NOT proof of the live n8n setting. Before changing any gate, read the active workflow and its current tests and obtain human review.

Markup AI scores MUST NOT be substituted for the Script Doctor score. All original hard gates remain in effect.

## Planned integration, not activated

1. Resolve organization authentication with the account owner.
2. Set up the brand voice, style guide, terminology and target persona using the approved TQO rules.
3. Discover and read back exact Markup AI profile IDs and available checks.
4. Run synthetic test input and verify each agent result and warning.
5. Run held-out drafts with source receipts; compare to Script Doctor without relaxing the latter.
6. Introduce a read-only advisory call into DEVON behind a feature flag only after change authorization.
7. Test negative-path auth failures, incomplete returns, no evidence, profile mismatch, and withheld human approval.
8. Require the normal production QC, disclosure and authenticated approval before publication.

## Guardrails

Never store credentials, provider tokens or raw sensitive content in this repository or n8n execution logs. Do not send unapproved private scripts to a third-party review service. Do not fabricate a personal test, a statistic, a date or a source. No automatic rewrite of unsupported claims as proven facts. No release state is emitted by this integration.

## Related source files

- `services/devon/persona.py`
- `services/devon/tqo_canon.py`
- `n8n/tqo-v5/build_script_prompt.js`
- `n8n/tqo-v5/compliance/qc_doctor_gate.js`
- `sites/tqohq/check.mjs`

This document and `review_adapter.py` are offline scaffolding only. No connector calls or workflow edges are introduced by this PR.
