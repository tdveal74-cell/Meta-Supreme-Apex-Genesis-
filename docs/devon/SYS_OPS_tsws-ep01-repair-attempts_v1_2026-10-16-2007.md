# TSWS Episode 1: first repair runs on real footage

Status record for 2026-10-16. It follows
`SYS_OPS_tsws-editable-repair-workflows_v1_2026-10-14-2109.md`, whose governing
fact was that no Episode 1 media had reached a machine that could run the repair
methods. That changed today. This doc records what came in, what each method did
with it, and what is still Tee's to decide. No Episode 1 shot is repaired.

## How the media got here

The build container can now reach Google Drive. `drive.usercontent.google.com`
answers (it returned 403 at the tunnel when the package was built), so a file
that is link shared downloads without signing in. The Drive connector cannot set
link sharing itself: its share tool takes a named email and nothing else, so Tee
switched sharing on and off by hand in the Drive app each time.

| file | Drive id | bytes | sha256 |
|---|---|---|---|
| `TSWS_S01E01_SOURCE_PART_01_v09_DRAFT.zip` | `1yGAzmKMSnaGFKUQgYeiDGlDysk0Cc6o2` | 82,867,337 | `1a5c287a6f4d9412...` |
| `TSWS_S01E01_SOURCE_PART_02_v09_DRAFT.zip` | `1ebSUjPCS9Rwh-OqjxEjBzM8uSugsdVWM` | 74,752,679 | `95f3b28a04c51df6...` |
| `TSWS_S01E01_SOURCE_PART_01_v10_DRAFT.zip` | `1tvdV2Ey_ikYgq03X4GE99NCola4z7Esp` | 54,203,602 | `c3b0fbbe255608ab...` |
| `TSWS_S01E01_REVIEW_v10_DRAFT.zip` | `11-GoUOPgVhG-pgrdSEDKlCiQnGwjsJCS` | 10,616,544 | `00f585dcec788830...` |
| `TSWS_S01E01_SH020_veo31_v3_NATIVE_MASTER_noaudio_DRAFT.mp4` | `1BdJJ9-KJyJH5ag16-7FsrBQBJ-XAApdA` | 12,090,781 | `8dffa0fba7a7af09...` |
| `TSWS_S01E01_SH150_veo31_v5_NATIVE_MASTER_noaudio_DRAFT.mp4` | `110Sdlhy15VH6bgqHvyrblhLwa7J42RP7` | 18,935,983 | `f02fc88616a89908...` |

Every size matched Drive to the byte and every zip passed `unzip -t`. The two
masters match the sha256 the editor recorded in
`EDITOR_SEVEN_PARENT_ACCEPTANCE_LIST_DRAFT.csv` (Drive
`1NcsO_ydV3LpXA5XToUYbKNZ7GtXewWbx`, read through the connector without any
sharing). Both are H.264, 1920x1080, 24 fps, 192 frames.

The four archives went back to private and were proven private by a download
that returned the Google sign in page instead of the zip. The two masters were
still link shared at the last check before this doc was written; see Open.

The archives do not hold the street native masters. Those sit in
`CLAUDE_EP01_RESCUE_v01_DRAFT` (`16rww8fYULj9OpgrhkrkYUmI7Q-Azkkfq`), which is
why the two masters were fetched separately.

## The editor's verdict per shot

From the acceptance list above. It sets the scope for everything below.

| shot | decision | defect named |
|---|---|---|
| SH020 | REVISE_NOT_SELECTED | costume like foreground masks f0/72/84; unmasked beige coat face f120/144/168; hair and shell discontinuity f168/185 |
| SH045 | HOLD_NOT_SELECTED | preview f0 to 120 reads toward Vespera, not the rear window |
| SH070 | FAIL_ACTION_NOT_SELECTED | the scarf woman is planted at f0/24/72/108/144/191; no last step into a stop |
| SH100 | FAIL_ACTION_NOT_SELECTED | whole heads disappear at f80/96, partial regrowth at f120 |
| SH135 | RETAIN_V10_STILL_ONLY | keep the v10 still |
| SH150 | REVISE_NOT_SELECTED | skyline shifts -25,+3 px at f95; head orientation and identity vary at f0/32/56 |
| SH160 | FAIL_COMPLETE_SHOT_NOT_SELECTED | unsupported front glazing f64 to 96; building morphs f122 to 140; ends at the window, not the rooftop |

SH070 and SH100 fail on performance, which no repair method can add. Both need
new footage, and new footage is a paid generation that waits on Tee's budget.

## SH020: two repair attempts, both refused

**The package's cleanup method.** Run on f164 to f189 with tracked per frame
band masks along the shell edge. Exit 1,
`HIDDEN_BACKGROUND_RECONSTRUCTION_DOMINANT_NOT_A_PASS`. 62,572 of 67,811 region
pixels (92.3%) were inpainted, because the camera is static (pan at most
0.103 px) while she walks toward camera and turns, so no neighbour frame shows
her own hairline at the same pixel. The temporal model was rejected on all 26
frames (ring error 12.8 to 36.3 against a limit of 9.0). The output is worse
than the source: hair smeared into the shell, a dark blotch on the cheek at
f168, and blue grey background pulled onto the forehead. A fresh verifier
reproduced the run byte for byte. The method fits defects fixed to the lens or
the scene, not defects attached to a moving subject.

