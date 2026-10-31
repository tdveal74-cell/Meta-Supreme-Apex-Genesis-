# OpenMontage: the 54 review findings verified, and three passes of fixes

Status doc for the independent verification of the 54 findings that the 2026-10-31 gauntlet review left unverified, and for the three passes of fixes that followed, each read by fresh critics and checked by independent verifiers. Written 2026-10-31. It closes the item both `SYS_OPS_openmontage-review-and-fixes_v1_2026-10-31-0123.md` and `SYS_OPS_openmontage-rulings-and-daily-audit_v1_2026-10-31-0438.md` carried as open. The 0123 doc had put the verification off to 2026-11-03 because the subagent limit stopped it; the limit was not in force on the morning of 2026-10-31, so it ran then and the trigger for 2026-11-03 was deleted.

## How they were verified

Workflow `wf_8f733393-de5`, from 05:37Z, with six verifiers re-run in `wf_eb99a2e2-c6e` after they failed on their output format. Each finding went to one verifier in its own worktree, and each MED to a second with a different lens. A verifier was handed the finding's own entry and the diff it reviewed, never the finder's reasoning, and asked two things: was the finding real at the reviewed commit `4f3b258`, and is it resolved on `main` at `d30b405`. Every verdict counted carried `d30b405` as its checked out head. 68 verifier runs in all, none on a wrong base.

| at `4f3b258` | count |
|---|---|
| confirmed | 49 |
| unsettled | 5 |
| refuted | 0 |

| at `d30b405` | count |
|---|---|
| resolved | 39 |
| partly resolved | 10 |
| split between two verifiers, resolved and partly | 1 |
| not resolved | 1 |
| not applicable, a one-off process step with nothing to change | 3 |

Severity moved down. Of the 14 findings raised as MED, both verifiers graded 13 of them LOW. The fourteenth, `rules-and-house-proxy-credentials-code-exec`, got LOW from one verifier and MED from the other, and both found it resolved by the disclosure and Tee's ruling. No verifier graded any finding HIGH.

The five unsettled ones are all graded NIT. Two (`installer-style-rather-than`, `rules-and-house-phrasing`) turn on whether Tee's prose rules ban "Y rather than X"; the verifiers could not find that rule in the repository. It is in his standing preferences for every session, so both were real, and both lines are already reworded. The other three are judgement calls the repository cannot settle: whether the scanners broke "no reviews", whether the pyasn1 bump was an unrequested change, and whether the install timings were sourced.

## What was still open, and what this arc did

| finding | residue at `d30b405` | now |
|---|---|---|
| `installer-no-prereq-check` | the Python refusal gave no way out; SKILL.md omitted ffmpeg and Node 22 | the refusal names `OPENMONTAGE_PYTHON`; SKILL.md lists both warnings; a test |
| `installer-observability-exit-codes` | no versions printed; the fetch had no time limit | the installer prints the node, uv and ffmpeg versions it found and fetches under the same limit as `make setup`; two tests |
| `upstream-claims-egress-and-footprint-incomplete` | `graphics/google_imagen.py`, which sends local reference images to Gemini (`:293-297`), was missing | added to the list |
| `upstream-claims-ambient-credentials-unaddressed` | whether the proxy hands its credentials to any process was unmeasured | measured, below |
| `rules-and-house-no-verifier-on-rule-claims` | SKILL.md said every finding had gone to a verifier; two had | the sentence gives the real history; this doc |
| `upstream-claims-timings-and-media-numbers-unsourced`, `rules-and-house-untraced-timings` | the 111 s install had no time record | SKILL.md says so; nothing more can be recovered |
| rule 3's count, found as an aside by two verifiers | "Eighteen tool files raise `PriceQuoteRequired`" | sixteen files raise it, three of them shared helpers; the other two of the eighteen are the class and the catcher |
| `installer` comment, found as an aside | "uv fetches it when the machine lacks it" was never exercised | the comment says so |
| `dependency-presence-image-unbuilt-in-ci` | CI builds the API image only, so a requirements change reaches the presence image untested | a ruling for Tee, on a card |
| `dependency-tests-dont-reach-pyasn1` | the 16 tests prove webauthn imports on pyasn1 0.6.5, and none reaches the android-key decode | a ruling for Tee, on a card; the record is corrected below |
| `dependency-advisory-claims-unsourced` | no OSV or GHSA link for the four ids | left as NIT: the ids, the fixed version and the hashes all verified |
| `installer-scope-additions`, `rules-and-house-process-residue` | scope and process observations | nothing to change |

