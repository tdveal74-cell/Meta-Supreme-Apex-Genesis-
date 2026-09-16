# The LiveKit trap fired six hours after it was written up

2026-09-16. At 09:40Z this session recorded that three environment variables on
the presence service were a trap: setting them read like completing a
configuration and was in fact how DEVON goes silent. At 11:13:58Z they were
set, and DEVON went silent. He was speaking again at 11:42:16Z.

Nothing here is a complaint. Tee was told, ruled "build the publisher", and
then moved ahead of the deploy, which is a reasonable thing to do when the
thing you asked for is being built. The interesting part is that a documented
hazard with a named remedy still landed, and why the failure was invisible
while it was happening.

## What the trap was

`apps/presence/main.py` defined `send_audio_over_websocket` as
`not livekit_configured`. Audio went over the WebSocket only while LiveKit was
unconfigured. Once configured, the other branch did not exist: the frames were
produced and dropped.

So the three variables behaved as an off switch wearing the clothes of a
setting. Worse, `POST /livekit/token` returned a 503 whose text instructed the
reader to set exactly those three.

## Why nobody would notice

This is the part worth keeping. Every signal a reader would check said fine:

| what a reader checks | what it said during the outage |
|---|---|
| `/health` status | `200` |
| the WebSocket | opens, accepts hello, sends `ready` |
| the breaker | `closed`, 0 breaches, 0 opens |
| `speech` | `cartesia`, the real clone |
| the logs | nothing, no error was raised |
| the page | renders, connection state healthy |

The only two fields that told the truth were `livekit_configured: true` and
`audio_over_websocket: false`, and only if you knew that pair meant silence.

## The timeline, from measurements rather than memory

| time | what happened |
|---|---|
| 09:40Z | trap written up, with the remedy, after reading `/health` |
| ~11:05Z | variables set on the **api** service, where they are inert |
| 11:12:29Z | variables moved to **presence**; Railway begins a redeploy |
| 11:13:31Z | deployment still `DEPLOYING`, `/health` still reads `false` |
| 11:13:58Z | `/health` reads `livekit_configured: true`, `audio_over_websocket: false` |
| 11:42:16Z | variables removed, `/health` reads `false`, `true`; audio restored |

The first landing is its own small lesson. Nothing under `app/`, `services/` or
`deploy/` reads `LIVEKIT_*`; only `apps/presence/` does. An estate can look
configured for LiveKit while the service that needs it has nothing, and the
variables sat somewhere harmless for several minutes without a single signal
saying so.

## What was built, and what it refuses

`apps/presence/livekit_publisher.py`. It connects, publishes a
microphone-source track, and turns each `pcm_s16le` chunk into an `AudioFrame`
carrying `len(pcm) // 2` samples. `PresenceSession` takes an `AudioSink` and
never learns LiveKit exists, so the socket path and the room path are two
answers to one question and the session stays testable without a room.

The room is the session id. That is not invented: `main.py` already registers
`runtime.sessions[session_id] = user_id` and `/livekit/token` refuses to mint
for a room whose registered owner is not the caller. The publisher's identity is
deliberately not the user's, because that endpoint mints with `sub`, and its
token is publish only: DEVON talks into the room and has no reason to receive.

Four refusals, each replacing a place that used to be quiet. A publish before
`start`, because a sink that accepts frames it never sends is the bug itself.
An odd length PCM buffer, because two bytes make a sample and half a sample
means the producer upstream is broken. A session with neither a socket path nor
a sink. And `LIVEKIT_*` set with the SDK missing, which now refuses at BOOT
rather than at the first turn, so the exact thing that happened at 11:13:58Z
would have failed the deploy instead of the audio.

## Written against the SDK, not against a memory of it

The SDK was installed in a throwaway venv and its signatures read before a line
was written: `capture_frame`, `connect`, `publish_track` and `disconnect` are
all coroutines, `AudioFrame` takes `samples_per_channel`, and
`TrackSource.SOURCE_MICROPHONE` is 2.

