# SYS_OPS: the Anthropic funding lane

Date: 2026-09-11. Supersedes nothing. Extends
`SYS_OPS_the-tqo-render-lane-and-two-content-stores_v1_2026-09-10.md`, which
left "confirm the Anthropic credential the script lane calls is funded" open.
That item is now closed, and not by funding it.

## What Tee asked for

"I need a solution for the anthropic api nodes on n8n. I cant afford to fund
it." Then, on a card, two rulings: move the lane to Gateway credits, and leave
the Gumroad buyer sync live.

## The answer, in the order it was found

The first answer was the cheap one: TQO FINAL V5 called
`claude-sonnet-4-6` in six places, and `claude-sonnet-5` is priced at 2 dollars
in and 10 dollars out per million tokens against 3 and 15, so the same lane on
the newer model costs a third less. That swap shipped first.

The better answer was already running in his own estate and nobody had noticed
it. `OS 29 Platform Policy Sensor` calls Claude through the native
`@n8n/n8n-nodes-langchain.anthropic` node with no credential attached at all,
and its own node note says why: it is on Gateway credits. Execution 6713 on
10 September carries three successful calls, `model: claude-opus-5`, real token
counts, no key of Tee's anywhere in the request. `list_n8n_gateway_services` on
the cloud instance reports `available: true` with `anthropicApi` in the
credential list and that node in the covered set.

So the six V5 calls did not need a cheaper model. They needed to stop being
HTTP Request nodes.

## What shipped, in three published versions

**Version a04712d7 was the state at the start of this arc.** There was an
unpublished draft sitting on top of it, `e090c078`, created about thirty
minutes after the previous arc's publish, and publishing anything would have
published that too. All 51 differing nodes were classified before anything else
happened: four differ only in canvas position, zero keys were added, zero non
position values changed, and every other difference is a parameter dropped
whose live value equals the node default, which is what the n8n editor does
when it re-serialises a workflow someone opened. The one difference that could
have been real was `Short Engine: Create Rows` dropping
`operation: "insert"`. Two independent checks settled it: the node catalog
reports `insert` as the dataTable node's default operation, and of the 29
dataTable nodes in the graph, `operation` was dropped from exactly the one whose
value was `insert` and kept on all 28 carrying `get`, `update` or `upsert`.
Cosmetic. Safe to publish over.

**Version eeae1ffd: the model swap, plus one defect the verification found.**
The six `Build*Prompt` code nodes moved from `claude-sonnet-4-6` to
`claude-sonnet-5`, one occurrence each, six total, verified by sha256 of each
node body read back from the API against the body computed locally. Every one of
the other 216 nodes was confirmed byte identical.

The read back also produced eleven nodes whose only difference was a credential
display label, because three credentials had been renamed in the n8n UI at some
point: `Header Auth account 3` is now `Antrhropic`, spelled that way, `account 8`
is `JSON2VIDEO` and `account 7` is `MailerLite`. Every credential id was
unchanged, so nothing moved. But reading that diff surfaced the real finding:
`Gumroad: MailerLite Buyer Sync` POSTs to
`connect.mailerlite.com/api/subscribers` while bound to
`TEJIJDPoEhid0aOE`, the credential that authenticates all six
`api.anthropic.com` calls. Its own note says what it should have been: "Attach
the same MailerLite credential used by Create Draft Campaign." So this was not
a guess about intent, it was written down and not done.

Two consequences, both live since the node was built. MailerLite rejects the
call, so no Gumroad buyer has ever been added to an offer group and the buyer
sequence has never started; `onError` is `continueRegularOutput` and
`retryOnFail` is on, so it failed silently three times per sale while
`Gumroad: Attribute Revenue` downstream carried on as though it had worked. And
the header that authenticates Anthropic was being sent to a third party host on
every sale. Rebound to `eYTecIAkpa16GAQ6`. Tee ruled on a card to leave it
enabled, so the next real sale is also the first time that sequence has ever
fired.

**Version b667807f: the six calls moved to Gateway credits.** Each HTTP Request
node was replaced by a native Anthropic node under the same name, at the same
canvas position, with the same one in one out wiring and the same per node retry
and `onError` settings where they existed. `modelId`, `system` and `maxTokens`
are expressions reading the body the node is handed, not hardcoded values, so
the model still lives in one place per lane, `Build X Prompt`, and the ceiling
still lives in `Token Budget: X`. Hardcoding the model into six new nodes would
have left `claudeBody.model` as dead but plausible data, which is the same
silent no op shape as the `provider` literal caught in the previous arc.
`simplify` is false, so the raw API shape reaches the parse nodes unchanged;
they read `content` and `stop_reason` only, never `statusCode`, `headers` or
`$json.body`. No `temperature`, `topP` or `topK` is set anywhere, because
Sonnet 5 returns a 400 on any sampling parameter.

The expression driven `modelId` was not assumed to work. A throwaway workflow,
`utBPYvpMyJtSBsaF`, was built with one code node emitting a `claudeBody` in the
same shape the V5 builders emit and one native Anthropic node reading it through
expressions. Execution 6775 returned `model: claude-sonnet-5`, the text
`PROBEOK`, and real token usage, on an auto assigned credential n8n names
`Gateway credits` with `source: aiGateway`. Only then was the pattern applied to
V5. The probe is archived.

