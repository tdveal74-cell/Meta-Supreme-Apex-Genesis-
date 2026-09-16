# The presenter lane, and a wallet that does not refuse

2026-09-16. Tee ruled the b-roll becomes his own presence rather than stock,
which opened the presenter question, which ended at a HeyGen wallet with auto
reload switched on. The ruling is MuseTalk, which is where 2026-09-15 started.
What is worth keeping is the road between those two points.

## What was wrong with the b-roll, and it was not the keywords

Episode 2 rendered 45 Pexels clips, zero from the owned pool, and Tee rejected
it on sight. Six of its ten keywords were abstract or unsearchable, which is
real, but fixing them would only have produced better stock of strangers.

`Plan B-Roll Segments` cuts the script into 5 to 12 second scenes and
`Pexels Search` fetches one clip per scene. There is no avatar anywhere in the
render lane. The source was the fault.

Two things were already sitting there unused. `Build Movie` carries
`POOL_SHARED = false`, retired 10 Aug 2026 after all 21 pool clips were reviewed
frame by frame and found to be abstract texture: in its own words, "Not one
contains a person, a desk, a screen, a keyboard or an office." And
`Build Script Prompt` still told the writer TQO was "A faceless YouTube
channel", which is the retired framing, live, in the node that writes every
script. That line is why the visual direction pointed at stock in the first
place.

## The arithmetic that decided the architecture

Episode 2 is 1261 words, about 504 seconds at 150 wpm. Tee supplied nine
reference scenes. Held 15 seconds each, the episode needs roughly 34 frames, so
nine assets would each appear about four times. Visible looping on a channel
whose promise is restraint reads as cheap.

A presenter base layer fills all 504 seconds with one continuous performance and
no repetition, and drops the cutaway count to 8 to 12. Nine assets is plenty for
that and nowhere near enough to carry the frame. That is why the answer was
presenter as base rather than a bigger stock pool, and it is arithmetic rather
than taste.

## The HeyGen road, and where it stopped

Tee supplied `1b799c8689a54ebcb6a55de37f92488c` and reversed the 2026-09-15
ruling to run both routes. The probe found three things a build would otherwise
have discovered the expensive way.

That id is a `talking_photo_id`, not an `avatar_id`. HeyGen's generate takes
`character: {type: "avatar", avatar_id}` or
`character: {type: "talking_photo", talking_photo_id}` and they are different
shapes, so wiring it as an avatar fails at the first render. Tee then chose the
real avatar `aada36d0b20f454b98f03748ec0e6ff0` instead.

Of the two HeyGen credentials, `Xz4mxIvFgUjLBowu` works and
`9i1bFLtfKwtf72z8` returns 401.

And the one that stopped the lane: `GET /v3/users/me` reports
`billing_type: wallet`, `remaining_balance: 0`, and `auto_reload` enabled at $10
with a $5 threshold. A generate call does not fail against an empty wallet. It
charges a card automatically with no confirmation. Tee ruled: do not spend,
MuseTalk only.

The free watermarked previews were not a way around it and should not have been
offered. The docs say an API key bills API plans while OAuth draws subscription
credits, and on v3 this account has no plan at all. The `plan_credit` 99 and
`studio_free_watermarked_preview` 3 came from the deprecated v2 endpoint and do
not map onto the wallet the key bills. That option was put on a card before the
contract had been read.

## Three mistakes, all the same shape

An empty answer from a query is not an empty world, and that happened twice in
one session. A pull request search with the repository name in the wrong case
returned `[]` and was reported as "no open pull requests". Then
`list_credentials` with `query: "heygen"` returned zero and was written into
this repository as "no HeyGen credential exists". Its `query` is a case
sensitive substring match: `heygen` gives 0, `HeyGen` gives 1, and neither finds
`HEYGEN_API_KEY`. Only the unfiltered listing is evidence.

