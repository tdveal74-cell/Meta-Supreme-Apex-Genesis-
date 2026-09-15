# Eight rulings, two merges, and TQO FINAL V5 brought current on the VPS

Tee ruled on 2026-09-15, on inline cards, on the eight calls the two
readiness audits put to him (`SYS_OPS_devon-readiness-audit_v1_2026-09-15.md`
and `SYS_OPS_n8n-cloud-to-vps-cutover-readiness_v1_2026-09-15.md`), then
said the VPS must be operationally green along with DEVON because he needs to
produce content. This doc records the rulings, what was done under them in
the same sitting, what was measured, and what is his to do next.

## The rulings

1. The devon-ops proxy debug lines: delete them and rotate the secret. Done
   as PR #221, merged at `642326b6`; the rotation of `DEVON_OPS_SECRET` on
   Vercel and the gateway is his and is not done here.
2. The Soul panel note: change "Configured rather than probed:" to
   "Configured only:". Done in the dock, the AST check and the smoke
   together, on the branch this doc rides.
3. PR #219: merge when CI is green. Merged at `baafe685` on 8 of 8 checks.
4. `GET /health/ready`: give it a real database check. Owed, a small PR
   after this one.
5. TQO FINAL V5 and the TSWS chain: the VPS owns both. My objection, logged
   once: the VPS copy was a day and a half behind Cloud and its Google Drive
   credential is disconnected, so Cloud keeping V5 was the safer order. Tee
   overruled; the port below is the first step of executing it.
6. The three unauthenticated V5 doors on the VPS: close the two link doors
   with header auth, Gumroad Ping stays open because Gumroad cannot send a
   header. Done, on the published version.
7. The 33 copies of 2026-08-31 vintage: re-export from Cloud with
   `scripts/n8n_migrate.py`. Owed; a sitting of its own with the API keys
   Tee holds.
8. The Build 13 reflection: a standalone Routine plus the pulse subject fix.
   The Routine is his to create on claude.ai. The subject change is one line
   in the Heartbeat's Compose Pulse node (`dRgTNLod2s8BAcPg`), written below
   for him to apply, and not applied here because the ruling was for a
   written change.

## What was done to the VPS copy of TQO FINAL V5

Under ruling 5 and Tee's instruction "make the VPS have the fresher copy
too", the VPS workflow `qEkGOUsNyVaRAmm6` was brought to the state of Cloud's
`gsGJQan7a6ZufhYt` version `0c1f7068` of 2026-09-11T22:15:43Z. Both payloads
were read in full (222 nodes each) and diffed node by node before a single
write. Of 111 nodes that differed, 101 differed only in exported defaults
(`resource: row`, `condition: eq`, `mode: runOnceForAllItems`) or in
credential ids that are the VPS's own bindings by name; those were left
alone. The real changes since the VPS copy was saved on 2026-09-10 were
seven, and five were ported verbatim through `update_workflow` on the draft
in four saves, then the draft was published:

| node | change | read back |
|---|---|---|
| `OS 28: Publish Gate` | authorship gate accepts the data table's string `human_review` values through the `TICKED` list; boolean true still works for Airtable rows | sha256 prefix `8243c79ad94facfd`, equal to Cloud |
| `Preflight: Can This Clear?` | the same `TICKED` list, so preflight and the gate agree | `36f977e4fa4e5477`, equal |
| `Show Context: Render` | `VOICE_READY` in one constant; the predicted `provider` field replaced by `providerEleven` and `providerSpeechify` candidates | `e3dabb07e8405ba0`, equal |
| `Mark Ready + Save URL` | `last_feedback` records which TTS node executed, or "UNKNOWN NARRATOR, do not publish" | `dffa5a28925e4cb6`, equal |
| `Run TQO (Link)`, `Run NCO (Link)` | `authentication: headerAuth` on the Devon Capture Key `MTZXcoob6BtzbJyH` already bound | equal; the active version's trigger info now reads "requires a header with name x-devon-key" on both |
| `Gumroad: MailerLite Buyer Sync` | credential was the anthropic header auth `EdFztvzdUL9PSycJ`, a binding error in the VPS copy; now `mailerlite` `XbLg8FnNraeTbEfJ`, as on Cloud | read back |

Two Cloud changes were not ported, on purpose. The six `Build * Prompt`
nodes on Cloud moved the model string to `claude-sonnet-5`; on the VPS the
six Claude calls go straight to `api.anthropic.com` with Tee's key through
`httpRequest` nodes, whereas Cloud converted them on 2026-09-11 to the native
Anthropic node on n8n Gateway credits, which the VPS does not have. Whether
Tee's key has Sonnet 5 access is unverified, and a wrong guess would break
all six calls, so the VPS keeps `claude-sonnet-4-6` and its HTTP nodes until
he says otherwise. That is the one remaining divergence.

Read back after publishing: `activeVersionId 89fef7ef-ee42-40e7-bd69-528832771044`,
`active true`, `triggerCount 7`, `errorWorkflow GbeNilHQzjmoWDz3`, every
ported value byte equal to Cloud's by hash, connections unchanged, and ten
untouched nodes showing only a credential name refresh (`Header Auth account
3` now reads `anthropic`, `7` reads `mailerlite`, `8` reads `json2video`,
ids unchanged). The previous published version `5e9d3a6a` is one
`restore_workflow_version` away.

## What still stands between the VPS and a content run

