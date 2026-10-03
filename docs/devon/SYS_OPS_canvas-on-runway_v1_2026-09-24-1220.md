# EditForge Canvas renders on Runway, and one allow rule outlived a test

Filed 2026-09-24 at 12:20Z. Follows `SYS_OPS_n8n-bot-access_v1_2026-09-24-1102.md`.

## Rulings

All from Tee on cards, 2026-09-24.

- "The providers for Canva on EditForge needs to be repointed to Runway." Canva is
  EditForge's Canvas workspace. Scope ruled on a card: stills and motion both move
  to Runway; dialogue stays on ElevenLabs.
- Merge on green, deploy with a dry run first, then one test still. Recommended;
  the stated cost was one Runway image generation.
- Restore `TQO Episode Email Drafter (Reach)` and remove the always allow rule
  described below. Both recommended; both are Tee's taps.

## Why Canvas moved

Read live from EditForge's `editforge_status` before any change: `XAI_API_KEY` is
not set on production, so `xai-image` and `xai-video` both read `readyToRun: false`
and Canvas could render neither a still nor a shot. `RUNWAY_API_KEY` is set and
`runway` read `readyToRun: true`.

## What shipped

EditForge PR #72, squash merged as `b8c70b6`.

- A new provider, `runway-image`: `POST /v1/text_to_image`, model `gen4_image`.
  Canvas aspects map to Runway resolutions: 16:9 to 1920:1080, 9:16 to 1080:1920,
  1:1 to 1080:1080, 4:3 to 1440:1080. 3:2 has no Runway resolution and is refused.
- A finished Runway still is copied into the artifact store on the first poll that
  reads success, so it outlives Runway's output link. A failed copy never fails the
  job, because Runway has already been paid; the job keeps the Runway link and its
  note says why the file was not stored.
- Runway video gains a mode, `reference-to-video`, that animates the caller's own
  still. Canvas uses only that mode or `text-to-video`. The existing
  `image-to-video` mode is the presenter B-roll path, where the server swaps in the
  private presenter reference, and Canvas never sends it. A Canvas clip therefore
  cannot animate Tee's likeness. A test puts a presenter file on disk and proves a
  Canvas clip still sends only the Canvas still.
- The render plan refuses, before the paid confirmation, a 3:2 still, motion that is
  not 16:9 or 9:16, a shot outside 2 to 10 seconds, a prompt over 1000 characters
  counting connected context, and a local reference still over 3.3 MB.

Runway's limits were read from its API reference through Context7, because the
docs host is blocked by this environment's egress proxy. None of it had been
exercised against the live API when this was filed.

## Proof

- Local: `vitest` 43 files, 483 passed, 20 new; `tsc`, `eslint lib modules` and
  `next build` clean.
- Ten mutations of mine, each turning the suite red, among them Canvas sending the
  presenter mode, stills routed back to xAI, the store step removed and the plan
  size check removed.
- A fresh critic in its own clone, on `32332e7`, ran eight mutations of its own,
  all killed, and returned PASS WITH CONDITIONS. Condition (a), keep stills
  durably, and (b), check reference size in the plan, were fixed in `2310d4e`.
  Condition (c), one live submit, is open below.
- CI on `2310d4e`: `verify` and `self-host` passed. The `Vercel` status reads
  "Deployment was blocked", identical on PR #71's `355dd7c`; EditForge ships to the
  VPS, not Vercel. Said once on the PR.
- Deploy: `Publish EditForge images` run 35991845047 succeeded for `b8c70b6`.
  `Deploy EditForge to Hostinger` dry run 35992034155 passed every step, then live
  run 35992107054 succeeded, both on tag `b8c70b610d23`.
- Read back after the deploy: `editforge_status` lists `runway-image`, which exists
  only in the new build, as `credentialSet: true`, `readyToRun: true`.

## The allow rule

`list_approval_rules` at about 12:10Z returned the 17 `require_approval` rows the
n8n doc records and one more row that doc does not: `effect: always_allow`,
`matchKind: tool`, `matchValue: mcp__n8n__archive_workflow`. It most likely came
from the approval Tee gave at 11:18Z on Pipeline Operator's archive card; that is
inferred from timing, not read from Rakazo.

By Rakazo's `planActionGate`, read from source earlier the same day, a
`require_approval` rule beats an `always_allow` rule at the same specificity, so
archive should still pause. That is a reading of code, not a live test, and it was
not tested because the only test is another archive. The rule contradicts Tee's
ruling that every n8n write is gated either way. Tee ruled to delete it; the
connector can only add require-approval rules, so the deletion is his tap.

Lesson worth keeping: a gate test belongs on a write whose approval costs nothing,
such as a throwaway folder, not on a real workflow. The deny path is still
unobserved.

## Open

- Tee renders one 16:9 still in Canvas. The EditForge connector's
  `submit_media_job` takes only gen-video, voice and avatar, so no session can send
  the still. The job record then settles critic condition (c), whether `gen4_image`
  accepts a request with no `referenceImages`, shows whether the still was stored,
  and gives its size against the 3.3 MB reference cap.
- Tee unarchives `6kwEVgUOsErRhvxE` in the n8n app and deletes the always allow row
  in Rakazo. A session then reads both back.
- Canvas voice transcription still calls xAI and stays down until `XAI_API_KEY` is
  set.
- Runway motion results are kept as Runway's URL, as xAI motion results were. How
  long those links live is not measured.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_canvas-on-runway_v1_2026-09-24-1220.md
DATE: 2026-09-24
DECISIONS: Tee ruled that EditForge Canvas renders stills and motion on Runway with dialogue left on ElevenLabs, that it merges on green and deploys with a dry run first and one test still, and that the archived TQO Episode Email Drafter is restored and the always allow rule for n8n archive_workflow is removed.
FINDINGS: Production had no xAI key, so Canvas could render nothing; EditForge PR 72 moved Canvas to Runway with a separate reference mode that cannot reach the presenter likeness, deployed as b8c70b610d23 and read back live. A critic passed it with conditions, two fixed and one needing a live still. Rakazo holds an always allow rule for n8n archive_workflow beside its require approval rule, most likely from the 11:18Z approval.
OPEN: Tee renders one Canvas still, unarchives 6kwEVgUOsErRhvxE and deletes the allow rule; a session reads all three back.
STATUS: Canvas on Runway is live and unproven against Runway; the allow rule is awaiting Tee.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
