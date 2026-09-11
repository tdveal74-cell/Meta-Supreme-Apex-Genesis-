# SYS_OPS: the render worker was never deployable

Dated 2026-09-11. Supersedes nothing. It closes four items Tee authorised in one
instruction, and it records the thing that turned up while closing the second:
the render worker could not have been started by anybody, on any host, at any
point in the last five weeks, and not for the reason every document says.

## The four items

Tee's instruction was "do them all" against a five item recommendation. Three
closed, one is his to close, and the second turned out to be a different job
than the one recommended.

## 1. Two dangling Cloud ids on the VPS, repointed

The bulk Cloud to VPS import carried Cloud ids into `TSWS 00 - Render Job`
(`CX07qa6O1hTSXlpj`). Neither resolves on the VPS, so wiring a real worker URL
into that workflow would have failed on auth rather than on DNS, which is the
harder failure to read.

Verified against the live estate before writing, not from a record:

| | VPS value | present in the estate |
|---|---|---|
| `Header Auth account 10` | `WpZNTg9qduOFC5NM` | yes, one of 19 httpHeaderAuth credentials |
| `b9FYEfGUlMiYJCCU`, what the nodes held | | no, not in the 19 |
| `OS - Error Handler (all pipelines)` | `GbeNilHQzjmoWDz3`, active | yes |
| `rqYmaQh91iCce8DJ`, what settings held | | no, not among the three error workflows |

```
Submit Job   credentials.httpHeaderAuth.id   b9FYEfGUlMiYJCCU -> WpZNTg9qduOFC5NM
Poll Job     credentials.httpHeaderAuth.id   b9FYEfGUlMiYJCCU -> WpZNTg9qduOFC5NM
settings.errorWorkflow                       rqYmaQh91iCce8DJ -> GbeNilHQzjmoWDz3
```

Three operations applied. Re-read afterwards rather than trusting the write
response: both nodes carry the new credential, settings carry the new error
workflow, `availableInMCP` survived the settings write, `versionId` moved
`1278ff9d` to `daabc50c`, and the node count is 13 before and after.

## 2. The render worker. Not a deployment job.

The recommendation was that this was deployment rather than construction,
because `jobs.js` existed and had a recorded run of 516 frames at 21.500000s.
That was wrong in two ways, and both only showed up on reading the file.

### There is no server

`jobs.js` is a library. It ends in
`module.exports = { JOBS, BadJob, safePath, ... }` and it exports job
definitions. Nothing in it listens on a port, checks a token, or spawns
anything. The Drive folder holding it contains four files: `jobs.js`, two
audit documents and an unrelated EditForge note. There is no `server.js`
anywhere in Drive.

So the documented worker had no half that could be started. Every document
describing how to deploy it, including this repository's own autonomy driver
doc, describes deploying a library.

### The copy on Drive is the pre-audit one

Two Drive documents describe this engine and they contradict each other.
`WORKER_jobs.js_rev2_AUDIT_7AUG2026` reports three defects found **and fixed,
all measured**, with before and after frame counts.
`EP01_AUDIO_DEFECT_8AUG2026`, written the next day, says `jobs.js` rev 2 still
carries two original defects.

The file settles it, and it is worse than either. Checked by grep against the
downloaded bytes:

| marker the 7 Aug audit says it added | occurrences in the Drive file |
|---|---|
| `normalizeChain` | 0 |
| `stills`, `clips`, `normalized_to` | 0 |
| `force_original_aspect_ratio`, `setsar` | 0 |
| `scanned_depth`, `skipped_done` | 0 |
| `assemble_cut` returning `expected_duration` | returns `{ output, shots }` only |

`scan_drop` still contains the hard coded two level walk the audit describes as
the defect, verbatim. A Drive full text search for `normalizeChain` and
`assemble_cut` returns exactly one `.js` file, this one, and the index does
cover `.js` because it returned that file. The audited copy was measured on
7 August and never written back.

That is the 7 August law failing against itself, and the 8 August record names
it: a fix applied to an output is not applied until it is written back into the
template that produced the output.

### The five defects, and the one that decides the show

