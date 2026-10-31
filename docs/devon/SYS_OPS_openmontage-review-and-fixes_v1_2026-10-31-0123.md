# OpenMontage: install, review and fixes

Status doc for the arc that installed calesthio/OpenMontage, reviewed it, and hardened it. Written 2026-10-31.

## The asks, in order

1. 2026-10-30, Tee: "Install this repo" with an X post linking calesthio/OpenMontage, "no reviews".
2. 2026-10-31, Tee: "Run a review".
3. 2026-10-31, Tee: "Fix per your recommendations and merge/deploy", then "Continue".

## What shipped before the review

| PR | change | merged as |
|---|---|---|
| #442 | `pyasn1` 0.6.4 to 0.6.5 for CVE-2026-119194, -119195, -119196 and -119197, which turned the dependency audit red on every branch on 2026-10-30. The pin and its two hashes moved with `pip-compile --upgrade-package`; `pyasn1` is transitive through `webauthn`, so `requirements.in` carries no line for it and this doc is where the reason lives. | `3d70844` |
| #441 | the `openmontage` skill, its pinned installer, and the skill count in `CLAUDE.md` | `4f3b258` |

Both merged under the standing approval of 2026-10-11 with every CI job green on the head. No deploy read back was recorded at the time; it was done during this arc and is below.

## Deploy read back of #441 and #442, 2026-10-31

| surface | state |
|---|---|
| Railway `api` | deployment `67e4e2ed` on `3d70844` built `pyasn1-0.6.5` at 00:02:40Z; deployment `9dc9b658` on `4f3b258` SUCCESS, reusing that pip layer from cache. `/api/v1/health` 200 healthy at 01:03:45Z |
| Railway `presence` | deployment `54d6ddac` on `3d70844` SUCCESS, build log shows `pyasn1-0.6.5` installed at 23:49:55Z; `4f3b258` SKIPPED by its watch patterns, correctly. `/health` 200 at 01:03:46Z: `speech` cartesia, `livekit_configured` true, `audio_over_websocket` false, breaker closed with no breaches |
| Railway `scheduler-cron` | deployment `d238371e` on `4f3b258` SUCCESS |
| Vercel `meta-supreme-apex-genesis-web` | production CANCELED (ignored) on `3d70844` and `4f3b258`; last READY production `7deda01`. `git diff 7deda01 4f3b258` over its four watched paths is empty, so nothing is owed |
| Vercel `devon-soul` | the same: ignored on both, last READY production `7deda01`, nothing under `deploy/soul` changed |

## The review

Four fresh read-only critics, one slice each, attacked the deliverable on the gauntlet's twelve vectors with an intake bundle of the ask, the diff, the commit messages and the PR texts, and nothing of the builder's reasoning. A separate agent reproduced the measured claims. Each finding was to go to an independent verifier.

The critics raised 56 findings, none HIGH. Two were verified before the subagent quota ran out ("You've hit your weekly limit, resets Nov 3, 5am (UTC)", every one of the twelve batched verifiers): the installer passing a caller's active virtualenv or conda env into upstream's `make setup` (CONFIRMED, MED), and the install running unpinned third-party code beside the proxy's credentials with no guard stated (CONFIRMED, MED). The other 54 are unverified by an independent agent. Each one acted on below was checked in this arc against the cited source line or by a test that fails on the old code, which is the fixing session checking its own fixes and not the independent verification the house rule asks for.

The reproducer re-ran every measured claim on `4f3b258` and all matched except the install time: a fresh install took 75 s with warm caches against the 111 s recorded, with the same 151 tools in 26 groups and 41 usable. Re-run 9 s, four refusals each exit 2 with the expected message, the demo file 1920x1080 h264 at 30 fps, 23.06 s, silent at -91 dB with no black segment, 100 skill tests passed, the count test failed 18 against 19 on the old `CLAUDE.md`, ruff clean, pip-audit clean on both requirement files, the passkey tests 16 passed on `pyasn1` 0.6.5.

## What this arc changed

The installer, `.claude/skills/openmontage/scripts/install.sh`:

- clears `VIRTUAL_ENV`, `CONDA_PREFIX` and `VENV_DIR` for `make setup` and passes `VENV_DIR=.venv`
- pins upstream's Python packages through `PIP_CONSTRAINT` to a new `constraints.txt`, 52 exact versions taken from the working install; a real fresh install resolved exactly those versions, with no difference in `pip freeze`
- checks git, make, python3, npm, npx and uv or python3.11 before fetching, and warns on a missing ffmpeg or a Node older than 22
- resolves paths with python3, so GNU `realpath -m` is no longer needed, and warns when it cannot find its own repository
- refuses a checkout git cannot read, a checkout whose origin is not OpenMontage (read raw, so an `insteadOf` rewrite cannot refuse its own checkout), and a checkout at the pin with local changes to tracked files
- caps `make setup` at `OPENMONTAGE_SETUP_TIMEOUT` (900 s), logs it to `openmontage-setup.log`, and exits 3 when it refuses, 4 when upstream skipped an optional step, and the failing tool's own code otherwise

The first fixed version called every install DEGRADED, because `make` echoes the recipe line carrying `[skip]` before running it. A real fresh install showed it; the check now matches only a line that starts with `[skip]`, a test pins it, and that test fails against the earlier pattern.

`test_openmontage_installer.py` is new: 18 offline cases with stub `make`, `npm`, `npx`, `node`, `uv` and `ffmpeg`, using a local fixture repository through a copy of the script whose PIN and REPO lines are replaced. 12 of the first 15 fail against the installer on `4f3b258`; the 3 that pass there are the resume, the raw origin read and the pinned commit named in the skill. All 18 pass on Python 3.13 and on 3.11. It is in the standalone job in `ci.yml` and in `CLAUDE.md`'s copy of that list.

