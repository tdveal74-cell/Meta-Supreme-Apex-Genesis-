# The ears arc, and what it could not prove

2026-09-17. DEVON could speak, see and think, and could not hear. Four pull
requests closed that gap: #251 taught the command parser to read a transcript,
#252 built a read only hearing door and the n8n lane that speaks through it,
#257 gave the presence socket an ear, and #258 answered a question the ears
made askable, whether an idea has already been on air. #259 then went back and
tried to prove the four things the first three left as claims.

Two of the four proved. One proved as far as it can go without Tee's key. One
turned out to be unprovable on this estate as configured, and saying so was the
answer rather than a failure.

## The pin that was facing another pin

`apps/presence/protocol.py` refused any hello whose version was not the
server's. `apps/web/lib/presence/protocol.ts` refuses any ready that is not the
client's. Those two refusals face each other, and the presence service and the
web app deploy separately. Bumping the server to v2 alone would have blacked
out every open browser while `/health` kept reading healthy, because the page
would refuse the ready it was answered with.

So the version is negotiated instead of pinned. The server echoes back the
number the client asked for, and a v1 client keeps working while a v2 client
gets `listen_start`, `listen_chunk` and `listen_end`. The transcript enters the
same `begin_turn` a typed `say` enters, which is why speaking a turn and typing
one converge a function later rather than growing two code paths.

Eight mutations, eight named failures. Two of them changed the work. Deleting
the protocol gate made the v1 refusal test hang rather than fail, because a
removed gate answers nothing and `receive_json()` blocks forever; the test now
sends a ping behind the expected refusal, so a broken gate fails in seconds.
Deleting `clip.reset()` left every test green while a retried `listen_end`
would transcribe and bill the same audio twice. Nothing covered the retry case
until that survivor pointed at it.

## The measurement that killed a floor

Episode coverage asks whether Tee has already made an episode about a thing.
The first design asserted a cosine floor of 0.45 and moved on. Measured under
`MockEmbeddingProvider`, an on topic question scored 0.6170 against the jobs
episode and a sourdough recipe scored 0.6406 against the same one. Two
hundredths apart, with the wrong one higher. No floor separates those.

A deployment falling back to mock embeddings would therefore have answered "yes,
you covered that" about an episode that does not exist. `already_covered` now
refuses outright and returns `answerable: false`, which is a different claim
from `covered: false` and is kept apart on the wire. The floor is still in the
file and still labelled unverified against hosted embeddings, because it is.

That floor cannot be verified here, and the reason is not that the measurement
is hard. The provider that embeds is resolved in `app/services/knowledge.py`
and reads `DEFAULT_AI_PROVIDER`; only mock and openai can embed; the Railway
api service carries no `OPENAI_API_KEY`. `app/services/knowledge_graph.py`
lines 204 to 218 had already written that down and verified it by running it.
I described it in session as though I had found it, and that was wrong; the
repository knew first.

## Reading a contract from the vendor instead of from memory

`api.elevenlabs.io` is blocked by this container's egress proxy, measured
rather than recalled: the CONNECT tunnel fails with a 403. Both probes ran
through n8n instead, nine read only requests across two throwaway workflows,
every one refused before any audio was read, so none cost a transcription.
Both workflows are archived.

The vendor named every field back. A 422 named `model_id`, a 400 named `file`,
a 400 on a synthesis model listed all four valid models, and a request to
`/v1/speech-to-txt` returned 404 as the negative control that makes the other
three mean something.

The header name came from a second probe with no credential attached at all.
No header returns "Neither authorization header nor xi-api-key received". Junk
in `xi-api-key` returns a different message, "Invalid API key". The same junk
in a header name I made up returns the first message again. So the header was
read and its value rejected, which is the only shape that distinguishes a
correct header name from a wrong one, because a wrong name is invisible.

That probe found a bug. `ELEVENLABS_STT_MODELS` listed two of the four models
the vendor accepts, so `ELEVENLABS_STT_MODEL=scribe_v2` would have been refused
at startup for a model that works. The fix was confirmed against the live
account rather than against a list of names: a fourth request sent `scribe_v2`
with a real credential and came back with the file refusal instead of a model
refusal.

## A guard that was a denylist, and let the wrong thing through

The coverage guard refused a `mock` provider by naming it. `DEFAULT_AI_PROVIDER`
holds a chat provider name, so `cerebras` passed a denylist of `("mock",)`,
reached the search, and raised `ProviderConfigError`. The caller saw a 503,
which is a plumbing error, where "these distances cannot carry a verdict"
belonged. The guard is now an allowlist, `TRUSTED_FOR_COVERAGE = ("openai",)`,
so anything unmeasured refuses instead of trying.

Both probes in #259 found a bug. That is the argument for probing rather than
reasoning, in one line.

## What the record said and the estate did not

`services/devon/vault.py` recorded DEVON Hears as inactive and never executed,
with an undeployed endpoint and an empty credential. Read from the estate on
2026-09-17, every part of that had stopped being true. The workflow is active.
Executions 288 and 335 both succeeded. An unkeyed POST to
`api-production-5644.up.railway.app/api/v1/devon/hear` answers 401 with
"Invalid or missing service key.", while a made up sibling path answers 404, so
the 401 is that route refusing a bare caller rather than a catch all.

Both executions ran in manual mode, which matters more than it looks. Manual
mode never checks the webhook header, so those two successes say nothing about
whether Railway and n8n carry the same key string. The record now says active,
two manual executions, no production webhook request yet, and the byte
identical copy under `deploy/soul` carries the same correction.

