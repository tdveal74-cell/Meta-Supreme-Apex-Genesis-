# SYS_OPS: the TQO render lane, and the two content stores

Dated 2026-09-10. Supersedes nothing. It answers the question Tee asked, how to
get DEVON to render a TQO video, and records the four rulings that came out of
the answer.

## The answer

Nothing renders today, and nothing is broken. TQO FINAL V5 is complete end to
end and parked in three separate places on purpose. The 46 ideas Tee had
written were sitting in a table the render lane stopped reading three weeks
earlier.

## Two content stores, and the live one was empty

Read from the live estate rather than from any record.

* Airtable Content, `tblx5CcNguOypBjLI` in base `app28z7XnKzjfTXwc`, held 66
  rows: 20 Published, each with a Drive video URL, and 46 Idea, 11 of which
  also carried a Drive URL from before the migration. Nothing in Scripted,
  Queued, Rendering, Ready or Error. Render Attempts 0 or empty on all 66.
  Newest row created 8 August 2026.
* **V5 does not read that table.** Its 222 nodes make 19 raw Airtable HTTP
  calls, and they hit nine other tables: Rules, Customers, Assets, Publishing,
  Signals, Offers, Performance, Primitives and the EditForge queue. The Content
  table id appears zero times in the whole 346 kB payload.
* The content lifecycle runs on the n8n data tables. `Show Context: Render`
  sets `tableId` to `tqo_content`, and 29 data table nodes drive Idea to
  Scripted to Queued to Rendering to Ready to Published. Node names still read
  "Save Script to Airtable" because they were never renamed after the 21 August
  migration, and a node called `DT Shim: Claimed Rows` maps the flat columns
  onto the Airtable display names and rebuilds a `fields{}` view. That shim is
  why the Airtable shaped expressions downstream still resolve; it was checked
  before those expressions were called a defect, and they are not one.
* `tqo_content` held exactly 2 rows, both retired smoke rows from 21 August.

So the queue the lane actually reads was empty while 46 scored ideas sat one
table away.

## The three holds, all deliberate

1. **All six schedule triggers on V5 are disabled**: Daily 6am Script Writer,
   Mon/Wed/Fri 7am Promote, Sunday 9am Quiet Brief, NCO Tuesday 7:30am Promote,
   Analytics Daily 5am, Every 3h Pipeline Pass. The workflow is active, so
   nothing autonomous runs. Only the seven webhooks and two manual triggers are
   live.
2. **The queue was empty.** `Get Queued Videos` takes one row where status
   equals Queued, oldest by createdAt. Nothing matched.
3. **`voiceReady` is false**, set 21 August pending an ElevenLabs renewal on 25
   August and never lifted. With it false the narration falls to the stock
   Speechify fallback, and the node's own comment says that voice is a stopgap
   so a degraded lane still produces reviewable drafts, and is not a shipping
   voice.

Execution history corroborates: only 7 executions were retained on V5, all
status error, all manual, all 8 September, and all of them the deliberate
refusals of a fake sale rather than anything to do with rendering.

## What a run produces

Claims one Queued row and stamps it Rendering; the Reaper releases a claim after
3 hours. Narration to Drive as MP3, made public. B roll from Pexels, render on
the worker, about 34 minutes for a known good render. MP4 to Drive, shared
public, `video_url` written back, and the status set to **Ready**, never
Published. The row's own note reads "Awaiting Human Review, nothing publishes
until that box is ticked by hand". The human gate Tee requires is already built
in, and `OS 28: Publish Gate` holds ten gates behind it including authorship,
disclosure, brand identity and a packaging check that refuses em and en dashes.

## Ruling 1: a stopgap voice must say so on the artifact

Tee ruled drafts may render in the stopgap voice, for review only, nothing
published. The recommendation had been to hold; he overruled it, and the
objection is logged here once: the fallback is a rented stock voice and his
standing rule is that voice and identity are owned, never rented. His ruling
keeps that intact because nothing leaves Ready without his tick, and the gate
above enforces it.

Acting on the ruling exposed the thing that made it unsafe. `provider` in
`Show Context: Render` was the fixed literal `elevenlabs`, and
`Mark Ready + Save URL` is its only reader: it writes it onto the row as
"narration on <provider>". So every row rendered under the hold since 21 August
would have recorded the clone as the narrator when the stopgap voice actually
spoke. A provenance error on the artifact, and precisely the thing that could
let a stopgap draft pass for a clone narrated one at review time.

