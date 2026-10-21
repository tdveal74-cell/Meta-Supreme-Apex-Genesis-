# Devon RSI operator boundary and evidence contract

Date: 2026-10-21. Version: 1. This extends the bootstrap specification without
replacing its sealed suite, scorer, gates or predecessors. Tee authorized this
implementation, PR, merge and isolated deployment. Future candidate promotion
is not authorized by that implementation grant.

## Authority and capability

The immutable v1 release remains pinned to manifest
0af7ba74e0ca7537099f2040fde69fb4ef206ceaffa61569138a841c13c036b3.
The new tools/devon_rsi_ops package is trusted operator code outside the maker
surface. A maker still submits four allowlisted settings as data. It cannot
edit the operator, registry, database, case corpus, signer or release pin.
No new tool enters services/devon, and no live application or n8n workflow is
activated by this package. There is no promotion endpoint or private signer.

| Component | Reads | Writes | Authority |
|---|---|---|---|
| Candidate maker | Public sanitized schema | Candidate data | Propose only |
| v1 evaluator | Sealed public synthetic suite and candidate | Fresh decision and journal | Recommend only |
| Observer | Read-only fixture inbox and sealed evaluator | Private SQLite state, fresh fixture runs, status | Batch and queue only |
| External verifier | Independently managed sources and private blind suite | Signed freeze and trial receipts | Attest evidence only |
| Evidence importer | Operator public-key registry and signed evidence | Registered protocols, replay ledger, review records | Verify and record only |
| Human review | Exact artifact and recomputed decision | Signed recommendation review | Separate consequential authorization still required |

A cryptographic signature proves who made an assertion. It does not prove that
source facts are true, that a run happened, or that sessions were independent.
The external verifier is accountable for those claims. Tests generate keys
only inside test fixtures; deployment installs no signer and trusts no new key.
A copied producer identity or arbitrary session label is not independent
Canon review. This system cannot perform Canon promotion at all.

## Durable observation

The observer accepts exactly inbox/run/evaluation/decision.json and its sibling
journal. It checks the sealed release, journal head, exact final decision
binding and recomputes accepted per-case results. Repeated content is deduped,
including copied rejections. A decision is one observation, never fifty
independent samples. Fixture and operational streams never share windows.
Only twenty distinct observations form a window. Failed fixture windows can
start fixture search; operational windows only request review.

SQLite uses WAL, FULL synchronization and BEGIN IMMEDIATE. Search intent
commits before work. A crash leaves RUNNING, never automatically retried.
Completion and the deduplicated review outbox commit atomically under a
one-use token. Two starts per UTC day is a fixed ceiling across restarts.
The v1 search retains its 32-candidate, 256-evaluation and 60-second ceilings.
A successful fixture report remains gain_claim=false and promoted=false.

The database has append-only audit triggers and a hash chain. Retain audit
heads externally with deployment receipts: a privileged administrator can
rewrite both a database and an unanchored chain. Snapshot status is replaceable;
audits and predecessor run directories are retained. Input cap: 2,000 inbox
entries, 258 journal files per run, 64 KiB per JSON record, 100,000 audit events.
Capacity errors stop processing, never prune history. Status returns the most
recent 100 windows and experiments; window_count records the full total.

The continuously running observer has no network, capabilities, credentials,
Docker socket or vault mount. Only its state directory is writable. systemd
starts it after Docker on host boot; Restart=no leaves runtime failures for
operator inspection. A health.json operator snapshot can be mounted in the
read-only inbox. Health output reports unknowns, Reflection age, Canon growth,
disagreement count, blind-test result and whether a review was recorded in the
current calendar month. It never declares human review complete itself.

## Frozen live experiments

experiments.py defines strict protocol and attestation shapes. The independent
freeze binds producer/session, baseline, candidate, suite, scorer, three source
versions (Charter, Canon, Reflections), every case and critical flag, at least
20 distinct sample blocks, comparison count, and an expiry of at most 30 days.
Source observations must be within seven days before the freeze. Source refs
must identify operator exports on the enumerated HTTPS hosts; never embed
credentials, raw transcripts or private source text in the public repository.

Each trial attestation binds the protocol, block/sample hash, distinct control
and candidate run IDs, start/finish time and the complete identical case set,
including output hashes. Every critical failure or regression vetoes acceptance.
The unchanged v1 statistical test requires variance and applies the predeclared
comparison correction. Fixtures cannot establish admissible live evidence.

