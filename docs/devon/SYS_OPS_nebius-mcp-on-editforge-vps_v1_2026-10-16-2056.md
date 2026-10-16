# Nebius MCP server on EditForge VPS

Status doc for the arc of 2026-10-16. Tee asked for the Nebius MCP server to be
installed by following `nebius/mcp-server` `AGENT_SETUP.md`. No code or config
in this repository changed; this doc is the only repo change. The install lives
on EditForge VPS (`srv1936199`), plus one scheduled task and one Notion page.

## Where it lives and why

The guide was first run inside the cloud container. Three Nebius hosts were
refused by the egress proxy in turn: `storage.eu-north1.nebius.cloud` (the
installer), `artifacts.nebius.cloud` (the binary) and `api.eu.nebius.cloud`.
Tee opened them across four environment edits; `artifacts.nebius.cloud` took
two. The CLI then installed and the server connected, but a container has no
browser for the Nebius sign in and does not survive being reclaimed.

The three hosts are still on the environment's allowed list. Nothing now
depends on them: the VPS reaches Nebius on its own network, and the monthly
recheck below needs only GitHub and PyPI. Removing them is Tee's call and costs
nothing.

Tee ruled on a card to put it on his own machine, then on a second card to use
EditForge VPS rather than the n8n VPS or a laptop, because the CLI was already
half there. Every VPS step ran through Termius on his phone, one command per
message, judged against a marker line.

## What is on the VPS

Every value here was read off output Tee pasted from the VPS. None was read by
this session directly.

| item | value |
|---|---|
| Nebius CLI | 0.12.291 at `/root/.nebius/bin/nebius` |
| profile | `def`, default, tenant `apricot-duck-tenant-mbm`, default project `default-project-eu-north1` |
| uv and uvx | 0.13.1 at `/root/.local/bin` |
| Claude Code | 2.1.300 |
| MCP entry | user scope in `/root/.claude.json`, name `nebius`, `SAFE_MODE=true` |
| shell | `export MCP_TIMEOUT=120000` appended to `/root/.bashrc` |
| plugin | `agent-archive` disabled, because its startup hook asked to create an account with a third party on every Claude run |

The registered command:

```
claude mcp add --env SAFE_MODE=true --transport stdio --scope user nebius -- /root/.local/bin/uvx --refresh-package nebius-mcp-server --with "pydantic<2.14" "nebius-mcp-server@git+https://github.com/nebius/mcp-server@main"
```

## Five things that broke

**The guide's own command does not start, as of 2026-10-16.** The package caps
`mcp` at `<=1.16.0`, uvx resolves mcp 1.16.0 with pydantic 2.14.1, and the
server dies on
`ImportError: cannot import name 'eval_type_backport' from 'pydantic._internal._typing_extra'`.
Reproduced twice in cloud containers, once by this session and once by the
critic; adding `--with "pydantic<2.14"` got past the import to the server's own
startup check. Anyone running the guide unchanged on that date would hit the
same error. A later upstream or pydantic release may change that, which is what
the monthly recheck watches.

**The first connect timed out.** `claude mcp list` reported
`Failed to connect, MCP server "nebius" connection timed out after 30000ms`.
The likely cause is that the first start builds the package from GitHub. The
fix applied two changes together, one manual run to fill the uv cache and
`MCP_TIMEOUT=120000`, and the same check then read Connected. Which of the two
carried it is not separated.

**A marker passed on a failure.** The first step 3 command ended in
`claude mcp list && echo "STEP 3 OK"`. It printed `STEP 3 OK` directly under
the timeout line, because `claude mcp list` exits 0 when a server fails. The
rerun gated the marker on `grep -q Connected`. A success marker has to depend
on the condition it names, not on the exit code of the command beside it.

**The Nebius sign in on a headless box.** `nebius profile create --no-browser`
printed an authorize link whose redirect is `127.0.0.1:43557`, which on a phone
points at the phone. The redirect address was carried back by `curl` from a
second Termius session on the VPS, and the waiting CLI completed.

**The Claude Code login on the VPS.** Claude Code there had an expired
Anthropic login. Its `/login` link wraps over several lines in Termius, a
manual selection cut it short, and Live Text on a screenshot corrupted it
(`ß`, `ó`, `«` and Cyrillic look alikes). Claude's own copy key was the
working path.

## What is proved and what is not

Proved, each from output Tee pasted:

- `nebius version` returns 0.12.291 and `nebius profile list` returns
  `def [default]`.
- `claude mcp list` with `MCP_TIMEOUT=120000` returns `nebius` Connected.
- `claude -p` calling `nebius_profiles` returned `{"def": {"name": "def", "is_active": true}}`.
- `claude -p` with `nebius_cli_execute` listed the tenant's default projects
  from the live API. Three rows were on screen (`me-west1`, `us-central1`,
  `us-north1`); the `eu-north1` row had scrolled off and was not seen.
