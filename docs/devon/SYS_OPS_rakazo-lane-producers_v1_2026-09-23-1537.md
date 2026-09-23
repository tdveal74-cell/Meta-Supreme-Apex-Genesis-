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

- Drive contents are unreadable to every bot. Until fixed, each producer can
  name canon files but not read them, and drafts would rest on its
  instructions alone.
- TQO canon v4 needs Tee's confirmation. NCO Forge needs the D9-B consent
  scope. ACX needs Tee to say what it makes. Idea Scout needs its eight
  answers.
- Not yet run: the handoff write path, the header match between EditForge and
  n8n, and n8n downloading an EditForge master. The first real ship proves
  all three.
- EditForge PR #69 must merge and deploy before the bots have Canvas, the
  edit worker or `ship_to_n8n`, and their instructions still describe the
  Airtable handoff until they are updated after that deploy.
- V5 still has 47 nodes calling Airtable outside the repurpose branch.
- The two probe bots and the Gemini connection on a retired model remain.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_rakazo-lane-producers_v1_2026-09-23-1537.md
DATE: 2026-09-23
DECISIONS: Tee ruled one production bot per lane for TQO, TSWS, NCO Forge and ACX, paid renders only on his go, and bots make while n8n ships. Idea Scout was adopted from botdirectory.ai under his delegation. Tee ruled Airtable migrated so the repurpose lane moves to n8n data tables, a repurpose only schedule with render and publish left off, all of EditForge for the bots, and Canvas as the TSWS bot's department.
FINDINGS: Five bots live on Sonnet 5 through the Claude subscription. V5's repurpose branch was on Airtable and not scheduled at all; it now reads the data tables and runs at 9:00 and 21:00 New York, published and read back at version e0264d05. A bot handoff webhook is live and refuses bad input without writing. EditForge PR #69 gives bots Canvas, the edit worker, catalog, stock, planners and ship_to_n8n, human gates kept. Every bot can list Drive but not read it, 401 upgrade your workspace, likely the connector service plan, unverified.
OPEN: Merge and deploy EditForge PR #69, then update the four producers' handoff instructions to ship_to_n8n. First real ship proves the handoff write, the header match and the n8n download. Fix Drive content reads. Tee to confirm TQO canon v4, D9-B consent scope for NCO Forge, what ACX makes, and answer Idea Scout. 47 Airtable nodes remain in V5.
STATUS: Bots built and briefed, repurpose moved and scheduled, EditForge tools in review, blocked on Drive reads and Tee's answers.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
