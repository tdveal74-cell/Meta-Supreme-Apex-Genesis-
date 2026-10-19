# Runtime evidence and skill revision gates

This implementation extends the offline baseline through the authenticated task
coordinator. `completed` still means the plan ended. Only
`task.verification.verdict` describes the declared deterministic checks. No
checks, absent results or an incomplete plan cannot yield VERIFIED. A failed
check takes precedence over missing checks. Undeclared semantic claims remain
unverified regardless of adapter prose or model votes.

## Task contract

POST `/api/v1/agent-tasks` accepts `task_family` and up to 50
`verification_requirements`. Each names an exact planned step, an ID, a checker
and its expectations. The supported checkers are:

| Checker | What the receipt establishes |
| --- | --- |
| `tool_succeeded` | The captured adapter returned `ok=true` |
| `output_sha256` | Captured output bytes match an expected SHA256 |
| `json_schema` | Captured JSON satisfies the supported closed schema subset |
| `artifact_properties` | Captured base64 bytes match declared size/hash or PNG IHDR dimensions |

Unsupported schema keywords are refused. Artifact checks do not prove a file
exists at an external destination, a complete image decodes, or visual quality.
PNG dimensions measure the signature/IHDR with CRC, not the full image.
Tool success alone cannot verify a claim of deployment, delivery or creation.

The server captures full tool results separately from task snapshots. Output and
error previews are bounded to 2048 characters. Oversized metadata is replaced
in the snapshot; the full sanitized metadata remains in durable storage.
Results larger than 16 MiB are refused. Approval credentials are removed from
captured metadata. Treat tool output as potentially sensitive owner data.

GET `/{task_id}/results/{result_id}` retrieves owned captured data and checks its
hash. GET `/{task_id}/verification-receipts` reads immutable reports. Both are
under `/api/v1/agent-tasks`. Records are append-only; task deletion removes its
results/reports, and account deletion removes owned records. Retention is tied
to that lifecycle, not an indefinite archive. Conversation compaction does not
delete the separate records. Agent-state rollback clears the current verdict
and later observation references but retains prior receipts and results.

Results, verification and the fenced execution result commit in one transaction.
A stale final execution fence rolls all three back. Existing durable effect
intents and human approvals still govern external writes; this evidence path
does not retry ambiguous effects or grant execution authority.

## Route measurement and calibration

GET `/api/v1/agent-tasks/evaluation/routes` aggregates recent owned receipts.
Versions, frozen input hashes, requirements, tool evidence, stop reasons and
latency are recorded by the coordinator. Cost remains null when unmeasured.
It reports the receipt limit, excludes repeated task content within a stratum,
and selects the newest receipt per task. This is a bounded recent sample, not
a population census. Input context is hashed at creation before execution.

Runtime labels use declared checks and observed read/inspect/search/query tool
names. They do not assess semantic answer quality or individual council-member
reasoning. Boundary pauses, errors and budget exhaustion are excluded from
premature stopping. Unmeasured routes remain unclassified. No live provider
benchmark, orchestration benefit or compaction benefit is established by the
fixture tests. See [AGENT_ROUTE_BENCHMARKS.md](AGENT_ROUTE_BENCHMARKS.md) for
paired frozen experimental comparisons.

POST `/api/v1/agent-tasks/evaluation/calibrate` accepts owned runtime receipt IDs
and votes from two to eight version-named evaluators. Truth comes from the
server's immutable declared-check receipts. It persists pairwise agreement,
correctness, missing votes, false approvals and shared errors. Caller votes
cannot override task verification. Agreement does not establish judge
independence or semantic truth. Training hash exclusion relies on the declared
inventory; it cannot prove unseen-data isolation.

## Skill revisions

Operator edits append exact instruction bytes, content hashes, parent versions,
provenance and evidence. Existing legacy skills are snapshotted on first edit or
rollback; already-lost historical versions cannot be reconstructed. Concurrent
changes serialize per owner/name. Rollback creates a new monotonic version
rather than rewriting history, and requires the expected active version.

Under `/api/v1/agent-tasks/learning/skills/{name}`:

- GET `/revisions` lists owned immutable revisions.
- POST `/rollback` takes `target_version` and `expected_version`.
- POST `/evaluations` takes exact candidate text, owned `source_task_id`,
  `suite_id` and `suite_version`; GET `/evaluations/{id}` reads the attempt.

Every owned evaluation attempt retains its exact candidate and status,
including unsupported formats/suites and failed checks. Unknown task ownership
is refused before recording. Only application-registered local runners issue
passing evidence. Evolved proposal promotion requires explicit human approval,
matching expected active version and an owned passing receipt less than 24
hours old, bound to the exact candidate and source task. A model score or
caller-supplied success cannot authorize promotion.

The bundled `receipt-decision-policy` v1 runner interprets a closed JSON
decision table on four public contract fixtures disjoint from the source task.
This is contract testing, not an unseen final benchmark or a general skill
quality evaluator. Natural-language skills require an independently implemented
trusted runner before evolved promotion. Explicit human edits remain available
and audited. Production model sampling and a fresh final holdout remain
operational work; the public fixtures must not be presented as those results.