- `claude plugin disable` returned `Successfully disabled plugin: agent-archive`.

Proved in this session's own tools: the scheduled task exists with the cron and
first run below, and the DEVON thread log page was created and later updated.

Not proved:

- Whether the server connects inside the default 30 seconds now that the cache
  is warm. Tee ruled not to measure it.
- Whether `agent-archive` stays off after a restart. In the cloud session it
  lists as `agent-archive@synced`, which suggests it comes from the account.
  Check: run `claude plugin list | grep agent-archive` on the VPS after the
  next reboot; if it is back, turn it off in claude.ai plugin settings.
- That `default-project-eu-north1` appears in the live list. Check: scroll the
  same output, or run `nebius iam v2 project list --parent-id` with the tenant
  ID on the VPS.
- Any Nebius write. None was attempted. That safe mode refuses delete,
  deactivate, purge and update comes from the server's own instructions, not
  from a test.

## Rulings

Taken on cards on 2026-10-16:

1. Install on Tee's own machine, then on EditForge VPS.
2. No browser on the VPS; sign in with `--no-browser`.
3. Disable the Agent Archive plugin rather than create an account.
4. Keep the pydantic pin and recheck it monthly.
5. Keep the two minute connect limit rather than measure 30 seconds.
6. Let the cloud session's half install expire with its container.
7. Close the arc in full: this doc, a fresh critic, a merged PR.

The monthly recheck is scheduled task `Nebius pydantic pin recheck`,
`trig_01FBQSvxz9BWTNtAihHWabnX`, cron `52 14 1 * *` UTC, first run
2026-11-01T14:52Z. It starts a fresh cloud session in this environment, runs
the server without the pin, changes nothing, and reports `Pin still needed:`,
`Pin can come off:` with the one line to rerun the registration, or
`Unverified:` with a cause. It needs no Nebius sign in: with no CLI installed,
a fixed package stops at the server's "Nebius CLI is not installed" check, and
the task's prompt treats that stop as the pass. It stores no connectors, which
it does not need.

The thread log entry for this arc is
https://app.notion.com/p/3fb68ff50db68168b3cce59f54e3daae, under Systems.

The fresh critic ran three lenses, checkable claims, house rules and honesty,
each finding re-run by an independent verifier. Eleven findings came back,
none refuted. Two were confirmations with no defect. The other nine were minor
wording and labelling problems, all corrected in this version.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_nebius-mcp-on-editforge-vps_v1_2026-10-16-2056
DATE: 2026-10-16
DECISIONS: Tee ruled on cards to install the Nebius MCP server on his own machine and then on EditForge VPS srv1936199; no browser on the VPS, sign in with --no-browser; disable the agent-archive plugin rather than create an account; keep the pydantic<2.14 pin with a monthly recheck; keep MCP_TIMEOUT=120000 rather than measure the 30 second default; let the cloud session's half install expire; close the arc in full with this doc, a fresh critic and a merged PR.
FINDINGS: as of 2026-10-16 the guide's command does not start, because mcp capped at <=1.16.0 fails against pydantic 2.14.1 on eval_type_backport, fixed with --with "pydantic<2.14" and reproduced twice; the first connect timed out at 30000ms and connected after a warm cache and MCP_TIMEOUT=120000 applied together, which of the two carried it is not separated; a STEP 3 OK marker printed under a failed connect because claude mcp list exits 0, rerun gated on grep Connected; the Nebius sign in redirects to 127.0.0.1 on the VPS and was completed by curl from a second Termius session; Termius cut the long Claude /login link and Live Text corrupted it, Claude's copy key worked; the cloud container needed storage.eu-north1.nebius.cloud, artifacts.nebius.cloud and api.eu.nebius.cloud opened, which stay allowed and nothing depends on.
OPEN: remove the pydantic pin when task trig_01FBQSvxz9BWTNtAihHWabnX reports Pin can come off, first run 2026-11-01T14:52Z; after the next VPS reboot check claude plugin list for agent-archive and disable it in claude.ai if it is back; confirm default-project-eu-north1 in the live project list; unmeasured whether the server connects inside 30 seconds, by ruling; no Nebius write attempted; removing the three Nebius hosts from the environment allowlist is optional and Tee's.
STATUS: live on EditForge VPS from pasted output: Nebius CLI 0.12.291 signed in as profile def, MCP server registered with SAFE_MODE=true and Connected under MCP_TIMEOUT=120000, nebius_profiles and a live project list both returned through claude -p, agent-archive disabled. Monthly recheck task scheduled. DEVON thread log at https://app.notion.com/p/3fb68ff50db68168b3cce59f54e3daae. Fresh critic run, 11 findings, 0 refuted, 9 minor defects corrected. No repository code changed. Arc closes when this doc's PR merges.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
