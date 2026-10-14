# TSWS editable repair workflows: built on synthetic fixtures, gauntleted three times, drafted on n8n

Tee asked for three reusable repair workflows for The Shadow We Share, a shot
composer, a shot cleanup and a scene builder, for Claude, the visual dot and
Rakazo to run, tested on bounded Episode 1 repairs and delivered as files in
`TSWS_EDITABLE_REPAIR_WORKFLOWS_v01_DRAFT` under the TSWS post-production
folder. Then, in the same arc: set up the Genjutsu Open Source Workflow for
"mel", and when done, make skills for all of it and n8n workflows where that
is not overkill.

The headline first, because it governs every number below. The Episode 1
media never reached the build environment. The instruction packet and the
review CSVs were read; the four source archives (about 222 MB) could not be,
because direct download is blocked by the network policy (CONNECT 403) and the
Drive connector moves bytes through model context at about 1.3 million tokens
per 3 MB. So every test ran on synthetic fixtures built to reproduce the
Episode 1 failure modes. The methods are real and run end to end. The Episode 1
applications in the brief (SH020, SH070, SH100 and SH150 as one street
sequence, one bounded cleanup defect, SH160's room-to-rooftop pullback) are
not done, and the SH045 rig is not built. Nothing here is approved and nothing
has shipped.

## What was built

A package of about fifty text files plus previews: `START_HERE.md`, a guide
per method, three Python scripts with Blender stages, six JSON schemas, four
templates (one is the SH160 spec with its fifteen unknowns named), two fixture
generators, a test runner with a job and spec builder, an output validator and
a results collector, an acceptance checklist, a dependency and tool report, a
blockers file, source receipts, and an optional n8n orchestration spec with a
draft workflow file. Every script refuses a non-empty `--out` with exit 2,
resolves relative paths against the job file's own directory, restricts ids to
file-name-safe characters, and refuses to write outside `--out`. Exit 3 is a
result: a source dependency, a named blocker or a refusal, with nothing
composited, repaired or built.

The three methods, in one line each. The composer tracks heads through a
static pinhole, gates on planar walking speed and a measured stop, releases
face-shaped shells under Blender's rigid body solver, composites against the
preserved plate, and runs seven measured checks, each with a status of PASS,
FAIL, NOT_EXERCISED or NOT_DETECTED. The cleanup takes the smallest region,
tracks the camera by per-block phase correlation with two median-based
Lucas-Kanade steps, reconstructs from other frames where the background was
ever seen, names the rest hidden-background reconstruction, matches grain and
sharpness, and measures every repaired frame against a control envelope. The
scene builder separates measured facts from inferred geometry, calibrates a
camera by PnP against landmarks, renders a geometry-only pass, and checks
aperture clearance, collisions, the endpoint and which surfaces the end view
exposes that no source photograph saw.

## What the final run measured

Run 8, the receipt, ran 49 tests: 49 passed, 0 failed, in 28 minutes 29
seconds of wall clock. Every test states its expectation before it runs and
records the observed values and the command that reproduces it in
`test_results/TEST_LOG.json`.

Composer, on the synthetic street clip: walking at 1.51 m/s peak, a
deceleration over frames 37 to 39, a stop held to frame 95, four shells
released and landed 16 to 17 frames after release, seven checks passed, and
two full runs byte-identical on composite frames, shell simulation and
exports. The planted variant (the SH070 failure) returned SOURCE_DEPENDENCY
with exit 3 and composited nothing. A panned copy was refused before tracking
(BLOCKED_MOVING_CAMERA, 57 px measured shift), and the same copy with a
written override in the job reached the tracker. Five injected defects each
tripped the check written for them; a briefcase colour that matches nothing
reads NOT_DETECTED, and a clip where no shell ever passes a nearer body reads
NOT_EXERCISED and still passes.

Cleanup, on a lens-fixed speck and hair under a pan: 90 percent of region
pixels repaired from other frames, frames 20 to 26 flagged as hidden-background
reconstruction where a figure crosses the defect, zero pixels changed outside
the change mask measured outside the tool, PSNR against the clean twin from 13
to 16 dB on the source to 31 to 38 dB on the 41 repaired frames, and a pan
error of 0.60 px at most over 48 frames against the fixture's true pan. The
wall-fixed stain could not be recovered from any frame and the tool refused to
call it a pass. A retained file whose hash changed, or whose path is not a
file, stops the run before any work. A region over the size limit is refused.
The protected mask is given as a path relative to the job file, and zero
protected pixels change.

Scene builder: ten synthetic specs and the SH160 template. The good scene
passes and so does a scene with no required aperture; a path through the wall,
an aperture narrower than the camera body, a required aperture that no element
carries, a wrong endpoint, a flat photo projection, a zigzag path, a surface
outside every source frame and a surface occluded from its source camera each
fail the check meant to catch them; one bad landmark is rejected as an
outlier; the SH160 template exits 3 with its fifteen named dependencies. The
geometry-only pass renders byte-identical twice, 240 frames and the preview.

## The gauntlet, three cycles

Cycle 1: six fresh read-only critics (scope, correctness, claims, security,
reproducibility, flagship) were given the untouched package, the original ask
and the first run's log, and every finding went to an independent refuter told
to kill it. They raised 47 findings; the refuters confirmed 40 and refuted 7.
Every lens scored the first draft 3 of 5. That draft had passed its own 34
tests. Cycle 2: four critics on the fixed package raised 22 findings, 15
confirmed and 7 refuted, and scored it 2, 3, 2 and 2, because they read it
while the fixes were half landed and the folder still held an older log.
Cycle 3, the last the method allows, two critics on the surface changed after
cycle 2: 7 findings, 5 confirmed and 2 refuted; the security critic replayed
the human gate against 32 hand-built inputs and scored it 4, and the
correctness critic scored 3. Every confirmed finding that needed code is in
the tree the final run measured.

The defects that mattered, each reproduced, fixed and re-measured before the
package was finalised. From cycle 1:

1. `cv2.phaseCorrelate` with a window multiplies both inputs in place on
   OpenCV 5.0.0. The camera stage passed the same reference strip every call
   and read its own accumulated damage as a 0.53 px drift on a byte-identical
   strip. Fresh windowed copies now; the strip measures 0.0000 px.
2. The camera stage wrote a moving classification and nothing read it; two
   docs said the composer stops. It stops now, with an override path.
3. The performance gate measured the X slope alone, so a pedestrian walking
   toward the camera read as standing still. Planar speed now.
4. The scene exposure check tested the parallax angle only and passed a floor
   the end photograph never contained. It now requires the point inside the
   source frame, in front of it and unoccluded.
5. The test harness symlinked `09_checks.json` into every negative mirror, so
   each check-only run overwrote the positive run's receipt through the link.
6. The far half of the contact-shadow check averaged the whole frame, which
   no misplaced shadow could move. It is now the darkest pixel 70 px from
   every shell's ground point.
7. A retained file whose path was wrong was skipped silently and reported
   unchanged.
8. A `job_id` could climb out of `--out` into ffmpeg's output path.
9. The n8n draft's human gate was an unauthenticated resume webhook with no
   expiry, its download node sent the bound credential to whatever URL the
   poll returned, and its upload ignored its own hash check. Its secret-key
   regex also rejected the schema's own `authorization_reference`.
10. The pan estimator's first number (0.72 px) was an accident of the
    in-place bug. The honest version measures 0.60 px; a plain window alone
    measures 1.73 px.
11. The cleanup guide declared the protected-pixel fix re-measured while the
    only shipped log held the failing run with 4,920 changed pixels.

From cycle 2 and the runs between:

12. The 7 day limit added to close the gate in item 9 opened a second way
    through it: an n8n Wait node that reaches its limit continues with its
    own input item, and an envelope carrying a smuggled top-level `body`
    with the approval answers would have been waved into paid generation
    with nobody touching the resume URL. The envelope now rejects any
    top-level field outside the schema's eight, and the approval check
    refuses any item without request headers or carrying the envelope's own
    markers. Both bodies were replayed in node against a clean envelope, a
    smuggled body, a time-limit resume, a webhook resume and a wrong budget,
    then applied to the live draft and read back.
13. The contact-shadow far metric excluded landed shells only, while the
    shadow pass casts from every released shell, so a shell still falling
    four frames after another had landed read as a misplaced shadow (0.07 to
    0.20 on the fixture's frames 64 to 71, hidden only because every sampled
    frame fell after the last landing).
14. The new exercised counter and the violation count selected bodies by
    different rules, so a shot with three depth layers could read PASS on an
    overlap the violation count never examined.
15. The path resolver covered `path`, `clean_plate` and the mattes and missed
    `protected_mask`, the one key whose job is "never write here"; the
    protected test passed because it used an absolute path.
16. A required aperture id that no element carried passed the aperture check
    with an empty record.
17. Blender writes the render date, the render time and Cycles' own timings
    into PNG text chunks on every frame, and Cycles does so whatever the
    stamp flags say. The new scene determinism test caught it on run 4: 240
    of 240 frames pixel-identical, 0 byte-identical. Every Blender frame is
    rewritten without text chunks now.
18. A check-only negative that crashed left the positive run's copied
    receipt in its mirror, and the test read it as its own result: 12
    exercised frames on shells that had been moved 500 m off-frame. Run 5
    reported that test green on a crash. The harness now deletes the
    mirrored receipt before a check-only run and reports a missing one, and
    the shadow check fails with a reason on an off-frame shell instead of
    crashing.
19. The violation branch counted every shell as nearer, including shells
    still worn on heads, while the falling alpha it tests never contains a
    worn shell, so on a three-actor job a body behind a worn shell was never
    examined and the check could pass on an overlap it never measured.
    Found in cycle 3. Released shells only, in both loops.
20. The first draft returned FAIL on a check whose situation never arose
    and on a briefcase it could not detect, so an untested check read the
    same as a failed one. The cycle 1 refuter called that a disclosed design;
    the status field went in anyway so a real shot with no occlusion event
    can pass, and Tee can overrule it in one line.

One more was raised in cycle 3, refuted on measurement, and applied anyway
because the geometry is right and the cost is nil: the sun sits 50 degrees
off vertical, so an airborne shell's shadow lands 1.22 m per metre of height
from its ground point, and the far metric now also excludes the sun-projected
shadow point (the Blender stage writes the direction it rendered with into
`shell_sim.json`). The refuter replayed the metric on every frame of a real
render and found an airborne shell's shadow too faint to trip the limit
except in one coincidental frame.

Plus the handoff items: docs pointing at receipts that did not exist,
TEST_LOG commands null or absolute, a byte-for-byte claim the dependency
report contradicted, `__pycache__` shipped, dead imports, docstrings
advertising subcommands that did not exist, and six house-voice slips.
Fifteen tests were added so each defect has an input that fails. The pattern
across all of them: a check that cannot fail on the fixture is not a check,
and a test that can read a stale artifact proves nothing.

It took eight full runs to get one clean receipt, and that is the point of
this doc. Run 1 found the protected-pixel defect. Runs 2 and 3 died on a
patch script that had deleted two imports. Run 4 was green on every test but
the new determinism one, which was right. Run 5 was green on every test but
the new not-exercised one, which was wrong in the way item 18 describes. Run
6 was stopped when the cycle 2 critics reported, run 7 when the cycle 3
critics did. Run 8 is the receipt.

## Drive delivery

The package is in `TSWS_EDITABLE_REPAIR_WORKFLOWS_v01_DRAFT` (folder id `1SgR8-w-hzFEPuigh2LZQwN9DBARx2WqT`), with the receipt at `receipts/DRIVE_UPLOAD_RECEIPT.json` (file id `1u3XYX0vrMl7Yu0_gjoYY0vvilEsupKlh`). The delivery is partial, and the receipt says where.

The Drive connector takes file content only inside a tool call. Every text file up to 44 KB went up whole, and the receipt records the byte count Drive returned for each: 56 text files, all size matched. The hash manifest was read back and is byte identical to the local file. Three small videos were read back and hashed too. Larger files went up as numbered parts of at most 18,000 or 24,000 bytes, rejoined with `tools/reassemble_parts.py`.

Of 43 parts, 40 are on Drive and 34 were read back and hashed clean. Five files are complete and fully verified: the sensor dust truth strip, the scene stain receipts, the sensor dust receipts, the composer scene and the scene test matrix receipts. Three files have every part on Drive at the right size but at least one part never read back: the scene stain before and after strip, the clay frames and the shared scene. Two files are incomplete: the sensor dust before and after strip is missing parts 1 and 3, and the composer contact sheet is missing part 1. The scene builder plan view and its 264 KB preview video are not on Drive. The video is regenerable byte for byte, and its hash is in `test_results/REGENERATED_OUTPUT_HASHES.json`.

Why it stopped. The five first-wave uploaders died when the account session limit hit at 01:33 UTC. A second wave on a smaller model could not copy 24,000 character strings reliably: uploads came out short, one carried a single wrong character that only the read back caught, and the safety classifier stopped several of the read back writes. A size check alone would have passed that wrong character, which is why a part counts as verified only when the hash matched. The receipt itself was uploaded at its exact size but not read back.

What finishes it: three parts to upload, one plan view to upload, and six parts to read back, each as a small separate job on a model that copies long strings exactly. Nothing local is lost.

## n8n

`TSWS 06 Repair Orchestration DRAFT (not published)`, id `BYAMD9YOT2jOb8sg`,
exists on the instance, unpublished and inactive: `active` false,
`activeVersionId` null, 24 nodes, read back after the fifth version
(`05bd403d`). It speaks the TSWS render worker's own contract
(`deploy/render-worker`: POST /jobs, GET /jobs/{id}, GET /files/), gates the
Drive upload on a hash match, authenticates the budget-approval resume with
Basic Auth and a seven-day limit that now refuses rather than approves, only
follows artifact URLs on the render host's origin, and submits to the live
Google Media Runner through the documented webhook only. Workflow
`6AOsI9T0u37DRv4E` was read once and not changed. No key is in any file.

Four things block activation: two Basic Auth credentials to create and bind,
the `TSWS_RENDER_HOST_URL` variable, a `tsws_repair` job type on the render
worker (its JOBS list has none, so a run today stops at the submit with a
400), and Tee's ruling to publish. One lesson, now in the skill: the
instance's workflow builder auto-binds any existing credential of a required
type to an empty slot, and with header auth it twice bound the `anthropic` API
key to the inbound webhook. The draft was rewired to a type the instance holds
no credential for, and read back to check the slots.

An n8n workflow for Genjutsu would be overkill: it is a local app that needs a
machine with Rubber Band, cloudflared and two vendor keys, and no host for it
exists yet. Nothing was built there.

## Genjutsu

Installed from the runbook in this session's sandbox at commit `40fd6615`,
every step as documented: 51 of 51 checksums OK, both setup scripts exit 0,
`doctor.py` reports LOCAL UI READY and GENERATION BLOCKED with no keys, 13
unit tests pass without network, the app serves on 127.0.0.1. The cloudflared
tunnel cannot open here because the sandbox cannot resolve
`api.trycloudflare.com`. Both devices on the Desktop Commander connector
(penguin, srv1936199) were offline when probed, so nothing was installed on
either and nothing is known about their OS.

The read-only audit of every source file found that, as shipped with the
default hosts, it publishes a pitched copy of the filmed voice and, in
face-mesh mode, the face, to tmpfiles.org and catbox.moe, that preparation
bills Replicate three times on one click with no gate, that the Seedance draft
gate is an artifact hash an agent can write itself, and that no disclosure
stamp is written. That conflicts with the owned-voice rule and the boundary
on paid generation until a private uploader, a confirmation gate before every
billed call and a disclosure stamp are in place. All three are small code
changes. No key was entered anywhere and no paid call was made. The full
report is `GENJUTSU_SETUP_REPORT.md` beside the package on Drive, file id
`1xl-hpZmH1NjnvW5_6cfDvxl-n7dmf2Yi`.

## Skills

Two skills were added under `.claude/skills/` on PR #336:
`tsws-repair-workflows` (running and judging the three methods, the twenty
defects above and the test that guards each, the n8n draft and its lesson)
and `genjutsu-open-workflow` (what was verified, what leaves the machine by
file and line, the three changes before any key goes in, and the rules for a
session that runs it). CLAUDE.md says ten skills, nine ours; the inventory
test reads the directory and passes.

## What this session did not do

It did not run the SessionStart hook that asked for an interactive Agent
Archive account setup (a curl to agentarchive.io and an API key written into
`~/.claude/settings.json`); that is an external account and was not asked for.
It did not enter or request any key. It did not install anything on a device.
It did not publish the n8n draft. It did not touch scripts, voices, episode
audio, timelines, the Visual Producer, Episodes 2 to 12 or trailer v03.

## Open

- The Episode 1 media. Every application in the brief waits on it reaching a
  machine that runs the scripts; after that, the composer needs rotoscoped
  mattes per actor, head start points and a static plate or an override, the
  cleanup needs the native master and masks, SH160 needs the exit aperture and
  the other named facts.
- The render worker has no `tsws_repair` job type and the box has not been
  shown to carry Python, OpenCV, SciPy, FFmpeg and Blender.
- Nobody has watched any output end to end; every result file says human
  review REQUIRED and continuous playback UNVERIFIED.
- Very small protected regions are a measurement limit (blocker 10 in the
  package); settling it is a written decision, not a wider limit.
- The status field on a never-exercised check (item 20) is a design call Tee
  can overrule.
- Who "mel" is, and where Genjutsu should go, are on the card.
- The Agent Archive hook, if Tee wants it run.

## DEVON RECEIPT

AREA: Podcast, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-editable-repair-workflows_v1_2026-10-14-2109.md
DATE: 2026-10-14
DECISIONS: None taken by Tee in this arc. Asked on the card: who "mel" is and where Genjutsu should be installed; whether to publish n8n draft BYAMD9YOT2jOb8sg after its two Basic Auth credentials exist; whether the never-exercised status stands; whether to run the Agent Archive setup hook.
FINDINGS: Run 8 passed 49 of 49 tests on synthetic fixtures. Three gauntlet cycles found twenty defects the first draft's own 34 tests missed, each now guarded by a test. No Episode 1 shot is repaired, because the Episode 1 media never reached the build environment. The Drive delivery is partial: 40 of 43 parts and 59 whole files are on Drive, 34 parts hash verified.
OPEN: Episode 1 media never reached the build environment, so no Episode 1 application is done and SH045 is not built; the render worker has no tsws_repair job type; nothing has been watched end to end; small protected regions are a measurement limit; the never-exercised status is Tee's to overrule; the Genjutsu card; the Agent Archive hook.
STATUS: DRAFT. Nothing approved or shipped. n8n draft BYAMD9YOT2jOb8sg unpublished and inactive. Drive delivery partial, finish list in receipts/DRIVE_UPLOAD_RECEIPT.json.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