| | defect | consequence |
|---|---|---|
| F1 | `assemble_cut` has no still handling | the image demuxer emits ONE frame and `trim=start=0:end=6` keeps exactly that one. 37 of 37 EP01 shots are stills, so a 14 minute episode renders as a 1.5 second slideshow |
| F2 | no geometry, SAR or fps normalisation before `xfade` | on mixed pixel sizes xfade fails to configure the output pad and ffmpeg writes a 0 byte file |
| F4 | `scan_drop` walks exactly two levels | `drop/EP01/manifest.json` is one level down and is never seen, so the job returns `count:0`, which reads as nothing to do |
| A1 | `duck_mix` builds its guards from an `afade` pair | `afade=t=out` holds zero forever and the following `afade=t=in` multiplies everything before its own start by zero. They never reopen |
| A2 | `amix=duration=first` unpinned | measured 58 ms short of its first input, leaving the last frame and a half with no audio |

A1 is the one that decides whether anything can ship. On EP01 it killed the bed
at 544.000s of an 880.907s episode, and because the dialogue stem ends at
827.75s by design, the final 53 seconds were digital silence under picture. It
passed every gate that existed, because the only gate measured length and a
silent file is exactly as long as a loud one. The 8 August record is blunt about
the blast radius: deployed as it stood, all eleven remaining episodes ship with
a dead sound bed.

`-nostdin` is a sixth, graded low and fixed anyway because it costs nothing.
Under systemd the process has no terminal, so the keystroke that kills a render
cannot reach it there.

### What was built

`deploy/render-worker/` now carries the engine, the missing server, a deploy
runbook and 32 tests. The engine leaves Drive for the first time and lives in
version control.

`server.js` is written to a contract that was already fixed and is not
negotiable, because the caller has been written since August. TSWS 00 pins the
`202` on submit, the `body.id` the poll reads, the `done` / `error` / `invalid`
status strings, and the `id`, `result`, `seconds`, `type`, `error` and
`exitCode` fields the two return nodes read. It inherits the engine's one rule:
every job is an argv array, `execFile` and never `exec`, so a single quote in an
episode title cannot become a command.

One thing was deliberately not changed. The v3 script treats a manifest's `in`
and `out` as timeline positions; `assemble_cut` treats them as source trims and
accumulates a different xfade offset. Both are internally consistent and nobody
has established which the TSWS manifest speaks. Changing it on a guess would
silently move every cut in the episode, so it is recorded rather than fixed.
This repository's own rule refuses a transformation that could change a number.

### What is proved, and what is not

Proved by execution:

* `jobs.test.js`, 16 tests, all passing. It pins what the builders emit, and it
  compares the new gain envelope numerically against the EP01 reference
  expression from 540s to 552s at 0.5 ms steps. Worst divergence `5.7e-14`.
* `server.test.js`, 16 tests, all passing, against a real listening server over
  real HTTP. It runs `{"type":"exists","params":{"path":"."}}`, which is the
  exact smoke test the sticky note on TSWS 00 prescribes and records as having
  never once succeeded, and gets `ok:true`.
* The negative control: the same `jobs.test.js` against the unfixed Drive copy
  fails 15 of 16. The one that passes is the ffprobe guard, correctly true in
  both. The tests detect the defects rather than agreeing with the fix.

The negative control also caught a defect in the test harness itself. `scan_drop`
passed against the known defective original, which is impossible. The harness
called the test function without awaiting it, so a failing async assertion became
an unhandled rejection and was counted as a pass. That test was asserting
nothing. Fixed, and the control then failed as it should. A green that means
nothing is the exact failure the first law names, and the only reason it surfaced
is that the control was run at all.

Not proved, with the reason and who can close it:

* **No ffmpeg exists in this container.** Every test above pins an argv and a
  filter graph. None of them ran ffmpeg, so none prove a pixel or a sample. The
  frame counts, the levels and the silences have to be measured on the box. The
  four step acceptance suite is in `DEPLOY.md` and it is Tee's to run, or
  anyone's with a host. Until it passes, this worker is unproven however green
  the unit tests read.
* **Where it should live.** The autonomy driver names srv1936199, the EditForge
  box, or its own host. srv1936199's public address is not recorded in this
  repository and was not invented here.

A second float finding worth keeping, because it was nearly written up as a
defect. At the two instants where a ramp meets the gap boundary the envelope
leaves a residual of `5.68e-14`, which is -264.9 dBFS. `duck_mix` writes
`pcm_s24le`, whose least significant bit is -138.5 dBFS, so that residual
quantises to exactly 0 in the output. It is true silence in the file. The first
assertion demanded exact float zero and failed; the assertion was wrong, not the
code, and the threshold it now uses is the 24 bit floor with the arithmetic
shown.

## 3. Schedule ownership. No action, and now measured.

The recommendation was to leave the schedules with Cloud and activate nothing on
the VPS. Read from the live estate rather than assumed, the position is stronger
than that.

