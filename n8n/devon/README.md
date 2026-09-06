# DEVON n8n Code node sources

n8n Cloud is where these run; this directory is where they are read, reviewed
and diffed. Each file is the exact body of one Code node in one live workflow.
Nothing here executes: n8n holds the graph, the credentials and the schedule,
and the node bodies are the part worth reviewing like code.

| Directory | Workflow | Id |
|---|---|---|
| `job-driver/` | DEVON Job Driver (Build 14) | `TT4TfFXyH9O7lfdc` |
| `drive-draft-writer/` | DEVON Drive Draft Writer (Build 16) | `J7Ly7riwXEd95D9a` |
| `driver-poll/` | DEVON Driver Poll (Build 14) | `mbIKJk4UuB7V27rP` |
| `action-router/` | DEVON Action Router, n8n lane (Build 05) | `ecLqrxALuLDdF2BN` |
| `airtable-row-writer/` | DEVON Airtable Row Writer (Build 17) | `ps2S6dWcTIpq5bvr` |
| `intake-former/` | DEVON Intake Former (Build 14) | `AEFgXee7IDJarNV7` |
| `face/` | DEVON Face (Build 15) | `LsmfRFMmI5feINs0` |

File names are the node names in snake case. `job-driver/decide.js` is the
Decide node.

Two drifts were found and closed on 2026-09-06 by reading every live node and
diffing it here: the live Absorb node had never received the HTTP 200 guard on
refusals as data that the repo copy carried since 2026-09-05 (the repo was
pasted into n8n), and the repo copy of the Drive Draft Writer's Advance
Envelope lacked the matched by note the live node carried (the live text was
copied here). The Intake Former's five Code nodes were added under
`intake-former/` the same day, when a Build 17 edit touched two of them, and
the Face's five under `face/` when the same build taught it the executors
that exist and let it attach an airtable object to a job.

## These are copies, and copies drift

n8n is the running system. A change made in the n8n editor and not copied here
leaves this directory describing a version that no longer runs, which is worse
than no copy at all. **No test compares these files to n8n**, and none can from
this repository: there is no n8n credential in CI. What the three tests below pin
is this directory against `vault.py`, so a change made here cannot silently
disagree with the estate's own record. Keeping these files equal to the live
nodes is a human step, done in the same arc as the n8n edit.

- `test_devon_integrity.py::test_draft_folders_match_the_executor_folder_map`
  compares the Area to Drive folder map inside
  `drive-draft-writer/validate_and_plan.js` against `vault.DRAFT_FOLDERS`.
  n8n cannot import the vault, so that map is duplicated on purpose. If the two
  disagree, DEVON writes a draft into a folder the vault does not permit for
  the Area and nothing else notices.
- `test_devon_integrity.py::test_action_router_allowlist_matches_the_vault_state`
  checks that every action in `action-router/authorise_and_resolve_target.js`
  dispatches to a workflow id `vault.WORKFLOWS` knows, and that the vault's
  Action Router state names the action and its ceiling. An executor that reaches
  production without a registry entry is a capability nobody wrote down. This
  test found five unregistered organs on its first run, the Spine among them.
- `test_devon_integrity.py::test_airtable_row_tables_match_the_executor_table_map`
  compares the table allowlist inside
  `airtable-row-writer/validate_and_plan.js` (table id, the two stamp fields,
  the writable fields) against `vault.AIRTABLE_ROW_TABLES`, and the base id
  against `vault.AIRTABLE`. Same reason as the folder map: a row written into a
  table the vault does not permit is a write nobody wrote down.

The rest of each file is reviewed by reading it. That is the point of the
directory: a Code node body is code, and code belongs where it can be diffed.

After editing a node in n8n, copy the body back here in the same arc, and after
editing a file here, paste it into n8n and publish. A draft edit in n8n changes
nothing until it is published.

## Not every node is here

These are the Code node bodies of seven workflows plus the Spine's two. The
graph, the HTTP nodes, the credentials, the data table nodes and the sticky
notes live only in n8n. So does every other organ. When a review needs one of
those, read it with `get_workflow_details` against the live workflow id in the
table above.