registry.py additionally requires durable registration before trial start.
An experiment ID cannot be replaced. The same baseline/candidate/suite/scorer
family cannot be re-registered under another ID to retry significance. The
first submitted outcome set consumes the experiment, including a failed or
incomplete set. Different replacements refuse. Run IDs cannot be recycled
across accepted experiments. Registry expiry/revocation is checked on replay.
A new replication policy would require independent upstream review, not a
candidate edit or database reset.

Human review signs the exact recomputed decision and comes from an identity
and session distinct from producer and all trial/freeze verifiers. An accepted
review records REVIEWED_RECOMMENDATION and external_authorization_required=true.
It never writes a live skill, Canon, Charter, gate or standing authorization.
The registry must be a separate operator-controlled file outside the evidence
directory. Empty or missing registries hold. No production trust key has been
provisioned by this work.

Operator commands, run with the pinned repository dependencies. Use a fresh
private bytecode directory on every invocation, including CLI runs; -B alone
does not prevent reading existing bytecode. The container uses a fresh tmpfs.

```bash
rsi_cli() (
  RSI_CACHE="$(mktemp -d)" || exit 1
  trap 'rm -rf -- "$RSI_CACHE"' EXIT
  python -B -X "pycache_prefix=$RSI_CACHE" -m tools.devon_rsi_ops.cli "$@"
)
rsi_cli register --state /operator/state --evidence /operator/evidence --keys /operator/registry.json
rsi_cli assess --state /operator/state --evidence /operator/evidence --keys /operator/registry.json
rsi_cli review --state /operator/state --evidence /operator/evidence --keys /operator/registry.json
rsi_cli snapshot --state /operator/state
```

Evidence contains protocol.json, freeze.json, trials/*.json and, for review,
review.json. Each signature envelope contains key_id, canonical payload JSON
string and base64 signature. No CLI command sends messages or effects.

## Meta-surface

The bounded meta comparator tests all sixteen data-only initial seed strategies
through the unchanged v1 search and exhaustive ablation. It ranks fixture score,
then counted evaluations, then deterministic fingerprint. It records every
subrun journal and recommends one seed without changing the operator. There is
a 60-second between-run deadline, at most 16 subruns, and the v1 per-run limits.
This is a useful operator experiment, not proof of live improvement. The scorer,
acceptance gates, immutable suite and trust boundary remain closed surfaces.

```bash
rsi_cli meta --state /operator/state --output /operator/fresh-meta-run --trust-sha256 0af7ba74e0ca7537099f2040fde69fb4ef206ceaffa61569138a841c13c036b3
```

## Current source and health evidence

Independent read-only verification on 2026-10-21 found 37 Reflections in
srv1936193, n8n-postgres-1, public.data_table_user_RuPMZKXkqcbuHRKa,
kind=reflection. Latest row 228 is dated 2026-10-15T11:44:30Z. There are
214 pulses, latest 2026-10-21T04:00:15.136Z. Pulse activity is not Reflection
cadence. Reflections are available; the bootstrap search limitation must not
be carried forward as a claim that they are unavailable.

Published workflows and current metadata independently show heartbeat table
RuPMZKXkqcbuHRKa and approval queue AomDw2Oa9XCUluRX. The older IDs in
services/devon/vault.py are stale. This artifact records locator corrections;
it does not mutate a live workflow or silently change constitutional authority.
Receipt table JCwPJ37BmyUW21r1 remains current. Existing approval infrastructure
does not prove that RSI review is integrated with it.

Current Context Pill: Drive 1uABYJfwt0q5Vy1z_ShnbOdd-HIoisy1U; apply October 13
correction 1d5wZ5nIn9_3HdSTt0X3OSqim5eZrx_fQ first. Standing authorizations:
1emNLhJj7O1F_sDUpCJ957mNCVIilE9a9, explicitly OPERATING and subordinate to
Charter v2. The bounded Drive, Core, Notion wiki and source-link search did not
locate current Charter v2 or a constitutional Canon snapshot. Script-writer
Canon is not a substitute. No live experiment or Canon session is invented.

## Remaining external prerequisites

The executable observation, meta comparison, admission and review mechanisms
are deliverable now. A meaningful live gain claim still requires the current
Charter and constitutional Canon snapshots, operator-established independent
signer registry, private blind suite, real paired trials and external review.
Monthly health judgment, Canon demotions, disagreement assessment and blind
testing remain human work; missing evidence stays visible. These prerequisites
cannot be completed by self-signing or relaxing a gate.