Of 60 workflows in the VPS project, exactly **two** are active:
`DEVON - Error Alarm` (`bqcnIS0Qv4RkTCU1`) and
`OS - Error Handler (all pipelines)` (`GbeNilHQzjmoWDz3`). Both carry
`triggerCount: 0`, so neither has a schedule or a webhook; they are error
handlers that fire only when another workflow fails. `TQO FINAL V5` is
`active: false` on the VPS entirely, so the question of its six schedule
triggers does not arise there.

Nothing on the VPS can fire on a clock. There is no double firing risk today and
nothing needed changing.

## 4. The stale brand skill. Tee's to close.

`shadow-we-share-brand` (`skill_01Hs1RJt7Pevt1cVgftrwTgQ`) is enabled at the
claude.ai account level. The tooling available in a session here is read only;
there is no call that can write a skill body. The container copy was deleted on
2026-09-10 after confirming it carried none of the delta, and it resyncs from the
account, so deleting it again achieves nothing. The account copy is the one that
loads everywhere outside this repository and it is the one that has to be
replaced, from the skill settings page. One minute on the phone.

## DEVON RECEIPT

```
AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-render-worker-was-never-deployable_v1_2026-09-11
DATE: 2026-09-11
DECISIONS: Tee authorised all five recommended items in one instruction. The second was recommended as a deployment job and is recorded here as a construction job instead, because the worker had no server and the only reachable engine was the pre-audit copy. The engine moves from Drive into version control under deploy/render-worker rather than being deployed from Drive. The timeline versus source trim divergence between render_ep01_v3.sh and assemble_cut is recorded and deliberately left unfixed, because changing it on a guess could move every cut in the episode and this repository refuses a transformation that could change a number. The inherited comments in jobs.js keep their em dashes so the diff against the Drive original stays auditable line by line, with every added line dash free; Tee can call for a mechanical pass instead. The worker gets its own token rather than continuing to share Header Auth account 10.
FINDINGS: The TSWS render worker has never run on any host, and the reason is not the missing URL every document names: jobs.js is a library that exports job definitions, nothing in Drive listens on a port, and there is no server.js anywhere in Drive, so the documented worker had no half that could be started. The jobs.js on Drive is the pre-audit copy and carries all three defects the 7 August audit reports as found and fixed with measurements, confirmed by grep against the downloaded bytes: normalizeChain, stills, clips, normalized_to, force_original_aspect_ratio, setsar, scanned_depth and skipped_done all appear zero times, assemble_cut returns only output and shots, and scan_drop still contains the hard coded two level walk verbatim. It also carries both defects the 8 August record names, so five in total. The one that decides the show is the afade pair in duck_mix, where afade=t=out holds zero forever and the following afade=t=in multiplies everything before its own start by zero, which on EP01 killed the bed at 544.000s of an 880.907s episode and left the final 53 seconds as digital silence under picture, passing every gate because the only gate measured length. Two Cloud credential and error workflow ids on VPS TSWS 00 resolved to nothing on that instance and would have failed a smoke test on auth rather than on DNS. The negative control caught a defect in the new test harness itself, where an async test was never awaited so a failing assertion became an unhandled rejection counted as a pass, which is a green that means nothing and surfaced only because the control was run. Of 60 VPS workflows exactly two are active and both are error handlers with triggerCount 0, so nothing on the VPS can fire on a clock.
OPEN: run the four step acceptance suite in deploy/render-worker/DEPLOY.md on a real box, because no ffmpeg exists in the container these fixes were written in and nothing here proves a pixel or a sample; choose and provision the host, srv1936199 or its own, whose public address is not recorded in this repository; settle whether the TSWS manifest speaks timeline positions or source trims before the first full episode assembles; split Header Auth account 10 so the worker holds its own token; replace the account level shadow-we-share-brand skill body with the committed v2, which only Tee can do from the skill settings page; run the psnr job and record a number for the three encode generations rather than carrying the worry; install playwright and chromium on the box if the render_mark_full mark layer is wanted, neither being pinned by this repository
STATUS: shipped to this repository, not to any host. VPS TSWS 00 repointed and re-read, versionId 1278ff9d to daabc50c with 13 nodes before and after. deploy/render-worker carries jobs.js with five fixes, the new server.js, a deploy runbook, a systemd unit and 32 passing tests, 16 pinning the builders and 16 exercising real HTTP. Negative control fails 15 of 16 against the unfixed original. The worker has still never been started on a host and no acceptance check has measured a sample. Branch restarted from origin/main after PR 193 merged.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
