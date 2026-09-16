# route_thinking answers for script writing, and it nearly answered wrong

Date: 2026-09-16. Supersedes nothing. Closes the one finding from
`SYS_OPS_duix-llama-and-coverr-evaluated_v1_2026-09-15.md` that was genuinely
unfiled.

`route_thinking("script writing")` returned DECLINED. It now returns
`cerebras`, which is where the work has actually run since Tee ruled it on
2026-09-15. The first attempt at this fix routed it to the Council, was wrong,
and was caught by reading the Context Pill before merging rather than after.

## What was wrong

`services/devon/ecosystem.py` holds two tuples and a function over them.
`CEREBRAS_DUTIES` names classification, summarization, extraction, bulk
analysis, routing assistance and preprocessing. `COUNCIL_DUTIES` names deep
deliberation, complex reasoning, risk analysis, multi perspective and sovereign
advice. Anything in neither came back DECLINED, with the function's own comment
explaining that a confident wrong route is worse than no route. That shape is
correct and was left alone.

Script writing was in neither. That is not an exotic duty here. TQO FINAL V5
carries a `Daily 6am - Script Writer` schedule trigger and a script lane whose
nodes are named `Write Script (Cerebras)` and `Expand Script (Cerebras)`. So
the registry that says where thinking goes was silent on the duty the studio
performs daily, and the silence read as a considered refusal.

## The near miss, which is the part worth keeping

The first fix added `script writing` to `COUNCIL_DUTIES`, reasoning that script
writing is judgement, that judgement goes to the Council by the module's own
doctrine, and that Tee had said "cerebras held" earlier in the session. Tests
were written, four suites and the full 2626 test run went green, a pull request
was opened, and CI began.

All of that was green and all of it was wrong.

"Cerebras held" meant the throwaway quality probe offered on 2026-09-15 stays
held. It did not mean Cerebras is barred from script writing, because Tee had
already ruled the opposite on 2026-09-15, on an inline card, recorded in
`SYS_OPS_the-two-pass-writer-and-the-owned-presenter_v1_2026-09-15.md`: the
Cerebras writer came in under the 1200 word floor five times running, at 894,
798, 1055, 1059 and 848 words, and the answer to that card was two pass
expansion on Cerebras. The Context Pill carried the same ruling in one line,
"The writer is TWO PASS on Cerebras, second expansion pass capped at two", and
noted that V5's nine model calls already use that lane.

The error was not the routing opinion. It was reaching a routing opinion
without first reading the standing rulings, then treating a short instruction
as license for it. Green CI on a wrong premise is exactly what "green is not
correct" is about, and this is the second entry in that ledger from the same
session: the previous document asserted two findings were unfiled when one had
been filed twice, for the same reason.

The pill was read only because updating it was the next task in the list. Had
the order been merge then update, the wrong route would have landed.

## What changed

`RULED_ONTO_CEREBRAS` was added, a map of duties whose lane was ruled rather
than derived, carrying one entry. `route_thinking` consults it before the two
tuples, so where the work actually runs beats where the doctrine would have put
it.

It is held separately rather than appended to `CEREBRAS_DUTIES` because the
reason differs and the reason is what a reader comes for. Everything in that
tuple is there because it is mechanical, and the function says so in its return
value. Script writing is the product. It is on the fast lane because that lane
is the funded one, the Anthropic account behind the Claude nodes being empty,
and because two pass expansion was measured to clear the floor. Collapsing it
into the tuple would make the registry call the studio's product mechanical in
the one place someone looks to find out why, so a test now fails if that
happens.

`describe_ecosystem` gained a `ruled_onto_cerebras` key so the map shows the
third category rather than hiding it inside the function.

## The measurement

Reproduced rather than asserted. The pre-fix module was loaded straight from
`git show HEAD:services/devon/ecosystem.py` into a temporary path, so the
working tree was never reverted to test it: DECLINED before, `cerebras` after,
with `classification` still `cerebras`, `risk analysis` still `council`, and an
unrecorded duty still DECLINED.

