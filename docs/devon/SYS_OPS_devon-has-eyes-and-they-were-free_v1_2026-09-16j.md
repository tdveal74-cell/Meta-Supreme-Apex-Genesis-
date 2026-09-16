# DEVON has eyes, and they were free all along

Dated 2026-09-16. Closes the vision arc opened by
`SYS_OPS_devon-gets-eyes_v1_2026-09-16i.md`, which shipped the lane and could
not make it answer. It answers now, at no cost, and the reason it did not
earlier was a wrong generalisation of mine rather than a missing capability.

## The measurement that ruled out a local model

Tee ruled on 2026-09-16 to host a vision model on the VPS rather than fund a
provider. `HARDWARE.md` section 5 already refuses that shape in general terms,
no GPU and inference is a provider's problem, so the objection was logged once
and the box was measured rather than argued about.

He read it off the host: 2 CPU cores, 7,940 MB of memory with 7,219 MB
available, and 96 GB of disk with 92 GB free. No GPU reported.

Memory and disk are not the problem. A quantised 2B to 4B vision model fits in
7 GB with room, and 92 GB is ample. Two cores is the problem, and three things
compound on it. A vision model pays a large one time cost pushing the image
through a vision tower before it emits a token, then generates at a few tokens
per second on two cores. That box is not idle: it runs the whole n8n estate,
62 workflows including TQO FINAL V5, the TSWS render lane, the Approval Queue
and every schedule, so saturating both cores for a minute an image stalls work
that has nothing to do with vision. And the lane's own Describe Image node
carries a 60 second timeout, so a local model slower than that fails every
call.

The per image timing above is an estimate and is labelled as one. The core
count is the measurement, and two is the wrong side of the line. So the local
ruling could not be executed on this host, and that was said rather than
quietly worked around.

## The correction: free and zero retention are not opposites

After `google/gemma-4-31b-it:free` was refused with `zdr-violation-by-account`,
this session concluded that the account's Zero Data Retention setting excluded
free endpoints as a class, and recommended funding a provider. Tee pushed back
with four words, that he had picked a free model, and he was right.

That conclusion was drawn from ONE sample. Testing a second free model settled
it in one call. `inclusionai/ling-3.0-flash-vl:free` returned HTTP 200 at cost
0 through provider Novita, in about two and a half seconds, and described the
test image correctly: three horizontal stripes, red then green then blue, which
is exactly the image that was built to be falsifiable.

So ZDR eligibility is per endpoint, not per price tier. Some free endpoints
meet the guardrail and some do not, and the only way to know is to ask. The
general claim was the error; the specific rejection was real.

This is the first law with the roles reversed. The rule usually catches an
assertion made without a check. Here the check was run, once, and its result
was widened into a class claim that a second check would have killed. One
sample is not a category.

## What is live now

Workflow `WjSNXSsGP8ZCxXMa`, path `devon-vision`, published,
activeVersionId `4fc9069d`, default model
`inclusionai/ling-3.0-flash-vl:free`.

Proven twice at the door and once through the default path. Execution 262 with
the model passed in the body, execution 263 with nothing in the body but the
image, taking the default model and the default prompt, returning 200 with a
correct description and writing row 6 of `devon_vision_log`. Six rows now hold
the whole arc: one guard refusal, three provider failures each answered as
data in the provider's own words, and two successes.

The failures matter as much as the successes. `z-ai/glm-5.2:free` reads no
images at all, `google/gemma-4-31b-it:free` is ZDR ineligible on this account,
and `openai/gpt-5-nano` returned 402 because the OpenRouter account has never
purchased credits. That last one still stands: the account is unfunded, which
is fine while a free endpoint carries the lane and is the same trap the
2026-09-16c doc recorded for the Anthropic account.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_devon-has-eyes-and-they-were-free_v1_2026-09-16j.md
DATE: 2026-09-16
DECISIONS: Tee ruled to host a local vision model on the VPS rather than fund a provider, which overrode HARDWARE.md section 5; the objection was logged once and the box measured rather than argued. The measurement closed it: 2 cores cannot serve a vision model inside the lane's 60 second timeout without starving the n8n estate that shares the host. Tee then ruled the free path again, and that ruling was correct: inclusionai/ling-3.0-flash-vl:free is now the lane default, published as activeVersionId 4fc9069d. The OpenRouter account stays unfunded on purpose while a free endpoint carries the lane.
FINDINGS: The VPS is 2 CPU cores, 7,940 MB memory with 7,219 MB available, 96 GB disk with 92 GB free, no GPU reported; memory and disk are ample and the core count is the blocker. A wrong generalisation is corrected here: after one free model was refused with zdr-violation-by-account this session concluded that Zero Data Retention excluded free endpoints as a class and recommended funding a provider, and Tee was right to push back. ZDR eligibility is per endpoint, not per price tier, proven by inclusionai/ling-3.0-flash-vl:free returning 200 at cost 0 through Novita in about two and a half seconds with a correct description of a falsifiable test image. Three provider failures stand as recorded: glm-5.2:free accepts no image input, gemma-4-31b-it:free is ZDR ineligible on this account, and gpt-5-nano returned 402 because the OpenRouter account has never purchased credits.
OPEN: The OpenRouter account remains unfunded, which is deliberate while a free endpoint serves the lane and becomes a blocker the moment a paid model is wanted. Free endpoints carry rate limits that have not been measured, so throughput under real use is unknown and the first busy day is the test. The local model ruling is unexecuted and stays that way unless vision moves to its own box, which is the pattern deploy/render-worker already uses. And VISION_IMAGE_ROOT stays unset by Tee's ruling, so the repository side vision.describe refuses every call while the n8n lane carries all real traffic.
STATUS: DEVON has vision. Workflow WjSNXSsGP8ZCxXMa is published on path devon-vision at activeVersionId 4fc9069d with default model inclusionai/ling-3.0-flash-vl:free, guarded by x-devon-key and proven by a 403 from outside with no key. Execution 263 sent only an image, took the default model and the default prompt, returned 200 with a correct description and wrote row 6 of devon_vision_log. Six rows hold the arc end to end: one guard refusal, three provider failures answered as data, two successes.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
