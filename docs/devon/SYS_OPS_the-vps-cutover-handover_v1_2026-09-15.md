# Handover: put the whole DEVON lane on the VPS, live and published

Written 2026-09-15 for the session that executes the cutover. Read this first
and `CLAUDE.md` second. Everything below was measured on 2026-09-15 through the
two n8n connectors, not copied from an older doc.

Tee ruled it twice, in these words: "Devon organs are on the vps?" and then
"everything needs to be on the vps live and published." He was offered the
option of waiting a week so the newly live content engine could prove itself
first, and he declined. That objection is logged here once and the ruling
stands. Execute it.

## The one sentence version

Forty organ pairs need rebuilding, counted from
`docs/devon/vps-cutover-organs_2026-09-15.json` rather than from this sentence:
thirty nine named DEVON plus the shared OS Error Handler. Their VPS copies are
unpublished and mostly stale.
Rebuild each from its n8n Cloud live version with every identifier remapped,
move the open ledger rows, then unpublish on Cloud and publish on the VPS in one
pass. The transform and the check are written and tested and the identity maps
are complete. One organ is done: Build 19, which has no Cloud twin, is proven
and published, and it has no Cloud twin so it is not in that list of forty.
None of the forty have been touched.

## What is already done, and where it lives

Committed to this branch, so a new session gets it from git rather than
re-deriving it:

| Thing | Path |
|---|---|
| The transform, Cloud workflow to VPS operations | `scripts/vps_cutover_rebuild.py` |
| The check, rebuilt VPS copy against the Cloud source | `scripts/vps_cutover_verify.py` |
| Every identity map, read from both live instances | `docs/devon/vps-cutover-maps_2026-09-15.json` |
| The forty organ pairs with their repository overlays | `docs/devon/vps-cutover-organs_2026-09-15.json` |
| The Code node bodies, already repointed at the VPS | `n8n/devon/*/` |
| The registry, already repointed at the VPS | `services/devon/vault.py` |

The repository already names the VPS throughout. `vault.N8N_HOST` is
`https://n8n.editforge.online`, sixty two workflow and webhook id fields carry
the VPS copy's id, and no URL under `n8n/devon/` names Cloud any more. That work
is finished and merged into the branch; the cutover is the live half.

Build 19, the Zapier executor, was built tonight and is PUBLISHED on the VPS as
`MIELNCkP9IyHWVlr`. It is the only organ with no Cloud twin, so it is not in the
rebuild list, and it is the first DEVON organ live on the VPS under this ruling.
Its door answers but nothing dispatches to it yet, because the Action Router's
VPS copy is still unpublished.

## Proof the tooling works

Do not trust this paragraph. Re-run it in ten seconds and see for yourself. A
fixture pair lives in the session scratchpad and is gone with the container, so
build your own: take any organ's Cloud and VPS payloads, generate the
operations, apply them in memory, and verify. On 2026-09-15 that round trip gave:

| case | result |
|---|---|
| verifier against the stale VPS copy | `ok: false`, nine mismatches, exit 1 |
| verifier against a copy built from the generated operations | `ok: true`, exit 0 |

Note the trap while you are reading exit codes: `python3 ... \| head` reports
head's exit code, not the script's. That is written in `CLAUDE.md` and it caught
this session once tonight. Redirect and check `$?`.

## The order of operations

Work one organ at a time, in this order. Do not fan out across forty subagents:
that was tried on 2026-09-15 and two agents returned "out of usage credits"
partway through, which is why this handover exists at all.

### 1. Fix the two credentials first

Nothing publishes until these are settled. One of the two is now settled.

**Zapier MCP. SETTLED, 2026-09-15 21:15Z.** The VPS credential
`krUcZs3zx3V6zhUt` first answered `HTTP 401, -31997 Invalid OAuth token` on
execution 112. Tee rotated the token, and execution 113 on the VPS ran the lane
end to end: `initialize` answered 200 and issued session
`96d7aabb-6745-40eb-93d7-06aebb488f70`, `tools/call` answered 200 with the
configuration URL, the envelope advanced to EXECUTING carrying a `zapier_call`
artifact and call log row 1, and `ledger_clean` came back true. Build 19 is
published on the VPS, `activeVersionId 09d88637`. Nothing here is left to do.

**Devon Capture Key.** This one is not a known failure, it is an unanswered
question, and it is the sharpest edge in the whole cutover. Cloud holds
`FYRvkRTOcROEYZ9P` and the VPS holds `MTZXcoob6BtzbJyH`, same name, same type.
Whether they hold the same secret is unverified. It decides three things:
whether the organs can call each other after the switch (they can either way,
since they all use the VPS credential), whether Tee's phone Shortcut still
reaches the capture and Gumroad doors, and whether anything else outside the
estate that holds the old header value keeps working.

