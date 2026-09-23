# The Floor Agent answers through Claude

Status record, 2026-09-23. EditForge on the VPS, editforge.online.

## What happened

Tee signed in to editforge.online after the Google secret was replaced and the
Canvas said the Floor Agent needed a connection. The cause was that the agent
only knew xAI and no `XAI_API_KEY` had ever been set. Tee ruled to switch the
agent to Claude. The objection was logged once: Claude needs a funded
Anthropic key, and transcription and Grok Imagine stay dark without xAI.

EditForge PR #68 moved the agent to Anthropic's Messages API. It uses
`ANTHROPIC_API_KEY` and `ANTHROPIC_AGENT_MODEL`, default `claude-sonnet-5`, with
structured outputs holding the reply to the agent's schema. Grok stays as the
fallback when only an xAI key is set. Every provider failure reads as a fixed
sentence, and the key never reaches the page or the log.

## Shipped

PR #68 squash merged as `14c8536` at 12:59Z. Images published from that commit
under tag `14c8536ef4ae`. `deploy-hostinger.yml` ran a dry run, then the live
tag swap at 13:02Z (run 35864345536). The log shows web, worker and provider
recreated on `14c8536ef4ae`, each healthy, and the public probe of
`https://editforge.online/api/health` at 13:03:06Z answered `healthy` with
`productionReady: true`.

The panel still says "Agent connection needed". That is correct until the key
is installed. No page read of the new Canvas code was taken; the evidence is
the image tag and the health probe.

## Verification, and what it cost

Head `71c85f3` passed 447 vitest and 19 worker tests, typecheck, lint, npm
audit and the build, with CI green. Earlier rounds killed 38 of 38 mutations
and drove the Canvas in real Chromium at 390 and 1440 pixels with a fake key.

Tee called out the verification spend on 2026-09-23 and was right. After CI
went green on `d61b65c`, three more workflow rounds went to minor and nit
findings: a phone scroll case, a 200 HTML answer, and wording in the key
script. Each was real, and none justified a multi-agent run. The rule taken
from it: once CI is green and the blockers are closed, remaining nits get one
local check and ship, not another workflow round.

## The key install script

`/root/ef-anthropic-key.sh`, v3, sha256
`0736856e85d91412b8e947c4688f845167f153255e883e460135627cea38f81b`. It checks the
key with Anthropic before writing (valid, can use the model, has credit,
accepts the reply format), writes one line of `.env` with a backup, recreates
only the web container from the image it already runs, and restores the backup
on a refusal. v2 had a full cold critic and a partial real Docker run. v3 closes
the critic's findings and passed seven scenarios in the stub harness; it was
not run against a real daemon.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_floor-agent-on-claude_v1_2026-09-23-1300.md
DATE: 2026-09-23
DECISIONS: Tee ruled to switch the Floor Agent to Claude, with the objection logged that it needs a funded Anthropic key. Default model Claude Sonnet 5 at $2 in and $10 out per million tokens. Tee funds the key on 2026-09-24.
FINDINGS: The Floor Agent had never had a provider key. The Google sign-in failure was a wrong client secret and is fixed. Three verification rounds after CI went green spent Tee's usage on nits.
OPEN: Tee funds the Anthropic account, creates a workspace-scoped key with a spend limit, and runs bash /root/ef-anthropic-key.sh on 2026-09-24. The first Floor Agent message then gives the real per-turn cost from the floor_agent_turn log. The old Google client secret can be deleted in Google Cloud. Pre-existing follow-ups: a rejected POST fetch shows only at the top of the page, and a second unsaved failure replaces the first.
STATUS: Merged, deployed and health checked. Agent inactive until the key is installed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
