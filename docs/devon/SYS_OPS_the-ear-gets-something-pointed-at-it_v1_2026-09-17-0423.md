# The ear gets something pointed at it

2026-09-17. Ears item 2, ruled by Tee on a card a few hours after
SYS_OPS_the-ears-arc-and-what-it-could-not-prove_v1_2026-09-17-0144.md was
written. That doc's open list says "the presence capture UI does not exist" and
"nothing in the browser asks for a microphone". Both were true when it was
written and neither is now, which is the one thing worth reading it beside.

PR #262 merged as 164fd7f on Tee's explicit authorization, eight of eight
checks green on ad6cf59.

## It was narrower than the item name suggested

"Build the presence capture UI" reads like starting from nothing. Reading
`useBargeIn.ts` first said otherwise: the microphone is already opened from an
explicit gesture, an `AudioContext` already exists, an `AnalyserNode` is already
running, and a `VoiceActivityDetector` is already fed from it every frame.

So the work was not opening a microphone. It was that an `AnalyserNode` cannot
produce a recording. `getFloatTimeDomainData` copies whatever sits in its window
at the moment you ask, so two reads a frame apart overlap or skip depending on
when the frame landed. For "is someone talking", which is the only question
barge in asks, that is exactly right and cheap. For a transcriber it is useless,
and the failure is silent: overlapping windows still sound like speech, just not
the speech that was said.

That is why the capture path is an `AudioWorkletNode` tapping the same
`MediaStreamAudioSourceNode` rather than a second read of the analyser. One
microphone, one permission prompt, one recording indicator, two readers asking
different questions of it.

## The pin that was still facing the other way

`apps/presence/protocol.py` refused any hello that was not the server's version
until PR #257 fixed it. `apps/web/lib/presence/protocol.ts` still refused any
`ready` that was not its own, and nobody had noticed that the second half of the
same trap was untouched.

A client pinned at 2 against a server rolled back to 1 blacks out the page for
precisely the reason the server pin used to, while `/health` reads healthy. So
this side now accepts any version in `SUPPORTED_PROTOCOLS`, the negotiated
number rides on the parsed message rather than being assumed, and `canListen`
gates the ear on it.

Shipping it was safe because the deployed service was read rather than assumed:
`/health` on the presence service returns `protocols [1, 2]` and `ears "mock"`.
A pure test cannot tell you that. It took one request.

## Measured across the language boundary

The encoder and the assembler are in different languages, so agreement between
them is a claim until something executes both. A 440 Hz tone went through the
client's `floatToPcm16` and `bytesToBase64`, then through the real
`parse_client_message`, the real `ClipInProgress` and the real `upload_for`:

| what | value |
|---|---|
| chunks accepted by the server's own parser | 4 |
| assembled | 96000 bytes, exactly 1.0s at 48 kHz |
| WAV header | format 1, mono, 48000 Hz, 16 bit |
| recovered from the decoded samples | 439.5 Hz, from 440 Hz sent |
| peak | 26214, against the 26213 that 0.8 full scale predicts |

Byte order, sample width, scaling and rate all survive that. A byte order slip
or a wrong declared rate would have destroyed the frequency reading rather than
producing a plausible one. `bytesToBase64` is byte identical to Node's `Buffer`
over every length from 0 to 300 and over 200 random buffers, which is the
difference between a base64 encoder that is tested and one that is asserted.

## Contiguity needed a browser, so it got one

Everything above tests arithmetic. None of it can show that the worklet hands
over every sample once and in order, and that claim is the only reason the
worklet exists at all.

`apps/web/scripts/capture-check.mjs` serves the shipped worklet over HTTP and
drives it in real Chromium against a known tone: 48000 samples for one second,
nothing dropped, and 439.5 Hz recovered across the concatenated chunks. A
dropped block is 128 samples short, a duplicated one is 128 long, and either
moves the recovered frequency. On the GitHub runner it printed the same numbers
this container did, which is worth more than either run alone.

It went into `audio-ci.yml` rather than a ninth workflow because the whole cost
of that job is the Playwright and Chromium install, and a separate workflow
would pay it twice. The job is renamed for both directions. `CLAUDE.md` said
FIVE files in that filter; it is nine paths now, counted from the file rather
than from the sentence.

## What refuses instead of guessing

