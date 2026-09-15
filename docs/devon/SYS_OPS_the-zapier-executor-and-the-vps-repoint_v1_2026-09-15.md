# The Zapier executor, and the repository repointed at the VPS

2026-09-15, evening. Tee ruled twice in the same hour. First: wire the Zapier
MCP server as DEVON's external executor, because Zapier is part of the
ecosystem and DEVON should reach it. Then, reading the reply: everything needs
to be on the VPS, live and published.

This doc records what was built, what was measured, and the one thing that
answered 401 when it should have answered 200.

## Build 19, the third real executor

`DEVON Zapier Executor (Build 19)` is `MIELNCkP9IyHWVlr` on
n8n.editforge.online, twenty three nodes, webhook `devon-zapier-mcp` on the
VPS Devon Capture Key. It is the fourth name on the Action Router allowlist
(`zapier.mcp`, ceiling reversible_write) and the third that does anything
physical, after the Drive Draft Writer and the Airtable Row Writer.

It reaches Zapier the way a client does, not the way a Zap does: JSON-RPC 2.0
over Streamable HTTP at `https://mcp.zapier.com/api/v1/connect`. One job opens
one session with `initialize`, reads the `mcp-session-id` header back, makes
exactly one `tools/call`, and drops the session. Nothing in the workflow holds
a token; the credential is bound by id.

The gates are the Airtable Row Writer's, because a call that leaves the estate
is at least as serious as a row:

- AUTHORIZED only, schema_version 1.0.0, a ULID intent id.
- A granted, unexpired approval on every envelope, whatever the label says.
- Blast radius no wider than reversible_write, and no wider than the tool's own
  recorded radius.
- An idempotency key of 8 to 128 characters with no whitespace, quotes, braces
  or backslashes.
- A structural payload. `intent.payload.zapier` carries a tool name and an
  arguments object, and nothing is guessed from the summary.
- No EditForge payload; renders go through Build 07.

Two things are new here. The tool allowlist lives in the executor and in
`vault.ZAPIER_MCP_TOOLS`, each tool carrying the blast radius it really has,
and `test_devon_integrity.py::test_zapier_tools_match_the_executor_tool_map`
pins the two together and refuses a tool wider than the ceiling. And the
executor owns its idempotency in its own data table, `devon_zapier_call_log`
(`k8q48ohh5dnwJS4a` on the VPS), rather than borrowing a marker from the
ledger: a call that already succeeded under this key, intent id and payload
fingerprint is reused; a call still in flight is refused; a call whose outcome
nobody could read is never retried by a machine when the tool writes.

That last rule is the one worth reading twice. An MCP call that times out may
or may not have run. For a read the next pass tries again. For anything wider
the row stays `unknown` and a human reads Zapier's own history before it moves.

## The card and the executor compute the same eight characters

The Job Driver binds `zapier.mcp` when the job carries a structural zapier
payload, names the tool and the argument values on the approval card, and
stamps an FNV-1a fingerprint of the canonical payload into the card line. The
executor computes the same fingerprint over the same value. If the payload
changes between the card and the dispatch, the driver parks the job rather than
running an act Tee did not read.

Measured, not assumed: a seven case harness over the driver's own Decide body
and the executor's Validate and Plan produced the same `61f656c0` from both
sides, and a payload edited after the card parked with
`bound_payload_mismatch`.

## What was measured

| what | how | result |
|---|---|---|
| the node bodies | 49 case offline harness over all six Code node sources | 49 passed |
| the driver binding and the fingerprint | 7 case harness over `decide.js` and the executor | 7 passed |
| the intake bounds and the floor | 10 case harness over `form_job.js` and `apply_tags.js` | 10 passed |
| the Face parser | 2 case harness over `parse_reply.js` | 2 passed |
| the graph end to end, happy path | pinned execution 109 on the VPS | EXECUTING, artifact `zapier_call`, call log row 1, ledger_clean true |
| the graph end to end, refusal | pinned execution 110 on the VPS | refused as data, HTTP 200, the reason names the allowlist |
| the live call from the VPS | execution 112, real credential | REFUSED: HTTP 401, see below |
| the live call again, after Tee rotated the token | execution 113, real credential | 200, session issued, EXECUTING with the artifact, ledger_clean true |
| the same call from Cloud | execution 7171, same minute, same endpoint | 200, session issued, 17 tools listed |

## The 401, stated plainly

Tee created a `Zapier MCP` header auth credential on the VPS
(`krUcZs3zx3V6zhUt`). The executor's first live call answered:

```
HTTP 401, -31997 Invalid OAuth token - please re-authenticate
```

The same `initialize` from the Cloud probe, against the same URL, at 20:56Z
the same minute, answered 200 and issued a session. So the endpoint works, the
method works, the workflow works, and the value on the VPS is not the value
Zapier expects. It is a token to re-copy, not a design to revisit.

The executor's own refusal named it: "the Zapier MCP credential on n8n is the
first thing to check." That is the honest path working as designed.

Tee rotated the token at 21:15Z and execution 113 settled it. `initialize`
answered 200 and issued session `96d7aabb-6745-40eb-93d7-06aebb488f70`,
`tools/call` answered 200 with the configuration URL, the envelope advanced to
EXECUTING carrying a `zapier_call` artifact and call log row 1, and
`ledger_clean` came back true. Build 19 is published on the VPS,
`activeVersionId 09d88637`: the first DEVON organ live there under the ruling.

