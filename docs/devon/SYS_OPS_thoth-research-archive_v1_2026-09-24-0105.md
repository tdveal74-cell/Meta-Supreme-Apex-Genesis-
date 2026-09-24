# Thoth and the research archive: one filing system in the vault

Filed 2026-09-24 at 01:05Z. Follows
`SYS_OPS_rakazo-lane-producers_v1_2026-09-23-1537.md`.

## Rulings

All from Tee, 2026-09-23 into 2026-09-24.

- Create Thoth, Researcher & Archivist: deep research, stored once, indexed,
  easy to find, "not a news writer or a salesperson".
- On a card: Thoth's one filing system is DEVON's Drive vault, not the Rakazo
  team computer's disk. The recommended option; the cost stated was building a
  write path first and adding Rakazo to the vault's write list.
- On a card: helpers run Claude only for now.
- On a card: Thoth files, Knowledge Librarian checks. The Librarian keeps no
  index of its own; Tee pastes its new brief because its current instructions
  cannot be read from here.
- Earlier the same night: the lane bots read Drive only through EditForge, and
  EditForge is attached to further bots in the Rakazo UI.

## Why the vault needed a write path

Before this, no bot could write to Drive at all. EditForge's `drive_search`
and `drive_read` only read, through the n8n workflow `DEVON - Drive Read for
Bots`. Rakazo's own Google Drive tools come from Pipedream Connect; they list
files but every download fails with 401 "Please upgrade your workspace", and
the same tool set carries delete, trash, share and remove-sharing. Using them
to write would have been an unapproved write from a platform the vault's
permission list did not name, by a tool that can also delete.

## What was built

| piece | where | proof |
|---|---|---|
| Research folder | `3. Resources/Research`, `1Y0Dp4WsrxgFRbLMEIKP6vlmhYeaIlxJb` | created by n8n execution 906 after checking none existed and that `4. Archive` resolved |
| Filer workflow | `DEVON - Bot Research Filer`, `jbDzwMVQDkEvkEM3`, webhook `bot-research-file` | executions 907, 908, 909; published, `activeVersionId` equals `versionId`; 403 with no token and with a wrong one |
| EditForge tool | `research_file` in `lib/mcp.ts`, gated mutating | EditForge PR #70, merged `0a69165`; vitest 463 passed; a wrong webhook path fails the new test |
| Deploy | image tag `0a691657b14b` | publish run 35940895769, dry run 35941181927, live run 35941230871, all success |
| Vault permission | `services/devon/vault.py` `RESEARCH_FOLDER` and `PERMISSIONS["Rakazo"]` | this PR; `test_rakazo_bots_write_research_only`; full api suite 3,228 passed |

The filer lists the Research folder, then decides in one Code node:

- A new slug files at v1 only. Name `AREA_SOURCE_slug_vN_YYYY-MM-DD.md`, area
  from DEVON's nine codes, under 80 characters, none of DEVON's banned status
  words.
- A slug already on file, in any area, is refused unless the call names the
  current piece's id and the next version number, and keeps its area.
- Markdown with an em or en dash is refused.
- It fails closed when Drive does not answer 200 or the folder passes 1,000
  files.

It creates the file, uploads the text, and reads it back, checking name, byte
size and parent. Only after that read back passes does it rename the old piece
`SUPERSEDED_` and move it to `4. Archive`. It never deletes, trashes or
shares, and has no node that could. Twenty four local cases passed before the
first live run.

Live runs on 2026-09-24:

- 907: v1 of `SYS_SOURCE_research-filer-wiring-test` filed, 202 bytes sent
  and read back.
- 908: a second v1 on the same slug was refused, naming the existing file.
- 909: v2 filed at 220 bytes; v1 now reads
  `SUPERSEDED_SYS_SOURCE_research-filer-wiring-test_v1_2026-09-24.md` in
  `4. Archive`.

The two wiring test files are still in Drive and are safe for Tee to trash.

## Thoth

Bot `cmuetc4hi009a2kp4r4k0qgil`. It was checked that no Thoth existed before
creating it. It runs on the space default, Sonnet 5 on Tee's Claude
subscription, with thinking high, the team computer, and EditForge. At 00:48Z
it read the TQO canon index through `drive_read`, 25,398 characters. Its
instructions confine filing to `research_file`, forbid every `google_drive-`
tool directly or through `pipedream_execute_tool`, and tell it to pass the
safety rules into every helper, because helpers started with `run_subagent`
do not inherit a bot's instructions.

