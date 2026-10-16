# The creator studio layer, and the Voice Lab ship lane

Written 2026-10-16. It covers one session that started from a screen recording Tee put on Drive on 2026-10-15. It records the analysis, his rulings, and what was built and measured for the first lane.

## The recording

The file is `ScreenRecording_10-15-2026 18-05-35_1.mp4` (Drive id 1P5ZSnYNKL4o2n4WnTSr08HIRbOPAx6re), 95.7 s of iPhone screen capture at 1180x2556. It shows the @restructureai Short "I Built an Entire AI Creator Studio With 0 Employees", which is co-branded with ElevenLabs.

It was read from 48 frames, one every 2 s, plus 12 full-resolution crops. The audio was not transcribed, because no speech model could be downloaded here, so the narration is known only from the burned-in captions.

Getting the file took one environment change. The network policy refused `drive.google.com` and `drive.usercontent.google.com`, and the Drive connector returns content only as inline base64, which a 152.7 MB file cannot fit through. Tee added both hosts under Allowed domains, and they took effect in the same session.

The video shows eight modules around one person:
- ideas and research;
- script and story;
- a Voice Lab, where the real take is kept and the clone re-reads flubbed lines;
- video and visuals through Higgsfield and Descript;
- global dubbing into ten languages;
- repurposing and posting at local time;
- an AI sales line on ElevenLabs Agents with Stripe and Cal.com;
- a data dashboard with a 7:00 brief.

Its revenue and view figures are mockup screens in a sponsored post. They are unverified, and they are not evidence.

## Rulings

Tee ruled on inline cards on 2026-10-15:
- The studio is incorporated as a layer on the shared engine. It is not a second studio.
- The Voice Lab ship lane is built first.

The case for building it first is in the repo. There have been 0 YouTube publishes since 2026-09-03. Presenter render cannot run on live V5, and the HeyGen lane is unfunded. Voice Lab routes around both: his real take is the base track, and the clone fills only the lines he flubbed.

## Gaps the video skips, carried here as gates

- An AI disclosure flag on every upload that carries clone audio. The sales agent also says it is an AI.
- His own voice and likeness only. The video's "Maya Cole" is a stock persona.
- A human watches the finished cut end to end.
- New lanes sit under the provider watchdog.
- A cost line for metered tools.
- A rights check on music and B-roll before dubbing.

## What was built

The render worker gained four things, in `deploy/render-worker/jobs.js`.

`align_script` lines the script up against word-timed speech to text.
- It keeps a reading only when it says the line verbatim.
- It chooses readings with a dynamic program that keeps the most script words in order. On a tie, the later reading wins.
- It returns `rerecord` with no edl when over 30 percent of lines are patched.

`take_patch` splices the take with the clone audio over a held frame.
- It renders one ffmpeg run per segment and joins them with the concat demuxer as a stream copy.
- It requires `take_duration`, and refuses spans past it or out of time order.
- It snaps every segment to whole frames on both tracks.
- It takes `width` and `height` so that segments are cut at the presenter canvas before the tonemap.
- It has no default for `hdr`.

`presenter_composite` gained `must_cover`.
- It refuses at submit when a clone window is not inside one opaque cutaway.
- It lays a black plate under each window, so a cutaway with no frames shows black and never his face.

`probe` now reports `pix_fmt`, `color_transfer` and `hdr`.

## Findings

Every number here was measured in the session container, with ffmpeg 6.1.1.

**The single-run `take_patch` would have killed the VPS.** On a 40 s 4K HEVC HLG take, 64 items as seeked inputs peaked at 13.6 GiB and died. The box has 7.8 GiB. Segmented, the same 64 items peaked at 1,068 MiB, and the output measured 736 frames against 736 planned. 256 items peaked at 1,427 MiB, with 2,944 frames against 2,944 planned.

**The first acceptance run found an A/V drift.** Video rounded to the frame and audio did not, so each splice added 13 ms. Every builder test was green while it happened. Segments are now whole frames. The acceptance script fails at frame 76 against a copy without that snapping, so it is a real negative control.

**A fresh critic quarantined the first commit, d535cf3.** Its blocker was that `align_script` kept readings one word off the script, for example "forty percent" against a script line saying thirty. Its other findings:
- the 64-item cap;
- 198 s of event-loop blocking;
- spans past the file end;
- an empty cutaway showing the face;
- out-of-order spans;
- greedy placement;
- a lip-sync lag of +28.4 ms after a seek.