One more thing the Cloud probe found, which changes what the lane can become:
the Zapier server now exposes seventeen tools, not the one it exposed this
afternoon. Among them are `execute_zapier_read_action` and
`execute_zapier_write_action`. The read tools can join the allowlist at radius
read whenever Tee rules on them. The write tool cannot join at all under a
reversible_write ceiling, and raising that ceiling is a ruling, not an edit.

## The repository now names the VPS

Tee's second ruling moved every host literal, every workflow id and every data
table id in the repository from n8n Cloud to n8n.editforge.online:

- `vault.N8N_HOST` is the VPS. Sixty two workflow and webhook id fields were
  rewritten from the Cloud copy's id to the VPS copy's, and no Cloud id remains
  in an id field. `Soul Index Setup` and `Build 08 Credential Probe` have no
  VPS copy and are recorded as such.
- Every URL in `n8n/devon/*/*.js` names the VPS, including the Action Router's
  three executor URLs and the Job Driver's HOST constant.
- `ZAPIER_MCP_TOOLS` and the `devon-zapier-mcp` webhook joined the vault, and
  the header key count moved from sixteen to seventeen.
- `deploy/soul/services/devon/vault.py` was re-copied so the byte identity test
  passes, and the learning lane skill's id tables were repointed the same way.
- `test_estate_reconcile.py` no longer hardcodes which host is the vault's own.
  It reads `vault.N8N_HOST` and names the other instance as the drift case, so
  the test survives the cutover instead of encoding the side it was written on.

## The cutover is prepared, not done

The tooling exists, is proven on a fixture pair, and is committed:
`scripts/vps_cutover_rebuild.py` turns a Cloud live workflow into VPS update
operations with the host, credential ids, data table ids, workflow ids, node
settings and error workflow mapped, and `scripts/vps_cutover_verify.py` compares
the rebuilt VPS copy against the Cloud source with the same maps applied and
exits non-zero on any mismatch. The maps and the organ list sit beside them under
`docs/devon/`, and `SYS_OPS_the-vps-cutover-handover_v1_2026-09-15.md` is the
plan of record for the session that runs it.

The maps are complete and first hand:

- 49 workflow id pairs, read from both instances.
- 11 data table pairs, every Cloud table matched by name; the VPS also holds
  `script_exemplars` and `devon_zapier_call_log`, which are VPS native.
- 28 of 30 credentials mapped by exact name and type. Two do not map:
  `Header Auth account 10` has no VPS twin, and the Zapier MCP credential is
  the 401 above.

What is not done: the thirty nine VPS copies with a Cloud twin have not been
rebuilt from their sources, nothing else has been published on the VPS, nothing
has been unpublished on Cloud, and the ledger rows have not moved. Tee ruled that the open jobs move
and the closed ones stay, and that the approval queue never moves because its
token column is never read. That is the plan of record; it has not run.

The reason it has not run is worth recording rather than hiding: the rebuild
was launched as a fan out across the forty organs and two of its agents
returned "out of usage credits" partway through. The inventory those agents did
complete is real and is on disk; the rebuild itself stopped before it started.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-zapier-executor-and-the-vps-repoint_v1_2026-09-15.md
DATE: 2026-09-15
DECISIONS: Tee ruled the Zapier MCP server is DEVON's external executor, wired as the fourth Action Router action zapier.mcp at ceiling reversible_write, bound by a structural intent.payload.zapier and never from words in a summary. Tee ruled every DEVON organ runs on the VPS, live and published, so the repository's host, workflow ids and data table ids were repointed from n8n Cloud to n8n.editforge.online. Tee ruled the cutover moves the open ledger jobs and leaves the terminal ones, and that the approval queue never moves. Tee created the Zapier MCP credential on the VPS himself.
FINDINGS: Build 19 is live on the VPS as MIELNCkP9IyHWVlr with 23 nodes, proven by pinned executions 109 (EXECUTING with a zapier_call artifact and ledger_clean true) and 110 (refusal as data naming the allowlist), and by 68 offline cases across four harnesses. The VPS Zapier MCP credential krUcZs3zx3V6zhUt answered HTTP 401 -31997 Invalid OAuth token on execution 112, while the Cloud credential answered 200 and issued a session against the same URL in the same minute on execution 7171, proving the token value and not the endpoint; Tee rotated it and execution 113 ran the lane end to end from the VPS with 200 on both calls, EXECUTING, a zapier_call artifact and ledger_clean true, so Build 19 was published (activeVersionId 09d88637). The Zapier server now exposes seventeen tools where it exposed one this afternoon, including execute_zapier_read_action and execute_zapier_write_action. 28 of 30 Cloud credentials have a VPS twin of the same type by exact name; Header Auth account 10 has none. All 11 Cloud data tables have a VPS twin by name. 49 workflow id pairs were read from both instances; Soul Index Setup and Build 08 Credential Probe exist only on Cloud.
OPEN: The forty VPS organ copies have not been rebuilt from their Cloud sources, nothing is published on the VPS and nothing is unpublished on Cloud, so the cutover Tee ruled has not happened. The ledger rows have not moved. Whether the VPS Devon Capture Key holds the same secret as the Cloud one is unverified and decides whether Tee's phone Shortcut keeps working after the switch. Which Zapier tools join the allowlist beyond get_configuration_url is Tee's ruling, and execute_zapier_write_action cannot join under the current ceiling.
STATUS: Build 19 built, proven offline, on pinned runs and on a live call, and published on the VPS after Tee rotated its token. The repository names the VPS throughout. The cutover is prepared and not executed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
