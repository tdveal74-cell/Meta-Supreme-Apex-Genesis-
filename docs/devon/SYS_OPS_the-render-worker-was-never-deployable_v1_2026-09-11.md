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
runbook, a hardened systemd unit, the byte-for-byte Drive original as a fixture,
a CI lane and 46 tests. The engine leaves Drive for the first time and lives in
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

* `jobs.test.js`, 27 tests, all passing. It pins what the builders emit, and it
  compares the new gain envelope numerically against the EP01 reference
  expression from 540s to 552s at 0.5 ms steps. Worst divergence `5.7e-14`. It
  also pins the exact xfade offsets and the protected-silence provision, both
  added after the critic proved nothing pinned them.
* `server.test.js`, 19 tests, all passing, against a real listening server over
  real HTTP. It runs `{"type":"exists","params":{"path":"."}}`, which is the
  exact smoke test the sticky note on TSWS 00 prescribes and records as having
  never once succeeded, and gets `ok:true`.
* `negative-control.js` runs the same suite against
  `reference/jobs.drive-2026-08-07.js`, the engine byte for byte as recovered,
  and requires that it fail. It fails 22 of 27. It checks the fixture's sha256
  and the absence of the audit markers first, so it cannot drift into testing the
  fixed file.
* Every guard added in the critic round was mutation tested: the fix reverted one
  at a time, the suite required to go red. Six for six.

The negative control has now caught two defects in the verification itself. The
first was in the harness. `scan_drop`
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

## 2b. The critic pass, and what it cost to skip

A fresh critic was spawned against the pushed commit with worktree isolation,
pinned to `b47986d` and made to echo the SHA back. It returned
PASS-WITH-CONDITIONS: safe as a repository artifact, not safe on the public
internet. It was right on every count that mattered, and two of its findings are
the interesting ones because they are about the verification rather than the
code.

**One authenticated request wedged the whole process.** The native job path had
no timeout at all, and its jobs used synchronous filesystem calls on the event
loop. `read_text` against a FIFO blocks in `open()` forever, so `/health` went
dark, the queue stopped, and because the process never exited systemd's
`Restart=on-failure` never fired. The critic demonstrated it against a real
listening server: health 200 before, `curl_exit=28` after. The runbook tells an
operator to poll exactly the endpoint that goes dark.

**`safePath` was lexical.** `path.resolve` does not follow symlinks, so a single
symlink inside the work root was a full read and write escape. The critic served
`/etc/passwd` through `exists` and `/etc/hostname` through `read_text`. On a
render box, symlinked media mounts under the work root are the normal wiring,
which is exactly where the unreleased media lives.

Also found and fixed: `http_download` validated the scheme and not the
destination, so it would fetch `169.254.169.254` and hand the result back through
`read_text`; `conform_grain` emitted `apad` with no ending to pad to, which with
no `-t` is a render that never ends, and it is the same defect this file had
already fixed in `duck_mix` two jobs over; the queue was unbounded; there was no
SIGTERM handler, so the unit file's stop comment described a drain that did not
exist; and `duck_mix` hardcoded `pcm_s24le` while the runbook told the operator
to write `.flac`, which does not mux, sending them into a muxer error on the one
acceptance check that decides the show.

### The two findings that were about the verification

**The tests did not pin the two most consequential pieces of logic.** The critic
mutated `offset += dur - xf` to `offset += dur`, which moves every cut in the
episode, and the suite returned 16 passed, 0 failed. It then deleted the entire
protected-silence provision, the guard that refuses a cut boundary inside a hold
pipeline 02 deliberately preserved, and the suite returned 16 passed, 0 failed
again. Six of eighteen job types were exercised; `conform_grain`, about 190 lines
carrying the cut, the grade, the ending and that provision, had none.

Both are now pinned, and every guard added in this round was mutation tested:
the fix reverted one at a time, the suite required to go red. Six for six. One of
those mutations crashed the dispatcher rather than failing an assertion, which
surfaced a further defect nobody had asked about: an exception inside `runNext`
killed the process and left the concurrency counter incremented, so the slot
would have leaked even without a restart. The right failure for a bad job is a
failed job, never a dead server.

**The strongest claim in the document was unreproducible.** "The negative control
fails 15 of 16 against the unfixed original" was the evidence for "the tests
detect the defects rather than merely agreeing with the fix", and nobody reading
this repository could run it, because the unfixed engine lived only on Drive. It
is now committed at `reference/jobs.drive-2026-08-07.js`, byte for byte, and
`negative-control.js` verifies its sha256 and the absence of the audit markers
before running the suite against it and requiring failure. It fails 22 of 27.
Testimony became evidence.

