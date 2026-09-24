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

## What exists

| piece | where | proof |
|---|---|---|
| Drafter workflow | `DEVON - Bot Script Drafter`, `pkddqOLe0guVGEk9`, webhook `bot-script-draft` | executions 988 to 991; published, `activeVersionId` equals `versionId` `c50c4a68-9e8a-4875-b233-9ffb7d7bec83`; 403 with no token and with a wrong one |
| EditForge tool | `script_draft` in `lib/mcp.ts`, gated mutating | EditForge PR #71; vitest 463 passed; a wrong webhook path fails the routing test; tsc, eslint and next build clean |
| Vault permission | `services/devon/vault.py` `SCRIPT_DRAFT_FOLDERS`, `WritePermission.also_folder_ids` | this PR; `test_rakazo_bots_write_research_only` now covers the four folders and seven folders that stay closed; dropping the check fails it |
| Writers | TQO Script Writer `cmuf7q45d00dx2kp4lh3k9hyr`, NCO Forge Script Writer `cmuf7qqf900e22kp4q2rgfwti`, TSWS Script Writer `cmuf7r8c100e72kp4xdjnfwee`, ACX Script Writer `cmuf7rop300ec2kp486tbhxub` | created through the connector with EditForge, thinking high, space default model |

The drafter lists the four script folders, then decides in one Code node:

- The name is `AREA_SCRIPT_slug_vN_YYYY-MM-DD`, the date stamped by the
  workflow, not the caller.
- The version is one more than the highest on that slug in that area,
  counting V5's own files and ones renamed `SUPERSEDED_`. A stated version
  that is not the next one is refused.
- An em or en dash in the title or text is refused, as are the banned slug
  words and names of 80 characters or more.
- It fails closed when Drive does not answer 200 or the folders pass 1,000
  files.

It creates one Google Doc by multipart upload with conversion, reads back the
name, type and parent, exports the Doc as text and compares the words. It has
no node that renames, moves, deletes, shares or publishes, and it leaves every
earlier version where it is.

Live runs on 2026-09-24:

- 988: index returned the seven existing TQO script files, V5's included.
- 989: v1 of `TQO_SCRIPT_drafter-wiring-test` saved, 48 words sent and 48
  read back, an accented letter and quotes intact.
- 990: v2 saved on the same slug, exact text match, v1 left in place.
- 991: an em dash refused before any Drive write.

Docs export each paragraph break as an extra blank line, so the first run's
exact match read false. The comparison now collapses runs of blank lines;
the second run read true.

The two wiring test Docs are in TQO 01_SCRIPTS and are safe for Tee to trash.

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

- EditForge PR #71 and this PR need Tee's merge. Until #71 deploys, the
  writers cannot save; they can interview and draft.
- Each writer's interview answers go into its instructions once Tee gives them.
- The first script, with Tee watching.
- The NCO area folder is the NCO draft folder, so the Rakazo permission covers
  the whole area folder there, as it does for ACX. The drafter only creates.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_script-writers_v1_2026-09-24-0732.md
DATE: 2026-09-24
DECISIONS: Tee created a script writer for each of the four producers, ruled that drafts save as Google Docs in each show's scripts folder through a checked create-only path, that YouTube stays unconnected, and that each writer interviews him in its own thread.
FINDINGS: A create-only drafter writes AREA_SCRIPT_slug_vN_date Google Docs, numbers versions after V5's own files, reads the text back word for word, and refuses dashes, proven in executions 988 to 991. EditForge carries script_draft in PR 71. The vault permission list names the four script folders for Rakazo.
OPEN: Merge and deploy EditForge PR 71 and this PR. The four interviews, then the first script with Tee watching.
STATUS: Drafter live; writers created; saving waits on the EditForge deploy.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
