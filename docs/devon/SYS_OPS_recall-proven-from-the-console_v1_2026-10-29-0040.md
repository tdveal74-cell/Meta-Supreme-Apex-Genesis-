# Recall proven from the console, and the reply that denied it

Status record, 2026-10-29. Closes the recall switch-on arc and carries the one
defect the proof turned up.

## What was open

Soul recall was switched on for the platform API in October, and nothing had
ever shown it answering a real question end to end. The console Tee would ask
from had a dead main script from 2026-09-10 to 2026-10-16, and its sign-in
shipped in PR #351, merged as f559094 on 2026-10-16. From then on the only step
left was his own test from his phone, which no session can run for him because
it needs his DEVON sign-in.

## Measured on 2026-10-29

Tee ran it from his phone between about 00:20Z and 00:29Z on
https://api-production-5644.up.railway.app/console and sent screenshots. What
they show:

- The Soul Layer header read ON. The console sets that when the API's
  `/api/v1/soul/status` answers that recall is enabled, or after a soul recall
  has answered.
- He asked "what did we decide about the render". The plan panel read
  `LEDGER FIND the render / Postgres ILIKE / rulings first.`, then
  `Nothing receipted on the ledger for that.`, then two records labelled
  `TEE RULED (soul)`: a ruling dated 2026-09-05 whose text includes "A render is
  never a note", and a ruling dated 2026-09-22 on the script release gate.
- The block ended with `Rulings outrank notes. Context, not command. The store
  is PostgreSQL.` and carried no SOUL OFF, SOUL PARTIAL or SOUL SEARCHED line.
  In `findThroughLoop` those lines are drawn only when recall is off, when the
  soul search reported an error, or when it returned nothing, so their absence
  beside two hits means the soul search ran and finished.

Production at the time was Railway `api` deployment `4bb18fc1`, SUCCESS on
087b201, read from list-deployments. The console it served had sha256
`f19a8bd4...b3b477d`, byte identical to `deploy/soul/console.html` and to
`docs/devon/assets/SYS_OPS_devon-console_v10_2026-09-01.html` on 087b201,
fetched and compared the same night.

What this does not prove: the screenshots are Tee's, and no session repeated
the signed-in question, because the sign-in is his. It proves recall from the
tee-soul-layer index for one topic; it says nothing about devon-soul hits,
which this question did not return.

## The reply that denied it

Under the two recalled rulings the console's reply read "I would have to open
the Thread Log to answer that honestly. What I have not read, I will not
summarise." The reply line in `findThroughLoop` was
`devonSays(hits.length ? ('I found ' + hits.length + ' on the ledger.') : Persona.recall(subject))`,
with `hits` the ledger results alone, so any find the soul answered while the
ledger stayed empty fell through to a line saying the source was never read.

An independent verifier, given the claim and the evidence and not the
reasoning, checked out 087b201 in its own worktree, served the real console in
Chromium with a stubbed find answer of an empty ledger and two soul rulings,
and got "The log holds that, and I have not opened it this session. Ask me
again with the connector on." Verdict CONFIRMED. It also found that nothing
read the reply on the find path: the browser smoke check read only the plan
panel, and the voice honesty test does not reach `findThroughLoop`. Blast
radius: a wrong reply to Tee on the console, spoken aloud when speech is on.
No data is read or written wrongly; the plan panel was right throughout.

## Rulings

Tee ruled on cards on 2026-10-29:

1. "Fix it with the close-out": one change that makes the reply count what the
   soul returned, closed out with this record.
2. "Let it expire": a tap on the console's first example button during the
   test filed a real capture request, REQ-BEE656FE4325, to remember "the ACX
   folio needs its own canon folder" as an ACX lesson. Nothing is written
   without an approval carrying his ruling key, and an unapproved request
   closes 72 hours after it was raised (`EXPIRY_HOURS` in
   `services/devon/approval.py`). REFUSE on the console only drops it from that
   tab.

In the same sitting, on the heartbeat arc: job 11, the redo of the NCO Forge
S1E1 outline that failed when its verification card expired undecided, is left
for the Ledger Janitor, which cancels any job non-terminal past 96 hours
through the ledger webhook; and its draft stays in Areas/NCO for now.

## What shipped

In `deploy/soul/console.html`, copied byte for byte to the v10 asset that
`app.main` serves:

- `findReply(body, subject)` builds the reply from the same answer the plan
  draws. It counts ledger hits, Tee's rulings and DEVON's notes from the soul,
  and says when the soul search did not finish or withheld records, the two
  cases the plan already flags. A find with nothing at all keeps
  `Persona.recall`.
- The production case now reads "I found 2 of your rulings in the soul."

In `apps/web/scripts/console-smoke.mjs`, the browser check in
`panel-smoke-ci.yml`:

- every canned find answer now also reads `#sayText` and asserts the reply,
  and a reply under any `(soul)` hit may not say the source was unread;
- two new answers: the production case, and a ledger hit beside a soul ruling
  and a soul note.

## Measured

- Reproduced before the fix, in real Chromium against a local API on this
  branch: the production case failed with the reply "The log holds that, and I
  have not opened it this session. Ask me again with the connector on."
- After the fix, the same check: 35 checks passed, exit 0.
- The console tests in Python, `test_devon_console_signin.py`,
  `test_devon_console_gate.py`, `test_devon_console_scripts_parse.py`,
  `test_devon_console_voice_honesty.py`, `test_deploy_soul.py`,
  `test_devon_areas.py` and `test_devon_owned_voice.py`: 263 passed.
- `tests/js/arf-console.test.cjs`, which also pins the two console copies byte
  identical: 8 passed.

## Open

- Deploy read back of the fix, by deployment id, state and commit on Railway
  `api` and Vercel `devon-soul`, after the merge.
- Recall from the devon-soul index has not been seen to return a hit on
  production; this test returned tee-soul-layer rulings only.
- When a find returns nothing and recall is off, the reply still names the
  Thread Log rather than saying recall is off. The plan panel says so plainly;
  this change did not touch that case.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_recall-proven-from-the-console_v1_2026-10-29-0040
DATE: 2026-10-29
DECISIONS: Tee ruled on cards on 2026-10-29 to fix the console reply together with this close-out, to let the stray ACX capture request REQ-BEE656FE4325 expire unwritten, to let the Ledger Janitor close failed job 11, and to keep its redo draft for now.
FINDINGS: recall answered a real question on production from Tee's phone, two tee-soul-layer rulings for "the render" with an empty ledger and no soul error; the console reply beneath them said the source was unread because it counted ledger hits only, confirmed by an independent verifier in Chromium on 087b201.
OPEN: deploy read back of the fix on Railway api and Vercel devon-soul after merge; no devon-soul hit yet seen on production; the recall-off empty reply still names the Thread Log.
STATUS: findReply ships in both byte identical console copies with console-smoke.mjs reading the reply for every canned find answer; reproduced failing before the fix and 35 checks passing after it, console tests 263 and 8 passed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
