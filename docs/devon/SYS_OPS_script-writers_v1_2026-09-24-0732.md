# Script writers on Rakazo: one per producer, drafts saved to Drive

Filed 2026-09-24 at 07:32Z. Follows
`SYS_OPS_thoth-research-archive_v1_2026-09-24-0105.md`, whose research filer
this lane copies.

## Rulings

All from Tee on cards, 2026-09-24.

- A script writer for each producer: TQO, NCO Forge, TSWS and ACX. ACX was
  recommended to wait until Tee confirms what ACX makes. He chose all four,
  so the ACX writer's first job is to ask.
- Drafts save as Google Docs in each show's scripts folder, through a checked
  create-only path. Recommended; the stated cost was an hour of build and a
  wider vault permission.
- YouTube is not connected. Recommended: a writer needs no YouTube access, and
  Rakazo's YouTube tools come from Pipedream, the same source whose Drive
  tools carry delete. Nothing can publish when nothing is connected.
- Each writer interviews Tee in its own Rakazo thread. Claude writes the
  answers into the writer's standing instructions.
- Later the same morning, in chat: "Scripts should be written like one
  continuous story and made into series and seasons." Every writer now carries
  a series and seasons section: a season plan saved before the first episode,
  each episode picking up where the last ended, slugs `sNNeMM-name`, and an
  eighth interview question on the series and season shape.
- Also in chat: "Already decided for ACX", with `ACX_RULINGS_2026-09-24.md`
  pasted. The ACX writer's eight answers are now written from rulings R1 to R5
  and it does not ask them again. One mapping is marked as not yet ruled: a
  Node is an episode and a Folio of 12 Nodes is a season.
- On a card: merge #71 and this PR once the critic passes and CI is green;
  TQO does the first script with Tee watching; the TSWS writer waits for the
  Season One continuity audit, as the 2026-09-24 TSWS rulings say.

## What exists

| piece | where | proof |
|---|---|---|
| Drafter workflow | `DEVON - Bot Script Drafter`, `pkddqOLe0guVGEk9`, webhook `bot-script-draft` | manual executions 988 to 991, 1040 and 1041; published, `activeVersionId` equals `versionId` `4c65606f-9cc7-4ec5-9f27-6975a6282b30`; 403 with no token and with a wrong one, before and after the critic's fixes |
| EditForge tool | `script_draft` in `lib/mcp.ts`, gated mutating | EditForge PR #71; vitest 463 passed; a wrong webhook path fails the routing test; tsc, eslint and next build clean |
| Vault permission | `services/devon/vault.py` `SCRIPT_DRAFT_FOLDERS`, `WritePermission.also_folder_ids` | this PR; `test_rakazo_bots_write_research_only` now covers the four folders and seven folders that stay closed; dropping the check fails it |
| Writers | TQO Script Writer `cmuf7q45d00dx2kp4lh3k9hyr`, NCO Forge Script Writer `cmuf7qqf900e22kp4q2rgfwti`, TSWS Script Writer `cmuf7r8c100e72kp4xdjnfwee`, ACX Script Writer `cmuf7rop300ec2kp486tbhxub` | created through the connector with EditForge, thinking high, space default model |

The drafter lists the four script folders, then decides in one Code node:

- The name is `AREA_SCRIPT_slug_vN_YYYY-MM-DD`, the date stamped by the
  workflow, not the caller.
- The version is one more than the highest on that slug in that area's own
  folder, counting V5's own files and ones renamed `SUPERSEDED_`. A stated
  version that is not the next one is refused.
- The area is checked as an own key of the four, so `__proto__` or
  `constructor` is refused rather than read off the object prototype.
- An em or en dash in the title or text is refused, as are the banned slug
  words and names of 80 characters or more.
- It fails closed when Drive does not answer 200 or the folders pass 1,000
  files.

It creates one Google Doc by multipart upload with conversion, reads back the
name, type and parent, exports the Doc as text and compares it with what was
sent, after collapsing runs of blank lines. A draft passes only when the text
matches, and one that does not answers HTTP 502 so EditForge reports an error. It has
no node that renames, moves, deletes, shares or publishes, and it leaves every
earlier version where it is.

Live runs on 2026-09-24:

- 988: index returned the seven existing TQO script files, V5's included.
- 989: v1 of `TQO_SCRIPT_drafter-wiring-test` saved, 48 words sent and 48
  read back, an accented letter and quotes intact.
