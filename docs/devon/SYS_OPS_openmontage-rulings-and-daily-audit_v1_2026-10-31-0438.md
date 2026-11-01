# OpenMontage rulings and the daily dependency audit

Status doc for the three rulings Tee made on 2026-10-31 and the work that carried them out. Written 2026-10-31. It supersedes the Open section of `SYS_OPS_openmontage-review-and-fixes_v1_2026-10-31-0123.md`, which listed all three as waiting on him.

## The rulings

Tee answered one card at 2026-10-31T04:00:46Z. Each answer was the recommended option.

| item | answer | cost the card stated |
|---|---|---|
| Remotion licence | "Free licence, 3 or fewer" | rests on the "terms apply" text, which was not read in full |
| Install trust | "Accept it, as disclosed" | a compromised upstream release could spend on Gemini or WaveSpeed, or write to the DEVON capture door |
| Daily audit | "Add it" | another CI job and a few Actions minutes a day |

The two declined install options were installing only in a second environment without the proxy's credentials, and never installing in a cloud session. The declined licence options were reading the full terms first and buying a Company License.

## What changed, PR #447

- `.github/workflows/dependency-audit-daily.yml`, new: ci.yml's `dependency-audit` job once a day at 05:23Z and on `workflow_dispatch`. It reads only and uses no secret.
- `.github/workflows/ci.yml`: the audit job now runs each audit as its own step, the later ones after an earlier one goes red, and `pip_audit` runs with `--strict`. Both came from the critic below. The daily job must equal this one, so it carries the same steps.
- `test_estate_reconcile.py`: two pins. One holds the daily job equal to ci.yml's in everything but its name and pins the daily file's triggers, single cron, permissions and top-level keys. The other sums the `jobs:` keys of every workflow file against the number CLAUDE.md states and fails when a workflow file is named nowhere in the Reproducing CI section.
- `CLAUDE.md`: the job count said THIRTEEN while the files held fifteen. `quality90-ai-review.yml` arrived on 2026-10-21 and `browser-worker-ci.yml` in PR #400 on 2026-10-22, and neither was counted or named. It now says SIXTEEN and describes all three newer files.
- `AGENTS.md` said CI is six jobs, and the steward skill said a Python-only pull request shows four. Neither states a stale count now; both point to CLAUDE.md.
- `.claude/skills/openmontage/SKILL.md`: both rulings recorded where each item was open, with the cost the card stated, and the provenance list names the licence a render ran under.

`main` moved twice during the work. PR #443 merged at 04:28Z with a new skill and a CLAUDE.md change, and was merged into the branch as `9f1f3ff` with no conflict. PR #444 merged at 04:36Z with another skill. Each PR had moved CLAUDE.md's skill count from nineteen to twenty, so `main` after both said twenty while the directory held twenty-one, and CI on `main` went red at `164497a` on `test_the_skill_inventory_is_counted_from_the_directory`. The same test failed on this PR's merge ref at `99a2b36`, 1 failed and 9190 passed, through no change of its own. PR #449, from the session that owns #444, carries the fix. Its two hunks were ported here verbatim in `498617f`, so whichever PR merges second takes those lines cleanly.

## The critic

A fresh critic ran on `9c23acd` as a workflow: five read-only scanners, one per dimension, then an independent verifier in its own worktree for each finding, two for any finding graded MED or higher. 24 agents, none failed. 19 findings, 17 confirmed, 2 refuted, none unsettled. Every confirmed finding was LOW or NIT. The two that mattered most were the audit steps masking each other once one went red, and the 0123 status doc still listing the rulings as open while the skill recorded them. All 17 are addressed in `99a2b36`.

A second workflow checked the fixes at `99a2b36`, 25 agents, none failed. One fresh verifier per finding re-ran its check: 15 of the 17 resolved, and the other two were the status record this doc is, which was not yet committed. A fresh critic read the fix diff alone and raised 7 findings, each then verified: 5 confirmed, all LOW or NIT, 1 refuted, 1 unsettled. The five were the local reproduction lines in CLAUDE.md and the steward skill missing `--strict`, the session start hook still saying CI is six jobs, the skill pointing at this doc before it existed, an AGENTS.md clause attached to the wrong noun, and a step id on the install step that read like an audit. All five are fixed in the commit that adds this doc, along with a `KeyError` a verifier found in the rewritten pin and a CLAUDE.md sentence that still said the steward skill gave the old count.

