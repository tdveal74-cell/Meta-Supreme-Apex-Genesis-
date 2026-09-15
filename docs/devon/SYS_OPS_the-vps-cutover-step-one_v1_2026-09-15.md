# The VPS cutover, step one: the capture key settled and the method changed

Written 2026-09-15 by the session that began executing
`SYS_OPS_the-vps-cutover-handover_v1_2026-09-15.md`. That handover is still the
plan of record and nothing here replaces it. This records what was measured,
what was done, and the one thing that stopped the remaining work.

## The capture key holds the same secret on both instances

This was the sharpest open edge in the cutover and it is closed. The VPS Devon
Capture Key `MTZXcoob6BtzbJyH` and the Cloud one `FYRvkRTOcROEYZ9P` hold the
same value.

Proved by echo, never by reading a credential. A throwaway VPS webhook door with
no authentication and no saved execution data reported only the length, the
first and last three characters, the character class counts and an FNV-1a hash
of each inbound header. One throwaway caller per instance attached its own
credential and called that door.

| field | Cloud, execution 7174 | VPS, execution 114 |
|---|---|---|
| header name | x-devon-key | x-devon-key |
| length | 46 | 46 |
| first three | dev | dev |
| last three | 76X | 76X |
| lower, upper, digit, other | 5, 28, 12, 1 | 5, 28, 12, 1 |
| FNV-1a 32 | 1054a6c1 | 1054a6c1 |

`sha256_12` came back null on both sides. The n8n Code node blocks
`require("crypto")`, which the body handled with a try and catch fallback to
FNV-1a rather than reporting nothing. Two strings agreeing on length, both ends,
all four class counts and a 32 bit hash are the same string.

That answers the question the handover actually cared about. The Cloud Capture
Hook's webhook node is bound to `FYRvkRTOcROEYZ9P` with header name
`x-devon-key`, read from the live workflow, so the value Tee's phone Shortcut
holds is that one, and it reaches the VPS capture and Gumroad doors unchanged
after the switch. Nothing on the phone needs editing.

All three throwaways were unpublished and archived: `rdiBm84KY8G2RQCC` the door,
`FrNPIRpXER1sboFP` the VPS caller, `nSvDIXDpojwPgVeV` the Cloud caller.

`Header Auth account 10` still has no VPS twin. No rebuilt node has asked for it
yet; capture-hook did not. The handover's instruction stands: decide when a
rebuild names the node that wants it, do not pre-create it.

## One organ rebuilt

`capture-hook`, Cloud `Cbd24ptTPWch3aZO` to VPS `bCZa6KVgjHgRup1Y`. Sixteen
operations applied. The report was clean: two credentials mapped, none
unmapped, no overlay requested, no unmatched overlay files, no type version
mismatch. The verifier exited 0 with four nodes and two edges on both sides.
The webhook id `37b341e8-8701-456f-a173-3ecb4c7b8c15` survived the update, which
is the thing that would have broken every caller holding the old URL.

It is not published. Publishing is step 4 and nothing publishes until every
organ verifies and the switch runs in one pass.

## Why the remaining thirty nine stopped

There is no n8n API key in a Claude Code on the web container. `N8N_SOURCE_KEY`,
`N8N_SOURCE_URL` and `N8N_API_KEY` are all unset, and both n8n connectors are
hosted MCP, so no key is reachable locally. Every workflow read therefore lands
in an agent's context and every write is emitted by hand.

That creates four transcription hops per organ, and three of them are safe:

| hop | caught by |
|---|---|
| operations into the update call | the verifier: the error lands on the VPS, the read back mismatches the source |
| the VPS read back into `vps-after.json` | the verifier, in the safe direction |
| the nine repository overlays | nothing to transcribe, the files are in the repository |
| the Cloud read into `cloud.json` | NOTHING |

The fourth is the problem. An error made reading Cloud into `cloud.json` flows
into the operations, onto the VPS, and back into `vps-after.json`, so the
verifier compares two copies of the same error and passes. `json.load` catches
truncation and broken escapes. A single changed character in the middle of a
Code node body does not surface until that organ runs.

Tee ruled on 2026-09-15, offered the choice: get an API key first rather than
hand transcribe thirty nine live organs. The remaining rebuild waits on that.

