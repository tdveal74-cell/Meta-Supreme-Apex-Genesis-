# Rakazo lane producers: four show bots, an idea bot, and the n8n handoff

Filed 2026-09-23 at 15:37Z on Tee's word "File it and give them they first brief".
Follows `SYS_OPS_rakazo-mcp-live_v1_2026-09-23-1457.md`, which ends before
any of this existed.

## Rulings

All from Tee on cards, 2026-09-23.

- One production bot per content lane: TQO, TSWS, NCO Forge and ACX.
- Paid renders: the bot asks first. Plans and mock renders are free; every
  billable EditForge job waits for Tee's go in the bot's thread.
- Bots make, n8n ships. The bots do script, voice, avatar and cut through
  EditForge; n8n keeps scheduling, Drive and repurposing.
- From botdirectory.ai, add what is valuable. One listing was adopted.

## What exists in the Rakazo space

All five run on the space default, Anthropic `claude-sonnet-5` on Tee's Claude
subscription, and none carries its own model setting.

| bot | id | EditForge |
|---|---|---|
| TQO Producer | `cmue968l9004b2kp4mtpu1sm2` | given |
| TSWS Producer | `cmue96dzm004g2kp4cfex10d0` | given |
| NCO Forge Producer | `cmue96jft004l2kp4dq0pa0nx` | given |
| ACX Producer | `cmue96oln004q2kp49wo8xi66` | given |
| Idea Scout | `cmue98u21004z2kp4uyf6fkru` | not given |

Every producer carries the same house rules in its instructions: Tee owns every
ship decision, voice and identity are owned and never rented, paid renders need
his go, canon is read from Drive and DEVON with the files named, no invented
numbers, TTS ready scripts of 1,200 to 2,000 words, no em dashes, and AI
disclosure flagged on every piece. The "ask first" rule is an instruction, not
a lock: the EditForge token is full access, per the earlier ruling.

Idea Scout is the botdirectory.ai listing "Content Idea Generator" (Marketing,
scouted by @elie2222), its prompt kept verbatim and then bound to the four
lanes and made read only. The directory is 664 prompt listings run by Inbox
Zero Inc., read through a Rakazo bot's browser because this container's egress
blocks the site. Listings that publish on their own or run faceless, such as
"AI Faceless Shorts Factory" and "Account Growth Coach", were rejected against
Tee's rules.

## The n8n handoff

Tee ruled at about 15:45Z that Airtable is migrated to n8n data tables, which
overturned the first version of this section. That version sent the bots to
write Airtable rows, read from the live `TQO FINAL V5` (`qEkGOUsNyVaRAmm6`) as
it then stood. The live workflow was half migrated: its content lane ran on 33
data table nodes while 52 nodes still called Airtable, the whole repurpose
branch among them. On Tee's ruling the repurpose branch moved.

In V5, six nodes changed, names kept so every reference still resolves.
`Repurpose: Due Slots`, `Fetch Asset`, `Find Render` and `Mark Handed Off` now
read and write `at_tqo_publishing` (`FrJojhuZu0kGNxni`), `at_tqo_assets`
(`sQStJ0EDlH6ZFK7R`) and `at_tqo_editforge_generation_queue`
(`nQdokQVuN9rjZRYC`). `Plan Drops` does the due time test in code, because
`scheduled_for` is stored as text, and treats an empty or unparsable time as
not due. `Confirm Drop` keeps the 2026-09-22 rule: a failed drop writes the
note and leaves status and posted time as they were. Both code nodes were run
against six fixture rows and three Drive answers before publishing.

The lane had not been running at all. `Every 3h - Pipeline Pass`, its only
feed, was already disabled, and it also feeds V5's render and publish passes,
which upload to YouTube. Tee ruled a repurpose only trigger instead,
`Repurpose: 9am and 9pm`, feeding `Repurpose: Config` alone. Render and
publish stay off. Published and read back: V5 `versionId` and
`activeVersionId` both `e0264d05-69ce-4140-bf8b-b319cf6b1669`, 253 nodes.

Bots cannot reach n8n data tables, so a new workflow takes the handoff:
`DEVON - Bot Handoff to Repurpose` (`wXl6p7hKN74lKH0e`), webhook
`bot-handoff`, authenticated with n8n's existing "EditForge MCP Token"
credential. It validates brand, platforms, times and an https master URL,
then upserts one render row (`Approved`) and one `Pending` slot per platform,
keyed so a retry cannot duplicate. Execution 867 proved the refusal path
writes nothing. The write path has not run.