## Measured: the proxy gives its credentials to any process

The question the credentials finding left open. On 2026-10-31 at 06:37Z a request to `generativelanguage.googleapis.com/v1beta/models` carrying no key returned HTTP 200 with 50 models, from curl and again from Python's `urllib` in this container. So any process here, OpenMontage's included, gets the Gemini credential. That is the exposure Tee's install trust ruling accepted as disclosed; SKILL.md now states it as measured.

## A correction to the record

PR #442 and its commit said the pyasn1 bump was checked by "tests that exercise webauthn". `test_passkeys_api.py` and `test_devon_password_recovery.py`, 16 passing, prove that webauthn and pyasn1-modules import and run their basic paths on pyasn1 0.6.5. None of them feeds `verify_registration_response` an android-key attestation, which is where pyasn1 decodes BER, so they do not reach the code the four advisories are about. The bump itself is sound: pip-audit is clean, the hashes match PyPI, and the API has served 0.6.5 since its deployment built it at 2026-10-31T00:02:40Z, per the read back in the 0123 doc.

## The second pass: a fresh critic of the fixes

Workflow `wf_7f26bdf3-651`, from 06:43Z, read the fixes cold at `f55a5f2`: three read-only scanners, one each for the installer, its tests and the skill, then a verifier in its own worktree for every finding and a second for the one graded MED. 32 agents ran and two failed on their output. The scanners raised 28 findings.

| verdict | count |
|---|---|
| confirmed | 25, graded 14 LOW and 11 NIT by their verifiers |
| refuted | 2 |
| unsettled | 1 |

The two refuted were F4, which called the proxy's four credentialed hosts unsupported when the container's own allow list names exactly those four, and F10, a coverage note whose one checkable figure, 1,585 files at the pin, was right. F3 was unsettled because its verifier failed. It said SKILL.md tells the reader the status docs record the verification of the 54 when neither of them does. That was true, and this doc is that record; SKILL.md now names it.

The 25 are answered in `1d8850a`. Run against the installer at `f55a5f2`, its tests fail 15 times: the 13 cases of the 10 behaviour tests added then, and two older tests whose expected message changed. Three tests added then pass there, because they cover behaviour that installer already had or check `constraints.txt`, which the third pass found and this session measured. The ones worth knowing:

- The Python check now does what upstream's Makefile does: `uv`, or `python3.X`, `python3` or `python` at the version asked for or newer. A machine with only a newer `python3` was refused before.
- A Python below 3.11 is refused, because `constraints.txt` pins numpy 2.4.6, and a venv on any version other than 3.11 gets a warning, because the pins were measured there only.
- `OPENMONTAGE_SETUP_TIMEOUT` must be a whole number above 0, since `timeout 0` turns the cap off. With no `timeout` binary the script says nothing is capped; it used to print a cap it did not enforce.
- A path with whitespace is refused, because pip splits `PIP_CONSTRAINT` on whitespace.
- The repository guard reads git's stdout only. Anything git wrote to stderr on success had switched the guard off with no warning.
- A failing `git status` refuses; it used to read as a clean checkout. An untracked `.py` under `tools/`, which upstream's registry would import, refuses too.
- The refusal tests run the installer's fixture copy, so a regression in them touches no network and nothing in this repository. The PIN test compares the full hash, and `constraints.txt` must name it.
- SKILL.md: a citation moved from `:225` to `:282`, the Remotion licence cites the remotion package's own lockfile line, the pin-move steps clear the old pins first, rule 4's gate sentence is scoped to its manifest, and the test count says how many passed and when.


## The third pass

Workflow `wf_0e79ee10-3bf`, from 07:34Z, read `1d8850a`: a fresh verifier for each of the 25 findings, and a fresh regression critic of that commit's diff with each of its findings verified. At 07:37Z this session misread a context compaction as a container restart that had killed the run, and launched the same script again as `wf_18098f69-93d`. The first run never stopped, so both ran to the end: every finding got two fix verifiers and the diff got two regression critics. The misreading cost one more thing. A worktree it took for a leftover and removed at 07:37Z belonged to the first run's verifier of `OM-INS-01`, which still returned a verdict on `1d8850a`, resolved, and the second run's verifier agreed. 74 agents ran; one failed on its output format.

