# APEX Reliability Framework (ARF) Stage 1 — Shadow Policy Contract

Status: draft, local-only evaluation. Not installed, deployed, connected to production, or authorized to enforce tool effects.

## Source alignment

Read the live repository's `CLAUDE.md` and `AGENTS.md` before applying this patch. The draft was authored against a read of the `main` branch's `services/agent_runtime/{contracts.py,runtime.py,tools.py,verification.py}` and steward skill on 2026-10-19. It does NOT modify `services/devon`, `services/agent_runtime/runtime.py`, tool routing, receipts, or `ApprovalQueue`.

Keep existing invariants:

- DEVON core is effect free.
- All WRITE and HIGH_IMPACT tools require the existing human authorization mechanism.
- Orphaned effect intents must not be automatically replayed.
- A model's approval statements and task context are never authority.
- Verified tool-output bytes do not on their own prove semantic correctness, media quality, or successful publication.
- Human rulings, protected creative canon, real spending consent, and production publish/deploy approvals remain outside ARF's authority.

## New draft components

- `policies/reliability/profiles.v1.json`: seven domain profiles (DEVON, Meta Supreme X, TSWS, TQO, NCO Forge, EditForge, WhatBroke), split into build, review, and release gates.
- `services/agent_runtime/reliability/policy.py`: read-only strict loader. Configuration cannot remove pinned global, protected-domain, human-review, release or spending-related rules.
- `services/agent_runtime/reliability/contracts.py`: immutable source, evidence and decision interfaces.
- `services/agent_runtime/reliability/observer.py`: exactly one recommended intervention, no effects.
- `services/agent_runtime/reliability/adapter.py`: pure adapter for existing `RuntimeResult.task.to_dict()`.
- `tests/reliability/test_arf_shadow.py`: local contract and adversarial tests.

## Integration seam (illustrative only)

After an EXISTING authorized runtime call, a trusted application route or worker may run:

```python
from pathlib import Path
from services.agent_runtime.reliability import ReliabilityPolicy, observe_runtime_result

policy = ReliabilityPolicy.from_json(
    Path("policies/reliability/profiles.v1.json")
)
# `result` must be the actual RuntimeResult from the existing AgentRuntime,
# which retains complete ownership of whether any tool has run.
# `tenant_id`, `domain` and `workflow_stage` must come from authenticated
# app routing, NOT task.context or an LLM-provided plan.
# `real_evidence_source` must query authoritative records with tenant isolation:
# approval binding, leased effect intent + receipt, media/canon tests,
# independent readbacks, and human reviewer records.
shadow = observe_runtime_result(
    result,
    domain=trusted_domain,
    tenant_id=authenticated_tenant_id,
    workflow_stage=trusted_workflow_stage,  # build | review | release
    policy=policy,
    tool_registry=existing_runtime.tools,
    evidence_source=real_evidence_source,
)
# Store redacted shadow observations only in an approved logging surface.
# Never assign `shadow.verdict` to AgentTask.verification or task.state.
```

This sample does not implement the evidence source, a logging sink or an app route. The function takes a *pre-existing* RuntimeResult; it never initiates a task run.

## Evidence source: required independent implementation

`EvidenceSource.load(task_id, tenant_id, domain, workflow_stage, policy_digest)` must:

1. Enforce authenticated tenant ownership and privacy before querying anything.
2. Bind every verified gate to fresh and attributable evidence in trusted stores.
3. Bind each `approved_step_id` to the exact existing approval record and arguments, not just a name or request ID in a task payload.
4. Bind each `receipted_step_id` to durable matched intent + receipt, including lease fences and the correct effect arguments and idempotency scope.
5. Treat pending/ambiguous effects as unapproved for repetition; surface ambiguity separately.
6. Obtain reviewer approvals only from the human approval/production record, never the LLM.
7. Record the policy digest and provenance revision corresponding to the exact gate evaluations; invalidate stale attestations.
8. Return only redacted reference IDs. Never log approval tokens, secrets, full tool arguments, or private scene drafts.

An empty or disconnected evidence source must fail closed. Unit-test `Source` fixtures are intentionally fake and are **not** a production adapter.

## Trust and terminology

`WOULD_HOLD`: the candidate shadow record lacks one or more mandatory signals.
`IN_PROGRESS`: scoped gates appear present but current runtime is not completed.
`WOULD_BE_ELIGIBLE_FOR_CLOSURE`: the supplied authoritative reader (in tests, the fake fixture) attested every applicable gate and the runtime reports complete. It does not close the task, authorize effects, promote skills, publish artifacts, or replace human review.

Never translate any of these into `READY_FOR_PUBLISH`, `SHIPPED`, `PRODUCTION_GREEN`, or `VERIFIED` without the separate existing domain authority and real deployed-state readback.

## Important project-specific floors

- TQO Script Doctor: >=90/100 as of 2026-10-19, not inherited from TSWS.
- TSWS acceptance: 99/100 requirement remains separate; EP01 close-up override and protected material must not be silently rewritten.
- DEVON: existing runtime approval queue and effect recorders remain authoritative.
- NCO Forge: review military claims and lip sync; synthetic-media disclosure is a release gate.
- WhatBroke: reproduce the specific failure, retest the fix, and limit claims to tested environments.
- EditForge: require real spend approval on every protected paid render; shadow reports are not a spending authorization.
- Meta Supreme X: council synthesis never overrules an operator decision.

## Required held-out work before enforcement

- Confirm DEVON current runtime and production state at the intended implementation commit.
- Build the real `EvidenceSource` adapter and verify trust origins, credentials and tenant limits.
- Review the domain gate taxonomy and protected canon against the authoritative current files with Tee; the present definitions are draft labels.
- Add stable task lineage, equivalent-strategy retry fingerprint tracking and durable measurement of false-positive/false-block rates.
- Test negative security cases involving forgery, replay, tampering, out-of-order receipts, tenant leakage, stale evidence and false-positive completion.
- Add independent media decode/inspection and verified publication/deployment readback for domain release flows.
- Replay held-out traces in shadow mode, compare human reviewer decisions and record disagreements.
- Obtain operator authorization before GitHub PR creation if required by repository governance; never merge, deploy or publish without explicit permission.

## Rollback

The draft is additive. Do not enable automatic enforcement. To withdraw it, stop calling the post-run adapter and remove the new-only files. There is no DB migration, n8n workflow change, or existing state mutation in this patch.
