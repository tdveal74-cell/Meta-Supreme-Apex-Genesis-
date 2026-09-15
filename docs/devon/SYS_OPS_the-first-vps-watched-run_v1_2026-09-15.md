# The first VPS watched run

Status doc, 2026-09-15. TQO FINAL V5 on the VPS (`qEkGOUsNyVaRAmm6`) produced
a finished episode file for the first time: execution 46 ran the render lane
end to end on the VPS render adapter and stopped at Human Review. Eight fires
were needed to get there. Every one of the seven failures was a real gap and
each is recorded below with its cause, because the next lane to be cut over
will hit the same shapes.

Supersedes nothing. It follows `SYS_OPS_eight-rulings-and-v5-on-the-vps_v1_2026-09-15.md`,
which recorded the V5 port and the sixteen rulings that preceded this run.

## Rulings by Tee on 2026-09-15, this arc

1. The VPS table is the feed for the watched run ("A table on n8n"). Read as:
   copy one real Idea row from Cloud `tqo_content` to the VPS, the S1E1 row.
2. Flip `VOICE_READY` to true on the VPS before firing. The hold from 21 Aug
   was never lifted after the 25 Aug renewal; the owned voice rule wins.
3. The VPS Anthropic key is unfunded and stays unfunded for now ("funds are
   low"). The script for the watched run is written in the Claude Code
   session from the repository's dated receipts and written onto the row as
   Scripted, with the Doctor and originality passes skipped for that row.
4. The VPS V5 renders on the VPS adapter at `172.16.2.1:8081`, the way the
   09-13 adapter test copy did, instead of the Oracle worker at
   `129.80.78.29:8080`.

Premise corrected on the way: moving the pipeline to the VPS removes the
n8n execution cap and the Gateway credit bill. It does not remove the Claude
bill. The Cloud copy used native Anthropic nodes billed to Gateway credits
($1.07 left on the usage page); the VPS copy calls `api.anthropic.com` with
Tee's own key, so script, doctor, manifest, packaging, QC and brief all bill
his account at API rates. TTS bills ElevenLabs. The adapter and Pexels are
the free steps.

## What was done, in order

| step | write | read back |
|---|---|---|
| Seed row | Cloud `tqo_content` row 3 (Airtable `recoa6bxOeTuNx7DL`) copied to VPS `tqo_content` `2GtmrFcTNqVMbddh` as row 4, status Idea | row read: topic, S1E1, Flagship; the idea field was empty on the first insert because the copy was written before the source row was read, caught on read back and patched through a one shot helper workflow, since archived |
| Voice | `Show Context: Render` jsCode, `const VOICE_READY = false` to `true`; published `511cebe7` | draft diff: one node changed, the flag line plus a trailing newline the tool call added |
| Script | S1E1 script, title, description with the disclosure line and the audit line, 11 b-roll phrases, plus the fields `Script: Fill Run Fields` would have set (ai_disclosure, claim_validity, recheck_by, primary_subject, thumbnail_headline, channel, asset_type), written by helper workflow, row 4 to Scripted | row read: 1,809 words, no em or en dash, provenance in `last_feedback` |
| Test row | VPS row 3 "TQO Adapter Controlled Test", Queued after the reaper, set to `Retired Test` so the render lane claims one row | row read |
| Render lock | `alwaysOutputData: true` on `Render Lock: Other Brand` and `Anything Still Rendering?`; published `d2c96718` | draft diff: exactly those two nodes, parameters unchanged, connections unchanged |
| Render path | `Start Render` and `Check Render Status` to `http://172.16.2.1:8081/v2/movies` with credential `f530bc56e109060d` (TQO Render Adapter); `Build Movie` and `Plan B-Roll Segments` jsCode from the adapter test copy `a11aa1a50e871723`; published `93df27a7` | draft diff: exactly those four nodes, parameters equal to the adapter copy byte for byte |
| Claims released twice | row 4 back to Queued after executions 39 and 42, by helper workflow, `render_attempts` 1 then 2 | row read each time |

Every helper workflow was a manual trigger plus one data table node, run
once, then archived: `zVXiZyDGe40n8D2B`, `UZeepNU30FOXESGR`,
`AXx73edOwCz3SUJ2`, `QovHR2po0vR0MXs4`, and the read only probe
`PF4sbhd5l1KGtacs`. The MCP has no row update tool, which is why they exist.

## The eight fires

| execution | stopped at | cause | fix |
|---|---|---|---|
| 27 | every lane empty, 2 s | the VPS tables held only test rows | seed row |
| 29, 31, 33 | `Write Script (Claude)`, 401 "x-api-key header is required" | the `anthropic` credential `EdFztvzdUL9PSycJ` on the VPS does not send `x-api-key`, and the key behind it is unfunded anyway | script written in session (ruling 3) |
| 38 | `Render Lock: Other Brand`, 0 items, lane ended silently | a data table read with zero rows emits no item, so the two shims and the IF that were written for a synthetic empty item never ran; Cloud V5 has the same shape | render lock fix |
| 39 | `Upload MP3`, 403 | the Google Drive API was disabled on Google Cloud project 828264336169, the project the reconnected credential belongs to | Tee enabled it |
| 42 | `Start Render`, 401 "Invalid API Key" | the Oracle worker at `129.80.78.29:8080` rejects the VPS `json2video` credential; the probe from the VPS showed the adapter at `172.16.2.1:8081` healthy (`ok:true, active 0, queued 0`) and accepting the TQO Render Adapter credential | render path (ruling 4) |
| 46 | `Write Brief (Claude)`, 401, after the render lane completed | the Brief lane found the new Ready row and called Claude on the unfunded key | none yet; see open |

Executions 30, 32, 34, 40, 43 and 47 are the VPS OS Error Handler
`GbeNilHQzjmoWDz3` firing on each failure, all success. The rebound handler
works on a real failure, which no test had shown before today.

## Execution 46, measured

- `ElevenLabs TTS (Tee Clone)`: 115.5 s, `audio/mpeg`, 8.78 MB, voice
  `LLhnFOCTr3y3wrH59DtJ`, true branch of the voice router; Speechify did not
  execute. The row's telemetry line reads "narration on elevenlabs, Tee clone".
- `Upload MP3`: Drive file `1nHGvDA65OH13zUPYBalXIedLsk1NVLmN`, made public.
- `Pexels Search` answered; `Build Movie`: 45 clips, 0 from the retired pool,
  0 held.
- `Start Render`: project `faca31e4-19f4-4ab7-b1e5-7a65c3d2c588`; seven polls
  at running, the eighth done with a file URL on the adapter.
- `Download MP4`: `video/mp4`, 159 MB. `Upload Video (Ready to Publish)`:
  Drive file `1KzmLIjpJ6Ztl22WDVC8Fyoea0UoBveCa`, named after the title.
- `Mark Ready + Save URL`: row 4 Ready, `video_url` set, claim released,
  `render_attempts` 0 (the node resets it). Start to Ready: eleven minutes.
- `Preflight: Can This Clear?` on the Publish lane recorded a skip: "Human
  Review is not ticked". No manifest, packaging, QC or YouTube call ran.
- Spend: three ElevenLabs syntheses of about 9,600 characters each across
  executions 39, 42 and 46, because a failed run does not keep its audio.
  No Anthropic spend anywhere.

The file for Tee to watch:
`https://drive.google.com/file/d/1KzmLIjpJ6Ztl22WDVC8Fyoea0UoBveCa/view?usp=drivesdk`.
Under the house rule it passes when he has watched it end to end, and the
script is a first draft written in session, not a Doctor passed episode.

## Findings that outlive this run

1. Cloud V5 `gsGJQan7a6ZufhYt` cannot render as it stands: the two render
   lock reads there have no `alwaysOutputData` either, so its render lane
   ends at the same node whenever `nco_content` holds no Rendering row, which
   is its normal state. It has not been touched.
2. `Reaper: Find Stale Claims` on the VPS carries `matchType: anyCondition`,
   so its two conditions are ORed and it returned the `Retired Test` row on
   an `isNotEmpty` match against an empty string. The shim filtered it out
   this time. Cloud's copy has no `matchType` set, which defaults the same
   way. Not fixed; grade before touching.
3. The Sunday Brief timer and the Publish lane's three Claude calls fail on
   the VPS until the Anthropic key is funded or the six Claude nodes are
   repointed. The Idea lane finds no Idea rows on the VPS, so the 06:00
   script timer would not spend.
4. The Oracle worker at `129.80.78.29:8080` is reachable and answers with
   FastAPI validation errors on GET; which key it accepts is unverified from
   here. The VPS `json2video` credential is not it.
5. n8n hides a credential's header name in the execution record, so a wrong
   header name can only be diagnosed from the far side's error text.

## The cap anchor, from the usage page

Tee sent the n8n Cloud usage page at about 08:50Z: 1,756 of 2,500 executions
in September, $1.07 Gateway credits, cycle reset 28 Sep 2026. The newest
Cloud execution id listed before that moment is 7130 (08:00:13Z); the next
listed id is 7135 at 09:00:00Z, so up to four unlisted ids were consumed in
that hour and the anchor is accurate to within four executions.

The five lines, for Tee to set on the Railway api service by hand (a session
never sets a production variable):

```
N8N_EXECUTION_CAP=2500
N8N_EXECUTION_CAP_ANCHOR_ID=7130
N8N_EXECUTION_CAP_ANCHOR_SPENT=1756
N8N_EXECUTION_CAP_ANCHOR_AT=2026-09-15T08:50:00Z
N8N_EXECUTION_CAP_RESETS_AT=2026-09-28
```

`app/services/n8n_telemetry.py` computes spent as anchor spent plus the id
delta from the anchor id, so the burn on the Execution Hub becomes an
estimate the day these land. The `N8N_SECONDARY_` set stays unset: the VPS
has no cap.

## Open

- Tee watches the file and says whether it passes. On his word: enable the
  six V5 schedules on the VPS, unpublish Cloud V5, with the Brief caveat
  above stated again at that moment.
- Fund or repoint the six Claude nodes on the VPS before any lane that writes
  scripts, packaging or briefs is expected to run on a timer.
- The Heartbeat pulse fix on Cloud (`2a1c5ab4`) still owes its 10:15Z
  re-measure.
- The five cap anchor lines above, on Railway, by Tee.
- Rotation of `DEVON_OPS_SECRET`; the standalone reflection Routine; the
  Sonnet 5 question; the 08-31 vintage port; the DEVON cutover.

## DEVON RECEIPT

AREA: Systems
TYPE: status
ARTIFACT: docs/devon/SYS_OPS_the-first-vps-watched-run_v1_2026-09-15.md
DATE: 2026-09-15
DECISIONS: four rulings by Tee on 2026-09-15 for the watched run: the VPS table is the feed, seeded with Cloud row 3 as VPS row 4; VOICE_READY true on the VPS; the S1E1 script written in the Claude Code session and written onto the row as Scripted because the VPS Anthropic key is unfunded; the VPS V5 renders on the VPS adapter at 172.16.2.1:8081 with the TQO Render Adapter credential.
FINDINGS: execution 46 rendered S1E1 end to end on the VPS in eleven minutes, ElevenLabs clone narration 8.78 MB, 45 clips, 159 MB MP4 on Drive as 1KzmLIjpJ6Ztl22WDVC8Fyoea0UoBveCa, row 4 Ready, Preflight skipped on Human Review; seven earlier fires failed on the empty tables, the anthropic credential's header, a zero row read that ended the render lane silently on both instances, the Drive API disabled on project 828264336169, and the Oracle worker rejecting the json2video credential; the error handler fired green on every failure; the cap anchor from the usage page is 1,756 of 2,500 at id 7130, reset 2026-09-28.
OPEN: Tee watches the file; schedules on the VPS and Cloud V5 unpublished on his word; the six Claude nodes on the VPS need a funded key or a repoint before the Brief and Publish lanes can run; the Heartbeat re-measure at 10:15Z; the five cap anchor lines on Railway; the secret rotation; the reflection Routine; the Sonnet 5 question; the 08-31 port; the DEVON cutover.
STATUS: the VPS content lane is proven from Queued to Ready on a real row with the owned voice; three VPS V5 versions published and read back today (511cebe7, d2c96718, 93df27a7); PR #223 merged at 8bd2dd00 and the branch restarted from main.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