All of these were fixed in a637d8f. The lag now lands within half a frame: -5.0, +9.4 and -10.6 ms against a -4.0 ms source. **A second fresh critic gave a637d8f PASS-WITH-CONDITIONS.** It confirmed the eight earlier findings fixed. The placement program matched an exhaustive search on 60,000 random cases with 0 mismatches. It then measured new silent failures:
- a take whose sound outlasts its picture rendered a clone line into nothing and returned ok;
- a window edge that six decimals round up showed one frame of the held face under the clone;
- must_cover was opt-in;
- a first or last patched line could never pass;
- a timed-out job kept its ffmpeg running;
- an output equal to the take destroyed the take;
- "rose 30%" was kept for a script saying "rose 30";
- a reading could end inside a hyphenated word.

All of these were fixed in the next commit:
- take_patch probes its own inputs and checks its output against the plan, and removes the output on a mismatch.
- It writes a must_cover sidecar that presenter_composite enforces.
- The black plate reaches one frame past each window edge.
- The server kills an abandoned job's ffmpeg.
- Symbols never match, and readings start and end on whole words.

The hard-cut check fails against a copy without the plate widening, at frame 173. The understated patch duration that was left as a caller contract is now probed and refused too.

**A third verifier gave b6789e1 PASS-WITH-CONDITIONS.** It confirmed N1 to N8 fixed, with 576 composites across six base rates and six composite rates showing 0 face frames over the clone, and with an abandoned job's ffmpeg dead and never two running at once. It then found six more gaps:
- the sidecar was lost on a copy, which rendered 46 face frames;
- documented use doubled the windows;
- one-word lines blew the scan bound (11 s, +2.1 GiB);
- symbols outside the blocked list got through;
- a perfect read with % could never be kept;
- stacked emphasis half a millisecond before a window showed the face.

All six are fixed:
- The windows now ride in the base track's own container metadata, so a copy or a symlink keeps them.
- Duplicate windows count once.
- The kept readings are capped at 200,000.
- The tokenizer allows only a fixed punctuation set to drop and lets a symbol match only itself.
- Emphasis must stay a frame clear of a window.

**A fourth verifier gave 45673c6 PASS-WITH-CONDITIONS.** It confirmed all six round three claims, and 144 composites across six base rates and eight composite rates showed 0 face frames in 15,819 frames under the clone. It then found one blocker for deploy and five should-fixes:
- A transcript of one ligature character, which folds to eighteen, held the worker's loop 20.2 s and grew it to 3.3 GiB through the real server, and a 16 MiB file crashed the heap.
- Five number spellings were kept as clean readings of a different number: ".5" for "5", "$.99" for "$99", "10²" for "102", "1,5" for "15" and "3,4" for "34".
- A base written to `.ts` lost its windows, and an `.mkv` kept them under a key the reader missed; both rendered 37 face frames.
- A base re-timed after `take_patch` kept its old windows and rendered 30 face frames.
- A patched last line was refused against the duration pin for one frame count in three at 30 fps.
- Overlapping vendor timestamps cut 50 ms off a kept word.

All six are fixed, and each has a test that fails against 45673c6:
- The transcript and the script are bounded by what they fold to. The same file is now refused in 155 ms at 71 MiB.
- A comma drops only as a thousands separator, a point before a digit is a token, and a character that folds to a digit is a token of its own.
- The base must be an mp4, mov, mkv or webm container, and the tag is read under any key case.
- A base whose picture is more than 1.5 frames off the length its tag records is refused.
- A window that rounds past the end of the file is clamped to it.
- A kept word is never trimmed.

Tee ruled on a card the same morning that the finished master does not carry the list of where his clone speaks, so `presenter_composite` now writes its output without the tag.

**Digits never match number words.** Whether ElevenLabs speech to text writes a spoken number as digits or words is unverified here. Either way a mismatch sends the line to the clone, which is the safe direction.

The suites after round four:
- `jobs.test.js`: 115 passed.
- `server.test.js`: 47 passed.
- The negative control fails 110 of 115 against the Drive original.
- `voice-lab-acceptance.js`: 19 passed, with real ffmpeg. Its three new checks each fail against 45673c6.

## Deployed

PR #347 merged as d75114d under the standing grant, with all seven checks green on 18b63b1. The worker was then deployed to N8N-HOST through Desktop Commander in two steps.

The first staged the merged files in `/tmp` and ran every suite on the box's own Node 18.19.1 and ffmpeg 6.1.1. The four file hashes matched the merge commit. jobs.test.js passed 115, server.test.js 47, the negative control failed 110 of 115 against the original, and `voice-lab-acceptance.js` passed 19, each with exit 0.

