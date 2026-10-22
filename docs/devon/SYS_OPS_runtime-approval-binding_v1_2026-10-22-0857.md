# Runtime approval binding hardening

## Boundary repaired

The capability boundary now compares the recomputed approval binding with the final authoritative marker appended by the runtime or conversation writer. Earlier text in the approval card can contain untrusted goals and arguments; a matching string inside that text is not approval authority. Approval consumption remains last, after identity, state, origin and exact argument checks. The effect handler cannot run on a rejected binding.

This is a narrow shared-governance correction, independent of the private browser client. It changes no tool risk class, canon, owner scope or approval decision route. Existing writers already append the authoritative marker as their final token.

## Verification

A fresh isolated reviewer verified the generic fix without the new browser client:25 focused generic/approval/council/wiring tests passed. The separate browser candidate was also checked with an injected earlier marker: the substituted action was refused before a worker request or approval consumption; the original approved action ran exactly once and a replay refused. Restoring the old substring comparison made all4 new marker regressions fail. The source was restored. All actions used doubles; no live browser or provider action ran.

Final full validation and exact-head CI remain required before merge. A merge is not a backend deployment, and Railway's Hobby builds remain paused in the official08:44UTC incident update onOctober22. No new production browser or computer is enabled by this fix.

## Rollback and follow-up

Reverting this correction would restore the weaker comparison. If rollout has a compatibility problem, disable the affected effect capability while reviewing its approval record format; do not silently relax exact argument binding. The dedicated browser worker, owner binding and Railway-to-VPS transport remain separate implementation work. A client contract is not a provisioned computer.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_runtime-approval-binding_v1_2026-10-22-0857.md
DATE: 2026-10-22
DECISIONS: Only the final authoritative runtime binding grants authority for exact effect arguments.
FINDINGS: Incidental binding text in an approval card must not authorize a substituted action; independent regression confirmed the correction.
OPEN: Full validation, exact-head CI, backend deployment; private browser worker and topology are not delivered.
STATUS: source correction independently verified; production deployment incomplete