`scripts/vps_cutover_apply.py` was written and committed against that ruling. It
reads both instances over HTTP, reuses `build_operations` unchanged, applies the
operations in memory, writes the result back and verifies it, so no workflow
JSON is ever retyped. It refuses an unknown operation type rather than skipping
it, and its webhook guard fails an organ rather than warning, both after the
in memory rebuild and after the write. It was proved against the capture-hook
pair already applied by hand: the interpreter's result equals the live read back
exactly, the webhook id survives and the verifier reports no mismatches.

The same key fixes step 5. `scripts/estate_reconcile.py` reads
`N8N_SOURCE_KEY` and without it reports `N8N_SOURCE_KEY is not set` and reads
nothing from n8n at all.

## What was measured that the records did not say

**Cloud carries thirty four active DEVON organs, not thirty three.** The
handover says thirty three. Counted from `search_workflows` over the forty
DEVON matching workflows: six are inactive on Cloud, `table-reader`,
`e2e-harness`, `capture-hook`, `master-index`, `vault-compare` and
`purge-list`. Forty minus six is thirty four.

**Step 3 has nothing to move today.** The Cloud ledger `VYyno7pDWmY6uxBz` holds
twenty one rows and every one is terminal, twelve CANCELLED and nine COMPLETED.
A filter for `terminal` equal to false returns zero rows, and the complement
returns all twenty one, so that is a real zero and not a filter that matches
nothing. The VPS table `QZvdxllOjWevb3Vo` holds the eight terminal rows of the
2026-09-03 snapshot the handover describes, and their `intent_id` values are
present on Cloud, so a reconcile by `intent_id` would insert nothing twice.

This is a measurement with a short shelf life. The Ledger Janitor sweeps
non terminal jobs past 96 hours to CANCELLED, so the ledger trends to all
terminal on its own, but any job filed between now and the switch is a new open
row. Re-measure immediately before step 3 rather than trusting this paragraph.

**Large MCP results spill to a file.** A data table read of 157,954 characters
was written to disk by the harness instead of being returned inline, and could
then be read verbatim with `jq`. Workflow reads at the size of the Approval
Queue, the largest organ, still come back inline, so this does not solve the
transcription problem for organs. It does mean a large data table can be moved
without retyping.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-vps-cutover-step-one_v1_2026-09-15.md
DATE: 2026-09-15
DECISIONS: Tee ruled the remaining thirty nine organs wait for an n8n API key rather than being rebuilt by hand transcription, after being shown that one of the four transcription hops per organ is not caught by the verifier. He was offered hand grinding all thirty nine, or hand grinding only the nine overlay organs whose Code bodies come from repository files, and chose the key.
FINDINGS: The VPS Devon Capture Key MTZXcoob6BtzbJyH and the Cloud FYRvkRTOcROEYZ9P hold the same secret, proved by echo on executions 7174 and 114 agreeing on header name x-devon-key, length 46, first three dev, last three 76X, class counts 5 28 12 1 and FNV-1a 1054a6c1; the Cloud Capture Hook webhook is bound to that credential, so Tee's phone Shortcut survives the switch untouched. capture-hook was rebuilt on the VPS, sixteen operations, clean report, verifier exit 0, webhook id 37b341e8-8701-456f-a173-3ecb4c7b8c15 preserved, not published. Cloud carries thirty four active DEVON organs and not the thirty three the handover states, counted from the workflow list. The Cloud ledger holds twenty one rows and every one is terminal, so step 3 has nothing to move today, and the VPS table holds the eight terminal rows of the 2026-09-03 snapshot whose intent_ids are all present on Cloud. There is no n8n API key in a web session container, so every read lands in context and every write is emitted by hand, and the Cloud read into cloud.json is the one transcription hop the verifier cannot catch. Large MCP results spill to a file on disk and can be read verbatim, but a workflow read at the size of the Approval Queue still returns inline.
OPEN: Thirty nine of the forty organ pairs are unrebuilt and nothing is unpublished on Cloud, so the cutover has not happened. Step 3 is a no-op as measured but must be re-measured immediately before the switch. Steps 4 and 5 are untouched. N8N_CLOUD_KEY and N8N_VPS_KEY must be set on the environment, and picked up by a new session, before scripts/vps_cutover_apply.py can run. Header Auth account 10 still has no VPS twin and no rebuilt node has yet asked for it.
STATUS: Step 1 settled and one organ rebuilt. The remaining rebuild is blocked on an API key by Tee's ruling, and the driver that consumes it is committed and proved against the one organ already done.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