| | first run | second run |
|---|---|---|
| fix checks resolved | 18 | 17 |
| fix checks partly resolved | 7 | 8 |
| regression findings | 13 | 9 |
| confirmed | 12 | 9 |
| unsettled | 1, its verifier failed | 0 |
| refuted | 0 | 0 |

The two critics agreed on nine findings and the first raised four more, so 13 in all, 6 LOW and 7 NIT. The one the first run left unsettled, the whitespace wording, the second run confirmed. Every head checked out was `1d8850a`.

The partly resolved verdicts left residue on eight of the 25, and most of it was what the regression critics found: zero padded timeouts such as `00` still switched the limit off, the rerun checks read git's stderr as local changes, a registry that failed to import exited 1 with no FAILED line, a repository with OpenMontage's origin and no commit was resumed without the untracked check, several guards had no test, nothing showed pip applying `PIP_CONSTRAINT`, and the time limit test failed slowly on a machine with no `timeout`. The four findings only the first critic raised: the first refusal tests still ran the shipped script against GitHub, and on a guard regression two of them would reach the network and one would write into this repository; the pin-move steps left out moving the old checkout aside; PATH narrowing in two tests leaned on what `/usr/bin` holds; and SKILL.md's exit codes left out 1, which both fix verifiers of `OM-INS-07` had also found.

All of it is answered in `0c5d046`, the third and last revision the fix loop allows:

- `OPENMONTAGE_SETUP_TIMEOUT` refuses a leading zero, so `00` cannot switch the limit off the way `0` did.
- The rerun checks read git's stdout only, so `GIT_TRACE` on a clean checkout no longer reads as local changes.
- The untracked check covers any file under `tools/` outside `__pycache__`, because the registry imports `.pyc` and `.so` as well as `.py`, and any `.py` at the top, where `make` runs Python. It also runs after a resumed fetch, which exits 1 when it fails. On the real install at `~/OpenMontage` it lists nothing.
- An existing `.venv`, which `make setup` reuses before it looks at uv or Python, is the interpreter checked and reported, and one older than the version asked for is refused.
- A registry that fails to import prints a FAILED line and exits 1.
- Every refusal test runs the fixture copy, PATH narrowing uses symlinks, and new tests pin the prerequisite list, the ffmpeg warning, the git-cannot-read refusal, Node's version call and every exit 1 path. An offline test shows pip taking the constrained version of a local package and failing on a constraint path with a space.
- SKILL.md: rule 3 cites what upstream says about the cost tracker (`skills/pipelines/explainer/asset-director.md:62, :67`, `skills/core/hyperframes.md:286`), the cache citations sit on their own clauses, the exit codes include 1, the pin-move steps move the old checkout aside, the whitespace guard is described as what it checks, and the test row says what was measured.

Left as residue, all NIT: no test for `git` missing as a prerequisite, because the narrowed PATH needs git itself; git `safe.directory` and `HOME` in the tests, which CI's runner does not trip; `OPENMONTAGE_PYTHON=abc` refused with the below-3.11 text, and `3.11.5` warned about as untested; the "124 means it ran past" note printed when no `timeout` exists; and the checkout-not-at-pin exit 1, which a verifier judged unreachable.

## The final check, at `0c5d046`

Workflow `wf_b9b9e3bd-6f1`, from 08:13Z, read `0c5d046` with a fresh verifier for each of the 13 regression findings and each of the five residues the fix verifiers had left, and one more fresh critic of that commit's diff, each of its findings verified. This round fixed nothing. The fix loop allows three revisions and `0c5d046` was the third, so what it found is recorded here and the choice of a fourth goes to Tee. 25 agents ran; every counted verdict was on `0c5d046`.

15 of the 18 were resolved. Three were partly resolved, and what they left:

- Top-level `.pyc`, `.so` and package directories still pass the untracked check, which covers a top-level `.py` only (RF10).
- A file staged with `git add` and never committed, in a repository with OpenMontage's origin and no commit, survives a resumed fetch unflagged; the reuse path would refuse the same state (X-OM-INS-08). It needs a hand-staged file in a hand-made repository.
- No test covers `git` missing as a prerequisite (X-T2).