Settle it before publishing, by echo and never by reading a credential: stand up
a throwaway VPS workflow with a webhook door on the VPS Devon Capture Key and a
Code node that reports only the length, the prefix and the character classes of
the received header, then call that door with the value the Shortcut holds. The
method is the one that found the soul token 401 on 2026-09-15 and it never puts
a secret anywhere it can be read later. Archive the throwaway afterwards.

`Header Auth account 10` (Cloud `b9FYEfGUlMiYJCCU`) has no VPS twin at all. The
rebuild reports which node wants it. Decide then, do not pre-create it.

### 2. Rebuild each organ

For one organ, with its ids from the organ list:

```bash
# 1. read both live versions (MCP: mcp__n8n__get_workflow_details detailLevel full,
#    then mcp__n8n_vps__get_workflow_details) and save each VERBATIM as JSON.
#    If the harness saves a large result to a file, copy that file. If it comes
#    back inline, pipe it through python3 json.load / json.dump. Never retype a
#    Code node body: one changed character is a broken organ.
python3 scripts/vps_cutover_rebuild.py \
  --cloud cloud.json --vps vps-before.json \
  --maps docs/devon/vps-cutover-maps_2026-09-15.json \
  --out ops --chunk 90 \
  --overlay n8n/devon/<organ>          # only for the nine that have one
# 2. read ops/report.json. A non-empty overlay_unmatched_files means STOP and
#    apply nothing: a repository file with no matching node is drift a human
#    reads. Note credentials_unmapped verbatim.
# 3. apply ops/ops-1.json, ops-2.json ... in order with
#    mcp__n8n_vps__update_workflow, pasting each file as the operations array.
# 4. read the VPS copy back as vps-after.json, the same verbatim way.
python3 scripts/vps_cutover_verify.py \
  --cloud cloud.json --vps vps-after.json \
  --maps docs/devon/vps-cutover-maps_2026-09-15.json \
  --overlay n8n/devon/<organ>
# exit 0 means it matches. Anything else, read the mismatches and fix them.
```

The overlay matters on nine organs and is what carries tonight's edits, which
the Cloud versions do not have: the Action Router's fourth allowlist entry
`zapier.mcp`, the Job Driver's binding and fingerprint check for it, the Intake
Former's payload bounds, and the Face's reply format. Those nine are
`action-router`, `airtable-row-writer`, `drive-draft-writer`, `driver-poll`,
`face`, `intake-former`, `job-driver`, `ledger-feeder`, `spine`.

The generator updates a node in place rather than recreating it, on purpose:
recreating a webhook node issues a new `webhookId` and breaks every caller
holding the old URL. Do not "simplify" that into a delete and re-add.

### 3. Move the ledger rows

Tee ruled: the open jobs move, the terminal ones stay, the approval queue never
moves.

Read `devon_state_ledger` on Cloud (`VYyno7pDWmY6uxBz`), take every row whose
`state` is not `COMPLETED` and not `CANCELLED`, and insert those into the VPS
table `QZvdxllOjWevb3Vo`. The VPS table holds a 2026-09-03 snapshot with eight
CANCELLED rows; reconcile by `intent_id` so nothing is inserted twice.

The approval queue stays where it is. Its `token` column is plaintext and the
standing rule is that it is never read, so it is never copied either. Decided
cards are spent and open cards can be raised again.

### 4. Switch, in one pass

Only after every organ verifies clean and the credentials are settled. The order
matters because two live copies of the same organ is the failure to avoid: two
heartbeats, two janitors sweeping the same jobs, two pollers driving the same
ledger.

1. Unpublish on Cloud, leaf organs first and the ledger and bus last.
2. Publish on the VPS, the ledger and bus first and the leaf organs last.
3. Build 19 is already published and needs nothing at this step.

The VPS Error Alarm (`bqcnIS0Qv4RkTCU1`) and OS Error Handler
(`GbeNilHQzjmoWDz3`) are already active there, so failures are caught from the
first minute.

### 5. Prove it, then write it down

A published workflow is a claim. Prove each door from outside: POST to it with
the key and expect a 200 or a designed refusal, POST without the key and expect
a 401. Drive one real job end to end through the intake, the card, an executor
and the verification card, the way job `01M1V6M3XG0RQR191QFF7W74WJ` was driven on
2026-09-06. Watch the first Driver Poll and the first Heartbeat actually fire.

Then run `scripts/estate_reconcile.py`, which now reads `vault.N8N_HOST` and so
points at the VPS by default, and close the arc with a dated
`docs/devon/SYS_OPS_*` status doc carrying the nine key receipt.

## What will bite

- **Two live copies.** The whole reason step 4 is one pass. If a wake or a crash
  interrupts it, finish the switch before doing anything else.
