# The rules had no exception layer

Dated 2026-09-17. Tee handed over a competitive teardown of the AI Impact
channel, dated 14 August 2026, and asked for the valuable parts to be taken.
Two ideas in it are worth taking, both are absent from this repository, and both
are now code with tests. Most of the rest of the document is either already
built here in a stronger form, or is a finding about the live estate that this
session did not re-verify and will not restate as current.

## What the source is

A 44 video teardown of `@aiimpact1`, a read of the open source repository
`github.com/starmynd-org/infinite-brain-os` (MIT), and a read-only pass over
Tee's Airtable, Drive and n8n on 14 August. It is a good document. It corrects
itself twice in its own receipts section, names what it did not verify, and
refuses to reproduce a benchmark whose method was never published. That posture
is the reason its ideas are worth reading rather than the ideas themselves.

Its live-state findings are 34 days old as of today. A credit balance, an
execution census with an eight day retention window, and two hosts reachable
over plain HTTP are all things that change. Nothing in this commit encodes any
of those numbers, and nothing below claims any of them still holds.

## What was already here, so it was not imported again

The teardown lists six things worth taking outright from the upstream
repository. Four of them are already built here, and built harder.

Its eight key frontmatter contract is this estate's nine key receipt, enforced
by `test_devon_receipt_shape.py` against every status doc that is not on the
migration backlog. Its lifecycle with operator-only promotion is the human gate
on every WRITE and HIGH_IMPACT tool call, plus human gated skill promotion. Its
1,089 line validator that fails the build is `test_devon_integrity.py`,
`test_devon_receipt_shape.py` and `test_estate_reconcile.py`, which between them
check provenance, the dash ban, the absence of a network capability in
`services/devon`, and the skill inventory counted from the directory rather than
from a sentence. Its session layer, one row per run so a dead chat can be
resumed, is the state ledger and the effect receipts.

Its context traffic light and its three tier model router were left alone. The
first is a habit, not a system. The second overlaps the provider routing and
spend cap that already exist, and rebuilding it on a teardown's summary rather
than on a measurement of this estate's own call mix would be guessing.

## The first import: rules that know whether they bend

`services/devon/rule_ledger.py`.

The idea is the teardown's one genuinely good steal, and it comes from the
Infinite Brain video: store the anti patterns beside the best practices as
records of the same standing, because a best practice is right most of the time
and the rest of the time is the part that has to be written down.

The finding it lands on is sharper than the idea. The TQO show canon is roughly
four thousand words inside a single n8n node, carrying a long ABSOLUTE RULES
block with no exception layer at all. Every rule in it reads as unconditional.
A model given a rule that is absolute and a case the rule does not fit will
either obey it stupidly or break it silently, and nothing records which one
happened.

The module splits rules into two classes and makes the split load bearing.
Compliance rules do not bend, and the constructor refuses one that carries an
exception or a scope, because a scope reads as a condition and a compliance rule
has none. The domains are the ones Tee's own standing rules name: platform
policy, AI disclosure, authorship, rights, channel identity. Craft rules bend,
must declare at least one scope so they are not shipped on every episode
regardless, and each exception carries evidence. An exception with no evidence
is refused outright, which follows the standing rule against widening a rule on
speculation about intent.

The part that matters most is the guard. Fragmenting a monolith into scoped
fragments introduces a failure this estate has no defence against: an assembled
prompt that quietly dropped a rule, producing a run that looks exactly like a
run that kept it. `check_assembly` refuses an assembly missing any compliance
rule, an assembly carrying a rule that is not in the ledger, and an assembly
whose rendered text falls under a floor. The floor has no default value. A
floor nobody measured is a guess, and the caller has to pass the number it
measured from the monolith the fragments replaced.

`test_an_assembly_missing_a_compliance_rule_is_refused` builds the broken
assembly by hand rather than through the constructor, because a guard tested
only against input its own code produced proves nothing.

## The second import: a prediction recorded before the measurement

`services/devon/wager.py`.

The first law in `CLAUDE.md` already says a fix is not fixed until it is
re-measured. That closes the loop on whether a change worked. It says nothing
about whether anyone knew in advance what the change would do, and those are
different questions. A measurement taken afterwards can be read to fit whatever
happened. A number written down before the run cannot.

The teardown pays for that gap inside its own build plan and says so: nobody
knows the render lane's cycle time from Queued to Ready, the author included, so
every budget in the plan is a guess with no way to tell later how bad a guess it
was.