EditForge PR #69 adds `ship_to_n8n`, which posts that handoff signed with
EditForge's own `EDITFORGE_MCP_TOKEN`. No new secret reaches a bot. Whether
n8n's credential matches that header exactly is inferred, not measured; the
first real ship settles it.

## All of EditForge, and Canvas

Tee ruled the bots get all of EditForge and that the TSWS bot works in the
Canvas department ("Canvas & Floor Agent"). EditForge's MCP had no Canvas
tools. PR #69 adds Canvas project list, read, create from template and save,
a render plan preview, the edit worker (submit, list, cancel, retry), the
asset catalog, the stock library, and the gen video, voice and avatar
planners. Left out on purpose: sign in and passkeys, recording a rubric pass,
Canvas render and its confirmation hash, the Floor Agent, uploads, and a long
form planner that only plans a built in sample. Master renders stay refused
without a rubric pass Tee records. 460 EditForge tests pass, typecheck and
lint clean, three mutations caught.

EditForge's own edit command code names the four properties `tqo`,
`nco-forge`, `tsws` and `ascension-caudex`, which is a second source for ACX
being Ascension Caudex. Tee has still not said so.

## Google Drive, QA/QC, and the deploy

Tee ruled two more things at about 15:58Z, both on cards: the bots reach his
Drive through n8n, and they keep every V5 QA/QC step through an independent QC
bot plus hard gates.

Drive. `DEVON - Drive Read for Bots` (`o9w8btGoLyKAh5Lc`) searches and reads
Drive with the live Google Drive credential, read only, and has no node that
could write. EditForge's `drive_search` and `drive_read` reach it. Executions
869 and 871 found the four TQO canon index versions and read v4 as markdown,
25,398 characters. At 16:24:28Z the TQO Producer called EditForge's
`drive_read` on that file and got the same 25,398 characters and its first
line, "The canon of record for The Quiet Operator." The Composio or Pipedream
401 on Rakazo's own Drive connector is not fixed; this route goes around it.

QA/QC. Read from V5's own nodes, the gates split into measured and judged.
The measured ones now run in n8n on the script text itself, in
`DEVON - Bot QC Record` (`MmFNWeewHEuG5x8T`), writing to data table
`bot_qc_verdicts` (`uW1IBc8D2hmFgYIn`): V5's `Script Gate: Quality` floors
(1,200 to 2,400 words, no dashes, doctor 70, b-roll 6 for TQO and NCO, and for
TQO the objective inside the first 70 words, 3 to 5 steps, a comments
question, no subscribe ask, no retired audit) and V5's `Originality Scan`
against the lane's back catalogue in `tqo_content`, `nco_content`,
`at_tqo_tsws_content` or `at_tqo_acx_content`. One deliberate difference from
V5: a missing originality score fails here, where V5 let it pass. Every
verdict carries a fingerprint of the exact script it judged. Execution 876
compared a test script against 2 prior TQO episodes and failed it on the word
floor.

The judged ones, V5's Script Doctor and QC prompts, run in a new QC Inspector
bot (`cmueatuqt005r2kp4igzyqftf`), which reads them verbatim from Drive file
`SYS_SPEC_bot-qc-prompts_v1_2026-09-23.md` (`1D3PghtjBgtR9Os0gCU6EP5g09IfeEc51`)
and records verdicts with EditForge's `record_qc`. QC clears only at SHIP 80.
Human review is Tee's alone, with AI disclosure required. The handoff webhook
now refuses unless the latest script gate, QC and human review all clear, and
QC was judged on the same script fingerprint as the script gate. Execution
875 refused a frame that had none of them and wrote nothing.

Graded honestly: `record_qc` and `ship_to_n8n` share EditForge's one token, so
a producer ignoring its instructions could record a QC verdict itself. The
measured gates cannot be faked that way, because n8n computes them. V5's QC
prompt also grades a repurpose batch the bots do not make; the Inspector
judges Part A and says so.

