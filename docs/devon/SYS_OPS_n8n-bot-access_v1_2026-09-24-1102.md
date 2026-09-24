# Two Rakazo bots hold n8n, and the write gate is not yet proven

Filed 2026-09-24 at 11:02Z from Tee's setup session.

## What was asked

Tee asked to finish giving two Rakazo bots gated n8n access. n8n was already
registered in Rakazo as server `cmufeyhnl00gt2kp4s4zr1k40`, 39 tools, no bots.
Five steps: gate the 17 n8n write tools, give n8n to Pipeline Operator and
DEVON Chief of Staff, prove it with one read and one denied write, send both
bots the n8n house rules, and file this doc. A wording fix in
`tdveal74-cell/rakazo-deploy` rode along.

## What was done and read back

Every line below was read back from Rakazo or n8n after the change, not taken
from the tool that made it.

Baseline. Before anything changed, `list_approval_rules` returned `[]` and
`list_mcp_servers` showed the n8n server with `"bots": []`.

Approval rules. `require_approval` added 17 rules. `list_approval_rules`
then returned exactly 17 rows, every one `effect: require_approval`,
`matchKind: tool`:

```
mcp__n8n__add_data_table_column      mcp__n8n__publish_workflow
mcp__n8n__add_data_table_rows        mcp__n8n__rename_data_table
mcp__n8n__archive_workflow           mcp__n8n__rename_data_table_column
mcp__n8n__create_data_table          mcp__n8n__restore_workflow_version
mcp__n8n__create_folder              mcp__n8n__test_workflow
mcp__n8n__create_workflow_from_code  mcp__n8n__unpublish_workflow
mcp__n8n__delete_data_table_column   mcp__n8n__update_folder
mcp__n8n__execute_workflow           mcp__n8n__update_workflow
mcp__n8n__move_workflows_to_folder
```

The n8n VPS connector in this session lists 39 tools. The other 22 are get,
list, search, validate and explore reads, plus `prepare_workflow_pin_data`.
That last one is ungated. Its name reads as preparation rather than a write,
but what it does on the server was not checked.

Bots. `give_bot_n8n` returned `tools: 39, gatedWrites: 17,
otherServersKept: 1` for both bots. `list_mcp_servers` then showed the n8n
server with exactly two bots, `cmu98ysko009311mg096zsw7r` (Pipeline Operator)
and `cmu98y9ws006z11mgf90mq9md` (DEVON Chief of Staff), each at 39 tools. Both
still hold EditForge at `all`.

The read. Pipeline Operator called `mcp__n8n__search_workflows`, empty
query, limit 5, at 10:59:07Z. It reported five workflows and a total of 72.
The same call from this session's own n8n connector returned the same five ids
in the same order and `count: 72`:
`pkddqOLe0guVGEk9`, `jbDzwMVQDkEvkEM3`, `6kwEVgUOsErRhvxE`,
`MmFNWeewHEuG5x8T`, `wXl6p7hKN74lKH0e`. So the bot reached the live
instance and did not invent its answer.

The write: no approval card appeared. The target was
`6kwEVgUOsErRhvxE`, `TQO Episode Email Drafter (Reach)`. It was picked
because it is inactive with no trigger, so an approval by mistake would not
stop anything that is scheduled.

- First attempt, 10:59:32Z. By the bot's own report, it addressed the tool
  as `n8n:archive_workflow` and got back
  `{"error":"Tool is unknown or not authorized for this bot"}`. No card
  reached Tee. No Rakazo-side record of the call was read, so the name and
  the error rest on the bot's word.
- The workflow was read back at once: still present, not archived,
  `updatedAt 2026-09-23T19:42:48.651Z`, unchanged.
- The read had worked under the name `mcp__n8n__search_workflows`, and the
  same error string met other bots on 2026-09-23 when they loaded EditForge
  tools under the wrong name. So the refusal could be the name and not the
  gate. The bot was asked once to try `mcp__n8n__archive_workflow`.
- Second attempt, 10:59:58Z. The bot refused to make the call. Its reasoning:
  an in-chat claim that a write will pause for approval is not something it
  can verify, and repeating a write on that premise is the pattern it should
  refuse. That was left standing. It was not argued into the write, and no
  other bot was tried to find one that would comply.

What this proves: an n8n write from this bot did not reach n8n. What it does
not prove: that Rakazo's approval gate intercepts a correctly named n8n write
and puts a card in front of Tee. Graded honestly, the gate is configured and
unexercised.

