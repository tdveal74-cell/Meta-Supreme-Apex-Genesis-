# The VPS cutover, executed

Written 2026-09-15, the night the switch ran. Supersedes the plan in
`SYS_OPS_the-vps-cutover-handover_v1_2026-09-15.md` as the record of what
happened, and `SYS_OPS_the-vps-cutover-step-one_v1_2026-09-15.md` as the record
of where it stood at step one. The handover remains the plan of record for why
the order is what it is.

Every DEVON organ now runs on the VPS. Cloud runs none.

## The switch

Measured immediately after, by reading both instances rather than by trusting
the script that did it:

| | before | after |
|---|---|---|
| DEVON organs active on Cloud | 34 | 0 |
| DEVON organs active on the VPS | 2 | 34 |
| organs live on both at once | 0 | 0 |

The two already live on the VPS were the Error Alarm and the OS Error Handler,
which the handover put there deliberately so failures are caught from the first
minute. They were.

`scripts/vps_cutover_switch.py` walks Cloud leaf to core and the VPS core to
leaf, refuses to run if any organ in the list is missing from its tier table,
and is idempotent so an interrupted pass is finished by running it again. It
reported 40 organs, 0 failed.

**It mirrors Cloud rather than publishing everything.** Six organs are
deliberately dormant on Cloud: `purge-list`, `master-index`, `vault-compare`,
`e2e-harness`, `table-reader` and `capture-hook`. Those are manual tools and a
read only debug reader. Tee's ruling is that the estate runs on the VPS, not
that a manual tool becomes a scheduled one, so the switch left them dormant.
That is a judgement made during execution and it is his to overturn.

## The rebuild, before the switch

All 40 organ pairs were rebuilt over the n8n REST API and every one verified
clean. The 19 caller facing webhook ids were unchanged by the write, checked
before and after. No VPS copy still names the Cloud host, so the HOST constants
behind the Approval Queue's approve and reject links landed correctly.

A rebuilt organ was executed live on the VPS as a smoke test before anything
was published: the Learning Lane Table Reader read all four data tables through
their remapped ids, returning 1, 2, 8 and 23 rows.

The first full dry run failed 14 organs and both causes were in our own tooling,
not the estate. Thirteen failed a webhook guard that treated every `webhookId`
as caller facing; measured across all forty, 15 nodes change type from `gmail`
to `emailSend`, the un-migrated half of the 2026-09-05 move to SMTP, and no
trigger node changes type anywhere, so no inbound URL was ever at risk. The
fourteenth was the Gumroad organ, whose six nodes sat on older `typeVersion`s
while being written Cloud's parameters, which is the more dangerous half of
that drift. Both are fixed in the committed tooling.

## The ledger

Nothing moved, because nothing was open. The Cloud ledger `VYyno7pDWmY6uxBz`
holds 21 rows and every one is terminal, 12 CANCELLED and 9 COMPLETED,
measured with both the filter and its complement so the zero is a real zero,
and re-measured immediately before the switch. The VPS table
`QZvdxllOjWevb3Vo` holds the eight terminal rows of the 2026-09-03 snapshot and
their `intent_id` values are all present on Cloud. Tee's rule is that open jobs
move and terminal ones stay, so the correct action was to move nothing.

## The doors

17 webhook doors are live on the VPS, 16 key protected and one deliberately
open because its token is the auth.

Every key protected door refuses an unkeyed caller. **All 16 answer 403, not
the 401 the handover predicts.** The body is `Authorization data is wrong!` and
the response carries `www-authenticate: Basic realm="Webhook"`, so that is
n8n's own auth layer refusing and not a proxy. The refusal is correct; the
expected status code in the handover is wrong.

Every one of the 16 accepts the Devon Capture Key, driven from inside n8n
because no session holds the secret. Zero 403s. The health console answered 200
with `status: healthy`, and the Action Router, Drive Draft Writer and Airtable
Row Writer each answered `REFUSED: no envelope in the request`, which is the
fail closed behaviour the invariants require.

**That proof cost Tee seven emails.** The probe body was deliberately invalid,
and six organs threw genuine faults rather than refusing cleanly: Spine,
Runtime, Ledger, Intelligence Router, Capture Webhook, EditForge Handoff and
Event Bus. The OS Error Handler classified each as a fault and sent, unthrottled,
at 23:39:32Z. A cleaner proof would have used a well formed envelope that fails
validation rather than garbage that throws. The consolation is that this proved
the VPS error lane end to end on its first night.