The unsettled one is the claim that the later audits run after an earlier one goes red. CI ran the new steps on GitHub at `99a2b36` and the job went green, which shows they run and pass, and says nothing about the red path. Proving that takes a run with a known vulnerable pin, which is the negative control listed under Not verified.

## Measured

| check | result |
|---|---|
| count pin against the old CLAUDE.md | red, `13 == 16` with the per-file breakdown |
| count pin with only the number fixed | red, naming exactly the three unnamed files |
| daily-audit pin under five mutations: job `continue-on-error`, job `if: false`, top-level `defaults`, a `push` trigger, a dropped step `if` | red each time, file restored byte for byte |
| count pin with one workflow's name removed from the section | red, naming it |
| `pip_audit --strict` on `requirements.txt` and `deploy/soul/requirements.txt`, locally | exit 0, no known vulnerabilities, for both |
| full api suite on `9c23acd`, local PostgreSQL 16 | 9249 passed, 2 skipped, exit 0 |
| full api suite on `99a2b36`, local PostgreSQL 16 | 9250 passed, 2 skipped, exit 0 |
| CI on `9c23acd` | all five ci.yml jobs green, the API suite at 04:31:58Z |
| CI on `99a2b36`, the dependency audit job with the restructured steps | green on GitHub at 04:52:42Z |

## Not verified when this was written

- That the new workflow runs green on GitHub. Only a `workflow_dispatch` after merge proves that, because GitHub registers a dispatchable workflow from the default branch.
- That the failure email reaches Tee. The rule that GitHub mails the account that last changed the cron line is recalled; merges here land as tdveal74-cell.
- The first scheduled run. New schedules here have taken five to six hours to fire.
- The full Remotion terms behind "terms apply", which the ruling chose not to wait for.
- The red path: that the soul host's audit and `pnpm audit` run after the first audit goes red. The test is a `workflow_dispatch` of the daily workflow on a throwaway branch that pins a version with a known advisory.
- The deploy read back after the merge.

## After the merge, read back 2026-10-31

PR #447 merged at 05:32:39Z as `d30b405`. `main` had taken #449 at 05:04Z and #448 at 05:28Z since this branch's last CI, so the merge commit joined this PR to #448 untested. #448 added no workflow file and changed CLAUDE.md, `test_estate_reconcile.py` and the gate ledger. On `d30b405` locally, those tests and the receipt, integrity, vendored skill and mpt-shorts tests passed, 2126 of them, and CI run 1554 on `main` passed at 05:45:26Z.

| check | result |
|---|---|
| `workflow_dispatch` of the daily audit on `main` | run 41173018792 passed at 05:33:23Z, every audit step green |
| the red path, a dispatch on a probe branch carrying `pyasn1==0.6.4` | run 41173033693: the first audit found the four pyasn1 advisories and exited 1; the soul host's audit and `pnpm audit` then ran and each found no known vulnerabilities; the job went red |
| the failure email for that red run | in Tee's inbox from notifications@github.com, "Run failed: Dependency audit daily - claude/audit-red-path-probe (36acc64)" |
| Railway `api` | deployment 92d128e5 SUCCESS at 05:46:08Z on `d30b405`, after CI passed; `/api/v1/health` healthy at 05:51:32Z |
| Railway `scheduler-cron` | deployment 49206f5c SUCCESS at 05:33:38Z on `d30b405` |
| Railway `presence` | SKIPPED on `d30b405`, correct: no path it watches changed; `/health` 200 with eleven keys, speech `cartesia`, breaker closed with no breaches |
| Vercel `meta-supreme-apex-genesis-web` | `dpl_9KMyintZMnccaGvTEMzab1qbUkhz` READY, target production, on `d30b405` |
| Vercel `devon-soul` | `dpl_DcPt5w7AAZ6iATaYfcf49tbcT9Tg` READY, target production, on `d30b405` |