Measured, not assumed. The Google Drive credential `NW3vR6nNcMoUkJyJ` on the
VPS is disconnected: execution 23 of 2026-09-13 died at `Upload MP3` with
"needs to be reconnected", and V5 binds it on nine nodes. Only Tee can
reconnect it, in the VPS n8n credential UI, and no run produces a file until
he does. The YouTube credential `2oUKSwU4rB6UKPPV` has never been exercised
on the VPS and its connection state is unread. All six schedule triggers are
disabled on both instances, so nothing writes a script or promotes a row
until a schedule is enabled or a door is hit. Cloud's copy is still active
with the same seven doors, so a poster aimed at Cloud still lands there.

DEVON itself is operational on Cloud today (the readiness audit's body table:
every scheduled organ on cadence, zero errors, ledger terminal). The DEVON
lane on the VPS is the cutover, runbook steps 3 to 6 of the v2 record, and it
is not started; the cutover audit lists the ten blockers in order.

## Eight more rulings, later the same day

Tee asked for the question bank on cards and ruled eight more. Done in the
same sitting, each read back after the write:

1. The five active VPS TSWS pipelines now name the VPS OS Error Handler
   `GbeNilHQzjmoWDz3` as their error workflow (was the Cloud id), published
   at `e50af1de`, `b77a7182`, `d3169ee6`, `df08db3b`, `69ce87e3`; the
   handler itself binds SMTP `AgSGuaA2pnZsrZcJ` and Airtable
   `Avhx7u29TskBaR67` instead of the two Cloud ids that failed in execution
   24, published at `95e4eae3`.
2. The Heartbeat subject fix was applied on Cloud, not left for Tee:
   `reflection_missing` is filed with `alert` true, published at
   `2a1c5ab4`; the section below is now history. The 10:00Z beat is the
   re-measure, and a check-in is armed for it.
3. The VPS Claude calls stay on `claude-sonnet-4-6` until the watched run
   passes.
4. `/health/ready` gets its real check now, PR #223.
5. The 33 copies of 08-31 vintage are ported through the connectors the way
   V5 was, one at a time, DEVON lane organs first, after the content lane.
6. The DEVON cutover starts after the content lane's watched run passes.
7. Tee reads the n8n Cloud usage page and sends the two numbers; the five
   cap anchor variable lines come back to him to set on Railway.
8. From 2026-09-16 every status doc carries a sequence letter after its
   date; `test_devon_receipt_shape.py` enforces it and CLAUDE.md says so.

And three on the content lane itself: after Tee reconnects the Google Drive
credential on the VPS, one watched run of `run-tqo-pipeline`; the six
schedules are enabled on the VPS only after that run passes; Cloud's copy of
V5 is unpublished after that run passes.

## The Heartbeat subject fix, as applied

In workflow `dRgTNLod2s8BAcPg`, node `Compose Pulse`, the reflection finding
is filed with `alert` false, so it lands under WATCHING and the subject stays
"DEVON Pulse: all quiet" while the reflection has been silent for 40 hours.
The one line that changed, exactly:

```
finding('reflection_missing', false, 'No fresh reflection: ...
```

became

```
finding('reflection_missing', true, 'No fresh reflection: ...
```

With `alert` true the finding counts as new on its first appearance, the
subject reads "DEVON Pulse: 1 thing(s) need you", and on later beats "1 open
item(s), nothing new" until a reflection lands. Nothing else in the node
reads the flag.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_eight-rulings-and-v5-on-the-vps_v1_2026-09-15
DATE: 2026-09-15
DECISIONS: eight rulings by Tee on 2026-09-15: delete the proxy debug lines and rotate the secret; change the panel note to "Configured only:"; merge #219 on green; give /health/ready a real check; the VPS owns TQO FINAL V5 and the TSWS chain (objection logged once, overruled); close the two V5 link doors on the VPS with header auth; re-export the 08-31 vintage with the tool; a standalone reflection Routine plus the pulse subject fix. Then: the VPS has the fresher V5 copy. Eight more the same day: the TSWS error path repointed and the handler rebound on the VPS, the Heartbeat subject fix applied on Cloud, Sonnet 4-6 stays on the VPS until the watched run, /health/ready now, the 08-31 vintage ported through the connectors, the cutover after the content lane, Tee sends the usage page numbers, sequence letters on status doc filenames from 2026-09-16; and on the content lane a watched run after the Drive reconnect, schedules and the Cloud switch off after it passes.
FINDINGS: PR #219 merged at baafe685 and PR #221 at 642326b6; the VPS V5 published at 89fef7ef with five Cloud changes ported and hash verified, the two link doors closed, and a mis-bound Buyer Sync credential corrected; the model bump to claude-sonnet-5 and the Gateway credit conversion were not ported because the VPS calls Anthropic with Tee's key; the Google Drive credential on the VPS is still disconnected and the six schedules are disabled on both instances, so no content run can complete yet.
OPEN: Tee reconnects Google Drive on the VPS and checks the YouTube credential; Tee rotates DEVON_OPS_SECRET; Tee decides whether the six schedules go live on the VPS and whether Cloud's V5 goes inactive; the /health/ready PR; the 08-31 re-export sitting; the Heartbeat subject line; the standalone reflection Routine; the Sonnet 5 question on the VPS key; the DEVON cutover itself.
STATUS: two PRs merged, one workflow published on the VPS under Tee's ruling, everything read back after the write. Content cannot flow until the Drive credential is reconnected, which is his hand on his OAuth.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