House rules. Both bots were sent the three rules: every write is approval
gated and a denied write is never retried or routed around; never pause or
unpublish a content trigger to quiet a provider outage; an n8n edit is a draft
until `publish_workflow` and a read back showing `activeVersionId` equal to
`versionId`. Pipeline Operator confirmed at 11:00:15Z and Chief of Staff at
11:00:19Z. The rules are in each bot's thread, not in its standing
instructions. Whether a thread message holds across later runs was not
checked. Rule 1 told both bots the 17 writes "wait for Tee's approval before
they run". That is how the rules are configured, and it is not yet proven, see
the write above.

rakazo-deploy. The `--plug-n8n` prompt in `mcp/install.template.sh`
told the operator not to rotate the n8n token or Claude's own n8n connector
would stop working. Tee reports the token was rotated on 2026-09-24 and
Claude's n8n link kept working, because it signs in by OAuth. This session's
n8n connector answered reads at 10:59Z and 11:00Z today, which fits. The
prompt now says rotating is safe for Claude's connector, which signs in by
OAuth and does not use this token, and that Rakazo keeps its own copy of the
token (the n8n server reads `hasSecret: true`), so `--plug-n8n` has to run
again after any later rotation. That a rotation breaks Rakazo's copy follows
from how a token rotation works and was not tested. A fresh critic flagged the
first wording as carrying a dated anecdote and an untested claim, and it was
revised. Rebuilt with `mcp/build.sh`: server sha256 `d4642beb`, installer
sha256 `411ec9c8`.
`npm test` returned 36 passed, 0 failed. `install/run.sh` against the built
installer returned `passed 72, failed 0`, and `--plug-n8n` is one of the
paths it drives. Commits `d839092` and `e5ef3a4` on branch
`claude/rakazo-n8n-bot-gating-g3fpuv` of rakazo-deploy. The built installer has not been delivered to the VPS, and
it does not need to be for this change: it alters one printed line.

## Open

1. Prove the gate. Three routes, Tee's call: send Pipeline Operator the
   archive request yourself from the Rakazo app, so it arrives from you and
   not from a session; have Chief of Staff attempt the same call; or trigger
   a gated tool from Rakazo's own UI. Until one of them shows a card, the
   17 rules are a configuration, not a proven control, and both bots have
   been told they are one.
2. Find out why `n8n:archive_workflow` came back "unknown or not authorized".
   If Rakazo hides gated tools from a bot rather than pausing them, bots cannot
   request a write at all, and the approval path never fires.
3. Decide whether the house rules belong in each bot's standing instructions
   through `update_bot`, where they would hold for every run.
4. `prepare_workflow_pin_data` is ungated. Read what it does before leaving
   it that way.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_n8n-bot-access_v1_2026-09-24-1102.md
DATE: 2026-09-24
DECISIONS: Tee asked for 17 n8n write tools gated in Rakazo, n8n given to Pipeline Operator and DEVON Chief of Staff, one read and one denied write as proof, three house rules sent to both bots, and the --plug-n8n rotate warning in rakazo-deploy corrected. The write test targeted inactive workflow 6kwEVgUOsErRhvxE so a mistaken approval would stop nothing scheduled.
FINDINGS: list_approval_rules reads back 17 require_approval rules, one per named tool. list_mcp_servers shows n8n on exactly the two bots at 39 tools each, EditForge kept. Pipeline Operator's search_workflows answer matched this session's own read id for id, count 72. No approval card appeared: the first archive attempt, named n8n:archive_workflow, returned "Tool is unknown or not authorized for this bot" and the workflow read back unchanged; the bot then refused a second attempt on its own safety rules and was not pressed. Both bots confirmed the house rules in thread. rakazo-deploy d839092 and e5ef3a4 reword the prompt; unit 36 passed, installer paths 72 passed. The first archive attempt's tool name and error rest on the bot's own report.
OPEN: The approval gate is configured and unproven, and the house rules told both bots it is in force; Tee picks the route to exercise it. Why a gated n8n write came back "unknown or not authorized" rather than pausing. Whether the house rules should go into each bot's standing instructions. prepare_workflow_pin_data is ungated and unread. The rakazo-deploy branch needs a PR and Tee's merge.
STATUS: Access granted and read back. Write gate unproven.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
