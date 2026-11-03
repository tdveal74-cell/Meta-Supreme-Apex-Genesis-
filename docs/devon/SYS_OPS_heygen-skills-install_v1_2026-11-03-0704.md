# HeyGen's agent skills and CLI: review and container install

Status doc for Tee's request at 2026-11-01T17:35:32Z: "Read https://raw.githubusercontent.com/heygen-com/skills/master/INSTALL_FOR_AGENTS.md and follow it. Ask me for any API keys you need." Written 2026-11-03, from notes taken on 2026-11-01. The install lives in this cloud container only and is gone when the container is reclaimed. Nothing was added to this repository except this record.

## What was read

- The guide, `INSTALL_FOR_AGENTS.md`, fetched at 17:35:39Z: 17069 bytes, sha256 beginning `6ded4866180ed988`.
- The skills repository, `heygen-com/skills` on `master` at `1bd5e4d` (2026-07-14), version 3.2.0, MIT licence, 47 files: three skills, `heygen-avatar`, `heygen-video` and `heygen-translate`, with their references, a `setup` script, an update-check script, plugin manifests for four hosts and three GitHub workflows.
- The CLI installer the guide pipes to bash, `https://static.heygen.ai/cli/install.sh`: 224 lines, sha256 beginning `c0e3d0d68768b7d9`.

## The review

One workflow, `wf_e5d5a255-f74`, sent four read-only readers over the skills' contract, the scripts and manifests, the installer, and the references, and one independent verifier over each reader's claims. 153 claims: 147 confirmed, 5 unsettled, 1 refuted.

Nothing in the repository installs hooks or runs when a skill loads. `setup` makes no network call, and the update check fetches one version file from GitHub only when asked. The installer downloads from `static.heygen.ai`, checks a SHA-256 checksum from the same host before installing to `~/.local/bin`, needs no root and edits no shell profile. It verifies no signature, so the checksum catches corruption and not a compromised host.

The skills' defaults conflict with the house rules in these places, each confirmed by a verifier:

- Face and voice. The avatar skill makes "the agent" a face by default, from a text prompt, and falls back to HeyGen's stock avatars. Voices come only from HeyGen's library. Neither the video skill nor the avatar skill takes an ElevenLabs voice or an audio file; the only audio-file input is in the translate skill, where it replaces HeyGen's clone of the speaker.
- Spend. "Quick Shot" renders on request with no gate, a change after delivery re-renders with no new gate, a single translation submits silently, and the guide's own smoke test is a paid render. No step states a cost first.
- Disclosure. All three skills tell the agent never to say which route it is using, which hides whether plan credits or API credits pay, and not to announce paid calls.
- Keys. The translate skill asks the user to paste the key into chat, the guide puts it in a shell profile, the CLI login writes `~/.heygen/credentials`, and a debug step prints the key's first 8 characters.
- Data leaving the machine. In CLI mode each skill sends HeyGen a rating and comment after every task, analytics are on unless opted out, finished videos go to Telegram or Discord without a confirmation, and a fallback makes source video or captions public on S3 or a gist.
- Script and footage. The Video Agent prompt carries a directive letting it expand the script, and the default style adds stock media.
- Billing switch. A set `HEYGEN_API_KEY` sends the video and translate skills to the CLI and API credits instead of the connector and plan credits, with no question asked. The skills look for MCP tools named `mcp__heygen__*`; this session's connector is `mcp__HeyGen__*`, and whether the match is case sensitive is unverified.
- Price. The guide says Avatar V costs "roughly 6 credits per minute"; HeyGen's API pricing page lists Avatar V on a digital twin at $7.20 a minute. The record does not choose between them.

## The rulings

Tee answered one card at 17:55:29Z, each answer the recommended option except the second:

| question | answer | what the card said it costs |
|---|---|---|
| how to install | "Install, house rules win (Recommended)" | lives in this container only; house rules override the skills' defaults every time |
| HeyGen's CLI | "Install CLI, analytics off" | a remote script piped to bash, checksum checked and not signed; a set key would switch the skills to API credits |
| the guide's smoke test | "Skip it (Recommended)" | none |

## What was installed

- The reviewed clone, copied to `~/.claude/skills/heygen-skills`, at `1bd5e4d` with a clean tree.
- The CLI, v0.11.0, to `~/.local/bin/heygen`, by running the reviewed `install.sh` from the scratchpad rather than a fresh download, with `HEYGEN_NO_ANALYTICS=1` set for the run. The binary's sha256 begins `b4923543e1b0d479`. `~/.heygen/config.toml` holds `analytics = false` and `update_check = false`; the second was not asked for and is one command to undo.
- No key anywhere. `HEYGEN_API_KEY` is set in no profile and no file, and no `~/.heygen/credentials` exists. At 17:56:38Z `heygen user me get`, run with the variable set to a placeholder for that one command, returned the account through the environment's proxy, so the CLI uses Tee's network secret without holding it.
- Step 5 of the guide, giving the agent a face, was skipped, and so was the smoke test.

How the house rules win, in practice: every HeyGen call uses Tee's own face, every paid call goes on a card with its cost, the route and which balance pays are named, the script is used word for word, and nothing is sent to anyone without Tee watching. `HEYGEN_API_KEY` stays unset except on the single command that needs it.

## Not verified

- Whether the three skills load in this session after being copied in.
- What the CLI binary sends beyond the installer, and whether it honours `analytics = false` in every command. Only the installer was read.
- Whether the skills' MCP detection matches this session's connector name.

## Open

- A copy of the skills in this repository, so they load in future sessions, is a separate ruling.

## DEVON RECEIPT

AREA: Systems, TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_heygen-skills-install_v1_2026-11-03-0704.md
DATE: 2026-11-03
DECISIONS: Tee asked at 17:35:32Z for HeyGen's agent install guide to be followed. On a card at 17:55:29Z he chose to install the skills with the house rules winning over their defaults, to install HeyGen's CLI with analytics off, and to skip the guide's paid smoke test.
FINDINGS: A review of 153 claims, 147 confirmed by independent verifiers, found the skills install no hooks and the CLI installer checks a checksum but no signature. Their defaults conflict with the house rules on whose face and voice, ungated spend, silent routing, key handling, data sent off the machine and script fidelity.
OPEN: a copy in the repository for future sessions, on a ruling; the CLI binary's own network behaviour, unread.
STATUS: Installed in this container only: the skills at 1bd5e4d in ~/.claude/skills/heygen-skills and the CLI v0.11.0 in ~/.local/bin with analytics and update checks off. No key held; the CLI reads through the proxy.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