## The credential that was nearly a leak

`Header Auth account 10` had no VPS twin, and the rebuild named the two nodes
that wanted it: `Create Notion Page` and `Find Existing Page` in the Notion
Buffer Drain. The VPS copy of `Create Notion Page` was bound to
`WpZNTg9qduOFC5NM`, which the VPS credential store says is the **TSWS Render
Worker**, under a display name cached from Cloud that read `Header Auth
account 10`. Publishing it would have sent the render worker's token to
`api.notion.com`. Nothing leaked, because that copy was never published.

Tee created `Notion Integration Token` `bQZHyw6TfiBHmFmE`. The token was proved
rather than assumed: `GET /v1/users/me` answered 200 as bot `n8n vps`. It was
not sufficient on its own, and the second probe is why. `GET /v1/databases/...`
answered 404 `object_not_found` and `POST /v1/search` returned exactly one
shared object, a page whose parent was the target database. The integration had
been connected to a single row rather than to the database. After Tee connected
the database itself, both the read and the query answer 200. The credential map
now holds 29 pairs and `credentials_with_no_vps_twin` is empty.

## What the reconciler found

`scripts/estate_reconcile.py check` ran against the VPS for the first time,
because the key that makes it possible only existed from tonight. It reported
71 OK and 3 drifts, of which two were repaired here and one belongs to Tee.

Repaired:

- `vault.WEBHOOKS` recorded the Face's chat door as
  `71510ab0-07eb-42d8-9734-c0741b398d49/chat`. That id is the chat trigger's own
  `webhookId` and is instance specific, so it did not survive the move. The live
  VPS door is `bf371d93-da93-4e81-b50b-4ffe988aeae5/chat`. The repointing pass
  rewrote id fields and could not see an id embedded in a path string, so
  anybody reading the vault for DEVON's chat URL would have got a dead Cloud
  link.
- `Soul Index Setup` and `Build 08 Credential Probe` were recorded as inactive
  and are absent, because both were one shot throwaways that only ever existed
  on Cloud. They are now recorded as retired and Cloud only rather than deleted,
  because older status docs cite the executions they produced.

Open, and not this arc's to change:

- `OS 29 Platform Policy Sensor` is recorded active and its VPS copy is
  inactive. It is not in the cutover list and the switch never touched it. It
  runs on Cloud, where it was improved through 2026-09-08, while its VPS copy is
  the untouched 2026-08-31 export. It is a TQO organ that the DEVON cutover does
  not cover, and whether it moves is Tee's call.

## What is still live on Cloud

Six workflows, none of them DEVON: the OS 29 Platform Policy Sensor and TSWS 01
through 05.

**The five TSWS workflows are marked active on both instances at once**, which
is the failure shape the handover warns about, though for TSWS rather than DEVON
and predating this switch. Graded before raising: `TSWS 01 Post-Production
Master` is the only one with a self firing trigger, a five minute schedule, and
that node reads `disabled: true` on **both** hosts. TSWS 02 through 05 are
`executeWorkflowTrigger` sub-workflows that only run when a master calls them.
Neither master has executed recently, Cloud last on 2026-09-10 in `integrated`
mode and the VPS never, and neither workflow suppresses execution saving, so
those counts are real rather than hidden.

So this is a latent double arm, not active duplication. It becomes real the
moment someone runs a master manually on the wrong host or re-enables that
schedule node. The handover forbids rebuilding the TSWS chain from its Cloud
copies, so nothing here was changed.

## What is not proven yet

- No real job has been driven end to end through the intake, a card, an
  executor and the verification card since the switch.
- The first Driver Poll and the first Heartbeat have not been watched firing on
  the VPS.

Both need wall clock rather than work, and neither is claimed.

### Amended 2026-09-16, after both were watched

The Driver Poll fired on its own at 00:00:41Z, execution 153, mode trigger. It
read the ledger's 8 rows, found 0 open jobs and passed quietly, which is the
correct answer for an empty queue and is the first scheduled organ to run on the
VPS without a human starting it.

