# route_thinking answers for script writing, and the cheap lane stays shut

Date: 2026-09-16. Supersedes nothing. Follows
`SYS_OPS_duix-llama-and-coverr-evaluated_v1_2026-09-15.md`, which raised the
finding this document closes.

The registry that decides where thinking goes could not route the one duty this
studio performs every day. `route_thinking("script writing")` returned
DECLINED. It now returns `council`. Cerebras was offered as the free lane and
Tee held it, so the fast lane is unchanged and the hold is now enforced by a
test rather than by anyone remembering it.

## What was wrong

`services/devon/ecosystem.py` carries two tuples and a function over them.
`CEREBRAS_DUTIES` names classification, summarization, extraction, bulk
analysis, routing assistance and preprocessing. `COUNCIL_DUTIES` named deep
deliberation, complex reasoning, risk analysis, multi perspective and sovereign
advice. Anything in neither list came back DECLINED, with the function's own
comment explaining that a confident wrong route is worse than no route, which
is correct and is why the shape was left alone.

Script writing was in neither list. That is not an exotic duty here. TQO FINAL
V5 carries a `Daily 6am - Script Writer` schedule trigger, one of the six
disabled triggers, and the script lane is the largest of the six Claude calls
by token budget at 24,000. So the registry was silent on the single question it
most needed to answer, and the silence looked like a considered refusal.

The finding was raised on 2026-09-15 while pricing a free script writer. It was
raised as unfiled, which was half right: a second finding offered in the same
breath, that Gateway credits are Cloud only and therefore unavailable to the
VPS script lane, turned out to be already filed twice, in
`SYS_OPS_the-anthropic-funding-lane_v1_2026-09-11.md` at line 118 and in its
receipt, with the consequence recorded at
`SYS_OPS_the-first-vps-watched-run_v1_2026-09-15.md` line 104. Only the
`route_thinking` boundary was genuinely absent from every document. Checking
before asserting would have caught that, and did not.

## What changed

`script writing` was added to `COUNCIL_DUTIES` in both copies of
`ecosystem.py`, with the ruling recorded in a comment above the tuple.

It goes to the Council because it is judgement carrying Tee's voice, not
because the Council is cheap. The Council lane is in fact the unfunded one
today. Routing is a pure function that returns a decision and spends nothing,
so recording the correct route costs nothing and leaves the funding question
exactly where it was.

## What did not change, on purpose

Cerebras remains the mechanical lane and `script writing` is not on it. Tee was
offered a measured probe on 2026-09-15, a throwaway VPS workflow writing one
real TQO script on `gpt-oss-120b` through the existing credential
`ENoUSqySnkK0NVsl`, and answered "Hold for now". Nothing was run, no workflow
was created on either n8n instance, and no token was spent. On 2026-09-16 he
ruled the Oracle box out, which closes the Duix question raised in the previous
document without the architecture check ever being run.

## The measurement

Reproduced before and after rather than asserted. The pre-fix module was loaded
straight from `git show HEAD:services/devon/ecosystem.py` into a temporary
path, so the working tree was never reverted to test it:

```
BEFORE (HEAD)      : DECLINED
AFTER  (worktree)  : council | 'script writing' is judgement...
on cheap lane?     : False
unknown duty still declines: DECLINED
```

Suites, all local, all exit 0: `test_devon_ecosystem.py` 61 passed;
`test_deploy_soul.py` with `test_devon_integrity.py` 358 passed; the CI
standalone job's file list reproduced with `PYTHONPATH`, `DATABASE_URL` and
`TEST_DATABASE_URL` unset, 694 passed; the full suite against PostgreSQL 16,
2626 passed in 193 seconds; `ruff check .` clean.

## The drift this nearly caused

`ecosystem.py` exists twice, at `services/devon/ecosystem.py` and at
`deploy/soul/services/devon/ecosystem.py`, and nothing regenerates the second
from the first. There is no sync script under `scripts/` and no test compared
them. A duty added to one and not the other would route differently depending
on which host answered, and nothing would have said so.

Both copies were edited and `test_the_soul_copy_routes_thinking_the_same_way`
now parses both files and compares the two tuples, so the next person to edit
one is told about the other. The guard is deliberately narrow: it covers the
two duty tuples, not the whole file, because the two copies could legitimately
diverge elsewhere and a byte equality test would fail on a difference nobody
cares about.

## DEVON RECEIPT

```
AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_route-thinking-answers-for-script-writing_v1_2026-09-16e
DATE: 2026-09-16
DECISIONS: Tee ruled three things across 2026-09-15 and 2026-09-16. He held the Cerebras script writer probe with the words "Hold for now", so nothing was run and no workflow was created on either n8n instance. He ruled the Oracle box out, which closes the Duix hardware question from the previous document without the uname check ever being run and without either Duix licensing PDF being read. He then instructed that route_thinking be made green, merged, filed, threaded and carried into the Context Pill. The decision taken inside this arc was mine and it was where to put script writing: the Council rather than Cerebras, because it is judgement carrying Tee's voice and because the cheap lane was explicitly held, accepting that the Council lane is the unfunded one today and that routing correctly does not fund it. I also chose to keep the change to one duty rather than adding every craft duty I could imagine, because widening a rule on speculation about intent is what this repository's first law forbids.
FINDINGS: route_thinking in services/devon/ecosystem.py returned DECLINED for "script writing" while TQO FINAL V5 carries a Daily 6am Script Writer trigger and the script lane holds the largest of the six Claude token budgets at 24,000, so the registry was silent on the duty the studio performs daily and the silence read as a considered refusal; the pre-fix behaviour was reproduced by loading HEAD's copy of the module into a temporary path rather than by reverting the worktree, returning DECLINED before and council after with the cheap lane unchanged and unknown duties still declining; ecosystem.py exists twice, at services/devon and at deploy/soul/services/devon, with no generator under scripts/ and no test comparing them, so a one sided edit would have routed differently per host silently, which is why both copies were edited and a narrow parsing guard over the two duty tuples was added rather than a byte equality test that would fail on differences nobody cares about; and one correction to the previous document's framing, that of the two findings it offered for filing only this one was genuinely unfiled, because the Gateway credits Cloud only constraint was already recorded in SYS_OPS_the-anthropic-funding-lane_v1_2026-09-11.md at line 118 and in its receipt with the consequence at SYS_OPS_the-first-vps-watched-run_v1_2026-09-15.md line 104, an error a check before the assertion would have caught.
OPEN: the script lane is routed correctly and still unfunded, so the 401s on the VPS stand until the Anthropic key is funded or the six Claude nodes are repointed, and no new option was created by this change; the Cerebras probe stays held and is Tee's to release; the free MuseTalk lip sync route recorded on main at 5063493 on 2026-09-15 has not been read against the Duix finding, and it may reopen the avatar question that ruling Oracle out appeared to close; neither Duix licensing PDF was read and both would need reading before any GPU spend; the wider drift risk between the two ecosystem.py copies is now guarded only for the thinking duties, with the rest of the file unguarded; and no other craft duty was added to either tuple, so anything beyond script writing still returns DECLINED by design.
STATUS: shipped to this repository. One code change across two copies of ecosystem.py, four tests added to test_devon_ecosystem.py, and this document. No dependency was added, no skill vendored, no n8n workflow touched on either instance, no credential read or written, and no provider called. Every number here is measured in this session rather than recalled, and the before and after routing values were reproduced rather than asserted.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