**No CI lane ran any of it.** Forty six tests, zero workflows, which is precisely
the shape CLAUDE.md already records for `check:audio`: it ran in no workflow at
all and four separate review passes found it. The precedent existed and was not
followed. `.github/workflows/render-worker-ci.yml` now runs the builders, the
HTTP contract and the negative control, path filtered to the worker directory,
with a step that fails if the worker ever gains an npm dependency.

The critic's one contradicted claim is worth recording too, because it was
checked rather than accepted: it reported that DEPLOY.md's "every line added by
the fixes is dash free" was contradicted by an en dash at `jobs.js:692`. The
diff shows that line is inherited from the Drive original, not added, so the
claim stood. The doc now states the inherited count exactly rather than saying
"em dashes included" and leaving the en dash unmentioned.

## 2c. It ran. 2026-09-12.

Deployed to `srv1936193` (`2.25.140.44`, Ubuntu 24.04.4 LTS, 2 cores, 7.8 GiB),
bound to `172.16.2.1:8080`, the `n8n_backend` docker bridge gateway. The three
suites passed on that box with exit code 0 each, checked individually rather
than inferred from a chain, and the negative control failed 22 of 27 against the
committed Drive original as it must.

Four jobs then ran against the live service, chosen to walk a different code
path each time rather than to repeat one green:

| job | what it proved |
|---|---|
| `exists` | the HTTP contract end to end: 202 with an id, queue, run, poll, `ok:true`. The smoke test the TSWS 00 sticky note records as having never once succeeded. |
| `probe` | the `execFile` path. A real **ffprobe** spawned, stdout captured and parsed, duration exactly 1.0 on a generated file. |
| `silence_detect` | a real **ffmpeg** spawned, **stderr** captured, the regex returning `count: 1` over 0 to 1 second. Non-empty on purpose, because an empty list cannot distinguish working from not working. |
| the two exposure checks | public IPv4 and IPv6 both refuse while the n8n container reaches the bridge address. Between them the bind is proved by behaviour rather than by reading the file. |

### Two things the estate taught the runbook

**A container's loopback is the container.** The recommendation to bind to
`127.0.0.1` was correct for a bare host and wrong here, because n8n runs as
`n8n-n8n-1` on two custom bridge networks. Had it shipped that way, every call
would have returned connection refused, which reads as a bad URL or a bad token
rather than as a network namespace boundary. Caught before the install only
because the box was asked what it actually looked like rather than assumed.

**`MemoryMax=8G` was a defect in the committed unit file.** The machine has
7.8 GiB total, so the ceiling never binds, and under pressure the kernel picks a
victim that could be n8n rather than the render. A limit above the machine's
total memory is not a limit. Corrected to `5G` on the box and the runbook now
says to set it below total RAM on any host.

