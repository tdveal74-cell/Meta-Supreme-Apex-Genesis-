# SYS_OPS: the voice lane and the registration gate

Dated 2026-09-10. What happened after the verb gauntlet closed: Tee opened the
control plane for the first time on his own account, and the first turn he took
through it produced a finding worth more than the door did.

## The registration gate, opened and closed in one sitting

`/control` needs a signed in account and Tee had none on this deployment.
`DEVON_REGISTRATION_KEY` did not exist on the `api` service; he created it and
left it empty, which reads as closed rather than open: `auth.py:191` strips the
value and compares its length against a 16 character floor, so unset and empty
behave identically and the route answers `503 Registration is closed`.

Three mechanics were learned the slow way and are written down so nobody pays
for them twice.

* **The two errors say different things.** `503 Registration is closed` means
  the deployment holds no usable key and nothing you type will work.
  `403 Registration key is not valid` means it holds one and yours does not
  match. Getting the second error is progress, not a failure.
* **Railway's Variable Generator is not the value.** Its own text says it
  governs what gets generated when a NEW environment is created from this one.
  `${{ secret(32) }}` typed there changes nothing about what production serves,
  and typed into the value field it is a 17 character literal that clears the
  length floor and never matches anything.
* **The key gates account creation only.** It is checked by `POST /auth/register`
  and nowhere else, so an existing account signs in without it, and deleting the
  key locks nobody out.

The account is created at Talk to DEVON rather than at `/control`.
`DevonChat.tsx:304` tries login first, and only on a 401 with an invite key in
hand does it register and then log in. `/control` has no registration form at
all; its `SessionDoor` points at `/command-center` and watches the same storage
slot.

Tee ruled the shape of this before doing it: set a key he could type by hand,
use it once, then delete it. He deleted it. Registration is closed again and no
invite key sits in the environment.

## The finding that mattered more than the door

His first turn through `/control` rendered `SPEECH cartesia` beside
`PROVIDER mock (fell back)`, and the caption read "Simulated response for:
hello. This output was produced by the offline mock provider."

The presence service's own `/health` named the cause exactly:

```
"last_reason":"cerebras: no first token within 500 ms"
"consecutive_breaches":1, "failure_threshold":3, "opens":0
```

Cerebras was not broken and no key was missing. `inference.py:151` raises
`ProviderConfigError` at STARTUP on a missing key or an unknown name, and the
service was up and serving, so the key had already been accepted at boot. What
happened was a latency breach: the panel measured 502 ms against a threshold of
500. Two milliseconds. One breach out of three never opened the breaker, so the
router covered that single turn from the fallback and carried on, which is
exactly what it was built to do.

The same `/health` reported `last_ttft_ms` of 319 ms. One sample either side of
the line. **A threshold parked inside a provider's own jitter band is not a
guard, it is a coin flip**, and that is the real defect rather than the two
milliseconds.

## The ruling: a cloned voice never speaks words nothing reasoned

The cost of that coin flip is not latency. When the mock covers a turn, its
invented sentence goes to Cartesia and leaves in a voice that is Tee's own, with
a panel field as the only tell. Tee's standing rule is that voice and identity
are owned and never rented, and that compliance items have no exception path.
Invented content delivered as him is an authorship failure, not a UX
preference.

Recommended and ruled: do both halves, in order.

1. `PRESENCE_TTFT_THRESHOLD_MS` moved from 500 to 1500 on the presence service.
   A variable change, no code, live in ninety seconds. Stated plainly at the
   time: 1500 is a judgement from two TTFT samples, not a measured
   distribution.
2. The mock's words no longer reach a real voice. On such a turn the invented
   tokens are drained rather than emitted, and DEVON says one honest line
   instead, so the caption and the audio agree.

**Keyed on the mock, deliberately not on `fell_back`.**
`PRESENCE_FALLBACK_INFERENCE` accepts any name in `INFERENCE_CHOICES`, so a
fallback to Anthropic or OpenAI is honest intelligence with every right to be
spoken. Keyed on the synthesiser as well, because mock words through a mock
voice lend nobody's identity to anything and are what this repository's whole
suite runs on. The hazard is one specific pairing.

