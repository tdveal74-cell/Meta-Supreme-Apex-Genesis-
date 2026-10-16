---
name: tsws-repair-workflows
description: Run, extend or judge the three TSWS editable repair workflows (shot composer, shot cleanup, scene builder) and their synthetic test suite. Load when a repair job for The Shadow We Share is being planned or run, when an Episode 1 shot (SH020, SH045, SH070, SH100, SH150, SH160) comes up, when someone asks whether a repair "passed", or before touching the n8n orchestration draft. Compiled 2026-10-13 from the build and the three-cycle fresh-critic gauntlet that found twenty defects the tests had not.
---

# TSWS editable repair workflows

Three reusable methods with measured acceptance checks and a refusal path, built for Claude, the visual dot and Rakazo to run on a machine with Python, OpenCV, SciPy, FFmpeg and Blender. Everything about them is DRAFT until Tee rules otherwise.

## Where the package is

Drive: `TSWS_EDITABLE_REPAIR_WORKFLOWS_v01_DRAFT`, folder id `1SgR8-w-hzFEPuigh2LZQwN9DBARx2WqT`, under the TSWS post-production folder `1ZTZe2OWJZITVXpyxoVhafJ_EJS0fCnSm`. Read `START_HERE.md` first, then the guide for the method, then `docs/REMAINING_BLOCKERS.md`. The hash of every file is in `receipts/PACKAGE_SHA256.json`; what landed on Drive is in `receipts/DRIVE_UPLOAD_RECEIPT.json`.

## The one fact that governs every claim

The package was built and tested on synthetic fixtures only. Episode 1 media first reached a build container on 2026-10-16 (`docs/devon/SYS_OPS_tsws-ep01-repair-attempts_v1_2026-10-16-2007.md`), and every attempt to repair a flagged frame was refused: no Episode 1 shot is repaired, and the SH045 rig is not built. Do not describe any Episode 1 shot as repaired on the strength of this package.

## Running a method

```
python3 tools/verify_tools.py --out test_results/TOOL_VERIFICATION.json
python3 workflows/shot_composer/tsws_shot_composer.py run --job JOB.json --out FRESH_DIR
python3 workflows/shot_cleanup/tsws_shot_cleanup.py run --job JOB.json --out FRESH_DIR
python3 workflows/scene_builder/tsws_scene_builder.py build --spec SPEC.json --out FRESH_DIR
```

Build the job or spec from `templates/`. A value starting `UNSET_` is a blank. Relative paths resolve against the job file's own directory. Ids (`job_id`, `scene_id`) are file-name-safe only; they are interpolated into output names. Every script refuses a non-empty `--out` with exit 2, because a re-run into a used directory would mix old and new frames into the exports.

Exit codes: 0 pass, 1 a check failed, 2 bad input or used output directory, 3 source dependency, blocked by named facts, or a refusal. Exit 3 is a result. Report the named blockers exactly. Do not retry, do not substitute a still or a generated clip, do not fill an unknown fact with a guess, do not widen a limit to pass. A limit changes only on a decision from Tee, written down with the reason.

A pass is a set of measurements on frames nobody has watched. Every result file says human review REQUIRED and continuous playback UNVERIFIED. Repeat both when reporting.

Every composer check carries a status: PASS, FAIL, NOT_EXERCISED (the situation never arose in the clip, so nothing was measured; listed under `checks_not_exercised` in RESULT.json and not a failure) or NOT_DETECTED (the check could not find what the job told it to look for, the briefcase colour for one; a failure whose fix is the job input). Report the status, not only the exit code.

## What each method refuses, by design

- Composer: a source without the required performance (walk, decelerate, stop measured on planar world speed) returns SOURCE_DEPENDENCY with nothing composited; a moving camera returns BLOCKED_MOVING_CAMERA before tracking unless the job carries `camera_override` with a written reason.
- Cleanup: a region above the size limit, a retained file whose hash changed, or a retained path that is not a file, all refuse before any work. Frames repaired by spatial inpainting are named as HIDDEN-BACKGROUND RECONSTRUCTION, never called recovered footage.
- Scene builder: an unknown fact is a named blocker; nothing is invented. The SH160 template exits 3 with fifteen named dependencies, which is the correct result today.

## The boundaries, which do not bend

No paid generation, purchase or upgrade. No change to scripts, voices, episode audio or timelines. Rakazo's Visual Producer stays paused. Episodes 2 to 12 and trailer v03 stay paused. Every original and checkpoint preserved. Do not modify the live Google Media Runner, workflow `6AOsI9T0u37DRv4E`. Generation and local compositing are separate operations. No key, token or password in a job file, prompt or log.