A third, smaller: a host running n8n in docker has no Node, because n8n never
needed it there. Ubuntu 24.04 ships 18.19.1, which is enough, so no third party
repository was required.

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
FINDINGS: A fresh critic on the pushed commit returned PASS-WITH-CONDITIONS and was right on every count that mattered, and the two findings worth keeping are about the verification rather than the code: mutating the xfade offset arithmetic so that every cut in the episode moves left the suite at 16 passed 0 failed, and deleting the entire protected-silence provision left it at 16 passed 0 failed again, so the two most consequential pieces of logic in the file were pinned by nothing; and the sentence carrying the whole verification argument, that the negative control fails against the unfixed original, was unreproducible by anyone reading the repository because the unfixed engine lived only on Drive. On the code: one authenticated request wedged the entire process, because the native job path had no timeout and its jobs blocked the event loop, so a FIFO through read_text took /health down without exiting and systemd's Restart=on-failure therefore never fired; safePath was lexical, so one symlink inside the work root served /etc/passwd through exists; http_download checked the scheme and not the destination, so it would fetch cloud metadata and hand it back through read_text; conform_grain emitted apad with no ending to pad to, the same defect already fixed in duck_mix two jobs over; the queue was unbounded; there was no SIGTERM handler, so the unit file's stop comment described a drain that did not exist; and duck_mix hardcoded pcm_s24le while the runbook told the operator to write .flac, which does not mux, which would have sent Tee into a muxer error on the one acceptance check that decides the show. Forty six tests ran in no CI workflow at all, the same shape CLAUDE.md already records for check:audio. The TSWS render worker has never run on any host, and the reason is not the missing URL every document names: jobs.js is a library that exports job definitions, nothing in Drive listens on a port, and there is no server.js anywhere in Drive, so the documented worker had no half that could be started. The jobs.js on Drive is the pre-audit copy and carries all three defects the 7 August audit reports as found and fixed with measurements, confirmed by grep against the downloaded bytes: normalizeChain, stills, clips, normalized_to, force_original_aspect_ratio, setsar, scanned_depth and skipped_done all appear zero times, assemble_cut returns only output and shots, and scan_drop still contains the hard coded two level walk verbatim. It also carries both defects the 8 August record names, so five in total. The one that decides the show is the afade pair in duck_mix, where afade=t=out holds zero forever and the following afade=t=in multiplies everything before its own start by zero, which on EP01 killed the bed at 544.000s of an 880.907s episode and left the final 53 seconds as digital silence under picture, passing every gate because the only gate measured length. Two Cloud credential and error workflow ids on VPS TSWS 00 resolved to nothing on that instance and would have failed a smoke test on auth rather than on DNS. The negative control caught a defect in the new test harness itself, where an async test was never awaited so a failing assertion became an unhandled rejection counted as a pass, which is a green that means nothing and surfaced only because the control was run. Of 60 VPS workflows exactly two are active and both are error handlers with triggerCount 0, so nothing on the VPS can fire on a clock.
OPEN: run the TSWS 00 smoke test from the n8n UI to prove the two URL edits and the credential, which is the last unproved link between n8n and the worker; run the four step acceptance suite in deploy/render-worker/DEPLOY.md on a real box, because no ffmpeg exists in the container these fixes were written in and nothing here proves a pixel or a sample, and two filter-level claims in particular rest on ffmpeg's documented semantics rather than on a run, that loop holds a single decoded frame for F frames and that apad with a zero pad_dur and no -t pads indefinitely; the acceptance suite covers F1, A1 and A2 but exercises F2 only incidentally, scan_drop not at all and -nostdin not at all, so add those two if the lane will lean on them; name-based SSRF through DNS is not closed by the private-address guard and cannot be closed at that layer; there is still no disk quota on the work root, so render_mark_full will accept a request for a great many 4K frames; the worker token is a single shared secret with no rotation mechanism; choose and provision the host, srv1936199 or its own, whose public address is not recorded in this repository; settle whether the TSWS manifest speaks timeline positions or source trims before the first full episode assembles; split Header Auth account 10 so the worker holds its own token; replace the account level shadow-we-share-brand skill body with the committed v2, which only Tee can do from the skill settings page; run the psnr job and record a number for the three encode generations rather than carrying the worry; install playwright and chromium on the box if the render_mark_full mark layer is wanted, neither being pinned by this repository
STATUS: deployed and running. The worker ran for the first time on 2026-09-12, on srv1936193 at 172.16.2.1:8080, having never run on any host before that. Four jobs proved four separate code paths: exists the HTTP contract, probe the execFile and stdout path with a real ffprobe, silence_detect the ffmpeg and stderr path with a non-empty parse, and the two exposure checks proving the bind by behaviour. Two deviations from the committed defaults were required and are recorded in DEPLOY.md: HOST bound to the docker bridge gateway because a container's loopback is the container, and MemoryMax cut to 5G because 8G sat above the machine's 7.8 GiB total and therefore never bound. Still unproved: n8n's own wiring inside TSWS 00, and every one of the five defect fixes at the sample and pixel level, because no acceptance check has measured a sample. VPS TSWS 00 repointed and re-read, versionId 1278ff9d to daabc50c with 13 nodes before and after. deploy/render-worker carries jobs.js with the five engine fixes plus six more from the critic round, the new server.js, a deploy runbook, a hardened systemd unit, the byte-for-byte Drive original as a committed fixture, and 46 passing tests: 27 pinning the builders, 19 exercising real HTTP against a real listening server. negative-control.js verifies the fixture's sha256 and requires the suite to FAIL against it, currently 22 of 27. Every guard added in the critic round was mutation tested, six for six. A path-filtered render-worker-ci.yml now runs all three. The worker has still never been started on a host and no acceptance check has measured a pixel or a sample. Branch restarted from origin/main after PR 193 merged.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
