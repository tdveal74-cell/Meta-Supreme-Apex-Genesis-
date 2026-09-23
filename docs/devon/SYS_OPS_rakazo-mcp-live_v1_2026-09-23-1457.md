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
- Whether a Rakazo bot can reach EditForge was unproven at filing time.
  Settled at 15:17:31Z, below.

## Bot runs were down on three providers, each for its own reason

Measured through the connector from 15:01Z, then read out of the `runs` table
on the VPS, because Rakazo drops a failed run from the thread and the worker
logs every one of those jobs as `success`. The first reading here, "it is the
model", was one provider's answer written as all three:

| provider | model | error in `runs.error` |
|---|---|---|
| Anthropic (API key) | claude-sonnet-4-5 | 400, credit balance is too low; the 08:28Z run also said the key is not scoped to a workspace |
| OpenRouter | google/gemini-2.5-flash-lite | 402, insufficient credits, the account never purchased any |
| Google | gemini-2.5-flash | 404, the model is no longer available to new users |

The Google row is a retired model id, not billing. `gemini-flash-latest` also
failed and its reason was not read. The local `qwen3:1.7b` did not fail but
never answered either, and that run was cancelled.

It predates the connector: the Chief's last reply is 2026-09-20T07:34Z.

## The fix, and the EditForge proof

On Tee's ruling, Anthropic was signed in with his Claude subscription in place
of the unfunded API key, through `connect_model` and `finish_model_signin`. It
replaced the same connection, `cmuducb81002h2kp4r9sh25pb`, now labelled
"Claude subscription", model `claude-sonnet-5`, default. Bot usage now draws on
Tee's Claude plan limits.

At 15:17:31Z the `EditForge Probe` bot on that model called EditForge's
`editforge_status` and returned its real answer: `store: file`,
`storeReachable: true`, and six providers `readyToRun`, among them runway,
elevenlabs, kokoro-local, hyperframes-local, heygen and mock. That proves the
whole chain: EditForge registered in Rakazo, the token accepted, and a bot's
sandbox reaching editforge.online.

A Gemini connection labelled "Gemini free tier" remains, on a retired model
id. Two probe bots remain in the space, `EditForge Probe` and `Control Probe`.
None of Tee's six bots was edited; those without their own model now run on the
default, and whether each carries its own model setting was not checked.

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
DECISIONS: Tee ruled EditForge gets full access inside Rakazo with the token, objection on paid render spend logged. The connector uses Tee's own Rakazo login and runs on the EditForge VPS. Model connection and bot creation were added to its tools. Tee ruled the bots run on his Claude subscription rather than a funded API key.
FINDINGS: Bot runs had failed since 2026-09-20T07:34Z on three separate causes read from the runs table: Anthropic API credit too low, OpenRouter never funded, Gemini 2.5 Flash retired. With Anthropic moved to Tee's Claude subscription on Sonnet 5, a bot called EditForge editforge_status at 15:17:31Z and got the live answer, so EditForge is registered, the token works and bots reach editforge.online. rakazo-mcp is live, health 200 and 401 without the key per n8n execution 864. Code in rakazo-deploy eee3b36, server sha 9b97ba54, installer sha d9e4576c.
OPEN: Bot usage now shares Tee's Claude plan limits. The Gemini connection sits on a retired model id. Whether each of the six bots carries its own model setting was not checked. Two probe bots to keep or delete. App-made bots need EditForge turned on by hand. Rotate the key if front door logs are shared. list_models output is cut at about 60000 characters, fix in rakazo-deploy. Anthropic key for the Floor Agent on the 24th.
STATUS: Connector live, bots running on the Claude subscription, EditForge reach proven.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
