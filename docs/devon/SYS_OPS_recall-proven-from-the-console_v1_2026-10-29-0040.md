# Recall proven from the console, and the reply that denied it

Status record, 2026-10-29. Closes the recall switch-on arc and carries the one
defect the proof turned up.

## What was open

Tee set `SOUL_RECALL_ENABLED` and the Pinecone key on Railway `api` on
2026-10-15, deployment `84a15677`, as the docstring of
`test_devon_console_signin.py` records. Recall still could not be proven,
because the console he would ask from needed a sign-in it did not have, and its
main script had been dead from 2026-09-10 to 2026-10-16. The sign-in shipped in
PR #351, merged as f559094 on 2026-10-16. From then on the only step left was
his own test from his phone, which no session can run for him because it needs
his DEVON sign-in.

## Measured on 2026-10-29

Tee ran it from his phone between about 00:20Z and 00:29Z on
https://api-production-5644.up.railway.app/console and sent screenshots. What
they show:

- The Soul Layer header read ON. The console sets that when the API's
  `/api/v1/soul/status` answers that recall is enabled, or after a soul recall
  has answered.
- He asked "what did we decide about the render". The plan panel opened with
  `LEDGER FIND the render / Postgres ILIKE / rulings first. Notion is missing.`,
  then `Nothing receipted on the ledger for that.`, then two records labelled
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

1. "Fix it with the close-out": one change that makes the reply say what the
   plan shows, closed out with this record.
2. "Let it expire": during the test the console's first example sentence,
   "Devon, remember the ACX folio needs its own canon folder", was sent and
   filed a real capture request, REQ-BEE656FE4325, to remember it as an ACX
   lesson. A tap on an example only fills the command line, as
   console-smoke.mjs pins, so the line was sent by a separate step after the
   tap; this record does not say which. Nothing is written without an approval
   carrying his ruling key, and an unapproved request closes 72 hours after it
   was raised (`EXPIRY_HOURS` in `services/devon/approval.py`). REFUSE on the
   console only drops it from that tab.

In the same sitting, on the heartbeat arc: job 11, the redo of the NCO Forge
S1E1 outline that failed when its verification card expired undecided, is left
for the Ledger Janitor, which cancels any job non-terminal past 96 hours
through the ledger webhook; and its draft stays in Areas/NCO for now.

## What shipped

In `deploy/soul/console.html`, copied byte for byte to the v10 asset that
`app.main` serves, `findReply(body)` builds the reply from the same answer the
plan draws:

- it counts ledger hits, Tee's rulings (source `tee-soul-layer`) and DEVON's
  notes (any other source, which the plan labels `DEVON NOTED (soul)`);
- it says when the soul search did not finish or withheld records, the two
  cases the plan flags, and only when recall is on, as the plan does;
- a find with nothing at all says which: both searched and empty, or recall
  off and the ledger empty.

`Persona.recall` now answers only a find that failed outright. The production
case reads "I found 2 of your rulings in the soul."

In `apps/web/scripts/console-smoke.mjs`, the browser check that
`panel-smoke-ci.yml` runs, every canned find answer now reads `#sayText` and
must match its own expected reply, and no reply to a find that ran may say the
source went unread. The canned answers grew from six to thirteen: the
production case, a ledger hit beside soul hits, recall off, the recall field
missing, a record from a third source, a hit beside both a failure and a
withheld count, and a ledger hit alone.

## Critics

Three fresh critics ran in isolated worktrees on 2d1f435, with lenses for
honesty of the reply, the record and regressions, and an independent verifier
re-ran each finding. Five were confirmed, all low, and one was refuted:

- A clean empty find still got the "not read" line under a plan saying both
  were searched. Fixed by the empty branches above.
- Seven single line mutations of `findReply` left the browser check green:
  dropping the recall-on condition from either flag, counting notes by one
  source name, rewording the empty reply, swapping which flag wins, forcing
  recall on, and treating a missing recall field as on. The seven new canned
  answers above are aimed at them.
- Three were wording in this record: the stray capture was first written as
  filed by the tap itself, the reproduction below was first written as the
  shipped script's result, and the plan header was quoted without its last
  sentence. All three are corrected here.
- Refuted: that nothing recorded the switch-on. The verifier found the
  sign-in test's docstring, now cited above.

The regression critic found nothing: both console copies byte identical, every
console script parses, both host modes load with no page error, and nothing in
the diff should turn a CI job red that the local run would not.

## Measured

- Reproduced before the fix, in real Chromium against a local API on this
  branch, with a scratch copy of console-smoke.mjs that ran only the production
  case: it failed with the reply "The log holds that, and I have not opened it
  this session. Ask me again with the connector on.", one of Persona.recall's
  two lines, which it picks at random. The shipped script against the pre-fix
  console stops earlier, at the partial case, whose reply it now also pins.
- After the fix: console-smoke 45 checks passed, exit 0, thirteen of them on
  the reply.

## Deploy read back

PR #439 merged as 7deda01 at 01:49:53Z. Read back by deployment id, state and
commit:

- Railway `api`: `4e78c712`, SUCCESS on 7deda01, last updated 02:03:36Z.
- Railway `scheduler-cron`: `b8f4d1a8`, SUCCESS on 7deda01, last updated
  02:15:34Z.
- Railway `presence`: `62d2c38e`, SKIPPED on 7deda01.
- Vercel `devon-soul`: `dpl_2MiZbAw4t8a3s8anffHPkSjvTb3D`, READY, target
  production, on 7deda01.
- Vercel `meta-supreme-apex-genesis-web`: `dpl_4rtRf8bTYEWXVBV1fSdv2iLJY2Q9`,
  READY, target production, on 7deda01.

The served page itself, fetched at 02:16:59Z from
https://api-production-5644.up.railway.app/console, answered 200, contains
`function findReply(body)`, and has sha256 `92cafefb...59f70505`, the same as
`deploy/soul/console.html` at 7deda01. The `devon-soul` console answers 401
without its token, so its page was not read; its record above is the evidence
for that host.

## Open

- Recall from the devon-soul index has not been seen to return a hit on
  production; this test returned tee-soul-layer rulings only.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_recall-proven-from-the-console_v1_2026-10-29-0040
DATE: 2026-10-29
DECISIONS: Tee ruled on cards on 2026-10-29 to fix the console reply together with this close-out, to let the stray ACX capture request REQ-BEE656FE4325 expire unwritten, to let the Ledger Janitor close failed job 11, and to keep its redo draft for now.
FINDINGS: recall answered a real question on production from Tee's phone, two tee-soul-layer rulings for "the render" with an empty ledger and no soul error; the console reply beneath them said the source was unread because it counted ledger hits only, confirmed by an independent verifier in Chromium on 087b201; three fresh critics then confirmed five low findings, all fixed here.
OPEN: no devon-soul hit yet seen on production.
STATUS: findReply ships in both byte identical console copies and console-smoke.mjs pins the reply for thirteen canned find answers; reproduced failing before the fix and 45 checks passing after it; PR #439 merged as 7deda01, Railway api 4e78c712 and scheduler-cron b8f4d1a8 SUCCESS, both Vercel production deployments READY, and the production console serves the fixed page byte for byte.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
