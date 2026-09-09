# Capture enrichment, wired: closing the call site half of DCD-07

Status record for the arc that gave `enrich_capture` a caller. Supersedes
nothing; the finding it acts on was raised in
`SYS_OPS_devon-hermes-agent-audit_v1_2026-09-02` and the ruling that scheduled
this work is recorded in `docs/devon/DEVON.md` under Cerebras enrichment.

## What was wrong

DCD-07, 2026-09-02: `services/intelligence/enrichment.py` held a complete
enrichment lane with sixteen tests, `app/services/intelligence.py` held a
provider factory for it, and nothing in the application called either one.
`ENRICHMENT_PROVIDER=cerebras` therefore configured a provider that no capture
ever reached, while `DEVON.md` described it as tagging them.

The failure is worth naming precisely, because it is the shape this estate keeps
producing: every test passed, the code was correct, and the behaviour did not
exist. Tests that only exercise a function cannot tell you whether anything calls
it.

## What was built

`app/services/capture_enrichment.py` is the call site. Two callers reach it: the
`/api/v1/devon/command` route and `KnowledgeLoop.propose`. The trust ladder is
unchanged: the suggestion goes to `Devon.ask`, which hands it to `resolve_area`,
which validates it against the nine and falls back to keywords.

Three things this had to get right that the finding did not say.

**Ask about the words that will actually be filed.** `propose` is fed prose from
the HUD, and prose parses as nothing until "remember" is on the front. Tagging
the raw text would have returned None from `area_suggestion_text` for the entire
knowledge loop, so the lane would have read as wired while never once running.
That is the same class of bug as DCD-07 itself, one layer in. `_utterance_for`
is now resolved once and shared by the enrichment call and the plan, because two
calls would agree today and are one edit away from not.

**Spend a call only when the answer would be read.** `Devon.area_suggestion_text`
returns None for a query, an empty payload, and an intent whose Area the intent
itself fixes. `FIXED_AREA_INTENTS` names that last case. It is a list of names
rather than something derived, because the handlers pass `force_area` inside a
call expression and there is nothing to introspect, so both halves are held shut
by tests: a name in the set that no longer forces an Area fails, and a capture
intent outside it that does force one fails too.

**Never lose a capture to a failed enrichment.** `enrich_capture` handles
`ProviderError` itself, but the metered wrapper raises outside that family.
`ProviderSpendCapExceeded` extends `AppError`; the cap check and the usage record
are database round trips that raise `DBAPIError`; a socket error arrives
unwrapped. The guard at the call site is broad, and `CancelledError` is a
`BaseException` and deliberately propagates. There is no `asyncio.wait_for`,
because timing out the await would strand the shielded usage write at
`app/services/provider_usage.py:258` behind a request that has already returned.
The bound already exists one layer down in `min(AI_TIMEOUT_SECONDS, 30.0)`.

## Why a green CI run proves nothing here

The offline lane asks nobody, on purpose. The mock provider fabricates a value
per declared JSON key without reading the capture
(`services/intelligence/providers/mock_provider.py:136`), so its Area is
discarded on the next line and asking it would spend a metered call and two
database round trips for nothing. Gating on the provider name rather than on a
new flag is also what makes DEVON.md's sentence true as written.

The consequence is that **the whole suite passes with `suggest_area` replaced by
`return None`**. So two test files drive a real `CerebrasProvider` over an httpx
MockTransport and assert the Area lands on the filing plan, and eleven negative
controls were run against them. Each went red on the named test and green again
on revert.

| mutation | test that went red |
|---|---|
| `suggest_area` returns None unconditionally | `test_a_supplied_area_reaches_the_filing_plan` and six others |
| exception guard narrowed to `ProviderError` | `test_enrichment_failure_degrades_to_no_suggestion`, all three cases |
| `episode_idea` dropped from `FIXED_AREA_INTENTS` | `test_a_call_is_spent_exactly_when_the_answer_would_be_read[episode_idea]` |
| a stale name left in `FIXED_AREA_INTENTS` | `test_every_fixed_area_intent_really_fixes_its_area[capture]` |
| `_utterance_for` stops prefixing "remember" | `test_prose_is_prefixed_before_it_is_tagged` and three others |
| `_plan_from` drops the suggestion | `test_a_supplied_area_reaches_the_filing_plan` |
| `propose` stops calling the lane | `test_propose_tags_prose_that_does_not_parse_as_a_capture` |
| `propose` tags the raw text | the same |
| the `enrichment` block leaves PLAN_CREATED | the same |
| `propose` asks when the caller already named an Area | `test_an_area_the_caller_supplied_spends_no_call` |
| the command route stops calling the lane | `test_the_chat_command_route_tags_a_capture` |