First real filing, end to end through the deployed EditForge and the
production webhook:

- 01:05:09Z, execution 913: Thoth ran `research_file` index. Nothing was on
  file for "executor".
- 01:10Z: he filed `SYS_SOURCE_executor-sh-profile_v1_2026-09-24.md`,
  6,846 bytes, read back, id `1WzUPr_ab-2qzsA6LRhMnpeajgCmSDzVQ`.

His piece and the research this session did for Tee disagree on two points,
and neither is settled here:

- Whether Executor holds botdirectory.ai's sponsor slot. Thoth read the live
  site on 2026-09-24 and found no Executor among 13 sponsors. This session read
  the site's source at commit 7334e5c, where Executor is the connect sponsor.
- Which Google scope the Drive integration requests. Thoth could not find the
  Google plugin in the repository's current tree and left the scope
  unverified. This session read `auth/drive` at commit d27e673.

The live pages and a clone at a fixed commit can both be right. Graded
unverified until one read settles it.

Thoth's chat replies still contained em dashes on both runs. The filed piece
did not: the filer refuses them.

## The Drive read fix for the lane bots

The TSWS Producer kept calling Pipedream's `google_drive-download-file` and
reporting Drive blocked. All four producers and the QC Inspector now carry an
instruction to read only through EditForge. At 22:23Z on 2026-09-23 the TSWS
Producer read the series bible v2.4 through `drive_read`, 42,312 characters.
While making that change the TQO Producer's instructions were overwritten with
a placeholder for about two minutes. They were restored on Tee's go and the
bot quoted its restored house rule and Drive line at 22:24Z.

EditForge was ticked onto older bots in the Rakazo UI. By a real call on
2026-09-23 at 22:38Z:

- Pipeline Operator and DEVON Chief of Staff read Drive through EditForge.
- Canon Guardian, Idea Scout, Knowledge Librarian and Chief answered "Tool is
  unknown or not authorized for this bot".
- Bot Roster Manager declined the check.

A bot's own list of its tools is not evidence. Two bots said "none" and then
called a tool, and two said they had called a tool that their next real call
showed they could not use.

## Found along the way

- executor.sh, which Tee asked about, is Executor, an MIT MCP gateway. Its
  Google Drive integration requests the full `auth/drive` scope, and the link
  Tee had was botdirectory.ai's paid sponsor slot on a site owned by Rakazo's
  author. Recommended against; not needed for Docs, Sheets, Slides or text.
- `3. Resources` holds three pairs of duplicate folders whose second copy has
  an HTML escaped name, for example `AI &amp; Automation` beside
  `AI & Automation`. Seen, not touched.

## Open

- Tee re-ticks EditForge for Canon Guardian, Idea Scout, Knowledge Librarian
  and Chief, then pastes the Librarian's checker brief and the Drive paragraph
  into the older bots' instructions.
- Rakazo's Pipedream Google Drive source still gives every bot delete and
  share tools. Removing it is Tee's call and the recommended fix.
- PDFs, images and video in Drive remain unreadable to bots.
- Two filings of the same new slug at the same instant could both pass the
  duplicate check. Not seen; noted.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_thoth-research-archive_v1_2026-09-24-0105.md
DATE: 2026-09-24
DECISIONS: Tee created Thoth, Researcher and Archivist, and ruled on cards that its one filing system is DEVON's Drive vault, helpers run Claude only, and Thoth files while Knowledge Librarian checks. The lane bots read Drive only through EditForge.
FINDINGS: Bots had no Drive write path. A create only filer now writes AREA_SOURCE pieces to 3. Resources/Research, refuses duplicate slugs, and retires superseded pieces to 4. Archive, proven in executions 907 to 909. EditForge 0a691657b14b carries research_file and is deployed. The vault permission list now names Rakazo for that folder only. A bot's report of its own tools proved unreliable twice; only real calls count.
OPEN: Tee re-ticks EditForge for four bots and pastes the Librarian brief. Pipedream's Google Drive source still gives every bot delete and share tools. PDFs stay unreadable to bots.
STATUS: Thoth live, the research archive live in the vault, first real filing recorded above.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