One verifier added a nit: the regeneration line at the top of `constraints.txt` names `~/OpenMontage/.venv`, so regenerating the pins after moving to a new `OPENMONTAGE_HOME` would read the old venv.

The critic raised six, all confirmed, none refuted:

| id | grade | finding | state |
|---|---|---|---|
| C3-1 | LOW | SKILL.md cited this doc before it existed | closed by this doc |
| C3-2 | LOW | the existing `.venv` check runs the target's Python before the target is known to be an OpenMontage checkout, and a directory that is not one, holding an old or broken venv, is refused for the venv and not for the real reason | open |
| C3-3 | NIT | top-level `.pyc`, `.so` and packages pass, as RF10 found | open |
| C3-4 | NIT | the leading-zero refusal also refuses `0900`, which `timeout` reads as 900 seconds, and its message explains only the all-zero case | SKILL.md half closed in `ebdb72c`; the message is open |
| C3-5 | NIT | on the resume path a git failure in the untracked check reads as files the pin does not carry, with an empty list, and the `git ls-files failed` refusal has no test | open |
| C3-6 | NIT | the test row said 37 while the file collects 58 | closed in `ebdb72c` |

## Railway does not build the Dockerfiles CI builds

Found while scoping Tee's ruling of 08:36:39Z to build the presence image in CI, and confirmed by two independent verifiers in `wf_9ff8c465-8e0`, one reading Railway and one reading the repository.

All three Railway services, `api`, `presence` and `scheduler-cron`, build with Railpack 0.43.0 from the repository root, on Python 3.13.16, which the build logs label "railpack default (3.13)". None sets a Dockerfile path, and the repository has no root Dockerfile, Railway config file or `.python-version`. `api` and `scheduler-cron` carry a `PYTHON_VERSION` variable whose value is not readable here; their builds ran 3.13.16 all the same. The presence build of `3d70844` (deployment `54d6ddac`) shows `pip install -r requirements.txt`, `copy / /app` and `cp313` wheels, and `api` deployment `a8cea51a` at `4b07466` shows the same plan. Both `infrastructure/docker/Dockerfile.api` and `Dockerfile.presence` start `FROM python:3.12-slim`.

So the CI job named "Railway container contract" (`.github/workflows/ci.yml:286-298`) builds an image Railway never builds. It differs in interpreter, base image, the files copied, the install flags (`--require-hashes` against a plain `-r`) and the start command. Every Python job in CI runs 3.11 or 3.12, and none runs the 3.13 that production runs. The comment that pins the audit job to 3.12 calls it "the interpreter Dockerfile.api ships, so the audit resolves the same set Railway builds", which is false. `DEPLOY.md:86`, the 2026-09-08 SYS_SPEC, the CHANGELOG, `scripts/estate_reconcile.py` and `app/services/agent_scheduler.py:10` also describe `Dockerfile.api` as Railway's image, and the deploy-readback skill gives presence's root directory as `apps/presence` where it is `.`.

The ruling rested on a premise this session gave Tee on the card: that a requirements change reaches the presence image untested. The pip install is the same in both Dockerfiles, and the API image's build already tests it. And neither Dockerfile is what Railway runs, so a CI build of `Dockerfile.presence` would test nothing production runs. That ruling goes back to him on a card with the premise corrected, and nothing was built on it. His second ruling, a test that reaches pyasn1's android-key decode, stands, and goes in the next pull request.

## Measured

| check | result |
|---|---|
| `test_openmontage_installer.py` at `ebdb72c` | 58 passed on Python 3.13.17 and on 3.11.17 |
| the same file against the installer at `1d8850a` | 12 of 58 failed, each a behaviour `0c5d046` changed |
| the file of `1d8850a` against the installer at `f55a5f2` | 15 of 37 failed; 3 tests added then passed |
| eight guards removed one at a time, with the new coverage tests | each removal failed exactly one test |
| three refusal guards removed one at a time, with the network pointed at a dead port | each test failed; nothing written into the repository |
| the new untracked pathspec on the real install at `~/OpenMontage` | nothing listed; 208 `__pycache__` files excluded |
| pip with `PIP_CONSTRAINT` on two local wheels, offline | the constrained version with the variable, the newer one without it, and a path with a space split at the space |
| `PriceQuoteRequired` at the pin | 18 files mention it, 16 raise it |
| full api suite on `0c5d046`, local PostgreSQL 16 | 9460 passed, 2 skipped, exit 0 |
| CI on `1d8850a`, `0c5d046` and `ebdb72c` | every check green on each, the API suite last at 08:45:57Z |
| Railway build plan for `api`, `presence` and `scheduler-cron` | Railpack 0.43.0, Python 3.13.16, read from the build logs by two verifiers |