## The summary now has a destination

`enrich_capture` generates a one line summary that nothing read. It is logged at
INFO and written whole into the intent's `PLAN_CREATED` payload, which is the
only way to tell a good tag from a lucky one when auditing a wrong Area later.

## Cost

One capture costs one provider call. Nothing dedupes, so the same text captured
twice costs two calls. Queries, effects, empty payloads and `episode_idea` cost
nothing at all.

## What a correction to the earlier record looks like

An earlier note in this session recorded an open finding that
`apps/presence/settings.py` validates the LiveKit triple but never checks that
`PRESENCE_SPEECH=cartesia` has a key behind it. Reading the file settled it as
mostly wrong: `build_speech` did check the key, at startup, by name, and
`main.py:140` calls it inside `create_app`. The gap was narrower than recorded
and was not a defect. It is written down here rather than quietly dropped,
because the first law cuts both ways and an over called finding spends attention
just as a missed one costs correctness.

## Verification

Five CI jobs reproduced locally before the push, and CI run 643 on `316ec76`
completed green on all five.

```
standalone   194 passed   offline list, PYTHONPATH and DATABASE_URL unset, stricter than CI
container    import contract OK
engine        25 passed, 2 deselected
api        1,739 passed in 205s
ruff         All checks passed
```

`test_deploy_soul.py` caught the vendored copy of `services/devon/assistant.py`
drifting from the original and it was synced in the same commit. `web-ci` does
not run: no path under `apps/web`, `packages/ui` or the lockfile is touched.

## Open

DCD-07 is **wired and unverified, not closed.** A mock transport is not a key.
The remaining evidence is a live readback: set `ENRICHMENT_PROVIDER=cerebras`
with a key on the deployment, file one capture whose words carry no keyword
signal, and read the `capture enrichment:` log line or the `enrichment` block on
that intent's `PLAN_CREATED` event. That cannot run from CI or from an agent
container and is a manual item for Tee or for a session with the deployment in
front of it.

Also open, and unchanged by this arc: the n8n tier has no read route, warning
thresholds on the budget are not built, and the Vercel Authentication wall on the
web project stays with Tee.

## What the fresh critic found, and what changed because of it

Spawned on `316ec76` in its own worktree, told to mutate the source rather than
read it. It echoed `316ec76` back, returned PASS-WITH-CONDITIONS, and found four
things worth acting on. All four were reproduced by execution before they were
raised, and all four are fixed in this arc.

**A bad byte in the model's summary lost the capture.** `summary` and
`model_suggested_area` are third party output copied into a hash chained jsonb
payload, and `_clean_summary` collapses whitespace without removing a NUL or a
lone surrogate. `provenance.check_payload` refuses both, so `append_event` for
PLAN_CREATED refused, `propose` answered 409, and a clean capture was lost. The
critic drove it through the live route with a model reply of
`{"area": "ACX", "summary": "a widget \u0000 note"}` and got the 409 alongside a
201 on the control. That contradicted this lane's own stated invariant. The fix
is `_ledgerable`, which asks the ledger's own checker and drops the note when it
refuses: losing an audit note costs one capture's provenance, losing the capture
costs Tee data. Asking the ledger rather than sanitising here is deliberate, so
there is one opinion about what jsonb accepts rather than two that drift.

**The paraphrase of every capture was reaching application logs at INFO.** The
critic put a card number, a password and a medical detail into a capture and read
them back out of the log, quoted by the model inside its own summary. Before this
module existed no capture content reached logs at any level, and four of the nine
Areas are Health, Money, Family and Learning. The summary moved to DEBUG; what
stays at INFO is the Area, the provenance, the model, the provider, the tokens and
the latency, which is everything needed to answer whether the lane is running and
none of it the capture.

**The gate disagreed with the factory about a provider's name.**
`create_provider` does `.strip().lower()`; the gate did not. So
`ENRICHMENT_PROVIDER=Mock` passed the gate, the factory lowercased it and built a
MockProvider anyway, and every capture spent a metered call and a cap check on an
answer discarded on the next line, which is exactly the waste the gate exists to
prevent. Measured across `Mock`, `MOCK`, `' mock '`, `'mock\n'`, `''`, a typo and
`None`.

