# DEVON gets eyes

Dated 2026-09-16. Tee asked how to give DEVON vision, then asked for all of it,
both tiers. This is what was built, what was measured on the way, and the four
things that are still his.

## What was asked and what the repo actually had

The question came out of Britain Eriksen's Omarchy Vision video. That project
was assessed and NOT installed: it needs Omarchy, which is DHH's Arch Linux
distribution running Hyprland, plus PipeWire, a V4L2 camera and the Wayland
tools grim, wtype and ydotool. Tee's primary device is an iPhone 15 Pro and
DEVON is FastAPI on Railway with Next.js on Vercel, so nothing in the estate
runs it. It is also a camera pointed at a physical desk rather than screen
capture, so it would not have filled the hole anyway. Two ideas were taken from
it: vision on demand rather than as a watcher loop, and a pluggable image
target so a local model is a setting rather than a retrofit.

Before any of that, three absences were verified by reading the files.
`ChatMessage.content` is typed `str` at
`services/intelligence/providers/base.py:41`, so no model in DEVON could accept
an image. `artifacts.body` is TEXT and its own schema file says "estate:// is a
path label, not a blob", so there was nowhere to put one. There is no
`UploadFile`, no multipart and no `File(` anywhere in the FastAPI app or
services, and nothing on the Next.js side, so there was no way in.

## The contract decision, and why the obvious answer was wrong

The first recommendation given to Tee was to widen the text contract, either an
images field on `CompletionRequest` or content parts on `ChatMessage`. A recon
pass and a three way design panel overturned it, and the evidence is stronger
than the original reasoning.

`ChatMessage(role="user", content=[{...blocks...}])` is accepted TODAY with no
error: the dataclass has no validation and no `__post_init__`. Both HTTP
providers then put that list on the wire completely untranslated. Measured
directly with `httpx.MockTransport` on 2026-09-16: Anthropic and OpenAI receive
BYTE IDENTICAL `messages` arrays for the same block list, despite the two
vendors' block schemas differing. So widening the type alone buys a contract
that silently works for one vendor and 400s the other. `MockProvider` raises
`AttributeError` on a list at `mock_provider.py:60`, and
`AgentTurn._compact_history` calls `str(item.content or "")`, which converts a
block list to its Python repr and loses the image with no error at all.

The second reason is cheaper to state. `services/intelligence/providers/base.py`
is byte mirrored into `deploy/soul/` and `test_deploy_soul.py` asserts the two
files are identical, so every edit there spends a production Vercel build of
devon-soul on a service that gains nothing from vision.

So the text contract was not touched. `services/vision/` is a separate path
with its own `ImageSource`, `VisionRequest`, `VisionResponse` and
`VisionProvider`, and it translates per vendor.
`test_devon_vision_path.py::test_the_two_vendors_get_different_bodies` asserts
the two request bodies DIFFER, which is the regression the text path would fail
right now.

## The gate, and why READ was refused

`vision.describe` is registered at `risk=ToolRisk.WRITE` with
`reversible=False`. READ is not a lighter class for the same operation, it is
the operation with three mechanisms removed at once: `approval_required` is
`risk in {WRITE, HIGH_IMPACT}` so there is no card, `presence.decide` returns
RUN for READ before it ever reaches the reversibility branch so there is no
confirm, and `AgentRuntime.run_next` writes the durable effect intent and
receipt only when `approval_required` so there is no receipt either. A frame
leaving the host for a third party with none of those is the wrong trade, and
`services/devon/commands.py` already wrote down the reason: screens hold
secrets.

Not HIGH_IMPACT, because `approval_required` is identical for both and every
member of that class changes durable state on a remote system. Describing an
image changes nothing anywhere. `reversible=False` is what does the work, and
it is true: no later action recalls bytes already sent.
`test_the_gate_stops_in_both_presence_lanes` makes the ruling executable:
CONFIRM for a present human, CARD for automation, and the reason reads "cannot
be undone", which is the true one.

## The screenshot intent was lying, and it has four copies

`take_screenshot` described itself as "Writes an image of the screen to disk."
DEVON runs on Railway and Vercel. There is no screen, and a full grep across
every file type found the name only in its own registration, in tests, in the
two console copies and in DEVON.md. Nothing executes it.

The sentence now reads: "Captures the screen of the machine DEVON runs on.
Nothing executes this today and the deployed API has no screen, so approving it
captures nothing. Gated because screens hold secrets." No test anywhere asserts
that string, which was confirmed by grep before the edit, so the local run was
going to be green whether or not the replacement was true. The truth of it had
to be argued rather than inferred from CI, which is the most literal form of
green is not correct.

It had a second copy as plain HTML data at `deploy/soul/console.html:1750`,
lowercased and reworded, that a grep for the Python string alone misses. Both
were changed, along with the byte paired asset
`docs/devon/assets/SYS_OPS_devon-console_v10_2026-09-01.html`. The nine
SUPERSEDED console assets carry the same line and were deliberately left alone.

## The n8n lane