The third is the same error wearing a clock. A `/health` read taken at
13:18:47Z was answered by the outgoing container during a deployment cutover,
reported as a clean boot of the incoming one, and then reasoned from to a
confident wrong conclusion that three variables were empty. The incoming
container had not finished booting until 13:18:49Z. The reasoning was sound and
the input was three seconds stale.

## What shipped while this was being worked out

The Cerebras 429 is fixed and published. `Daily 6am - Script Writer` fired at
`0 6 * * *` and `Every 3h - Pipeline Pass` at `0 */3 * * *`, both America/New_York,
so 06:00 sat on both grids and two executions of a 240 node workflow started in
the same millisecond every day. On 2026-09-16 that killed both:
`Write Script (Cerebras)` on requests per minute, `Write Packaging (Cerebras)`
on tokens per minute. Script Writer moved to `20 6 * * *` and both nodes gained
retry. n8n caps `waitBetweenTries` at 5000ms, so retry alone could never clear a
per minute window; the schedule move is the fix and the retry is cover.

`Build Script Prompt` no longer calls TQO faceless. It names Tee as the
presenter in his own likeness and cloned voice, and the broll instruction now
describes cutaways over a presenter with stock people standing in for him banned
outright. Verified byte for byte against the computed text before publishing.

## DEVON RECEIPT

```
AREA: TQO, Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-presenter-lane-and-a-wallet-that-does-not-refuse_v1_2026-09-16p.md
DATE: 2026-09-16
DECISIONS: Tee ruled on inline cards through 2026-09-16: the b-roll becomes his own avatar at a computer rather than stock; the presenter is the base layer with stock as cutaway; the faceless line in the live writer prompt is fixed now; the Cerebras 429 is fixed by moving the schedule and adding staggered retries; HeyGen and MuseTalk both run rather than one replacing the other; the two HeyGen credentials are told apart by measurement rather than recall; the avatar TERRANCE drives the base track rather than the talking photo; and finally, on seeing the wallet, do not spend and run MuseTalk only. PR #250 and PR #255 merged on his explicit authorization.
FINDINGS: The b-roll fault was the source and not the keywords: the whole visual track is Pexels and no avatar exists anywhere in the render lane. The owned pool machinery is present and deliberately off since 10 Aug 2026 because all 21 clips were abstract texture with no person, desk or screen in any of them. The live writer prompt still called TQO faceless, which is the retired framing and the reason the visual direction pointed at strangers. Nine reference scenes across a 504 second episode would repeat about four times each, which is why the presenter had to be the base layer rather than the pool being enlarged. The id Tee supplied is a talking_photo_id and not an avatar_id, which would have failed at the first render. Credential Xz4mxIvFgUjLBowu works and 9i1bFLtfKwtf72z8 returns 401. HeyGen billing_type is wallet with remaining_balance 0 and auto_reload enabled at $10 with a $5 threshold, so a generate charges a card automatically rather than refusing. The free watermarked previews were offered before the contract was read and are not reachable by an API key. Three of my own errors share one shape: an empty query result treated as an empty world, twice, and a health read taken inside a deployment cutover treated as a clean boot.
OPEN: Nothing has been shot, so the presenter is blocked on the 20 minute recording session and a rented GPU. Build Movie emits type video only, so stills would need that line changed to emit type image with a pan and zoom. Episode 2 sits at Ready with human_review unticked and failed on b-roll. Three production Vercel deployments were CANCELED in twenty minutes and production web is stale at c653559, cause unchecked. Episode 2 telemetry crediting elevenlabs and the Tee clone is unverified against the render node. The dead HeyGen credential 9i1bFLtfKwtf72z8 should be deleted or repaired rather than left to be picked by a future session.
STATUS: The Cerebras fix and the presenter led writer prompt are live on TQO FINAL V5, published as 1544dcca then 363fba04, revert 39874380. The shot list is written and merged. The HeyGen lane is credentialed, its avatar chosen, and deliberately unfunded. The presenter itself is not built and waits on footage.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
