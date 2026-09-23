# Rakazo MCP is live, and EditForge is plugged into Rakazo

Filed 2026-09-23 at 14:57Z on Tee's word "It answered, file the status doc".

## What was asked

Tee asked for two things: plug EditForge into Rakazo, and build a server that
lets Claude reach Rakazo over MCP. He later widened the second one so Claude
can also connect models and create bots.

## Rulings

Every ruling came from Tee on a card.

- EditForge access inside Rakazo: full access with the token. The objection is
  logged once: any Rakazo bot given EditForge can submit paid renders, and
  nothing in Rakazo caps that spend.
- Rakazo login for the connector: Tee's own login. The connector acts as the
  owner, so anyone holding the connector address can do what the owner can.
- Hosting: on the EditForge VPS, next to Rakazo.
- Scope: models and bots added to the tool set.

## What was built

All of it lives in the private repository `tdveal74-cell/rakazo-deploy` at
commit `eee3b36`. Nothing was added to this repository except this record.

`mcp/server.mjs` is a single Node file with no dependencies, sha256
`9b97ba541b0f4ee9cd724ac85ca0cf2840479b42d02ae46df8cc7890429b1fe3`. It signs in
to Rakazo's own API and gives Claude tools to read spaces, bots, groups and
threads, send a message and wait up to 40 seconds for the answer, stop a
thread, create and update bots, and list, connect and set default models. A
model key never passes through chat: Claude names a key stored on the server,
or hands Tee a sign-in link.

The installer is `mcp/dist/rakazo-mcp-install.sh`, sha256
`d9e4576c308465468962d75f4ef394e34a4c8c8160924e0bc2c863c2cbb4055f`, which is
the fingerprint Tee matched before running it. It checks Rakazo sign-in before
changing anything, runs the server as container `rakazo-mcp` on network
`rakazo_app`, registers EditForge inside Rakazo with the token the running
EditForge holds, then adds one site block to the shared Caddy front door. The
block is validated first, and every existing site is checked before and after
the reload, with a rollback if any site got worse.

DNS: one A record, `rakazo-mcp` to `2.24.109.87`, added through Hostinger. No
other record changed.

## How it was checked

Before the install: 29 server tests against a stand-in Rakazo built from the
library versions Rakazo pins, and 60 installer checks against stand-in docker
and curl. A fresh critic returned one major finding and eleven minor ones. The
major one was real: an interrupt during the certificate wait left the site in
place while the script said nothing had changed. All twelve were fixed and the
mutations that proved them were caught by the tests.

After the install, read back through n8n execution 864 at 14:50Z, because this
container cannot reach the VPS domains directly:

- `https://rakazo-mcp.editforge.online/health` answered 200 `{"ok":true}`
- `POST /mcp` without the key answered 401
- `editforge.online/api/health` answered 200 healthy
- `rakazo.editforge.online` answered 200

Then Tee added the connector in Claude and it answered. That is the end to end
proof: the certificate, the key, the Rakazo sign-in and the tool list all had
to work for that to happen.

## What is not proven

- EditForge being registered inside Rakazo was not observed at filing time.
  Settled at 15:01Z: `create_bot` found it and answered `editforge: given`.
- Whether a Rakazo bot can actually reach `editforge.online` from inside its
  sandbox is still unproven, because no bot on a paid model can run at all.
  See the next section.

## Bot runs are down, and it is the model

Measured through the connector at 15:01Z to 15:03Z. A probe bot given
EditForge (`create_bot` answered `editforge: given`, which settles the first
open item above) failed its run with no reply on Anthropic `claude-sonnet-4-5`
and again on OpenRouter `google/gemini-2.5-flash-lite`. A control bot with no
EditForge failed the same way on OpenRouter, so EditForge is not the cause. The
same control bot on the local `qwen3:1.7b` was accepted and sat in `running`
instead of failing; it had not replied when this was written.

It predates the connector. The Chief's last reply is 2026-09-20T07:34Z, and
every message to it since, 08:35Z that day and two test messages at 08:28Z
and 08:31Z today, went unanswered.

Tee confirmed the cause: the Anthropic API account needs funding. Why
OpenRouter failed the same way was not checked. The failed run's reason is not
readable through the connector, because Rakazo drops a run from the thread
once it ends.

Two probe bots stay in the space for the retest, `EditForge Probe` and
`Control Probe`. None of Tee's six bots was changed.

## Open

- Bots made in the Rakazo app, not through `create_bot`, get EditForge only
  once it is turned on for them in Rakazo.
- The front door's error log can record the connector address while
  `rakazo-mcp` is down. If those logs are ever shared, run the installer with
  `--rotate-key`.
- The Anthropic key for the Floor Agent is still Tee's to install on the 24th.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_rakazo-mcp-live_v1_2026-09-23-1457.md
DATE: 2026-09-23
DECISIONS: Tee ruled EditForge gets full access inside Rakazo with the token, objection on paid render spend logged. The connector uses Tee's own Rakazo login and runs on the EditForge VPS. Model connection and bot creation were added to its tools.
FINDINGS: Every bot run on a paid model fails, Anthropic and OpenRouter alike, since 2026-09-20T07:34Z; Tee confirmed the Anthropic API needs funding. EditForge is registered in Rakazo, create_bot reported it given. rakazo-mcp is live at rakazo-mcp.editforge.online, health 200 and 401 without the key per n8n execution 864, and the connector answered in Claude. Code in rakazo-deploy eee3b36, server sha 9b97ba54, installer sha d9e4576c. editforge.online and rakazo.editforge.online both answered 200 after the install; the other front door sites were checked only by the installer, whose output was not seen here.
OPEN: Fund the Anthropic API, then rerun the EditForge probe on a paid model and set the default to Sonnet 5 if Tee wants it. OpenRouter failing too is unexplained. Bot reach to editforge.online untested. App-made bots need EditForge turned on by hand. Rotate the key if front door logs are shared. Anthropic key for the Floor Agent on the 24th.
STATUS: Connector live, confirmed by Tee. Bots down on model funding.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
