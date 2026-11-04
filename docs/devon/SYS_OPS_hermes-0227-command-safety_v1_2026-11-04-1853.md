# Hermes v0.22.7 command safety candidate

Status: isolated branch candidate, not a production update.
Supersedes: no earlier historical record; narrows the November 4 notification.

## Upstream receipt

Official v0.22.7 was published 2026-11-03T21:53:16Z at
b200f5bc60e31588ba2cb60e288029c4a54ba5fa.
Release: https://github.com/NousResearch/hermes-agent/releases/tag/v0.22.7
Approval design inputs: 8f6bb36594b797523c537c811d7767b909234d3d,
ad2b705b4995a958b0a795e9097be661e2d1ef63 and
74b2ed65e6564bfcafd29236e5fab2447a68fc76.
No upstream package is installed by this change. DEVON remains a custom runtime.

## Independently verified defects and changes

At base 22f249c75d2d120e03ba7d62d569508d323d9bbb the pure classifier returned
ungated for c${s:=url} and /usr/bin/cur[l] with curl upload flags. Hidden
bidirectional U+202E and supplementary variation selector U+E0100 also passed.
The independent verifier reproduced these without executing shell commands.

The candidate recognizes possible curl/wget program words using globs and
variable expansion, then applies the existing remote mutation rules. It refuses
hidden or bidirectional Unicode before parsing and before the presence window.
It preserves ordinary Unicode, supported emoji presentation, local/read policy,
source file bytes and all effect-bound operator approvals. It never executes a
command to classify it and changes no services/devon module.

The presence gate is not consent. A fresh human signal allowing a plain upload
is the existing explicit policy, not proof of upstream's approval-reuse bug.
Operator argv bindings and one-use approval consumption remain unchanged.

## Production evidence correction

At 2026-11-04T18:50:53Z the independent VPS read timed out against both Presence
and the API on TCP 443. The earlier Presence-only diagnosis is not established.
Reachability from this VPS is impaired; app failure, public ingress failure and
root cause remain unverified. No restart, route change or deploy is justified by
this check alone. Railway deployment state is not an HTTP health receipt.
A second server at 2026-11-04T18:57:32Z also could not reach either Railway
endpoint while self-hosted n8n health returned 200. This confirms reachability
failure from two servers without locating its cause.
The provider migration patch 0b5a7869-182d-49d0-b24d-6643ec8f0cda remains a
separate staged change and is not applied here.

## Validation and rollback

Before patching, 19 Unicode denial cases failed and 5 controls passed.
Before HTTP classification patching, 5 upload cases failed and 5 controls passed.
Targeted gate/operator/receipt check after the first patch: 1002 passed, 1 skipped.
Final full suite: 9701 passed, 3 skipped, 56 subtests passed, exit 0.
Standalone suite read from CI: 5834 passed, 1 skipped, exit 0.
Engine/security lane: 25 passed, 2 intentionally deselected, exit 0.
Repository ruff, container imports and Alembic upgrade/downgrade/upgrade passed.
Strict root/soul pip audits and pnpm audit found no known vulnerabilities.
Fresh critic reviewed 0300c03b1c7a1fb57c3d0c36df0908631789bfd4 in its own
worktree: 961 passed, 1 skipped. Removing the Unicode guard and reverting the
HTTP matcher in memory each restored the old failure. No blocking issue found.
The gate skip is the existing real-transcript fixture unavailable on this host.
The final record-only edit does not change the reviewed executable source.
Rollback is a revert of this isolated change; no credentials or schema change.

## Deferred design inputs

Per-skill locks, pre-inference hooks, child-transcript publication ordering,
scheduler cancellation/missed-run behavior and delivery idempotency require
separate DEVON contract work. They are not implemented or claimed by this patch.
Preserve the effect-free core, tenant isolation, human approvals and canon.
The canonical automation host remains https://n8n.editforge.online with n8n
Data Tables. Authenticated workflows and tables were not inspected in this arc.
No historic Cloud/Airtable record is evidence of their current wiring.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_hermes-0227-command-safety_v1_2026-11-04-1853.md
DATE: 2026-11-04
DECISIONS: Tee requested Update Devon; isolate compatibility work and preserve approvals.
FINDINGS: Independently reproduced obfuscated HTTP-client and hidden Unicode classification gaps.
OPEN: GitHub CI and review; provider migration and network diagnosis remain separate.
STATUS: candidate only; no merge or deployment performed