An `AudioContext` runs at whatever rate the hardware gives it. 44100 and 48000
are both in the server's `LISTEN_RATES`, so the common case needs no conversion.
When the rate is not one the server takes, the module refuses and names the
rate rather than resampling. A resampler written quickly aliases, and audio at
the wrong rate does not fail loudly: it transcribes into a fluent sentence
nobody said, which is the failure `wav_from_pcm`'s docstring already warns
about. A refusal costs a retry.

The clip ceiling is mirrored from the server so the client can stop while the
speaker still holds the thought, rather than at `listen_end` after they have
finished and waited. When it fires, `listen_end` is never sent at all: the
server would otherwise transcribe the part that arrived, and half a sentence
becomes a whole one that nothing downstream can tell from a good one.

## Two mistakes of mine, both worth keeping

**A mutation that fails to apply reads exactly like a survivor.** Fourteen
mutations were run against this change and one first came back clean. It had
not survived anything: the `sed` pattern had six spaces of indentation where the
file has eight, so nothing changed and the checks passed on unmodified source.
The rerun asserts the file actually differs before it believes a result. Both
flush mutations then died, losing 11904 of 48000 samples, which is the last
quarter second of every sentence.

**A CANCELED Vercel record is not always the block.** 17 of the last 20 records
on the web project read CANCELED and I was one sentence from reporting the
production surface as stale because of the account block. It is not.
`ignoreCommand` produces CANCELED too when it correctly skips a build, and
`f0f1e7e..main` touches zero files in that project's watched paths, so
production sitting at `f0f1e7e` is correct. The block is real and separate; it
is established by the absence of any record at all since `ce70236` at
22:58:52Z, across four later commits that each ran Actions.

## One local red that was mine

A full suite run failed `test_interrupt_mid_turn` with 16 frames against 8
while a browser and two servers were competing for this container. It passes
five of five alone and the uncontended full run is clean, so it was the harness
rather than the branch, established by reproduction rather than called a flake.
`CLAUDE.md` already warns about concurrent runs against the shared cluster; this
is the same shape with CPU instead of the database.

## The lane it was all pointed at could not hear, and nothing knew

Found 2026-09-17 while preparing the one keyed request this arc has been
waiting on. Rather than hand Tee a recipe that had never been executed, the
request shape went to a throwaway copy of the devon-hears webhook first. That
probe found the lane broken.

`Is There Audio To Hear` gated on `$binary.data.fileSize`. n8n sets fileSize to
a HUMAN READABLE STRING, `"38.4 kB"`. A number comparison against it does not
answer false, it throws:

```
NodeOperationError: Conversion error: the string '38.4 kB'
can't be converted to a number [condition 0, item 0]
```

The run died at node 2 and the caller got an empty body. No status, no reason,
nothing to read. `typeValidation: loose` did not save it; the failing node
resolved `looseTypeValidation: false`. The number lives on `.bytes`, 38444.

So every keyed voice note ever sent to this lane would have returned nothing at
all, and the arc would have spent an afternoon chasing a silent failure.

WHY IT SURVIVED A BUILD, A MERGE AND A STATUS DOC. The guard and the guarded
path are different code. Every execution ever run carried no audio, and that
path never reaches the comparison: with no binary the ternary yields a real 0,
and `0 > 0` is an honest false, so the refusal fires correctly. PR #252 tested
the refusal and recorded the lane as working. Testing a guard against absence
proves nothing about presence, and presence is the only case anybody wanted.

Measured on a throwaway copy of that exact node, fed over the live webhook:

| gate reads | no audio | wav | m4a | multipart |
|---|---|---|---|---|
| `fileSize` | refuse | throws | throws | throws |
| `bytes` | refuse | transcribe | transcribe | refuse |

Two things fell out of the same probe. Multipart lands on `data0` rather than
`data`, so a multipart upload is refused as if nothing arrived; the note goes up
as a RAW body. And the mime type rides through untouched, so an iPhone voice
memo arrives as `audio/m4a` and is fine.

The live lane now reads `bytes`, published 2026-09-17, with the refusal path
re-checked by execution 390 so the spend guard is known intact rather than
assumed. Both probes are archived. The trap is written into the n8n house
conventions, because the part that generalises is not the key name: it is that
a guard which refuses on absence has to be exercised with presence too.

## What is still open