## Not verified

- What value `PYTHON_VERSION` holds on `api` and `scheduler-cron`; Railway returns variable names only, and both built on 3.13.16 regardless.
- The installer on any machine other than this Linux container, and any OpenMontage pipeline end to end.
- That the residue above is all there is. Each pass found less than the one before, 28 findings, then 13, then 6, and a fourth critic would likely find more NITs.

## Gauntlet verdict

```
VERDICT: PASS-WITH-CONDITIONS
Deliverable: PR #452, the OpenMontage installer, its tests and skill after three passes, and this record | Ask: "Fix per your recommendations and merge/deploy", and the 54 findings left open
Critic mode: subagents, fresh, every finding verified independently; the review's 54, then 25, 13 and 6 confirmed from three more critics, 2 refuted in all, both in the second pass
Scores: correctness 4, scope 4, verification 5, security 4, reversibility 5, failure handling 4, idempotency 5, traceability 5, observability 4, completeness 4, maintainability 4 | mean 4.4 | flagship floor: met, conditional
Security is 4 and not 5 for C3-2: the installer runs the target's .venv python before it has shown the target is an OpenMontage checkout, which the header's "left alone" promise does not allow. The target is a directory the operator chose, so no boundary is crossed.
Conditions: Tee's ruling on a fourth revision for the open residue, and his re-ruling on the presence CI job now that the Railpack finding is verified.
Recommendation: merge under the standing approval when CI is green on the head; the PR is strictly better than main, and the residue is LOW or NIT. The human owns SHIP.
```

## Open

- Tee's ruling, on a card: a fourth revision for C3-2, C3-3, C3-5, C3-4's message, RF10, X-OM-INS-08, X-T2 and the `constraints.txt` regeneration line.
- Tee's ruling, on a card: the presence CI job, re-asked with the Railpack finding.
- The android-key attestation test for pyasn1, ruled at 08:36:39Z, in the next pull request.
- The stale records that name `Dockerfile.api` as Railway's image, and the deploy-readback skill's presence root, to be corrected with whatever the presence ruling becomes.
- Carried from the 0438 doc: the first scheduled run of the daily audit, and the probe branch `claude/audit-red-path-probe`, which the proxy would not delete.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_openmontage-finding-verification_v1_2026-10-31-0642.md
DATE: 2026-10-31
DECISIONS: The 54 unverified findings of the 2026-10-31 OpenMontage review were verified the same day once the subagent limit was found lifted, and the 2026-11-03 trigger was deleted. The fix loop stopped at its third revision, as ruled, and the residue goes to Tee. Tee ruled at 08:36:39Z to build the presence image in CI, path filtered, and to add an android-key attestation test for pyasn1; the first goes back to him because its premise was wrong.
FINDINGS: 49 confirmed, 5 unsettled and all NIT, none refuted; 13 of the 14 MEDs graded LOW. Three passes of fixes drew 25, then 13, then 6 confirmed findings, all LOW or NIT, 2 refuted in all; the installer now has 58 offline tests. The proxy gives its Gemini credential to any process in the container, measured. Railway builds api, presence and scheduler-cron with Railpack on Python 3.13.16, not from the Dockerfiles CI builds on 3.12, so CI's Railway container contract tests an image Railway never builds; confirmed by two independent verifiers.
OPEN: Tee's rulings on a fourth revision of the installer and on the presence CI job; the android-key pyasn1 test; the stale records naming Dockerfile.api as Railway's image; the first scheduled daily audit run; the probe branch.
STATUS: PR #452 green on ebdb72c, this doc its last commit, to be merged under the standing approval once CI passes on that head; verdict PASS-WITH-CONDITIONS.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