**A head locked tool, built today on Tee's ruling.** It tracks her head, warps
the shell edge band from one clean reference frame (f172) onto each frame, and
refuses any frame it cannot fit. It went through a build, a fresh critic, a fix
round and a second critic. Version 2 processed only f170, f171, f173 and f174,
where the edge was already nearly clean, and refused both flagged frames:

- f168: the paste would move the edge 3.024 px against a 3.0 limit, and with
  the limit raised to 3.1 it was still reverted for a jump against the untouched
  f167. The source already jumps 2.166 px from f167 to f168.
- f185: 26 tracking inliers against a limit of 30, error near the band
  1.456 px.

The tool's own verdict is `AUTOMATED_CHECKS_FAIL`. The second critic returned
DO-NOT-SHIP, and found one defect left open: an object 2 to 4 px wide crossing
the hairline is partly painted out while the synthetic suite reports a pass, so
a pass from this tool is not a safe signal. The reading behind both refusals is
that her head turns in depth, which a 2D fit cannot follow; that is inferred
from the gates, not proven.

Tee ruled SH020 parked for software repair and moved to the regeneration list
with SH070 and SH100. The head locked tool lives only in the session container
at `/tmp/claude-0/headlock` and was not preserved; this doc carries its result.

## SH150: the camera move measured

The editor's -25,+3 at f95 is confirmed as a displacement from f0 (skyline phase
correlation -24.43,+3.16; NCC -24.72,+3.26), not a jump between frames: f94 to
f95 moves -0.38,-0.06 px. The camera pans smoothly and speeds up, reaching
-90.4 px by f191, with dy rising to +4.4 near f52 and falling to -2.9. No hard
cut was found: the largest frame to frame skyline step is 1.12 px, and the
largest full frame difference ratio is 1.14 against its neighbours.

The composer's camera stage classifies it moving at 89.22 px against a 0.5 px
limit. Translation only stabilisation brings it to 0.93 to 1.50 px depending on
which region supplies the offsets, still moving. A near storefront drifts about
+30 px in dy by f95 while the skyline moves +3, so the motion is depth dependent
or a generative warp (inferred). An honest pass needs a per frame camera solve,
which v01 does not automate. A verifier reproduced every number and narrowed one
claim: the stabilisation result depends on the offset source.

## Defects found in the repair package

Found by today's mapping pass; none is fixed yet.

- `docs/WORKFLOW_1_SHOT_COMPOSER.md` calls `PLATE_masked_master.png` a street
  plate. It is the interior room couple.
- The composer guide's decode command, `ffmpeg -i source.mp4 -vsync 0
  frames/%04d.png`, numbers frames from 0001 while the job template sets
  `first_frame` 0. Decode with `-start_number 0`.
- `templates/SH160_SCENE_SPEC_TEMPLATE_UNRESOLVED.json` points every room
  landmark at the same whole list facts, so filling them as declared crashes
  calibration (reproduced by the mapper, not by the critic). The template also
  places the rooftop on the far side of the room from the camera path and gives
  the roof box zero thickness.
- The composer has no way to use a face shaped shell: the schema's `shell`
  object has no mesh field and `blender_shell_release.py` line 118 adds a UV
  sphere.
- Running the scene builder without `python3 -B` writes `__pycache__` into the
  package. Two such folders appeared today and were removed.

## Open

- Switch SH020 and SH150 back to Restricted on Drive. Both were still link
  shared at the last check.
- SH020, SH070 and SH100 need new footage. A paid generation, waiting on Tee's
  budget.
- SH150 needs a per frame camera solve before the composer can run on it.
- SH160 waits on Tee's rulings on the fifteen named facts, starting with the
  exit aperture and whether the front glazing is canon.
- SH045 waits on rulings on the turn direction and the identity references, and
  on a head model that does not exist.
- The package defects above.

## DEVON RECEIPT

AREA: TSWS
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tsws-ep01-repair-attempts_v1_2026-10-16-2007.md
DATE: 2026-10-16
DECISIONS: Tee link shared and then revoked the four Episode 1 archives; link shared the SH020 and SH150 masters over a recommendation of SH020 only; ruled the head locked tool be built; ruled SH020 parked for software repair and moved to the regeneration list.
FINDINGS: All six files match Drive sizes, and the two masters match the editor's sha256. The cleanup method refused SH020 with 92.3% of region pixels inpainted. The head locked tool processed 4 of 26 frames, refused f168 and f185, and was judged DO-NOT-SHIP by a second critic. SH150's -25,+3 at f95 is a smooth accelerating pan, not a cut, and translation stabilisation does not pass the composer's camera stage. Five package defects found.
OPEN: SH020 and SH150 masters still link shared at last check; SH020, SH070 and SH100 need paid regeneration; SH150 needs a camera solve; SH160 and SH045 wait on rulings; package defects unfixed.
STATUS: DRAFT. Nothing repaired, nothing generated, nothing billed. human_review REQUIRED, continuous_playback UNVERIFIED.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
