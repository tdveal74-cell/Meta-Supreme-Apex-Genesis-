# DEVON spoke into a real LiveKit room

2026-09-16, 13:27:51Z. Tee opened the presence stage and heard DEVON answer
through a LiveKit room rather than over the WebSocket. That is the first audio
this estate has ever put into a real room, and it closes the line that three
separate files carried as unproven.

## What was unproven until today

The publisher was written against the installed SDK rather than from memory,
and it said so. `apps/presence/__init__.py` ended its LiveKit paragraph with
"no turn has been spoken into a live LiveKit server from this build".
`useLiveKitAudio.ts` opened with "UNVERIFIED: this LiveKit path has not been
exercised against a live LiveKit server". Both were accurate when written and
both are now false, so both were corrected in this change rather than left to
rot into a claim a later session would trust.

## The evidence

Tee listened to the turn end to end, which is the standard this estate holds:
a test does not read the artifact, a human does. The machine side corroborates
rather than substitutes for that.

```
13:18:46.25Z  Starting Container
13:18:49.58Z  Application startup complete        boot with all three LIVEKIT_ set
13:24:19Z     /health  livekit_configured true, audio_over_websocket false
13:27:51.02Z  WebSocket /ws/presence [accepted]
13:27:51.02Z  connection open
13:27:51.02Z  OPTIONS /livekit/token  200
13:27:51.02Z  POST    /livekit/token  200
```

`POST /livekit/token` answers 200 only when the service holds all three
variables; unconfigured it returns a 503. So the browser minted a join token
and entered the room named for its session id, which is the room the publisher
writes to. No error was logged on that turn.

The boot itself proves a second thing that was open. `main.py` calls
`load_rtc()` whenever `livekit_configured` is true, and that raises when the
SDK is missing. The service came up instead of refusing, so the 27.8 MB
closure installed and `livekit.rtc` imports on Railway.

Serving `f459ba0`, which carries `apps/presence/livekit_publisher.py` and pins
`livekit==1.1.18`. The browser side is byte identical to production's
`c653559`: `git diff c653559 origin/main -- apps/web packages` is empty, so the
stale Vercel production deployment made no difference to this test.

## Two cheap checks I skipped, and what they cost

A `/health` read taken inside a deployment cutover is answered by the outgoing
container. At 13:18:47Z I read `livekit_configured: false` and reported it as a
clean boot of the new deployment. The incoming container had started at
13:18:46Z and did not finish booting until 13:18:49Z, and the deployment did
not report SUCCESS until 13:18:52Z. Tee's values were in place the whole time.
I then reasoned from that stale reading to a confident and wrong conclusion:
that because a half configured triple crashes the boot and the service was
healthy, all three values had to be empty. The logic was sound and the input
was three seconds stale. Deployment state has a clock, and a reading has to be
timestamped against it before it can be reasoned from.

`list-variables` returns names only for an OAuth credential. A variable NAME on
a service therefore says nothing about whether it holds a value, and treating
the name list as evidence about values is the same error in a different coat.
The behaviour is the measurement.

## Still open

Three production Vercel deployments in twenty minutes were CANCELED: PR #250's,
PR #252's and PR #254's. Production web is `c653559` from 12:02Z. It did not
matter here because the web workspace has not changed since, but it will matter
the next time an actual web change needs to reach production. The likely cause
is Vercel auto cancelling superseded builds, and the other candidate is deploy
quota exhaustion. Not checked, so not claimed.

The Script Writer lane failed at 10:00:00Z on a Cerebras HTTP 429 at
`Write Script (Cerebras)`. Two executions started in the same millisecond and
both died the same way, which points at concurrent triggers rather than at the
vendor. The Data Table reads inside that failed run worked, so it is not the id
conversion.

Episode 2 of The AI Shift rendered at 13:09:20Z and sits at status Ready with
`human_review` unticked. Its render telemetry reads "narration on elevenlabs,
Tee clone", which is worth one look against the render node before it is
trusted, because a fixed `elevenlabs` literal was removed from V5 on 2026-09-10
for crediting the clone while Speechify spoke. Unverified either way.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_devon-spoke-into-a-real-room_v1_2026-09-16o.md
DATE: 2026-09-16
DECISIONS: Tee set the three LIVEKIT_ variables on the presence service after PR #250 deployed, in the order this estate had already ruled correct: merge, let presence redeploy with the publisher, set the variables, then listen to a turn end to end. He listened and confirmed it himself rather than accepting a green health read, which is the standard. The three claims of non verification carried in apps/presence/__init__.py, useLiveKitAudio.ts and the deploy-readback skill were corrected in the same change rather than left for a later session to trust.
FINDINGS: DEVON spoke into a real LiveKit room at 13:27:51Z, the first time this estate has put audio into one. The service log carries the socket accept and OPTIONS and POST on /livekit/token at 200, and that endpoint answers 200 only when all three variables are set. The boot at 13:18:49Z additionally proves the pinned livekit 1.1.18 closure installs and imports on Railway, because create_app calls load_rtc when the flag is true and raises when the SDK is missing. My own error is the finding worth keeping: a /health read at 13:18:47Z was answered by the OUTGOING container during a deployment cutover, and I reported it as a clean boot of the incoming one, then reasoned from it to a confident wrong conclusion that all three values were empty. The incoming container started at 13:18:46Z, finished booting at 13:18:49Z and the deployment reported SUCCESS at 13:18:52Z. Separately, list-variables returns names only for an OAuth credential, so a variable name present on a service is not evidence that it holds a value.
OPEN: Three production Vercel deployments were CANCELED in twenty minutes and production web is stale at c653559 from 12:02Z; harmless here because apps/web is unchanged since, unchecked as to cause. The Script Writer lane failed at 10:00:00Z on a Cerebras 429 with two executions starting in the same millisecond, which is not the id conversion because the table reads inside that run worked. Episode 2 of The AI Shift is rendered and sits at Ready with human_review unticked, and its telemetry crediting elevenlabs and the Tee clone is unverified against the render node.
STATUS: Closed. The LiveKit room path is proven end to end against a live server with a human listening, the publisher is deployed on f459ba0, and the three files that said otherwise now say what is true.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