**Nothing could tell that the lane had stopped running.** With
`get_enrichment_provider` raising unconditionally, which is the production shape
of a missing or invalid key, all 56 enrichment tests still passed and the only
signal was one log warning per capture. That is DCD-07's own shape recurring. It
was a disclosed residual rather than a hidden defect, and it is now readable:
`GET /api/v1/devon` carries `capture_enrichment` with the configured provider,
whether the gate lets it run, and whether a provider has ever actually been
built. The reading says plainly that `provider_built` False cannot distinguish a
failed factory from a lane nothing has asked yet, because it cannot.

Two more, recorded rather than fixed. The command route now parses twice on text
that matches no intent, which the critic measured at 276 ms of blocking CPU on a
4000 character input; the gate moved ahead of the parse so the offline lane pays
nothing, and the root cause, `parse` recomputing `normalize` per phrase per call,
predates this arc. And a comment in `assistant.py` named
`test_devon_area_enrichment.py`, a file that does not exist, inside the very
comment that exists to point at a drift guard. Under a repository whose first law
is to read the file before saying where something lives, that one stung.

Six further negative controls were run on the fixes, each going red on the named
test and green again on revert: the block reaching the ledger unchecked, the block
being dropped unconditionally, the gate losing its normalisation, the summary
returning to INFO, the gate moving back behind the parse, and `_provider_built`
never being set. Seventeen negative controls across the arc in total.

Three things the critic checked and found clean, worth recording so they are not
re-derived: `Devon.ask` has exactly three non test call sites so no unenriched
capture surface exists; `latency_ms` in a hash chained record is not a replay
problem because `verify_chain` recomputes from the stored payload; and 200
concurrent calls on the shared `_DEVON` produced one distinct result with the
shared approval queue still empty.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_capture-enrichment-wiring_v1_2026-09-09
DATE: 2026-09-09
DECISIONS: gate the lane on ENRICHMENT_PROVIDER naming a real provider rather than on a new flag, so DEVON.md's sentence becomes true as written and the offline lane is untouched; resolve the utterance once and share it between the enrichment call and the plan rather than calling the selector twice; keep FIXED_AREA_INTENTS a hand written set and hold both of its halves shut with tests rather than deriving it from source; guard the call site with a broad except Exception and let CancelledError propagate; add no asyncio.wait_for, because the provider already carries the timeout and a wait_for would strand the shielded usage write; write the whole EnrichmentResult into the PLAN_CREATED payload so the generated summary has a destination
FINDINGS: a fresh critic on 316ec76 returned PASS-WITH-CONDITIONS and found four things by executing them, all fixed here: a NUL or lone surrogate in the model's summary made the ledger refuse the PLAN_CREATED event and lost the capture, contradicting this lane's own invariant; the model's paraphrase of every capture was reaching application logs at INFO, card numbers and medical details included, where no capture content had ever gone before; the gate did not normalise the provider name the way create_provider does, so ENRICHMENT_PROVIDER=Mock spent a metered call per capture on an answer discarded on the next line; and with the factory raising unconditionally all 56 enrichment tests still passed, which is DCD-07's own shape recurring, now readable at GET /api/v1/devon. Also: propose is fed prose that parses as nothing, so tagging the raw text would have left the entire knowledge loop unenriched while the finding read as closed, which is DCD-07 one layer in; ProviderSpendCapExceeded is an AppError and not a ProviderError, so enrich_capture's own handler does not cover the metered stack; the whole suite passes with suggest_area returning None, so no green run can evidence this wiring; test_deploy_soul.py caught the vendored soul copy of assistant.py drifting; an earlier claim in this session that settings.py fails to check the Cartesia key was over called, build_speech checks it at startup by name
OPEN: DCD-07 is wired and unverified, not closed; the command route still parses twice on text matching no intent, which is 276ms of blocking CPU on a 4000 character input, root caused to parse recomputing normalize per phrase and predating this arc; a live Cerebras readback is the only remaining evidence and cannot run from CI or an agent container; nothing dedupes, so one capture is one provider call and a resubmission is another
STATUS: seventeen negative controls across the arc, each red on the named test and green again on revert; app/services/capture_enrichment.py added with two callers wired; FIXED_AREA_INTENTS added to services/devon/assistant.py and the vendored soul copy synced; 33 new tests across two files, one of them database free and added to the offline CI job and to CLAUDE.md; five CI jobs reproduced locally, 1,739 passed in the full api suite, ruff clean; CI run 643 on 316ec76 green on all five jobs
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
