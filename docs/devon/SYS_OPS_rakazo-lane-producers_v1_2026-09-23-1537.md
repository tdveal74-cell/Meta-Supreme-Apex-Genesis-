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

Read from the live `TQO FINAL V5` (`qEkGOUsNyVaRAmm6`, 252 nodes, published
version equals draft) and the Airtable schema, not assumed. No n8n change was
needed. The repurpose branch, fed by `Every 3h - Pipeline Pass` and gated to
9:00 and 21:00 New York time, reads `Publishing` (`tblQgQ3JdpoKOANXh`) for
`Status = Pending` past `Scheduled For`, then finds the render in `EditForge
Generation Queue` (`tblsWef63twib7dIr`) by `Frame ID` with `Status = Approved`
and a non empty `Output URL`, downloads it and drops it in the platform's
Repurpose folder. It routes on `Platform` only, so every brand can use it.

So on Tee's "ship", a producer writes one Generation Queue row and one
Publishing row per platform, with its own `Brand` option, and never sets
`Ready` or `Posted`. If it cannot write to Airtable it hands Tee the rows to
paste. The old Brand field marked OLD is never used.

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
- Not yet tried: a bot writing to Airtable, and n8n downloading an EditForge
  master from the URL a bot records. The first real ship proves both.
- The two probe bots and the Gemini connection on a retired model remain.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_rakazo-lane-producers_v1_2026-09-23-1537.md
DATE: 2026-09-23
DECISIONS: Tee ruled one production bot per lane for TQO, TSWS, NCO Forge and ACX, paid renders only on his go, and bots make while n8n ships. Idea Scout was adopted from botdirectory.ai under his delegation.
FINDINGS: Five bots live on Sonnet 5 through the Claude subscription. The handoff uses V5's existing repurpose branch through the Publishing and EditForge Generation Queue tables with no n8n change. First briefs cost nothing and all four producers report the same blocker, Drive listing works and content download returns 401 upgrade your workspace, likely the connector service plan, unverified. ACX is very likely Ascension Caudex, unconfirmed.
OPEN: Fix Drive content reads for bots. Tee to confirm TQO canon v4, D9-B consent scope for NCO Forge, what ACX makes, and answer Idea Scout. First real ship proves the Airtable write and the n8n download. Probe bots and the retired Gemini connection to clean up.
STATUS: Bots built and briefed, blocked on Drive reads and Tee's answers.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