The second checked `/status` and found nothing running or queued. It kept the three old files as `.bak-20261016`, swapped in the new ones and restarted the service. The service read active, `/health` read 21 job types on the bridge address n8n uses, and the live files read back byte identical to the merge commit.

The n8n Voice Lab workflow below calls the new jobs. Tee published it on 2026-10-16, and it has not run yet.

## The n8n Voice Lab workflow

Tee ruled on a card on 2026-10-16 to build it now. `TQO Voice Lab (DRAFT, not published)` was created on the live instance as `jKrUIEQSUcGzr4tK` at 2026-10-16T03:24:31Z, 36 nodes, in Tee's personal project. Read back after creation it shows `active: false`, `activeVersionId: null` and version `1da529a4`. Its error workflow is `GbeNilHQzjmoWDz3`, and success and error execution data are both saved, so a run always leaves something to read.

The chain runs from an n8n form to Plan Run, then shares the take by link, has TSWS 00 run `http_download`, and removes the share. The worker probes the take, then measures and normalises its loudness into a 16 kHz FLAC for speech to text. That FLAC is the only file the loudness jobs touch. The workflow fetches it and sends it to ElevenLabs `scribe_v2` for word timings, then calls `align_script`. A re-record verdict emails the missed lines and clones nothing. Otherwise each missed line is read by the clone voice, uploaded to Drive, shared while the worker downloads it, unshared, and probed for its length. Then `take_patch` runs and an email report names each clone window.

The clone call uses V5's voice `ypnKDQtIhp4N3yn4UnqO`, its model `eleven_multilingual_v2`, and its stability 0.5, similarity 0.75, style 0.1, speaker boost and speed 0.99. Speed was missing from the first version. `Show Context: Render` in the committed V5 export sets it explicitly so it cannot drift, and Tee ruled on a card to match it. Live V5 was not read for this.

It differs from the card in three places:

- Intake is an n8n form behind n8n login, not a Drive inbox trigger. The script has to arrive beside the take, and a public form could spend ElevenLabs credit and share any Drive file the account can reach.
- It ends in an email report, not an Approval Queue item.
- The card listed loudness after `take_patch`. Here loudness is applied to the speech to text FLAC only. Neither `take_patch` nor `presenter_composite` normalises loudness, so `base.mp4` and `narration.wav` leave at the take's own level. Loudness for the finished master belongs after `presenter_composite`.

It also stops at the base track. Cutaways and `presenter_composite` were never on the card and are not in it.

What is proven: `validate_workflow` returned valid, and all 14 code nodes parse. A contract run in this container fed fixture data through the real `align_script`, Patch Lines, Prep Fetch Clone, Build Splice, the `take_patch` builder and Compose Report. The builder accepted the parameters and planned 3 segments with one clone window from 2.133333 s to 4.366667 s. That patch path ran with `max_patch_share` raised to 0.5, because the three line fixture patches one line in three and the default ceiling of 0.3 turns that into a re-record. The workflow never sends the parameter. The same fixture at the default returned `rerecord`, which is the re-record path.

What is not proven: the workflow has never executed. It has made no call to ElevenLabs, so the speech to text response shape is proven only against the fixture, and no real take has been through it. The expressions in the non-code nodes have not run either, the Unshare Clone Line URL among them. A run can also start from the editor's test listener, or through the n8n MCP `execute_workflow` tool, because the workflow carries `availableInMCP: true`. The second is a gated write under the outward gate. Neither was tried.

Residuals, graded:

- No node throw leaves the take shared. Only Prep Fetch Take and Fetch Take sit between Share Take and Unshare Take, and Fetch Take continues on error, so a failed download still reaches Unshare Take before Check Fetch throws. The clone side has the same shape. A file does stay shared by link in four cases, and each share then has to be removed by hand:
  - Unshare Take throws, which leaves the take shared.
  - Share Clone Line fails on one line, which leaves every earlier clone line shared.
  - Unshare Clone Line fails on one item, which leaves that item and every later one shared.
  - The run is stopped, crashes or meets an instance restart while a download is in progress, with no unshare and no error email. TSWS 00 waits up to six hours on a job, and N8N-HOST has a pending restart, noted above.