## What the gauntlet found, and the test that now guards each one

The first draft passed its own 34 tests. A fresh critic, given only the package and the ask, found these; each was reproduced, fixed and re-measured before the package shipped.

- `cv2.phaseCorrelate` with a window multiplies both inputs in place (OpenCV 5.0.0). The camera stage passed the same reference strip every call and measured its own accumulated damage as a 0.53 px drift on a byte-identical strip. Fresh windowed copies now; the strip measures 0.0000 px.
- The camera stage wrote a moving classification and nothing read it. Guarded by `composer.negative_moving_camera_refused`.
- The performance gate measured the X slope alone, so a pedestrian walking toward the camera read as standing still. Guarded by `composer.gate_measures_planar_speed_y_walk`.
- The exposure check tested the parallax angle only and passed a floor the end photograph never contained. Guarded by `scene.occluded`.
- A scene with no required aperture failed the aperture check. Guarded by `scene.noaperture`.
- The test harness symlinked `09_checks.json` into the negative-test mirrors, so every check-only run overwrote the positive run's receipt through the link. Receipts are copied now.
- The far half of the contact-shadow check averaged the whole frame, which no realistic misplaced shadow could move. It is now the darkest pixel 70 px from every landed shell.
- A retained file whose path was wrong was skipped silently and reported unchanged. Guarded by `cleanup.retained_asset_missing_path_refuses`.
- A `job_id` could climb out of `--out` into ffmpeg's output path. Guarded by `schema.job_id_path_traversal_rejected` and a realpath check in both scripts.
- The n8n draft's human gate was an unauthenticated resume webhook with no expiry, its download node sent the bound credential to whatever URL the poll returned, and its upload ignored its own hash check. All three rewired; see `n8n/ORCHESTRATION_SPEC.md`.
- The pan estimator's first measurement (0.72 px) was an accident of the in-place bug. The honest version with a squared Hanning window and two median-based Lucas-Kanade steps measures 0.60 px against the fixture's true pan; a plain window alone measures 1.73 px.
- The cleanup guide declared the protected-pixel fix re-measured while the only log in the package was the failing run, byte-identical to its own "before" copy. The final run's log replaced it. A fix is not fixed until the same measurement is shown clean in the artifact a reader opens.
- The n8n draft's 7 day resume limit, added to close the unauthenticated gate, opened a second way through it: an n8n Wait node that hits its limit continues with its own input item, and an envelope carrying a smuggled top-level `body` with the approval answers would have been waved into paid generation with nobody touching the resume URL. Found in cycle 2. The envelope now rejects any top-level field outside the schema's eight and the approval check refuses any item without request headers or carrying the envelope's own markers. A fix that adds a path adds an attack surface; replay the new path before calling the gate closed.
- The contact-shadow far metric excluded landed shells only, while the shadow pass casts from every released shell, so a shell still falling four frames after another had landed read as a misplaced shadow (0.07 to 0.20 on the fixture, hidden because every sampled frame fell after the last landing). Every released shell's ground point is excluded now.
- The new exercised counter and the violation count selected bodies by different rules, so a shot with three depth layers could read PASS on an overlap the violation count never examined. Both use the same set now, and the note says the bounding-box test is a geometric proxy.
- `resolve_job_paths` covered `path`, `clean_plate` and the mattes and missed `protected_mask`, the one key whose job is "never write here"; the protected test passed because it used an absolute path. The key is covered and the test passes a relative one.
- A required aperture id that no element carried passed the aperture check with an empty record. It fails with a reason now, and the badaperture spec proves it.
- Blender writes the render date, the render time and Cycles' own timings into PNG text chunks on every frame, and Cycles does so whatever the stamp flags say. The scene determinism test caught it (240 of 240 frames pixel-identical, 0 byte-identical); the frames are rewritten without text chunks after each Blender stage.
- A check-only negative that crashed left the positive run's copied `09_checks.json` in its mirror, and the test read it as its own result: 12 exercised frames on shells that had been moved 500 m off-frame. The harness now deletes the mirrored receipt before a check-only run and reports a missing one. A test that can read a stale artifact proves nothing; make the artifact impossible before the run.
- The violation branch counted every shell as "nearer" including shells still worn on heads, while the falling alpha it tests never contains a worn shell, so on a three-actor job a body behind a worn shell was never examined and the check could pass on an overlap it never measured. Found in cycle 3. Released shells only, in both loops now.