The skill, `.claude/skills/openmontage/SKILL.md`, corrected and extended:

- the description no longer states an install that a new container does not have
- licences: AGPL for upstream, plus the Remotion licence read on 2026-10-31 at remotion.dev/docs/license/pricing, free with unlimited commercial use for individuals and companies of up to 3 people, terms apply, otherwise a paid Company License
- the X post's "700+" figure set against the README's own unit, which the checkout meets
- the install section: the Bash timeout, prerequisites, exit codes, the time limit, the constraints, and what the install runs and can reach, the four credentialed proxy hosts named
- voice: speech from video generators counts; `voice_id` and not `voice`, because the selector maps one to the other only for two other tools; the value from `TEE_CLONE` in `services/devon/show_registry.py`; read `data.voice_id` back after every call; no clone at any vendor without a ruling
- likeness: `kling_avatar`, `kling_lip_sync`, the `faceswap` Layer 3 skill and reference images added; his wife's voice consent does not extend to her face
- spend: what warn mode really does (it raises above $0.50 and on a tool's first paid use; only the total is a warning), that nothing outside tests constructs a `CostTracker`, eighteen tools that need a quote, approval on a card, and a session ceiling
- upstream gates: `human_approved` is a caller-set argument and an `approval_policy` entry pre-authorizes a run, so neither may be set without Tee's card answer
- publishing: the false line about the OS 28 gate is gone; nothing goes to a poster, a schedule or a consumed Drive folder until Tee has watched it and said so on a card; a 30 minute render limit and a three failure stop
- disclosure, rights and provenance: a provenance list with every render
- code execution: scene code only from Tee's brief, never from third-party text
- the outbound map widened to the sixteen tools that send local media and marked as partial, the missing optional packages named, the unattended session rule, and Remotion's Chrome located inside the checkout
- the citation that misplaced `math_animate`'s sandbox sentence, and the claim that every fact carried a file and line, both corrected

`CLAUDE.md`: the skill paragraph's sentence in a construction Tee's prose rules ban is rewritten, and the new test is named.

## Findings not fixed, and why

- No scheduled dependency audit exists, so a new advisory waits for an unrelated pull request. It predates this arc and adding a workflow changes the CI count; offered to Tee.
- No test reaches the `pyasn1` decode path that `webauthn` uses for android-key attestation. The bump is a patch release with the constraints satisfied; recorded as residual risk.
- The presence image is not built in CI. The read back above shows it built `pyasn1-0.6.5` and serves.
- `npx --yes hyperframes` still fetches the latest release at every registry load, inside upstream's code. Pinning it means editing upstream; disclosed in the skill, and the trust question is offered to Tee.
- Process findings (no critic before the first merges, the second branch for #442, scope): this review is the answer to the first, the fix PR uses the designated branch, and the scope choices are disclosed in the PR texts.

## Gauntlet verdict

```
VERDICT: not yet a verdict; findings routed, re-audit pending (cycle 1 of 3)
Deliverable: openmontage skill, installer, CLAUDE.md change, pyasn1 bump | Type: Lens A, D, E | Ask: install calesthio/OpenMontage
Critic mode: subagent for the review; the re-audit of the fixes is simulated (the subagent quota ran out)
Scores at 4f3b258: correctness 2, scope 3, verification 3, security 3, reversibility 4, failure handling 2, idempotency 3, traceability 2, observability 2, completeness 3, maintainability 3 | mean 2.7 | flagship floor: MISSED
Scores after the fixes (simulated): correctness 4, scope 3, verification 4, security 4, reversibility 4, failure handling 4, idempotency 4, traceability 4, observability 4, completeness 4, maintainability 4 | mean 3.9 | flagship floor: MISSED
Blocking after the fixes: security is 4, because install-time and preflight code can still reach the proxy's credentialed hosts; independent verification of 54 findings is outstanding.
Recommendation: fix-then-ship. The human owns SHIP.
```

## Open

- Tee's ruling: whether his operation qualifies for Remotion's free licence.
- Tee's ruling: the install trust model, accept the disclosed exposure to the proxy's credentials or install only where the proxy carries none.
- Tee's ruling: whether to add a scheduled dependency audit.
- The 54 unverified findings, and a fresh critic on the fixes, after the quota resets at 2026-11-03T05:00Z.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_openmontage-review-and-fixes_v1_2026-10-31-0123.md
DATE: 2026-10-31
DECISIONS: Tee asked for OpenMontage installed with no reviews (2026-10-30), then asked for a review, then for the fixes to be made, merged and deployed (2026-10-31). It is installed by a pinned installer outside this repository, not vendored.
FINDINGS: The gauntlet raised 56 findings, none HIGH; two were independently confirmed at MED (the installer leaking into a caller's virtualenv, and install code running beside the proxy's credentials) before the subagent quota ran out. The skill misdescribed warn mode, upstream's gates, the OS 28 gate and the voice paths, and its rules missed video generators, Kling and faceswap. A real install exposed a false DEGRADED in the first fixed installer. Production serves pyasn1 0.6.5 on api and presence.
OPEN: Remotion licence eligibility, the install trust model and a scheduled dependency audit are rulings for Tee; 54 findings and the fixes await independent verification after 2026-11-03T05:00Z.
STATUS: #441 and #442 merged and read back live; the fix PR from this arc carries the installer hardening, the constraints, the new test and the corrected skill.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