- On a published run the error email names the failing node. On an editor test run no error workflow fires: the n8n MCP tool description says failure handling runs for production executions only. Every run before publishing therefore reports a fault only in the editor and in its saved execution.
- Unshare Take deletes the `anyoneWithLink` permission, so it also revokes a link share Tee set on the take before the run. Tee ruled on a card to record this rather than guard it: a take shared before a run is re-shared by hand. That permission id has not been exercised against what Share Take creates. A mismatch throws, which is the first case above.
- Clone mp3s are never deleted. The first version filed them in `1lLEo3sHfXRdie-EXrXMQJ0L6AAQhHGDO`, the folder V5's `Upload MP3` writes to, whose name is `TQO_RETIRED_root-legacy-folder_2026-06_unmerged-Tee-to-triage`. Tee ruled on a card to give Voice Lab its own folder. `_Voice Lab`, `1SsSKW-COAVM4vgl-a2ptu0Uy_6IyqT3F`, was created in the TQO show folder `1DXDzO_qY17i1ChE-gOqL3oOwBVbaveLH`, and its only permission reads owner `tdveal74`. After the unshare each clone line stays there, owner only. V5's folder is unchanged.
- The ElevenLabs credential `IRr81VQl9EiLIf03` is V5's, so Voice Lab spends from the same account V5 narrates with.
- An ElevenLabs refusal throws rather than being swallowed. The provider watchdog opens the newest 25 errored executions whatever host they called, classifies each by HTTP code and then by message, and alarms inside a 6 hour window. So a refusal here alarms once the lane runs, unless 25 newer failures crowd it out; the critic found none since 2026-10-15T21:00Z. Whether that error listing includes editor test runs is unverified. `api.elevenlabs.io` is not in `PROVIDER_HOSTS`, which matters only for a node that swallows a refusal, and no node here does.
- Two email nodes use SMTP `AgSGuaA2pnZsrZcJ`, and five nodes use Drive `NW3vR6nNcMoUkJyJ`, all of them throwing. CLAUDE.md counts those credentials across active workflows, so its numbers moved when this was published.

The card edit landed as version `17cf08f8`. Read back afterwards, the workflow showed `active: false` and `activeVersionId: null`, Clone Voice sends `speed: 0.99`, Upload Clone Line points at `_Voice Lab`, and the canvas note states the speed and the folder and records the take share behaviour.

Tee said publish on 2026-10-16. Before publishing, the name, description and canvas note dropped the draft label, and no node logic changed. It was published as version `bc3ad4ef` at about 05:18Z. Read back, it shows `active: true` with `activeVersionId` equal to `versionId`, both `bc3ad4ef`. A GET of the production form URL `/form/tqo-voice-lab` answered 302 to the n8n sign-in page, so the form is live and behind login. Published, a failing production run goes to the error handler, which fires for production executions only, and a provider refusal errors the run into the list the provider watchdog reads. Neither has been exercised, because the workflow has not run.

Publishing adds two `emailSend` nodes on SMTP `AgSGuaA2pnZsrZcJ` and five nodes on Drive `NW3vR6nNcMoUkJyJ` to the active estate. Both CLAUDE.md counts were enumerated from the estate on 2026-09-22, and the SMTP one says to re-run the enumeration rather than add to it, so neither was edited here.

The first run with a real take is Tee's, because it shares a Drive file by link and spends ElevenLabs credit.

## Approvals in this session

Tee asked that he not have to approve every command. Up to the deploy, the session record showed ten tool calls stopped for him: seven cards, one plan, and three Desktop Commander `start_process` calls, each a root shell command on a VPS. Every other Desktop Commander call ran on the repository's allow rule from PR #344, with the session in Auto mode. So Auto mode still stopped on root shell commands despite the server-wide rule. Why it did, and whether a rule naming `start_process` would change it, is unverified. The outward gate prompts for nothing; it only refuses.

Tee ruled on a card to keep the gate's 30 minute window rather than lengthen it to four hours or exempt Desktop Commander. The deploy was folded into two `start_process` calls, so it cost two approvals.

## Reaching the worker

The render worker runs on N8N-HOST, which had no Desktop Commander device, so nothing in a session could reach it. Tee ruled on a card on 2026-10-16 to link it. Desktop Commander 0.3.0 needs Node 22.12 or newer, and the box's system Node is 18.19.1, which the worker runs on. So Node 22 went into `/opt/node22`, beside the system Node, and Desktop Commander runs from it as root in a tmux session named `dc`. Tee set it up from Termius on his iPhone and approved the device. A read on the box afterwards showed the worker's files dated 2026-09-15, the service active, ffmpeg 6.1.1 and 5.7 GiB available. Its writes go through the outward gate like the EditForge box's.

The login banner on N8N-HOST reports a pending restart and offers Ubuntu 26.04. Both were left alone. A restart takes n8n and every pipeline down, and a release upgrade changes the system Node and ffmpeg under the worker.