Three tests hold all three directions: the refusal fires on mock plus a real
voice, does not fire on mock plus a mock voice, and does not fire on a real
fallback. The correctness of draining rather than suppressing mid stream rests
on a fact read from `breaker.py` rather than assumed: the router settles
`provider` and `fell_back` BEFORE it yields anything, on both paths, so the
question is answered once and cannot flip halfway through a turn.

## A correction against this session's own record

The merge commit for PR #202 says the full api suite reported **2431 passed**.
It reported **2436**. The number was written from expectation while the run was
still going rather than from the run, which is the exact failure the first law
of this repository names. The commit is on main and history is not being
rewritten over a digit, so the correction lives here instead.

## Estate reads taken while answering a question

Tee asked how to make DEVON render a TQO video. Read from the live estate
rather than from memory:

* **`TQO FINAL V5` is active on Cloud** with 7 triggers and 222 nodes, error
  workflow wired to `OS - Error Handler`, timezone America/New_York. The VPS
  copy is inactive with zero triggers, so nothing done there renders anything
  today.
* The authenticated entry point is `POST /webhook/run-tqo-pipeline` on the Cloud
  host carrying the `x-devon-key` header. It responds immediately with
  "Workflow got started", so a 200 means accepted rather than rendered.
* **Two triggers are unauthenticated GETs that start the pipeline**,
  `▶ Run TQO (Link)` and `▶ Run NCO (Link)`. Their unguessable path suffixes are
  the only thing protecting them, and anything that follows a link can fire
  them: a chat app's preview bot, a browser prefetch, a history sync crawler. A
  run costs provider credits and can push an artifact. Raised as worth fixing
  rather than urgent. The suffixes stay out of this document, as ruled
  previously.
* The VPS holds **29 credentials**, including `Eleven Labs` and `Cerebras
  Cloud`. That matters for the outstanding rotation: the ElevenLabs key found as
  a literal in the archived Rendering sub workflow needs rotating at the
  provider, and this VPS credential needs updating in the same sitting or the
  VPS copy will hold a dead key.

The n8n trigger information above came from `triggerInfo`, the summary field
that PR #193 discredited on the VPS for workflows carrying no published
version. This workflow has one, which is the condition where that field was
trusted, so it is reported as a summary rather than as a node graph read.

## DEVON RECEIPT

```
AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-voice-lane-and-the-registration-gate_v1_2026-09-10
DATE: 2026-09-10
DECISIONS: Tee ruled the registration gate stays and is closed again after one use rather than removed from the code, and deleted the variable himself once his account existed; he ruled both halves of the voice fix in, the threshold raise and the refusal, after asking for a recommendation rather than picking from the card; the loop against the n8n verb guard was ruled closed at six ticks earlier the same day
FINDINGS: a control plane turn spoke invented words in Tee's cloned voice because Cerebras missed a 500 ms first token deadline by two milliseconds and the router covered the turn from the mock, with health reporting last_ttft_ms 319 ms on another sample, so the threshold was sitting inside the provider's own jitter band; no key was missing and none was misconfigured, which is provable because a missing key raises at startup and the service was serving; the registration key gates account creation only and an empty value is identical to an unset one; TQO FINAL V5 is active on Cloud with 7 triggers while the VPS copy is inactive with zero, so the VPS renders nothing today; two of those Cloud triggers are unauthenticated GET requests that start the whole pipeline and can be fired by anything that follows a link; the VPS holds 29 credentials including Eleven Labs, which the outstanding rotation has to update; one number in this session's own PR 202 merge commit is wrong, 2431 where the run said 2436, written from expectation before the run finished
OPEN: rotate the ElevenLabs key at the provider and update the VPS credential in the same sitting; rule on the two unauthenticated GET link triggers on TQO FINAL V5; rule on the 45 grandfathered SYS_OPS docs; the contrast pass on /control; confirm whether TQO FINAL V5 renders from a seeded idea row or picks its own topic, which was offered and not yet taken up; 1500 ms is a judgement from two samples rather than a measured distribution and deserves a real reading once the lane has served some turns
STATUS: shipped; PR 202 merged as 7da04d4 with all six CI checks green on de5dc93, and the presence service redeployed on the merge commit; PRESENCE_TTFT_THRESHOLD_MS set to 1500 on the presence service, verifiable at the service's own /health where the breaker block should now read 1500.0; registration closed again with the variable deleted; branch restarted from origin/main
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