`DEVON Vision Describe`, workflow `WjSNXSsGP8ZCxXMa`, path `devon-vision`, 11
nodes, created INACTIVE. POST one image as binary with the existing
`x-devon-key` and the description comes back in the HTTP response. Every
refusal happens BEFORE the paid call and resolves to data with a reason and an
HTTP status, never a throw. `neverError` and `fullResponse` are on so the node
cannot throw and `Read Result` reads `statusCode` back itself, which makes a
non 2xx a failure that answers. One row per attempt lands in
`devon_vision_log` `lapnGsgr33wcX0Ef`, success or refusal, so a lane with no
rows is visibly a lane that did nothing.

`devon-capture-file`, workflow `bCZa6KVgjHgRup1Y`, already accepts photos from
an iOS Shortcut and files them to Drive, and it is inactive. It was left alone.
Filing and describing are two jobs and the house rule is one path, one job.

## The suffix raced again, and CI would have caught it second

This doc was written as 2026-09-16h. PR #242 merged while the work was in
flight and took h for the same day, so merging main produced two h files and
the sequence letter rule would have failed. Caught by recounting the letters
from the directory after the merge rather than trusting the number picked
before it. It is now i; e stays free on main but is claimed by the unmerged
branch behind PR #239, which is the open PR about this exact race.

## Two findings withdrawn before they were raised

Both cost a grep and both were wrong. The Capture Hook's Cloud id
`Cbd24ptTPWch3aZO` and VPS id `bCZa6KVgjHgRup1Y` are both recorded correctly,
with the mapping in the cutover doc. The Devon Capture Key's Cloud id
`FYRvkRTOcROEYZ9P` and VPS id `MTZXcoob6BtzbJyH` are both recorded too, and the
step one doc proves the two hold the same secret by echo. The second nearly
became a false finding because the checking grep was piped through `head` and
the truncation hid the evidence. Grade a finding before raising it, and check
that the check itself was complete.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_devon-gets-eyes_v1_2026-09-16i.md
DATE: 2026-09-16
DECISIONS: Tee ruled to build both tiers. Omarchy Vision assessed and not installed: wrong platform, wrong capability, wrong gate posture. The text completion contract was NOT widened; services/vision is a separate path, ruled after measurement showed a block list reaches both vendors byte identically today and that base.py is byte mirrored into deploy/soul. vision.describe carries risk WRITE with reversible False, not READ, because READ removes the card, the confirm and the effect receipt together. OpenRouter chosen for the tier one lane on Tee's answer, over funding the Anthropic account or adding an OpenAI credential. Vision is on demand only, and the local model seam was built on day one rather than retrofitted.
FINDINGS: ChatMessage accepts a block list today with no validation and both HTTP providers put it on the wire untranslated, producing byte identical JSON for two vendors whose schemas differ, measured with httpx.MockTransport. MockProvider raises AttributeError on a list and AgentTurn stringifies it silently. There is no upload path anywhere in the FastAPI app, the services or the Next.js side, and artifacts.body is TEXT. take_screenshot described writing an image of the screen to disk on a service with no screen, no test asserted that string, and a second copy of the same false claim sat in console.html where a grep for the Python string misses it. The VPS has no OpenAI credential and the Anthropic account behind J2kxUFwXcqTltKaw is the unfunded one from the OS 29 finding, so a vision node pointed at it fails the same way. n8n reported the OpenRouter credential was SKIPPED during auto assignment on the Describe Image node. Two suspected record drifts were withdrawn: both ids were already recorded correctly, and the second was nearly raised because a verifying grep was truncated by head.
OPEN: Four things are Tee's. DEFAULT_MODEL in the n8n Guard node is empty because openrouter.ai is blocked by the session egress proxy and no model id was invented, so the lane refuses 424 until he sets one. The OpenRouter credential needs binding by hand on the Describe Image node. VISION_IMAGE_ROOT is unset, which refuses every vision.describe call, because what writes images into a directory on a Railway container is a deployment decision. And the 017 usage ledger charges a vision call at the text rate with no column for cost, model or modality, so an image is under charged against the daily cap by whatever factor the vendor prices image input above text; VISION_MAX_IMAGE_BYTES bounds the error and a test pins the behaviour, but the real fix is a migration touching four places in ci.yml and both conftest lists and needs his ruling. Separately, the latent hole where ChatMessage accepts a block list is untouched and unclosed; closing it edits the byte mirrored base.py and is its own PR.
STATUS: Tier two is in the repo and green: services/vision with base, providers, adapter and the local seam; MeteredVisionProvider so the call is capped like any other; vision.describe wired into build_tool_registry, which took the Hermes surface from 20 tools to 21 and required the counts fence and the manifest to move with it; 43 new tests across test_devon_vision_path.py and test_devon_vision_spend.py, with the offline file added to the CI standalone list and to the CLAUDE.md mirror of it. The screenshot description is corrected in all four copies. Tier one exists as workflow WjSNXSsGP8ZCxXMa, INACTIVE, registered in vault.py in the same change per the house rule, and has NEVER been executed, so nothing about its runtime behaviour is proven by a run.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