- 990: v2 saved on the same slug, exact text match, v1 left in place.
- 991: an em dash refused before any Drive write.
- 1040, after the critic's fixes: `area: "__proto__"` refused before any
  Drive write.
- 1041: v3 saved through the new `Saved Cleanly` branch, exact match.

All of these are manual runs. The first save a writer makes through the
deployed EditForge will be the first end to end production call.

Docs export each paragraph break as an extra blank line, so the first run's
exact match read false. The comparison now collapses runs of blank lines;
the second run read true.

The three wiring test Docs are in TQO 01_SCRIPTS and are safe for Tee to trash.

## The critic

A fresh critic in its own worktree, on `1a91eef`, returned PASS WITH
CONDITIONS: nothing in the drafter can publish or delete, and every failure it
could produce reported `saved: false`. Its findings and what was done:

- The area check read `FOLDERS[area]`, so `__proto__`, `constructor` and
  `toString` reached the create branch. Fixed; four cases added.
- The receipt said the text was read back word for word while only the word
  count gated the result. Fixed in the workflow, so the claim is now true.
  Swapping a word at the same count now fails; reverting the check lets it
  through.
- A failed save answered HTTP 200 with `saved: false` one level down, which a
  bot could read as success. It now answers 502.
- Node timeouts could add to 150 seconds against EditForge's 90. They now add
  to 85.
- A file named for one area in another area's folder bumped the version, and a
  huge version in a name produced a scientific notation name. Fixed: counted
  only in the area's own folder, versions capped at four digits.
- Not fixed, graded low: two submits at the same instant can both create the
  same name, since the name check is not atomic. The cost is an extra draft Doc.

The drafter's local cases went from 24 to 30, all passing.

## The writers

Each one works to its producer's lane standard, copied from that producer's
instructions, and to one shared brief: a hook in the first two or three
sentences, labelled sections, narration written to be read aloud, a
transition into each section, a real example per section, `[B-ROLL: ...]` and
`[ON SCREEN: ...]` lines, the lane's close, and a writer's notes block naming
every file read and everything unverified. TSWS scripts are dialogue with
`AUREN:` and `VESPERA:` labels. Each writer reads Drive only through EditForge,
saves only through `script_draft`, and hands a reviewed draft to its producer,
who sends it to the QC Inspector. None may call `ship_to_n8n`, `submit_edit`,
`record_qc`, a render tool or any `google_drive-` tool.

The first script runs in three steps with Tee watching: outline, full draft in
chat, then save on his word.

## Open

- `NCO_RULINGS_2026-09-24.md` now exists twice in the NCO Forge folder, ids
  `1rJW832e3-EwNS87e8b4EqRLVE-zFRcMx` (07:13Z) and
  `1aEZd2uV0L_NIxcVVxmGjjsUMeK8xDYql` (07:41Z), seen in the drafter's own
  folder listing. Not written by this lane, which creates only `_SCRIPT_`
  names. Which one is current is Tee's call.

- Merge #71 and this PR on green, then deploy EditForge. Until #71 deploys,
  the writers cannot save; they can interview and draft.
- Each writer's interview answers go into its instructions once Tee gives them.
- The first script, with Tee watching.
- The NCO area folder is the NCO draft folder, so the Rakazo permission covers
  the whole area folder there, as it does for ACX. The drafter only creates.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_script-writers_v1_2026-09-24-0732.md
DATE: 2026-09-24
DECISIONS: Tee created a script writer for each of the four producers, ruled that drafts save as Google Docs in each show's scripts folder through a checked create-only path, that YouTube stays unconnected, that each writer interviews him in its own thread, that scripts are one continuous story made into series and seasons, and that the ACX answers come from his ACX rulings of the same day.
FINDINGS: A create-only drafter writes AREA_SCRIPT_slug_vN_date Google Docs, numbers versions after V5's own files in the same folder, reads the text back and fails when it differs, and refuses dashes, proven in manual executions 988 to 991, 1040 and 1041. A fresh critic returned pass with conditions and its conditions were fixed. EditForge carries script_draft in PR 71. The vault permission list names the four script folders for Rakazo.
OPEN: Merge and deploy EditForge PR 71 and this PR. The four interviews, then the first script with Tee watching.
STATUS: Drafter live; writers created; saving waits on the EditForge deploy.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