Deploy. EditForge PR #69 merged as `6dc5927`, images published in run
35886920957, and `deploy-hostinger.yml` swapped to `6dc592777947` in run
35887912366 after a clean dry run. At 16:24:01Z the TSWS Producer called
`canvas_list_projects` on the live server and got 1 project and 7 templates.
The Vercel status on EditForge PRs reads "Deployment was blocked" and did on
#68 too; the repo ships to the VPS, not Vercel.

The four producers' instructions now read canon from Drive, route final
scripts to the QC Inspector, and ship with `ship_to_n8n` behind the gate; the
TSWS Producer builds in Canvas.

## First briefs, 15:31Z

A readiness run for the producers: tools, Drive, canon, gaps, a proposed first
piece, no production and no spend. All four answered inside two minutes and
none spent anything.

- EditForge: all four read the same providers ready, runway, elevenlabs and
  heygen billed, kokoro-local, hyperframes-local and mock free.
- Drive: every producer can search and list, and none can read contents.
  Every download returned `401 "Please upgrade your workspace to use this
  feature"`. The string is not in Rakazo's source, and Rakazo's integrations
  run through Composio and Pipedream, so the likely source is the plan on the
  connector service. Unverified.
- TQO found canon index v4 of 2026-09-22 with three same night superseded
  versions, and asks Tee to confirm v4 is authoritative before drafting.
- TSWS listed the series bible v2.4, visual bible v1.4, both soul codices and
  the D17 rulings by name, flagged the withdrawn and "do not build against"
  versions, and refused ElevenLabs for Auren and Vespera without an explicit
  override, which is the consent rule working.
- NCO Forge found only a brand package PDF and a pointer to the D9-B likeness
  consent in the TQO folder, and asks whether that consent covers NCO Forge.
- ACX found `ASCENSION_CAUDEX_INTAKE_v0.1.md`, the R1 to R5 node images and a
  Loop 1 text, and asked Tee what the lane makes. Airtable independently
  carries a Brand option "Ascension Caudex" and ACX canon tables, so ACX is
  very likely Ascension Caudex. Tee has not confirmed it.
- Idea Scout has no YouTube connection and asked its eight setup questions,
  including read only OAuth or a public channel URL.

The first briefs ran before the handoff was added to the producers'
instructions, so none of them has seen it in a run yet.

## Open

- TQO canon v4 needs Tee's confirmation. NCO Forge needs the D9-B consent
  scope. ACX needs Tee to say what it makes. Idea Scout needs its eight
  answers.
- Not yet run: the handoff write path and n8n downloading an EditForge
  master. The header match is proven by the live drive_read. The first real
  ship proves the rest.
- Test rows labelled TEST-QC-WIRING-2026-09-23 sit in `bot_qc_verdicts`; they
  gate only that frame id.
- V5 still has 47 nodes calling Airtable outside the repurpose branch.
- The two probe bots and the Gemini connection on a retired model remain.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_rakazo-lane-producers_v1_2026-09-23-1537.md
DATE: 2026-09-23
DECISIONS: Tee ruled one production bot per lane for TQO, TSWS, NCO Forge and ACX, paid renders only on his go, and bots make while n8n ships. Idea Scout was adopted from botdirectory.ai under his delegation. Tee ruled Airtable migrated so the repurpose lane moves to n8n data tables, a repurpose only schedule with render and publish left off, all of EditForge for the bots, and Canvas as the TSWS bot's department. Tee ruled the bots reach Drive through n8n and keep every V5 QA/QC step through an independent QC Inspector plus hard gates.
FINDINGS: Four producers, Idea Scout and a QC Inspector live on Sonnet 5 through the Claude subscription. EditForge 6dc5927 is deployed and bots used Canvas and read Drive live through it at 16:24Z, 25,398 characters of TQO canon. V5's repurpose branch now reads the data tables on its own 9:00 and 21:00 schedule. V5's measured QA/QC gates run in n8n on the script text and the handoff refuses without script gate, QC 80 and human review on the same script. Rakazo's own Drive connector still returns 401 upgrade your workspace and is bypassed, not fixed.
OPEN: First real ship proves the handoff write and the n8n download. record_qc shares one token with the producers. Tee to confirm TQO canon v4, D9-B consent scope for NCO Forge, what ACX makes, and answer Idea Scout. 47 Airtable nodes remain in V5. Probe bots and the retired Gemini connection to clean up.
STATUS: Bots built, briefed, reading Drive, gated by QA/QC, EditForge deployed; waiting on Tee's answers and a first real brief.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