A `Wager` carries a subject, a metric, a measured baseline, and a predicted
value. Both the baseline and the outcome are `Measurement` objects, and a
`Measurement` with no receipt is refused, in the same shape as a `Finding` with
no evidence in `flagship.py`. Reading `miss`, `actual_delta` or `direction_held`
on a wager that has not been settled raises rather than returning a number, so
an open prediction cannot be quoted as a result. Settling twice is refused.

`direction_held` is separate from the size of the miss on purpose. Predicting a
20 point gain and getting 5 is a bad estimate of a real effect. Predicting a 20
point gain and getting minus 3 is a wrong theory. Only one of those is a reason
to stop.

`WagerBook.calibration` returns None over zero settled wagers rather than a
bias of 0.0, because a bias of zero measured over forty wagers and a bias of
zero measured over none print identically and mean opposite things.
`WagerBook.adjust` is the carry forward: consistently optimistic by five points
on a metric means the next prediction on that metric starts five points lower,
and when there is no record to carry, the prediction comes back untouched with a
reason saying it is the first one and it is a guess.

## What this does not do

Neither module is wired into a lane. They are doctrine, effect free, sitting
beside `precedence.py` and `flagship.py`, and importing them does nothing. The
show canon is still four thousand words inside an n8n node, and moving it is a
separate job that touches the live estate rather than this repository.

Nothing here re-verified a single live-state claim in the teardown. The
Anthropic balance, the render and TTS host exposure, the unrotated credentials,
the row counts and the execution census were all read on 14 August by someone
else and are reported unverified here. Two of them are security items with a
clock on them and they are on the card in this session, not closed by this
commit.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-rules-had-no-exception-layer_v1_2026-09-17-1440.md
DATE: 2026-09-17
DECISIONS: Two of the teardown's ideas were taken as code and the rest were refused with reasons. Taken: the exception layer on rules, and the wager. Refused as already present in a stronger form: the eight key frontmatter contract, lifecycle with operator-only promotion, the validator that fails the build, and the session layer. Refused as not worth building on a summary: the context traffic light, which is a habit rather than a system, and the three tier model router, which overlaps the existing provider routing and spend cap and would need a measurement of this estate's own call mix rather than a teardown's description. The assembly floor was given no default value, so a caller has to pass a number it measured. Compliance rules were defined by the five domains Tee's standing rules already name rather than by a new list invented here.
FINDINGS: The TQO show canon is roughly four thousand words inside one n8n node and its ABSOLUTE RULES block carries no exception layer, so every rule in it reads as unconditional. This repository had no way to express a rule that bends, and no guard against an assembled prompt silently dropping a rule that may not be dropped. It also had no record anywhere of a prediction made before a measurement: grep found no wager and no calibration of predictions against outcomes in services, app or the root test files. The first law requires a fix to be re-measured and does not require anyone to have known in advance what it would do. Separately, adding a module to services/devon is three places rather than one: test_deploy_soul.py globs that directory and requires a byte identical vendored copy under deploy/soul/services/devon, and the full api suite is the only check that catches a missing one. The standalone job, ruff and the new modules' own tests were all green while the deployed soul service would have shipped without the new rules. That is now written into CLAUDE.md.
OPEN: Neither module is wired into a lane, so the show canon is still a monolith in a node and moving it touches the live estate rather than this repository. Every live-state finding in the teardown is 34 days old and was not re-verified here: the Anthropic credit balance, the render and TTS hosts reachable over plain HTTP by bare IP with the TTS node at authentication none, five credentials unrotated since roughly 17 July including a raw Airtable token used by 33 nodes, the 790 execution census, and the 204 content row distribution. The render lane exposure was still recorded in this repository as recently as 2026-09-10 and the readiness audit of 2026-09-15 still listed a rotation as open, so neither is demonstrably closed, but neither was checked against the live estate in this session. The packaging findings in section 06 of the teardown are a brand decision for Tee and nothing was done with them.
STATUS: On branch claude/review-incorporate-feedback-ke22i8, not merged. Measured locally on the final tree: 38 new tests pass; three mutations of the two load bearing guards each produced a named failure and were reverted; the standalone job reproduced with PYTHONPATH unset is 938 passed exit 0; the full api suite is 3049 passed exit 0; python3 -m ruff check . is clean, which is where the stale type annotation left by a rename was caught after the module's own tests had passed it. Not shipped, not merged, awaiting Tee.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