The entry had been correct on the day it was written. It went stale the moment
PR #252 deployed, and nothing in this estate re-reads a vault entry on a merge.
That is worth watching: the record drifts in the direction of the day it was
last touched, and only a deliberate read from the estate pulls it back.

## What is still not proven

No audio has been through the devon-hears lane. What remains is one keyed POST
carrying a voice note to the production URL, and the key lives on Tee's phone.

The presence capture UI does not exist. Nothing in the browser asks for a
microphone, so the ear built in #257 has no mouth pointed at it. `PRESENCE_EARS`
defaults to mock, so the deployed service behaves exactly as it did before a
client opts in.

Nothing transcribes an episode. Transcripts arrive as text, and the lane that
turns a rendered mp4 into that text needs ffmpeg, a download path and a machine
auth story. None of those are answered here.

Migration 020 on the production database is unchecked. The episode routes
answer 401 before touching the database, so their presence proves the code
deployed and says nothing about whether the migration ran. Anyone with the
Railway database credentials can settle it with one `alembic heads`.

Three things were offered and never authorized: homophone tolerance on the wake
word, per word confidence gating from ElevenLabs logprobs, and a Drive intent
in `commands.py`. The homophone gap was measured in session on 2026-09-16 and
was not filed, so a future session should re-measure rather than quote it.

The Vercel account block is the fifth on this estate, after 2026-09-02, 09-04,
09-05 and 09-15. Its signature is the absence of deployment records rather than
a red status: the last record on either project is 22:58:52Z on `ce70236`, and
the two pushes on PR #259 created none while Actions ran green. Only a human on
the Vercel account can clear it, so no re-run was spent on it. At this rate it
is worth asking Vercel why the account keeps blocking, rather than having each
session re-diagnose it from scratch.

## DEVON RECEIPT

```
AREA: Systems, Learning
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-ears-arc-and-what-it-could-not-prove_v1_2026-09-17-0144.md
DATE: 2026-09-17
DECISIONS: Tee ruled on inline cards across 2026-09-16 and 2026-09-17: build ears item 2, the presence socket, over an iPhone Shortcut, which overruled my recommendation; then ears item 3, connected transcript sources, and on the shape of item 3 he handed the call back and I took the episode transcript lane; then prove the four things the arc left unproven. He authorized PR #257, #258 and #259 to merge, each explicitly. Two decisions inside the arc were mine: the protocol version is negotiated rather than pinned, because two pins facing each other across separately deployed services would black out the page on a one sided bump; and the coverage guard is an allowlist rather than a denylist, because a denylist has to name every provider that cannot be trusted and a new one is trusted by default.
FINDINGS: A 0.45 cosine floor was asserted and not measured; measured under mock embeddings an on topic question scored 0.6170 and a sourdough recipe scored 0.6406 against the same episode, so the floor was removed as a decision rule rather than tuned. DEFAULT_AI_PROVIDER holds a chat provider name, so a denylist of ("mock",) let cerebras through the coverage guard into a ProviderConfigError the caller saw as a 503. ELEVENLABS_STT_MODELS listed two of the four models the vendor accepts, so a valid model would have been refused at startup. The ElevenLabs header name was proven by a probe with no credential attached, with a made up header name as the negative control, because a wrong header name is invisible to the caller. api.elevenlabs.io is blocked by this container's egress proxy, CONNECT 403, so both probes ran through n8n and none of the nine requests reached audio. A deleted clip.reset() left every test green while a retried listen_end would have transcribed and billed the same audio twice. A deleted protocol gate made a test hang rather than fail, because a removed gate answers nothing. services/devon/vault.py recorded DEVON Hears as inactive and never executed while the estate had it active with executions 288 and 335 and the endpoint returning 401 rather than 404; the entry was correct the day it was written and went stale on the merge that deployed the door. Both of those executions ran in manual mode, which never checks the webhook header, so they prove nothing about the key. I described the embedding provider quirk as my own finding when app/services/knowledge_graph.py lines 204 to 218 had already recorded and verified it.
OPEN: No audio has been through the devon-hears lane; what remains is one keyed POST to the production URL and the key is on Tee's phone. The presence capture UI does not exist, so nothing sends the new ear any audio and PRESENCE_EARS stays on mock. Nothing turns a rendered episode into a transcript; that lane needs ffmpeg, a download path and a machine auth story. COVERAGE_FLOOR stays unverified against hosted embeddings and cannot be measured on this estate, because the Railway api service carries no OPENAI_API_KEY. Whether migration 020 ran on the production database is unchecked, since the episode routes answer 401 before touching it. The Vercel account block is the fifth occurrence and only Tee can clear it. Homophone tolerance on the wake word, per word confidence gating and a Drive intent in commands.py were offered and never authorized.
STATUS: PR #252, #257, #258 and #259 are merged on main. CI is green on all four merge commits, read from the Actions history rather than from a handover: 94de84b run 35095736299, 616a0cd run 35141055999, ce70236 run 35160162292, and 3112aea run 35171212016, five of five jobs each. The last of those is the one that matters most, because a collision lives only in the merge commit and a green pull request proves nothing about it; its three migration steps, the fresh Alembic deploy, the same database check and the ledger and knowledge suites against the Alembic build, all passed at 01:44Z. The hearing door and both episode routes are deployed and refuse an unauthenticated caller, measured on 2026-09-17 against a 404 control. The presence ear ships behind PRESENCE_EARS=mock and changes no deployed behaviour until a client opts in. The vault entry for DEVON Hears now matches the estate.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