Suites, all local, all exit 0: `test_devon_ecosystem.py` 62 passed, the four new
tests confirmed by name rather than inferred from the count;
`test_deploy_soul.py` with `test_devon_integrity.py` 358 passed; the CI
standalone job's file list reproduced with `PYTHONPATH`, `DATABASE_URL` and
`TEST_DATABASE_URL` unset, 694 passed; the full suite against PostgreSQL 16,
2626 passed; `ruff check .` clean.

## The drift this nearly caused as well

`ecosystem.py` exists twice, at `services/devon/ecosystem.py` and at
`deploy/soul/services/devon/ecosystem.py`, and nothing regenerates the second
from the first. There is no sync script under `scripts/` and no test compared
them. A duty added to one and not the other would route differently depending
on which host answered, silently.

Both copies carry the change and `test_the_soul_copy_routes_thinking_the_same_way`
now parses both files and compares all three collections. The guard is
deliberately narrow, covering the duty collections rather than the whole file,
because the copies could legitimately diverge elsewhere and a byte equality
test would fail on a difference nobody cares about.

## DEVON RECEIPT

```
AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_route-thinking-answers-for-script-writing_v1_2026-09-16e
DATE: 2026-09-16
DECISIONS: Tee ruled three things in this exchange. Oracle is out, which closes the Duix hardware question from the previous document without the uname check ever being run and without either Duix licensing PDF being read. Cerebras stays held, which on reading the record means the throwaway quality probe stays held rather than that Cerebras is barred from script writing, because he had already ruled the writer onto Cerebras on 2026-09-15. And route_thinking was to be made green, merged, filed, threaded and carried into the Context Pill. The decision taken inside this arc was mine and it was to hold script writing in a separate RULED_ONTO_CEREBRAS map rather than append it to CEREBRAS_DUTIES, so that the returned reason states the real one, a funding fact and a measured floor, instead of calling the studio's product mechanical. I also reversed my own first answer: the change that routed script writing to the Council was written, tested, pushed and under CI before the standing ruling was read, and it was replaced rather than defended.
FINDINGS: route_thinking returned DECLINED for "script writing" while TQO FINAL V5 carries a Daily 6am Script Writer trigger and a script lane whose nodes are named Write Script (Cerebras) and Expand Script (Cerebras), so the registry disagreed with the estate it describes; the first fix routed the duty to the Council on the reasoning that script writing is judgement, passed 2626 tests and reached CI before being found wrong, because Tee had ruled the writer onto Cerebras on 2026-09-15 on an inline card after five measured undershoots of the 1200 word floor at 894, 798, 1055, 1059 and 848 words, a ruling recorded in SYS_OPS_the-two-pass-writer-and-the-owned-presenter_v1_2026-09-15.md and carried in one line of the Context Pill; the phrase "cerebras held" referred to the throwaway quality probe offered on 2026-09-15 and not to the lane, and reading a short instruction as license for a routing opinion is what produced the wrong change; the error was caught only because updating the Context Pill was the next task in the list, so a merge-then-update order would have landed it; and ecosystem.py exists twice with no generator under scripts/ and no test comparing the copies, so a one sided edit would have routed differently per host silently, which is why both copies carry the change and a narrow parsing guard over the three duty collections was added.
OPEN: the script lane is now routed to the lane it runs on, and nothing about funding changed, so the Anthropic account behind the remaining Claude nodes is still empty and any node still pointed at it fails the same way; the Cerebras quality probe stays held and is Tee's to release, though the writer already runs there so the probe would now measure the live lane rather than a candidate; the wider drift risk between the two ecosystem.py copies is guarded only for the thinking duties, with the rest of both files unguarded; no other craft duty was added to any collection, so anything beyond script writing still returns DECLINED by design; and the free MuseTalk lip sync route recorded on main at 5063493 has not been read against the Duix finding, which ruling Oracle out appeared to close but may not have.
STATUS: shipped to this repository. One code change across two copies of ecosystem.py, four tests added to test_devon_ecosystem.py, and this document. No dependency was added, no skill vendored, no n8n workflow touched on either instance, no credential read or written, and no provider called. Every number here is measured in this session rather than recalled, the before and after routing values were reproduced rather than asserted, and the wrong first attempt is recorded above rather than quietly dropped.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