A test double for a vendor SDK is a story about an API unless something holds
it to the real one, so `test_the_double_matches_the_real_sdk` reads the
installed package and asserts every call the publisher makes exists with the
arguments it passes. It passes rather than skips, because the SDK is now pinned.

## The dependency, and a correction I owed

Tee ruled to pin the SDK. I had told him a platform tagged wheel inside a hash
pinned file could fail on a Mac. That was wrong: `pip-compile` collected SIX
hashes for `livekit`, one per distribution, so every platform finds its own.

The real cost is bigger than I quoted. `livekit` drags in `numpy` and
`protobuf`, so it is 27.8 MB added to a closure that nine CI jobs install, not
the 11.8 MB of the wheel alone.

Regenerating also tried to drift `anyio`, `greenlet` and `ast-serialize` to
newer versions as a side effect, which is exactly the unrelated bump
`requirements.in` says belongs in its own pull request. It was caught by diffing
the pins before and after rather than by reading the output, and the closure now
gains exactly five packages with nothing else moved. The cause is worth
recording: `pip-compile` only honours existing pins when it is writing to the
file it is reading, and the first attempt wrote to a scratch path.

## What is still unproven

No turn has been spoken into a live LiveKit server from this build. The double
is held to the SDK's shape, not to a real room's behaviour. That is said in the
package docstring as well as here, because a reader who finds this file has
already gone looking and a reader who does not should still be told.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-livekit-trap-fired_v1_2026-09-16n.md
DATE: 2026-09-16
DECISIONS: Tee ruled to build the room publisher rather than guard the trap, and to pin the LiveKit SDK in requirements.txt rather than hide it behind an optional import. The session logged one objection to each and then executed: the guard was the cheaper fix, and the pin puts a compiled 27.8 MB closure into nine CI jobs and the presence image. The publisher is additive at the session boundary, taking an AudioSink so PresenceSession never learns LiveKit exists. The variables were NOT removed from the live service by this session even while DEVON was silent, because Tee set them deliberately and reverting a human's explicit production change without asking is not a session's call; he was told plainly, twice, and removed them himself.
FINDINGS: A hazard written up at 09:40Z with its remedy named still landed at 11:13:58Z, which is worth more than the fix: every signal a reader checks said healthy during the outage. 200 from /health, a socket that opens, a breaker reading closed with zero breaches, speech cartesia, no log line, and a page that renders. Only livekit_configured true paired with audio_over_websocket false told the truth. The variables first landed on the api service where they are completely inert, because nothing under app/, services/ or deploy/ reads LIVEKIT_ and only apps/presence/ does, so an estate can look configured while the service that needs it has nothing. The claim inherited from PR #248 that livekit_configured false is "pinned by test_presence_service.py:106" is wrong in a way that matters: that test builds the app from the TEST environment where the variables are unset, so it pins the local value and says nothing about production. And my own warning that a platform tagged wheel in a hash pinned file could fail on a Mac was wrong; pip-compile collected six hashes for livekit, one per distribution. The real cost is 27.8 MB rather than 11.8 MB, because livekit drags in numpy and protobuf. Regenerating also silently drifted anyio, greenlet and ast-serialize until it was rerun against the file it reads rather than a scratch path, which is the only way pip-compile honours existing pins.
OPEN: No turn has ever been spoken into a live LiveKit room from this build, so the room path is proven against the SDK's shape and not against a real server's behaviour. The three LIVEKIT_ variables are off the presence service again and must not go back until the publisher is deployed; the correct order is merge, let presence redeploy, set the variables, then listen to a turn end to end with someone watching. PR #250 is green on 8539d6c through a dispatched run and the merge is Tee's word. Pull request events have stopped creating CI runs on this branch, so three commits had no checks until they were dispatched by hand, and a PR status of success can mean Vercel and CodeRabbit alone.
STATUS: Built, tested, CI green on all five jobs including the dependency audit and the container image build, and deliberately not deployed. DEVON was silent for roughly 28 minutes and is speaking again. The trap that caused it is closed in code but the code is not live.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