After the conversion, `TEJIJDPoEhid0aOE` appears nowhere in the workflow, and
neither does `api.anthropic.com` outside the documentation notes. TQO FINAL V5
no longer holds or sends an Anthropic key.

## A number this session had wrong

The swap's own version description said the `max_tokens` values were left as
they were, at 4000, 24000, 1500, 6000, 5000 and 8000. Those are the values in
the `Build*Prompt` nodes, and they are not what gets sent. Each
`Token Budget: X` node sits between the builder and the call and overwrites
`max_tokens` on the way through. The effective ceilings are 7000 for the
manifest, 24000 for packaging, 3000 for the brief, 10000 for the script, 9000
for QC and 12000 for the doctor. Nothing was changed in either layer, so no
behaviour moved, but the statement described the wrong layer as operative.

## The cost of the ruling, stated plainly

Gateway credits is an n8n Cloud feature. `list_n8n_connect_services` on the VPS
returns `available: false`. So this pins the TQO render lane to n8n Cloud: the
day it moves to `n8n.editforge.online`, these six nodes go back to HTTP Request
with a funded Anthropic key, or the lane does not run. That is a real constraint
on the cutover recorded in
`SYS_OPS_n8n-cloud-to-vps-cutover_v2_2026-09-06.md`, and it was put to Tee on
the card before he ruled. Converting back is the same six node edit in the other
direction.

## DEVON RECEIPT

```
AREA: TQO, Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-anthropic-funding-lane_v1_2026-09-11
DATE: 2026-09-11
DECISIONS: Tee ruled on a card to move the six Anthropic calls in TQO FINAL V5 onto n8n Gateway credits rather than keep paying for them on his own key, accepting that this pins the TQO render lane to n8n Cloud because the VPS reports Gateway credits unavailable, and accepting that converting back is part of the cutover cost if the lane ever moves. He also ruled to leave the repaired Gumroad buyer sync enabled, so the next real sale is the first end to end exercise of that MailerLite sequence. Earlier in the same arc he ruled the single word Swap twice, first for the model change and then for the Gateway conversion. The model was left as the one source of truth inside each Build X Prompt node rather than hardcoded into the six new nodes, which was a judgement call taken to avoid leaving dead but plausible data behind, not a ruling.
FINDINGS: the estate already had the answer to the funding problem running unnoticed, OS 29 Platform Policy Sensor calling Claude on Gateway credits with no key attached, proved by execution 6713 returning three successful claude-opus-5 calls with real token counts; the 51 node unpublished draft sitting on V5 was an editor re-serialisation, four position nudges and the rest parameters dropped whose values equal node defaults, settled for the one ambiguous case by the node catalog reporting insert as the dataTable default and by operation having been dropped from exactly the one insert node out of 29; Gumroad: MailerLite Buyer Sync was bound to the Anthropic credential while POSTing to connect.mailerlite.com, so no Gumroad buyer has ever reached an offer group and the header authenticating Anthropic was being sent to a third party on every sale, failing silently three times per sale because onError is continueRegularOutput and retryOnFail is on, with the node's own note naming the credential it should have had; three n8n credentials had been renamed in the UI, account 3 to Antrhropic spelled that way, account 8 to JSON2VIDEO, account 7 to MailerLite, which is why eleven unrelated nodes showed a diff on read back with every credential id unchanged; the effective max_tokens for each lane comes from the Token Budget nodes, 7000, 24000, 3000, 10000, 9000 and 12000, not from the numbers in the Build X Prompt nodes, correcting a statement made in this arc's own first version description; Gateway credits is a cloud only feature, list_n8n_connect_services on the VPS returns available false
OPEN: no V5 lane has yet executed end to end on Gateway credits, because every schedule trigger is still disabled and running the pipeline by hand would write real rows, so the conversion is proven at the node level and on an isolated probe but not on a full episode; the first real Gumroad sale is also the first execution of the repaired buyer sync and nobody has watched that MailerLite sequence run; the previous arc's open items all stand, which are the ElevenLabs key rotation at the provider with the VPS credential updated in the same sitting before the voice hold lifts, the publish gate comparing Human Review against boolean true while the data table column is a string so no data table row can clear it, the watchdog alarm never having been seen to fire on a live Error row, the TSWS lane's writes being unverified so its watchdog scan cannot be pointed correctly, TSWS 00 still carrying a literal placeholder worker URL that has never once succeeded, the Devon Capture Key credential still empty on the VPS at reach 24, the 45 grandfathered SYS_OPS docs needing a ruling, and the contrast pass on /control; prompt caching on the long system blocks and the Batch API on the non urgent passes were offered and not ruled on, and matter less now that the calls are on credits
STATUS: shipped to the live estate, not to this repository's runtime. TQO FINAL V5 published three times in this arc and verified after each: eeae1ffd carrying the six model swaps with every node body sha256 matched against the locally computed body and the other 216 nodes byte identical, then b667807f carrying the six native Anthropic nodes on Gateway credits with connections, positions, per node retry settings and the six prompt builder hashes all re-verified against the previously published version. versionId equals activeVersionId at b667807f, so no undrafted delta remains. The Gumroad credential rebind is live in both. The throwaway probe utBPYvpMyJtSBsaF is archived. No repository code changed in this arc; this document is the only artifact.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