Two more changes were raised, refuted on measurement, and applied anyway because the geometry is right and the cost is nil: the sun sits 50 degrees off vertical, so the shadow far metric now also excludes the sun-projected shadow point of every released shell (the Blender stage writes `sun_direction_world` into `shell_sim.json`); the refuter showed an airborne shell's shadow is too faint to trip the limit except in one coincidental frame. And the status field on a never-exercised check, below.

One change the gauntlet argued about rather than found. The critic said two composer checks returned FAIL when their situation never arose (no shell ever over a nearer body; no briefcase blob found); the refuter called that a disclosed design, since the guide and the check's own note said so. The status field went in anyway, because on a real shot with no occlusion event the first form could never pass and the agent could not tell untested from failed without reading the numbers. Guarded by `composer.negative_occlusion_not_exercised` and `composer.negative_briefcase_not_detected`. Tee can overrule it; the first form is one line.

The pattern across all of them: a check that cannot fail on the fixture is not a check. Before trusting any new check here, give it an input that should fail and watch it fail. The second pattern is in the handoff: a number in a guide is a claim until the receipt it came from is in the folder beside it.

## Episode 1, what unblocks each shot

Read the 2026-10-16 status doc first. What it measured:

- Getting media in: the container reaches `drive.usercontent.google.com`, so a link shared file downloads; a private one returns the Google sign in page, which is the check for "shared". The Drive connector cannot set link sharing (its share tool takes an email only), so Tee switches it on and off by hand. Verify every download against the sha256 in the editor's `EDITOR_SEVEN_PARENT_ACCEPTANCE_LIST_DRAFT.csv` (Drive `1NcsO_ydV3LpXA5XToUYbKNZ7GtXewWbx`, readable through the connector). The four source archives do not hold the street native masters; those are in `CLAUDE_EP01_RESCUE_v01_DRAFT`.
- The editor's list scopes the work: SH070 and SH100 fail on performance and need new footage, which is a paid generation and Tee's budget call. SH020 is parked for regeneration on Tee's ruling after two refused repair attempts.
- The cleanup method fits defects fixed to the lens or the scene. On a defect attached to a moving, turning subject (SH020's shell edge) it inpainted 92.3% of the region and refused. Do not retry it on that class of defect.
- A 2D head locked transplant was built and judged DO-NOT-SHIP: it could only touch frames that were already clean, because a head turning in depth defeats a 2D fit. The next attempt on that class of defect needs a 3D head fit or new footage.
- SH150's editor note (-25,+3 at f95) is a smooth accelerating pan from f0, not a cut; translation only stabilisation still fails the composer's 0.5 px camera stage on its own probe (0.93 to 1.51 px). Only a probe on the same region that supplied the offsets reads static, which is circular. It needs a per frame camera solve.
- Five package defects are listed in the status doc (a mislabelled plate, a frame numbering mismatch, the SH160 template's shared landmark facts and rooftop placement, no mesh path for a face shell, and `__pycache__` written without `python3 -B`).

Beyond the media: the composer needs rotoscoped mattes per actor (the workflow assembles layers from supplied mattes; it does not separate people from the plate), head start points, a static plate or a camera override with a reason, and the face-shaped shell mesh. The cleanup needs the native master, a mask on the defect frames and a mask of the passing regions to protect. SH160 needs the exit aperture and the other named facts in `templates/SH160_SCENE_SPEC_TEMPLATE_UNRESOLVED.json`. SH045 is not built because the brief's conditions (Auren's likeness, fitted mask, anchored thread, verified window-directed turn) cannot be met from synthetic geometry.

## n8n

`n8n/orchestration_DRAFT_not_imported.json` is a specification with a draft file, and the same graph exists on the instance as `TSWS 06 Repair Orchestration DRAFT (not published)`, unpublished and inactive. It speaks the TSWS render worker's own contract (`deploy/render-worker`: POST /jobs, GET /jobs/{id}, GET /files/), but the worker has no `tsws_repair` job type yet, so a run stops at the submit with a 400 until that job type is written and the box is shown to have Python, OpenCV, SciPy, FFmpeg and Blender. Publishing is Tee's ruling. Two Basic Auth credentials do not exist yet (the inbound repair-jobs credential and the budget-approval resume credential); the runner, worker and Drive credentials are bound to the ones the instance already holds, and no key is in any file. A lesson from creating it: the instance's workflow builder auto-binds any existing credential of a required type to an empty slot, and with header auth it twice bound the `anthropic` API key to the inbound webhook. Never leave an inbound auth slot of a type the instance already holds credentials for; pick a type with none, or create the dedicated credential first, and read the workflow back to check the slots.
