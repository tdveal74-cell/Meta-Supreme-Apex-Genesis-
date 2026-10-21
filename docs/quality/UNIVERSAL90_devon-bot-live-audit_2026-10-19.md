# DEVON Bot QA/QC and Repurposing: Universal 90 Live Audit

DATE: 2026-10-19 (Eastern)
OWNER: Tee
STATUS: Verified READ-ONLY production evidence; offline correction tested, NOT deployed

> This is an independent technical evidence report, not a DEVON-issued operational receipt, a published artifact, or a release approval.

## Host and inventory

Authenticated read-only n8n inspection through Desktop Commander on `srv1936193` found **183 workflows, 56 active**. A scoped quality-threshold search found **four active candidate workflows**. Two were already identified in the TQO V5 audit; the other two are DEVON-owned bot QC and repurpose workflows.

| Live workflow | ID | Active | Node count | Last-reported update |
|---|---|---|---:|---|
| DEVON - Bot QC Record | `MmFNWeewHEuG5x8T` | Yes | 8 | 2026-10-19 04:02:41 UTC |
| DEVON - Bot Handoff to Repurpose | `wXl6p7hKN74lKH0e` | Yes | 11 | 2026-10-19 04:02:44 UTC |

### Original live fingerprints

| Workflow | Export SHA-256 | Target node | Node code SHA-256 |
|---|---|---|---|
| Bot QC Record | `c44fc2796b15e521015e108a94f94e5f757e396f163278fddb14e518fa6ff22f` | Run Gate | `2f38bb3fdb1b96ece79ff521fdbd448c78650ef0d53231513bb0617269a53259` |
| Bot Handoff | `7fbf2c739ca2b4e3861f4c49a5c13563fed94071029f89e0f851a0d6f667bac5` | QC Gate | `4bb150ddaafb3610d4e82ba620254265b106e058ea0cd4c8b9fbc9bf96435779` |

The two active workflow bodies must be re-exported and fingerprint-checked immediately before any later deployment. These hashes are an observation of the captured source, not proof the production instance remains unchanged forever.

## Findings

- `DEVON - Bot QC Record / Run Gate` defaults to **Doctor 99 and QC ship 99** and overrides only The Quiet Operator to 90. TQO's newest ruling is now **universal 90 for every brand**; therefore TSWS, NCO Forge and ACX are out of alignment.
- `DEVON - Bot Handoff to Repurpose / QC Gate` trusts the latest script, QC and human-review records and states that the QC floor is **TQO 90, other brands 99**. It checks a local text fingerprint between QC and script, but that fingerprint is not cryptographic, and the handoff does not independently verify a signed final-artifact receipt.
- Its pending review proof must be bound to the exact final artifact and cannot be waived by a manually written passing QC row.
- No QC score threshold claim is made about unrelated active workflows without inspecting them.

## Tested, no-spend correction

`n8n/tqo-v5/slop-curator/live_devon_bot_universal90_candidate.mjs` accepts only the two pinned live export SHA-256 values and pinned target node-code SHA-256 values. It fails closed on drift, updates the default Doctor and QC threshold to **90 for all four registered brands**, and eliminates the brand-specific 99 override.

The candidate also deliberately **refuses to report passed script/QC/repurpose states until independent final-script evidence verification is wired**. It cannot clear even a score of 100 while the signer is missing. The output is **inactive**, has **no production workflow ID**, and preserves the complete original graph and credential references.

A local no-spend smoke execution on the actual captured workflows passed **64 assertions**, including:
- 89, 90 and 100 for each of four brands
- 89 failing the numerical floor
- 90 and 100 held because no real independently verified signed receipt exists
- a forged set of three `passed=true` stage records unable to release repurposing
- exactly one changed Code node per workflow and unchanged node counts, graph, settings and credential references
- both patched JS node bodies parsing

There were **no live database writes, workflow imports, activation, media generation, publication, or paid provider calls**.

## Additional active workflows to audit

This broad pattern scan identified `DEVON - Drive Draft Writer (Build 16)` (`FdQgiX2Thgk38CSa`) as an active candidate with a generic quality term. It has **not** been proven to enforce a 99-point numerical quality score and should not be changed without further inspection. The current search covers n8n workflow parameter strings, not external APIs, installed Skills or every connected application.

## Activation blockers

1. An authenticated independent reviewer and signer must produce source-verified, versioned receipts after final script expansion. A self-signed model flag is not an independent receipt.
2. A trusted consumer must check exact final artifact SHA-256, rubric, canon and evidence references. A writer-controlled `passed` field or QC override must not suffice.
3. The runtime workflow identity and export fingerprints must be re-read, a rollback retained, and the staged candidates compared to those fresh captures.
4. A separate human deployment authorization and no-spend smoke/readback are required. Production publication and paid generation have not been authorized.

Tracking: PR #377 for reviewed source, issue #380 for end-to-end live closure.
