# Face-on Shorts, and Voice Lab on the right clone

2026-10-31. Follows `SYS_OPS_mpt-shorts-tailored_v1_2026-10-31-0044.md`, whose
receipt left any n8n wiring of MoneyPrinterTurbo as follow-on work. That wiring
was mapped and then not built, because Tee ruled that every Short carries his
face. This doc records what was mapped, the rulings, the one live change made
(Voice Lab), the reference Short as measured, and the worker code that the
Shorts need first.

## The wiring that was mapped and dropped

Tee asked to wire the wrapper to n8n. Three readers mapped it, and two
independent verifiers re-checked every claim that something was missing or
wrong. Every claim survived: none refuted.

- The TSWS render worker runs on srv1936193, the n8n host, reached at
  `http://172.16.2.1:8080` by `TSWS 00 Render Job` (CX07qa6O1hTSXlpj).
  MoneyPrinterTurbo is installed on srv1936199. No private link joins the two
  boxes and n8n holds no SSH credential (53 credentials, none of type ssh).
- No Short rows exist in `tqo_content` (60 rows) or `nco_content` (36 rows),
  and no node in TQO FINAL V5 (qEkGOUsNyVaRAmm6) moves a Short past Idea. V5's
  Pexels search asks for landscape clips and its Build Movie renders 1920x1080.

Asked on a card which shows could use voice-only Shorts, Tee answered: "My face
needs to be on them and my shorts needs to be like
https://youtube.com/@vaibhavsisinty". MoneyPrinterTurbo cuts, shuffles and
mutes its clips and has no lip sync stage, so it cannot carry a face. Its role
in the Shorts ended there, and its runner was not built. The install on
srv1936199 is untouched and idle.

## Voice Lab moved to his professional clone

The live map found `TQO Voice Lab` (jKrUIEQSUcGzr4tK, active) sending its
re-read lines to ElevenLabs voice `ypnKDQtIhp4N3yn4UnqO`, while the live V5's
comment in `Show Context: Render` (read 2026-10-31 by a verifier; the repository's
V5 exports are from 2026-10-28 and predate it) called that voice "an ElevenLabs voice GENERATED from a written description, so
not his voice". Tee ruled on a card to move it. The `Clone Voice` node now posts
to `LLhnFOCTr3y3wrH59DtJ` with V5's settings, and its sticky note records the
move. Published at 2026-10-31T22:26Z.

Read back independently: `versionId` and `activeVersionId` both
`9575d206-5da4-4b19-bb47-49becc522c17`, `activeVersion.sameAsDraft` true, all
36 nodes read in the draft and the live version, the old id in no executable
node. Voice Lab has never run (0 executions with every execution saved), its
`_Voice Lab` folder is empty and no `voicelab-` file exists in the Drive, so no
line was ever read in the wrong voice.

Then measured at the source, because the repository says the opposite:
ElevenLabs lists `LLhnFOCTr3y3wrH59DtJ` "T Veal" as category `professional`
and `ypnKDQtIhp4N3yn4UnqO` "T Veal 2.1" as category `generated`, with a written
persona as its description. A third, `NSXFHN6nIewAIPGaUMq7` "T Veal", is
category `cloned`. `services/devon/show_registry.py:96` (and its deployed
copy) still sets `TEE_CLONE` to the generated voice and calls it his
Professional Voice Clone; another session's draft PR #460 corrects it, so this
arc left it alone. The previous Voice Lab version, bc3ad4ef, stays in the
workflow's history for a rollback.

## The reference Short

Tee sent a Vaibhav Sisinty Short as a screenshot and then a screen recording.
It is `youtube.com/shorts/zopfY5ONIjA`. Gemini read the whole Short from
YouTube; the first 50 seconds were checked at one frame every 2 seconds against
the recording, which Tee link-shared for the download and set back to Restricted,
confirmed from the session by the link redirecting to a Google sign-in. Of the
14 shots Gemini placed in that span, the 13 that landed on a sampled frame
matched; the 1 second "#02 PAGES" card fell between samples. One correction (chest up, not waist
up) and one withdrawn claim (relabelled product screens) are recorded in the
canon doc, `TQO_CANON_face-on-shorts-format_v1_2026-10-31.md`, with the full
format and the evidence file.

## The rulings that set the build

On one card: the face comes from his HeyGen avatar on native Short scripts
(the recommendation was clipping long-form masters, which spends no credits;
the objection is in the canon doc once), the frame splits 50/50 now, and a
Short ends on one comment keyword with a real deliverable within 24 hours,
which wins over the TQO skill's old no-ask line.

## What changed in the repository