No human has held the control and spoken. Nothing in CI grants a microphone, so
press, release and the browser permission path are unexercised, and that is the
honest gap at the end of this item.

`PRESENCE_EARS` is `mock` on the deployed service, so the first clip comes back
as MockHearing's scripted line rather than as real transcription. That is the
correct default and it is what makes the first human test cost nothing.

The control will not appear on the deployed page until the Vercel account is
unblocked and a web build runs. This is the first change in a while that
genuinely needs one: ten of its files are in that project's watched paths.

The devon-hears lane still has no audio through it. It is now CAPABLE of taking
some, which it was not this morning, and what remains is one keyed request from
Tee's phone. Nothing yet turns a rendered episode into a transcript.

## DEVON RECEIPT

```
AREA: Systems, Learning
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-ear-gets-something-pointed-at-it_v1_2026-09-17-0423.md
DATE: 2026-09-17
DECISIONS: Tee ruled on a card to build ears item 2, the presence capture UI, and authorized PR #262 to merge. Three decisions inside the item were mine. The capture path taps the microphone useBargeIn already opened rather than opening a second stream, because two getUserMedia calls means two permission states and two contexts competing for one device. An unsupported hardware sample rate is refused by name rather than resampled, because a hurried resampler aliases and wrong rate audio transcribes into confident nonsense rather than failing. And the new browser check went into the existing audio-ci job rather than a ninth workflow, because that job's entire cost is the browser install.
FINDINGS: devon-hears could not transcribe anything from the day it was built: its audio gate compared $binary.data.fileSize, which n8n sets to the human readable string "38.4 kB", so a real voice note threw a conversion error at node 2 and returned an empty body rather than refusing or transcribing. The number is on .bytes. It survived a build, a merge and a status doc because the guard and the guarded path are different code and every execution ever run carried no audio, a path that never reaches the comparison. Fixed and published 2026-09-17, refusal path re-checked by execution 390. Multipart lands on data0 rather than data, so the note must go up as a raw body. An AnalyserNode cannot produce a recording; getFloatTimeDomainData copies its current window, so consecutive reads overlap or skip, which is right for barge in and useless for a transcriber. The client half of the mutual protocol pin was still in place after #257 fixed the server half, so a rollback to a v1 server would have blacked out the page for the same reason the server pin used to. The deployed presence service returns protocols [1, 2] and ears mock, read rather than assumed. A 440 Hz tone survives the client encoder and the real server assembler at 439.5 Hz with a peak of 26214 against 26213 predicted, so byte order, sample width, scaling and rate all hold across the language boundary. The shipped worklet hands over exactly 48000 samples for one second in real Chromium with 439.5 Hz recovered across concatenated chunks, and drops 11904 of them if its tail flush is removed. A mutation whose sed pattern does not match reads exactly like a survivor and reports a false clean, which happened once here. A CANCELED Vercel record is ignoreCommand skipping as often as it is the account block, and f0f1e7e..main touches zero files in the web project's watched paths, so production at f0f1e7e is correct rather than stale. One local suite red was CPU contention from my own smoke stack, established by reproduction.
OPEN: The devon-hears lane is now capable of taking audio and still has had none through it; what remains is one keyed request from Tee's phone as a raw body. No human has held the control and spoken, so press, release and the browser permission path are unexercised; nothing in CI grants a microphone. PRESENCE_EARS is mock on the deployed service, so a clip returns MockHearing's scripted line rather than real transcription. The control is not on the deployed page until the Vercel account is unblocked and a web build runs, and this is the first change in a while that genuinely needs one. The devon-hears lane still has no audio through it, which needs one keyed request from Tee's phone. Nothing turns a rendered episode into a transcript. COVERAGE_FLOOR stays unverifiable on this estate because the api service carries no OPENAI_API_KEY, and migration 020 is unchecked on the production database.
STATUS: PR #262 merged as 164fd7f, eight of eight checks green on ad6cf59. The devon-hears audio gate is fixed on the live lane, published 2026-09-17, and the trap is recorded in the n8n house conventions and in vault.py. Protocol v2 on the client, the capture worklet, the hold to talk control and a new browser check are on main. This doc supersedes the claim in SYS_OPS_the-ears-arc-and-what-it-could-not-prove_v1_2026-09-17-0144.md that the presence capture UI does not exist.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
