# DEVON read the frame, and misread one word

Dated 2026-09-17. Supersedes the OPEN section of
`SYS_OPS_the-empty-description-was-a-spent-budget_v1_2026-09-17-1231.md`, which
merged in PR #265 saying the fix was unproven in production. It is proven now,
about two hours later, and the proof also found the limit of the model.

## The controlled measurement

Deployment `418b4066` reached SUCCESS at 13:19:24Z on `3b30e10`, the merge of
PR #265, which is the first build carrying `VISION_MAX_OUTPUT_TOKENS`. Both
calls that had failed were then re-run against the same model, the same image
and the same prompts. Only the budget differed.

| prompt | on the 700 ceiling | on the 2000 ceiling |
|---|---|---|
| "Describe this image." | empty description, 700 output tokens spent | full description, 654 tokens, truncated false |
| quote the text verbatim and count the blocks | empty description, 700 output tokens spent | full description, 906 tokens, truncated false |

906 is the number that settles it. That call could not have fitted inside 700
under any circumstances, so it was structurally impossible rather than
unlucky, and no amount of re-running would have produced an answer.

The first row is the one that looked like flakiness. At the 700 ceiling the
same call returned nothing twice and nine words once; at 2000 it finished in
654. Reasoning length varies run to run, and 700 sat close enough to the
requirement that the outcome changed with it. That is why three identical
calls produced three different results and why "flake" was the wrong reading.

Latency was 6032 ms and 6683 ms, against 7074 ms for the truncated call, so a
bigger budget did not cost time here. The model stops when it is done.

## What it actually saw

`scripts/make_vision_test_frame.py` draws "DEVON VISION" at scale 5 and
"TEST FRAME 3" at scale 4, plus a solid accent bar.

The model returned "DEVON VISION" exactly, in both calls, and named its colour
correctly. It returned "TEST RA E 3" in both calls, dropping the F and the M
from FRAME. It described the bar correctly and counted two distinct blocks of
text, which is right.

So the same misread twice, independently, on the smaller of the two lines. Not
a random slip. This model reads large text reliably and fumbles the same
characters at scale 4 on this font.

That is the frame earning its keep. It was built to be falsifiable, and
nothing else in the estate would have caught a partial misread: a tool that
returns fluent prose about an image nobody has checked is indistinguishable
from one that works. `image_sha256` on every call matched `0df18808`, so what
was described is the committed file and not a cached or substituted one.

## What this does not prove

One model, one image, one font. It says nothing about photographs, screenshots
of real interfaces, or handwriting, and nothing about any other model. The
2000 default is measured to be enough for this model on this image, not proven
sufficient in general; the setting exists precisely so the next model can be
given more without a release.

A vision call still costs no money on this endpoint, so none of the above
tested the billing path.

## Corrections this arc owes

The 1231 doc and PR #265's merge commit both say the api service had taken no
deployment since 04:30Z. That was true at 12:37Z when it was written and false
by 13:09Z when the merge landed: the service deployed `cfe29b0` at 12:52:10Z
and succeeded at 13:00:06Z. The claim was checked once and built on rather than
re-checked at the moment it mattered.

Two SKIPPED deployments were also over-read into "deployments are broken". The
real behaviour is `checkSuites: true` making Railway WAIT for the commit's
check suite, which is what `418b4066` did for ten minutes before deploying.
WAITING and SKIPPED are different states and were treated as one.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_devon-read-the-frame-and-misread-one-word_v1_2026-09-17-1422.md
DATE: 2026-09-17
DECISIONS: Tee ruled on an inline card on 2026-09-17 that this arc closes with a superseding status doc now rather than folding the proof into the next arc or leaving it in the transcript, because the merged 1231 doc's OPEN section would otherwise stay the newest word on a question that is answered. He had earlier authorized the merge of PR #265 explicitly, and separately authorized me to approve vision cards myself, which is what made these two measurements runnable without him.
FINDINGS: The output budget was the whole cause and the proof is a single variable change. The same model, image and prompts that returned empty descriptions on a 700 token ceiling returned full descriptions on 2000, spending 654 and 906 tokens with truncated false. The 906 call could never have fitted in 700, so it was structurally impossible rather than flaky, and the 654 call sat close enough to 700 that reasoning length alone decided the outcome, which is why three identical calls gave three different results. The model reads large text reliably and misreads smaller text: it returned DEVON VISION exactly and TEST RA E 3 for TEST FRAME 3 on both calls independently, dropping the same two characters at scale 4. image_sha256 matched 0df18808 on every call, so the described file is the committed one. A larger budget cost no latency, 6032 and 6683 ms against 7074 for the truncated call.
OPEN: One model, one image, one font: nothing here covers photographs, real interface screenshots or handwriting, and the 2000 default is measured enough for this model rather than proven sufficient in general. The endpoint is free, so the billing path is untested. Tee's password remains disclosed and unrotated from a 2026-09-17 screenshot. The ten year access token issued to this session remains live and is revoked only by rotating SECRET_KEY on both the api and presence services together with RECEIPT_SIGNING_KEYS_PREVIOUS carrying the old value, which is unstarted. ACCESS_TOKEN_EXPIRE_MINUTES is set to 1440 and took effect with this deployment, so only tokens issued before it keep the old lifetime. Approval card REQ-F3F9F01CB06F expires unruled on 2026-09-20.
STATUS: PR #265 is merged as 3b30e10 with all five CI jobs green on f287690, run 35224550336. Railway deployment 418b4066 reached SUCCESS at 13:19:24Z on that commit and is what these measurements ran against. Two corrections are recorded above rather than quietly fixed: the 1231 doc and the merge commit both claim no deployment since 04:30Z, which went stale twelve minutes before the merge, and two SKIPPED deployments were over-read into a broken gate when the real behaviour is checkSuites making Railway wait.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