- **The Approval Queue is stale in four ways.** Its VPS copy predates the
  2026-09-05 repair: it lacks the `Decided?` node, still uses a Gmail node where
  Cloud uses SMTP, has no error workflow, and does not suppress stored execution
  data, which is how a failed run once kept a plaintext token and two live
  links. The rebuild fixes all four, and that is the organ to verify hardest.
- **The email links carry the host.** The Approval Queue builds its approve and
  reject links from a HOST constant inside two Code nodes. The generator rewrites
  it. Check it by eye anyway, because a card whose links point at Cloud is a card
  Tee cannot act on.
- **`$workflow.id` is written into the ledger.** Several organs stamp their own
  workflow id into `execution.workflow_id` as a single flight lock and into trace
  notes. After the cutover those are VPS ids. That is correct and expected; do
  not read an old Cloud id in a migrated row as drift.
- **Cloud history stays Cloud history.** Execution numbers, `open_ruling` strings
  and older status docs name Cloud ids because that is where those things
  happened. The two instances share no ids. Do not rewrite history to match.
- **Usage credits.** They ran out on 2026-09-15 mid-fanout. Work one organ at a
  time with direct reads. Forty organs is a long job, not a hard one.

## The state of everything, measured 2026-09-15

- Forty organ pairs in the rebuild list: thirty nine named DEVON plus the OS
  Error Handler. On the VPS the Error Alarm and the OS Error Handler are active
  and the rest are unpublished. Thirty three of their Cloud twins are active.
  Build 19 is a fortieth DEVON-named workflow on the VPS, published, with no
  Cloud twin and no place in the rebuild list. Count these from the organ list
  file before trusting them again.
- Two vintages on the VPS: eight rebuilt 2026-09-10 and thirty one exported
  2026-08-31. The older vintage predates the hourly Soul Committer and the third
  executor.
- Forty nine workflow id pairs mapped. `Soul Index Setup` and
  `Build 08 Credential Probe` exist only on Cloud and are one shot throwaways.
- Eleven data table pairs mapped, every Cloud table matched by name. The VPS also
  holds `script_exemplars` and `devon_zapier_call_log`, both VPS native.
- Twenty eight of thirty credentials mapped by exact name and type. The two
  exceptions are named in step 1, and the Zapier one is now settled.
- TQO FINAL V5 and the TSWS chain are already live on the VPS and are NOT part of
  this cutover. Do not rebuild them from their Cloud copies; the Cloud copies are
  the stale ones.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-vps-cutover-handover_v1_2026-09-15.md
DATE: 2026-09-15
DECISIONS: Tee ruled every DEVON organ runs on the VPS, live and published, and declined the offer to wait a week for the newly live content engine to prove itself first; the objection is logged once here and the ruling stands. Tee ruled the cutover moves the open ledger jobs, leaves the terminal ones, and never moves the approval queue because its token column is never read. Tee created the VPS Zapier MCP credential himself.
FINDINGS: The rebuild list is forty organ pairs counted from the organ list file, thirty nine named DEVON plus the OS Error Handler, in two vintages: eight rebuilt 2026-09-10 and thirty one exported 2026-08-31. Forty nine workflow id pairs, eleven data table pairs and twenty eight of thirty credentials were mapped by reading both live instances. The VPS Zapier MCP credential krUcZs3zx3V6zhUt answered HTTP 401 Invalid OAuth token on execution 112 while the Cloud one answered 200 against the same URL in the same minute; Tee rotated the token and execution 113 then ran the lane end to end from the VPS, 200 on initialize and on tools/call, the envelope advanced to EXECUTING with a zapier_call artifact and ledger_clean true, so Build 19 was published (activeVersionId 09d88637) and is the first DEVON organ live on the VPS under this ruling. Whether the VPS Devon Capture Key holds the same secret as the Cloud one is unverified and decides whether Tee's phone Shortcut survives the switch. Header Auth account 10 has no VPS twin. The Approval Queue's VPS copy predates the 2026-09-05 repair in four ways including a Gmail node where Cloud uses SMTP and stored execution data that once kept a plaintext token. The rebuild transform and the verifier were proven by a round trip: the verifier reports nine mismatches and exit 1 against the stale copy and ok true with exit 0 against a copy built from the generated operations.
OPEN: No Cloud organ has been rebuilt on the VPS and nothing is unpublished on Cloud, so the cutover has not happened; Build 19 is the one organ published there and it has no Cloud twin. The ledger rows have not moved. Whether the two Devon Capture Keys hold the same secret is still unverified and still gates the switch. Usage credits ran out on 2026-09-15 during a forty agent fan out, so the executing session works one organ at a time.
STATUS: Prepared and handed over, one organ executed. The transform, the verifier, the identity maps and the organ list are committed to the branch, and Build 19 is live on the VPS; the forty organ pairs in the rebuild list are the next session's work.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