## Shown to Tee

A private artifact, the studio map, holds the module ledger, the lane, the measurements and the build order: https://claude.ai/artifact/VJtHwKunUb42gMv4dyzSpZ

## Open

- The first run of `TQO Voice Lab` `jKrUIEQSUcGzr4tK` with a real take, Tee's.
- A re-enumeration of the CLAUDE.md SMTP and Drive counts, which this workflow changes.
- One real episode end to end, watched by Tee.
- The MuseTalk proof in `deploy/lipsync/README.md`, step two. A GPU pod was provisioned on 2026-10-16: one NVIDIA L40S on RunPod Secure Cloud, US-TX-3, with a 60 GB network volume at `/workspace`. Tee ruled on a card to stop it until take A is recorded and keep the volume. He confirmed it stopped the same night. This session cannot reach the pod, because the network policy blocks the RunPod API and outside DNS, so the proof runs from the pod's web terminal. If it passes, clone lines could be lip-synced onto his own face instead of covered by a cutaway.
- The consent record for the clone, and the YouTube altered content label rule.
- Later phases, each on its own card: wiring into V5, dubbing, local-time posting, the sales line, the 7:00 brief.

## DEVON RECEIPT

AREA: TQO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_creator-studio-voice-lab_v1_2026-10-16-0006.md
DATE: 2026-10-16
DECISIONS: Tee ruled on cards on 2026-10-15 to incorporate the one-person creator studio from the @restructureai Short as a layer on the shared engine rather than a separate studio, and to build the Voice Lab ship lane first. He added drive.google.com and drive.usercontent.google.com to the environment's allowed domains so the recording could be read. On 2026-10-16 he ruled to link N8N-HOST to Desktop Commander so a session can deploy the worker, to strip the clone window tag from the finished master, to keep the outward gate's 30 minute window, and to build the n8n Voice Lab draft now. After the fifth critic he ruled to send V5's clone speed of 0.99, to file clone lines in a new _Voice Lab folder, and to record rather than guard the revoked take share. He then said publish, and it went live the same day.
FINDINGS: The video's eight modules map onto the estate with Voice Lab, dubbing and the AI sales line missing. A single-run take_patch peaked at 13.6 GiB on 64 items of 4K HEVC against a 7.8 GiB VPS; segmented, it peaked at 1,068 MiB with 736 of 736 frames. The first acceptance run found a 13 ms per-splice A/V drift that every builder test missed. A fresh critic quarantined d535cf3 because align_script kept off-script readings at 0.9 similarity; a637d8f keeps verbatim readings only. A second critic gave a637d8f PASS-WITH-CONDITIONS and measured eight silent failures, all fixed after it, each with a test and the face-frame one with a negative control. A third gave b6789e1 PASS-WITH-CONDITIONS with six more gaps, among them a copied base track losing its windows; all six were fixed, the windows now ride in the file's metadata, and the copy case is in the acceptance run. A fourth gave 45673c6 PASS-WITH-CONDITIONS with 0 face frames in 15,819 and one deploy blocker, a ligature transcript that held the loop 20.2 s at 3.3 GiB; that and five should-fixes were fixed, each with a test that fails against 45673c6. On the box, Node 18.19.1 and ffmpeg 6.1.1 passed 115, 47 and 19 with the negative control failing 110 of 115, and /health read 21 after the swap. The n8n draft jKrUIEQSUcGzr4tK read back inactive with activeVersionId null; its fixture contract run passed and it has never executed. A fifth critic gave that record PASS-WITH-CONDITIONS: the clone call omitted V5's speed of 0.99, loudness reaches only the speech to text file, clone lines landed in a folder named as retired, and four share paths were named. The speed and the folder were fixed on Tee's card in draft version 17cf08f8, which read back inactive with activeVersionId null. Published as bc3ad4ef, it read back active with activeVersionId equal to versionId, and the production form answered 302 to the n8n sign-in page.
OPEN: the Voice Lab workflow's first run with a real take, Tee's; a re-enumeration of the CLAUDE.md SMTP and Drive counts, which this workflow changes; why Auto mode still prompts for Desktop Commander start_process; one real episode watched end to end; clone consent record and the YouTube label rule; later phases on their own cards.
STATUS: Merged as d75114d and deployed to N8N-HOST on 2026-10-16, with every suite and the acceptance run passing on the box and /health reading 21; the n8n Voice Lab workflow jKrUIEQSUcGzr4tK is published as version bc3ad4ef with its form behind n8n login, and has not run; nothing it makes is posted anywhere.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