`provider` is now derived from a single `VOICE_READY` const that the Voice
Router already gates on, so the flag and the record cannot drift apart. Measured
by executing the node body rather than by reading it: before the change, with
`voiceReady` false, it returned `elevenlabs`; after, it returns the stopgap
voice plus "STOPGAP VOICE, not for publish"; with the const flipped true it
returns the clone. `tableId` and the voice ids are byte identical across the
change, and the routing did not move.

One residual is named in the code rather than hidden: once the hold is lifted,
an ElevenLabs error that degrades into the fallback mid run would still record
the clone. It cannot happen while the hold stands, and it needs the run's own
execution record to settle rather than a context field.

## Ruling 2: the 46 ideas moved

All 46 Airtable Idea rows are now Idea rows in `tqo_content`, carrying topic,
title, the editorial brief, primary subject, show, brand, channel, asset type
and, where Airtable had them, season and episode. `Build Script Prompt` needs
exactly one field, Topic, and throws without it; all 46 carry one.

Three decisions inside the migration worth recording.

* **Five rows were inserted one at a time, in his stated priority order, before
  the other 41 went in as a batch.** The script lane takes the two oldest Idea
  rows by createdAt, and 46 rows written in one call share a timestamp, which
  would have made "produce 1st" through "produce 5th" meaningless. Verified
  afterwards by reading the table sorted by createdAt ascending: the first five
  are PRIORITY 1 to 5 in order, each a few seconds apart, and the remaining 41
  all sit later.
* **`video_url` was left empty on all 46**, including the 11 that carry a
  pre-migration Drive render. Those files are real but they are not this lane's
  output, and `Get Ready to Publish` selects on status Ready plus a non-empty
  `video_url`. The Drive file id went into `notes` as provenance instead, with a
  line saying why.
* **Eight topics keep their em dashes and were not rewritten.** They are names,
  and this repository's own rule refuses a transformation that could change a
  name. Nine editorial briefs did have dashes restructured, because those are
  working notes rather than names, and each rewrite was printed and checked.
  The place where the rule has teeth is the publish gate, which counts em and
  en dashes in the packaging block and refuses to publish on any.

## Ruling 3: the watchdog was watching the wrong tables

`DEVON Pipeline Watchdog` runs every 4 hours and scanned three Airtable Content
tables for status Error or Rendering. TQO and NCO left those tables on 21
August, so two of its three scans watched tables the pipeline no longer writes.
Status could never become Rendering or Error there again, so it would have
reported a clean pipeline forever. A guard credited for a check it no longer
performed, which is the failure class this repository's first law names.

Both scans are now data table reads on `tqo_content` and `nco_content`, using
the same `anyCondition` two condition shape already proven in V5 rather than an
invented one. The TSWS scan stays on Airtable deliberately, because nobody has
verified what the TSWS lane writes, and that is now stated on the sticky note as
the open question rather than left implicit.

`Build Digest` reads both shapes, and three things improved with the move.
Stall timing on a data table row now comes from `updatedAt`, which IS the moment
the lane claimed the row because the claim writes status, system status and
feedback together; the old note said createdTime was used because no last
modified field was confirmed, and that is still true for Airtable and still
labelled approximate per row. Every listed row names which store it is in. And
a scan that returns exactly its 50 row limit now says so, because a truncated
scan and a clean one are otherwise identical.

The negative control was run rather than described: against one data table row
stuck Rendering for two hours plus one in Error, the old node returns silence
and the new one alerts.

Two stale notes on that workflow were corrected in the same pass. The sticky
note claimed the field names Status and Title were unverified studio canon;
checked against the live schema, Status is real and Title does not exist, which
is why the old label fell through to the record id.

## Ruling 4: the schedules stay off

No action, and that is the point. All six remain disabled and were confirmed
byte identical after the V5 edit. Tee fires the lane by hand or by link while it
is being brought back, so there is no surprise 6am run against a half migrated
table.

## What is proved, and what is not

Proved by execution, not by reading:

* The V5 change: the pushed node is byte identical to the file that was
  executed, all 221 other nodes and every connection are byte identical to the
  dump taken before the edit, and the published `activeVersionId` matches the
  draft. n8n saves and publishes separately and both steps were taken.
* The migration: 46 Idea rows read back, priority order confirmed by createdAt,
  `video_url` empty on all of them.
* The watchdog: execution 6739 succeeded with all three scans returning success
  and zero rows, which is the correct silent path and proves both data table
  reads resolve their tables. The digest and the alert did not run, because
  there was nothing to report.

Not proved, with the reason and who can close it:

* **The alarm has not been watched firing on the live workflow.** That needs one
  row temporarily set to Error, and this session's n8n tooling can insert data
  table rows but cannot update or delete them, so doing it would leave a test
  row behind with no way to remove it. The local control above runs the real
  node bodies and is strong, but it is not the live chain including the email.
  Tee or anyone in the n8n UI can close this in under a minute.
* **The render worker did not answer from this container.** No TCP connect at
  all in 20 seconds against a bare IP over HTTP on port 8080, which is
  consistent with this session's network policy dropping it rather than the host
  being down. It cannot be told apart from here. n8n Cloud is the only caller
  that can settle it.
* **Whether the Anthropic credential the script lane uses is funded.** The 21
  August smoke run died at a funding wall on that call, and nothing since has
  exercised it.

## A correction against my own read

Two claims made earlier in the same session were wrong and are corrected here
rather than quietly dropped.

The first was that the pipeline's content table was empty, which was said of
`tqo_content`. That turned out to be the right table after all, but it was said
before the workflow had been read, so it was right by luck and not by check.
The second went the other way: on seeing 66 rows in Airtable, the next move was
almost to report Airtable as the live content system and correct the first
claim. Reading V5's node graph showed there is not a single Airtable node for
Content in it. A correction stated confidently would have been the more
expensive of the two errors.

Also corrected: an earlier note recorded one Airtable row carrying a System
Status of HOLD. The field named System Status is empty on all 66 rows, checked
directly. That value lives in the data table's `system_status` column, which is
where the render lane writes its claim stamps.

## DEVON RECEIPT

```
AREA: TQO, Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-tqo-render-lane-and-two-content-stores_v1_2026-09-10
DATE: 2026-09-10
DECISIONS: Tee ruled four things on a card after the render lane was traced. Drafts may render in the stopgap fallback voice for review only with nothing published, overruling the recommendation to hold, and the objection is logged once in this doc. The 46 Airtable Idea rows migrate into tqo_content with Airtable kept as the archive of what shipped. The DEVON Pipeline Watchdog is repointed at the data tables for TQO and NCO rather than retired, with the TSWS scan left on Airtable until someone verifies what TSWS writes. All six V5 schedule triggers stay disabled until the voice and the queue are settled.
FINDINGS: TQO FINAL V5 is complete and parked in three places at once, all six schedule triggers disabled, the Queued queue empty, and voiceReady false since 21 August, so no video could have been produced and nothing was broken; the content lifecycle moved to the n8n data tables on 21 August while 46 scored ideas stayed in Airtable Content, which V5 does not read at all, its content table id appearing zero times in 346 kB of workflow; the provider field that the render lane writes onto every finished row as the record of who narrated it was the fixed literal elevenlabs with no other reader, so every row rendered under the hold would have credited Tee's clone for words the stopgap voice spoke, which is a provenance error on the artifact and the one thing that made the drafts ruling unsafe; the DEVON Pipeline Watchdog had two of its three scans pointed at Airtable tables the pipeline stopped writing on 21 August, so it could only ever report clean, a guard credited for a check it no longer performed; the publish gate's authorship check compares Human Review against boolean true while the data table column is a string, so it currently fails closed and no data table row can clear it; the Airtable field named System Status is empty on all 66 rows, correcting an earlier note in this session that read one of them as HOLD
OPEN: watch the repointed watchdog alarm actually fire on the live workflow, which needs one row temporarily set to Error and cannot be done from this session because the n8n tooling here can insert data table rows but not update or delete them; confirm the render worker is reachable, which this container's network policy prevented settling; confirm the Anthropic credential the script lane calls is funded, last seen dying at a funding wall on 21 August; decide what to do about the publish gate's authorship comparison before anything is meant to publish from a data table row; verify what the TSWS lane writes so its watchdog scan can be pointed correctly; rotate the ElevenLabs key at the provider and update the VPS credential in the same sitting, then lift the voice hold and run the three line listen test before anything narrated by the clone ships; rule on the 45 grandfathered SYS_OPS docs; the contrast pass on /control; the two link triggers on V5 now carry the x-devon-key header guard but the sale ping still does not
STATUS: shipped to the live estate, not to this repository's runtime. TQO FINAL V5 draft a04712d7 published as the active version with the node verified byte identical to the executed file and all 221 other nodes and connections unchanged; 46 Idea rows inserted into tqo_content and read back with the five priority rows first by createdAt; DEVON Pipeline Watchdog draft b42f64e5 published, execution 6739 success with all three scans clean; the six V5 schedule triggers still disabled; branch restarted from origin/main after PR 203 merged
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