Both Vercel projects built when a skip was expected. The web build log shows the ignore command running and then `vercel build`, the fail-open signature. Neither project's watched paths changed between its last READY production build, `7deda01`, and `d30b405`, so both serve the same code as before. Why the guard fired here, when the three commits before it skipped against the same base, is not established.

The probe branch could not be deleted. The environment's git proxy answered the delete with HTTP 403, and its rules say a policy denial is reported, not retried. `claude/audit-red-path-probe` stays on GitHub until Tee deletes it; nothing deploys from it.

Still unmeasured: the first scheduled run of the daily audit, which new schedules here have taken five to six hours to fire, and whether a scheduled run's failure email reaches the same inbox. The email above came from a run dispatched under tdveal74-cell; who GitHub mails for a scheduled run is the recalled rule, and the first scheduled red run will show it.

Re-graded after the read back: verification 5, because the green path, the red path and the alarm channel each ran on GitHub. Mean 4.5. The verdict stands at PASS-WITH-CONDITIONS on one condition, the first scheduled run.

## The first scheduled run, read back 2026-11-01

Run 41304000680 is the first with `event: schedule`, read from the workflow's run list at 2026-11-01T12:01Z. It started at 11:55:05Z against the `23 5 * * *` slot, 6h32m late, which is later than the two first runs CLAUDE.md records, 5h06m and 6h03m. It ran on `main` at `a85af9a` and passed: the pinned requirements audit, the soul host's audit and `pnpm audit` each passed, and the job finished at 11:55:37Z. That meets the one condition on the verdict above.

Still unmeasured: who GitHub mails when a scheduled run goes red. A green run sends no failure email, so this run cannot show it.

## Open

- The 54 findings from the 0123 arc that no independent agent has verified. That doc gave the subagent limit as the reason and scheduled the verification for 2026-11-03T05:30Z. The limit was not in force today: the 24 agents above ran between 04:16Z and 04:34Z with no failure, so the verification can run sooner.

## Gauntlet verdict

```
VERDICT: PASS-WITH-CONDITIONS
Deliverable: PR #447, daily dependency audit, CI count pin, two recorded rulings | Ask: Tee's card of 2026-10-31T04:00Z
Critic mode: subagent, fresh, 24 agents, verifier per finding
Scores: correctness 4, scope 4, verification 4, security 5, reversibility 5, failure handling 4, idempotency 5, traceability 5, observability 4, completeness 4, maintainability 4 | mean 4.4 | flagship floor: met, conditional on the dispatch
Recommendation: merge under the standing approval when CI is green on the head, then prove the workflow by workflow_dispatch and run the red-path negative control. Verification is 4 and not 5 because neither has run yet. The human owns SHIP.
```

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_openmontage-rulings-and-daily-audit_v1_2026-10-31-0438.md
DATE: 2026-10-31
DECISIONS: Tee ruled on one card at 04:00:46Z: the free Remotion licence for an operation of three or fewer, the OpenMontage install trust accepted as disclosed, and a daily scheduled dependency audit added.
FINDINGS: CLAUDE.md counted thirteen CI jobs while the files held fifteen, and two workflow files were named nowhere; the count is now pinned by a test. A fresh critic confirmed 17 LOW or NIT findings on the first commit, among them audit steps that hid each other once one went red, all addressed.
OPEN: the 54 unverified findings from the 0123 arc, verification running since 05:37Z; who GitHub mails for a scheduled red run, since the first scheduled run on 2026-11-01 was green; the probe branch, which the proxy would not delete; the full Remotion terms.
STATUS: PR #447 merged as d30b405 at 05:32:39Z, CI run 1554 green on main. The daily audit is proven by dispatch on main, green, and on a probe branch, red with the later audits still running, and its failure email reached Tee. Read back: api and scheduler-cron SUCCESS on d30b405, presence correctly skipped, both Vercel projects READY production on d30b405 with unchanged code.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