- `deploy/render-worker/jobs.js`: `presenter_composite` takes `split` (0.3 to
  0.75, stacked only); without it the graph is the 1250 one, byte for byte.
  The default caption margin follows the seam by a formula that reproduces the
  measured 92 at 1250 and gives 136 at 0.5. A new job, `caption_srt`, turns a
  `word_timings` file into seam captions of at most five words.
- Tests: jobs.test.js 136 passed (115 on main, 21 new), acx_node 35, server 47
  and tsws-repair 22 with the job count moved from 24 to 25, and the negative
  control failing 131 against the unfixed engine; each run alone with its own
  exit code 0. The argv without `split` is pinned against the one captured
  from b9422ef, byte for byte.
- A real render with the builder's own ffmpeg arguments put the caption on the
  960 seam at 0.5 and on the 1250 seam without `split`.
- A fresh critic on the first commit (5449b3b) found nothing critical or high
  and reproduced one real defect: a `split` whose seam fell on an odd row
  passed submit and stopped ffmpeg at render (exit 234) on a square or
  portrait zone clip, at 0.333 and 0.56. Reproduced here, fixed by rounding
  the seam to an even row, and re-rendered clean at 0.333, 0.56, 0.66 and 0.5
  with 1080x1080 and 720x1280 clips. It also found word times coerced from
  null or text, out of order words making a 1 ms cue, a newline gluing two
  words, a job count that read both 24 and 25 in DEPLOY.md, the "2 to 5 words"
  claim (a cue holds at most five, and a lone last word can stand alone), and
  three overstatements in the canon (the frame check was one frame every 2
  seconds, not frame by frame; 13 of 14 shots were sampled, not all). Each is
  fixed or corrected. Each code fix has a test that fails when the fix is
  reverted, run on a copy. Left as found: `safePath` follows a dangling
  symlink out of the work root, which every output in the worker shares and
  this change does not touch.
- DEPLOY.md documents both and the count. The skills `tqo-viral-output`,
  `nco-forge-viral-output` and `mpt-shorts` carry the rulings; CLAUDE.md names
  the ruling beside the mpt-shorts entry.

## What is still open

Each of these is its own piece of work, and the gated ones go to Tee on cards:

- Upgrading the live worker to carry `split` and `caption_srt`, by the
  "Upgrading the live box" procedure.
- The n8n Shorts lane: script, his clone voice, the HeyGen avatar, word
  timings, `caption_srt`, `presenter_composite`, then Drive. HeyGen's balance
  is read before each render.
- The worker has no on-screen text (numbered cards, hook headline), no punch-in
  zoom and no sound effects; a 16:9 proof clip letterboxes in the 1080x960 top
  half where the reference fills it.
- Each Short's comment deliverable, and how the pinned comment link is posted.
- A consent record for the voice clone; the likeness consent is signed.
- No portrait Short has rendered end to end. Tee watches the first one through
  before anything publishes.

## DEVON RECEIPT

AREA: TQO, NCO, Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_face-on-shorts-and-the-voice-lab-clone_v1_2026-10-31-2306.md
DATE: 2026-10-31
DECISIONS: Tee ruled on cards that every Short carries his face and looks like Vaibhav Sisinty's, which takes MoneyPrinterTurbo out of the Shorts and stops its n8n wiring; that TQO Voice Lab moves to his professional clone; that the face comes from his HeyGen avatar on native Shorts; that the Shorts frame splits 50/50 now; and that a Short ends on one comment keyword with a real deliverable, over the TQO skill's no-ask line. He link-shared his screen recording for one download and set it back to Restricted.
FINDINGS: The render worker is on srv1936193 and MoneyPrinterTurbo on srv1936199, with no private link or SSH credential between n8n and the second box. Voice Lab read lines in a generated voice, never used; fixed and read back. ElevenLabs confirms LLhnFOCTr3y3wrH59DtJ as his professional clone and ypnKDQtIhp4N3yn4UnqO as generated, against show_registry.py. The reference Short's format was read by Gemini and its first 50 seconds checked at one frame every 2 seconds; one Gemini claim was withdrawn. The worker gained a 50/50 split and a seam caption job, tested and rendered. A fresh critic reproduced an odd-seam render failure at splits other than 0.5 and several smaller defects and overstatements; all fixed or corrected, each code fix pinned by a test that fails without it.
OPEN: live worker upgrade; the n8n Shorts lane with HeyGen balance checks; on-screen cards, zooms, sound effects and zone fill; comment deliverables; the voice clone consent record; PR #460 for show_registry; the first portrait Short and Tee's watch of it; whether to remove the idle MoneyPrinterTurbo install.
STATUS: Repository work in review on branch claude/mpt-shorts-tailored; the Voice Lab change is live and verified; nothing has published.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