A real job was then filed through the front door at 00:36:07Z. A throwaway
workflow posted a well formed envelope to
`https://n8n.editforge.online/webhook/devon-intake` carrying the Devon Capture
Key, an `airtable.row` payload for the Inbox Captures table, and the idempotency
key `vps-cutover-proof-20260916`. The throwaway is archived. What the estate did
with it, read from the ledger row rather than from the response body:

- intent `01M2KT8WM4RPZ90BCTZPVXH6HK`, ledger row 9, 12 trace events, written at
  00:36:14Z
- the spine advanced RECEIVED to UNDERSTANDING on `VUXIyCaur9lejAhL`
- the runtime loaded the area, recalled 8 prior Systems jobs with 0 open, and
  planned
- the router raised the stated level 1 to level 2 on the blast radius floor and
  sent it to WAITING_APPROVAL, because a reversible write still passes the queue
- the brief came back from cerebras gpt-oss-120b recommending proceed
- card `REQ-20260916-37xZi6` is pending in the queue, expiring 2026-09-19T00:36:11.577Z
- the card names its executor, the table, the payload fingerprint 068eeb86 and
  the first 182 characters of the body, so Tee can read what will be written
  before he decides

Nine organs ran on the VPS to produce that: intake, spine, runtime, the intel
router, the approval queue, the ledger, the event bus and the two the router
called through. The job stops there and is meant to. The executor does not run
until Tee taps the card, which is the WRITE gate invariant doing its job rather
than a fault, so the executor and the verification card stay unproven until he
does.

The Heartbeat still reads 0 executions at 00:38Z. Its cadence is six hours, so
that is wall clock and nothing else. It is the last item on this list.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-vps-cutover-executed_v1_2026-09-15.md
DATE: 2026-09-15
DECISIONS: Tee authorised the full switch in one pass after being shown that the Notion database read answered 200. He created the Notion Integration Token bQZHyw6TfiBHmFmE and connected the target database to the n8n vps integration. The switch mirrors Cloud's active state rather than publishing all forty, so the six organs deliberately dormant on Cloud stay dormant on the VPS; that was a judgement made during execution and is his to overturn. The TSWS chain was left untouched on both hosts because the handover forbids rebuilding it.
FINDINGS: The switch moved 34 DEVON organs from Cloud to the VPS with zero failures and zero organs live on both, verified by reading both instances afterwards rather than trusting the script. All 40 organ pairs rebuilt and verified clean beforehand with all 19 caller facing webhook ids unchanged. The ledger moved nothing because all 21 Cloud rows are terminal. All 16 key protected doors refuse an unkeyed caller with 403 and not the 401 the handover predicts, the body reading Authorization data is wrong with a www-authenticate header, so it is n8n's own auth layer; all 16 accept the key. The door proof sent seven fault emails to Tee at 23:39:32Z because the probe body was garbage that threw rather than a well formed envelope that fails validation. The VPS copy of Create Notion Page had been bound to WpZNTg9qduOFC5NM, the TSWS Render Worker credential, under a display name cached from Cloud, so publishing it would have sent that token to api.notion.com; it never was published. The Notion integration was first connected to a single database row rather than to the database, which answers 404 object_not_found rather than 401. estate_reconcile reported 71 OK and 3 drifts; the Face's chat door id and the two Cloud only one shots were repaired here. The five TSWS workflows are active on both instances, but the only self firing trigger among them is disabled on both hosts, so it is a latent double arm and not active duplication.
OPEN: Amended 2026-09-16. The first Driver Poll fired on its own at 00:00:41Z, execution 153, and passed quietly on an empty queue. A real job was filed through the intake at 00:36:07Z and reached the approval card: intent 01M2KT8WM4RPZ90BCTZPVXH6HK, ledger row 9, 12 trace events, card REQ-20260916-37xZi6 pending. It stops at the card because the executor waits on Tee's tap, so the executor and the verification card are still unproven and are his to unblock. The Heartbeat has still not fired; it reads 0 executions at 00:38Z on a six hour cadence. OS 29 Platform Policy Sensor is recorded active while its VPS copy is inactive; it runs on Cloud, is outside the cutover list, and whether it moves is Tee's call. The five TSWS workflows remain armed on both hosts. The Vercel account is blocked, so nothing can deploy to either Vercel surface until a human clears it, though nothing is currently owed to either.
STATUS: The cutover is executed. Every DEVON organ runs on the VPS and Cloud runs none of them. Proof of a live job and of the first scheduled organs firing is outstanding.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
