# Presence hardening and account recovery (v1, 2026-08-27)

Status doc for the 2026-08-27 arc that began as an adapter proof and ended
with four merged pull requests, a schema migration applied to the live
database, and a working password recovery path. Supersedes nothing.
Companion to `SYS_SPEC_presence-authority_v1_2026-08-26.md`, which describes
the presence model this arc hardened rather than changed.

Tee authorized merging and delegated in-arc decisions
("Merge and continue until completion. You can make decisions in my behalf
per your recommendations and only report back when done. You also have
permission to merge on my behalf.").

## How the arc started

The task was to prove DEVON's capability adapters against their real
backends rather than against mocks. Ten adapters were exercised. Nine
behaved as documented. The tenth produced a green tick that meant nothing,
and unpicking it produced everything below.

`operator.command` was handed `{"command": "echo", "args": ["adapter-proof-marker"]}`.
It ran a bare `echo`, returned ok with empty output, and said nothing about
the ignored key. Had the proof stopped at the green tick it would have
reported a working capability that had done nothing.

## Scoreboard

| Item | State | Receipt |
|---|---|---|
| Declared argument surfaces on every tool | DONE | PR #82, merged `b97a6a3`; `test_devon_tool_arguments.py` |
| Approvals are spendable, not standing | DONE | PR #83, merged `c3ee0c1`; migration `013_approval_consumption` |
| A forgotten password is recoverable | DONE | PR #84, merged `a509e7a`; `test_devon_password_recovery.py` |
| The recovery path has a door in the UI | DONE | PR #85, merged `b2c19fe`; live at `/command-center` |
| GitHub writes configured in production | DONE | `DEVON_GITHUB_TOKEN` + `DEVON_GITHUB_ALLOWED_REPOS` set on Railway |
| First real read by Tee through the conversation path | DONE | Tee, 2026-08-27, in the Command Center; see "The chain was closed by the only person who could close it" |
| An approval actually spent by a live effect | WAITS ON TEE | a read is not approval gated, so this arc still has no live receipt for `013_approval_consumption` |

## The three defects worth remembering

**An argument a tool does not read must not be silently dropped.** The
silent drop is a nuisance. The governance consequence is the defect: the
approval binding is computed over the whole argument dict, so the card and
the queue row named arguments the process was never going to honour.
"Approve what you see" holds only while every key the human reads is a key
the adapter honours, and a model inventing plausible parameter names is
ordinary behaviour rather than an attack. `ToolSpec` now declares its
surface and both invocation paths refuse anything else. In the conversation
path the check sits ahead of the presence verdict, the binding, and
`_authorise`, so an invented key never reaches a card and never mints an
approval row. The guard immediately caught the same defect in this
repository's own tests, where `runtime.schedule_goal` was handed a cron it
does not read while the test asserted the write had succeeded.

**An approval was permission forever, not permission once.** The capability
boundary satisfied itself that a record was APPROVED and bound to the exact
arguments in hand. Both facts stayed true forever, because nothing marked an
approval spent, so anyone holding the runtime metadata could replay a
governed effect indefinitely and every replay passed every check honestly.
Demonstrated by removing the new consume call and watching a second
identical `github.create_branch` return ok with a fresh branch. This
predates presence authority and survived it: presence changed who may
approve and how fast, not how long an approval lasts once given.
`ApprovalState.CONSUMED` closes it through a compare and set transition on
both stores. The spend goes last among the checks, so a call refused for any
other reason leaves the approval intact, and before the handler, so a failed
effect needs a fresh approval rather than leaving a live one behind a
partial write.

**A forgotten password was an unrecoverable account.** The API had register,
login and passkeys and nothing between them, and nothing in it can send a
link anywhere. Tee hit exactly that on the first real sign in to the Command
Center. `POST /auth/password/reset` borrows the trust boundary the Operator
Bridge already uses: a secret held in the deployment environment, readable
only by whoever owns the deployment. It fails closed when
`DEVON_RECOVERY_KEY` is unset or under 32 characters, and the key is
verified before the account is looked up so the endpoint cannot be used as a
user directory. `DEVON_RECOVERY_EMAIL` optionally pins the key to one
account. PR #85 gave it a door: the sign in panel toggles into recovery
mode and signs straight in with the password just set.

## Production state at close

Railway service `api` in project `devon-api` carries `DEVON_GITHUB_TOKEN`,
`DEVON_GITHUB_ALLOWED_REPOS`, `DEVON_BROWSER_LIVE_FETCH`,
`DEVON_RECOVERY_KEY` and `DEVON_RECOVERY_EMAIL`, all with clean names.
Migration `013_approval_consumption` applied to the live database on the
PR #83 deploy; the deploy log records
`Running upgrade 012_live_state_ledger -> 013_approval_consumption`
followed by `Application startup complete`. The Command Center at
`/command-center` serves the recovery toggle from the PR #85 production
build.

Three naming accidents cost three failed builds and no downtime, because a
failed Railway build leaves the previous deployment serving. Worth
recording because the failure messages are indirect: a variable named
`DEVON PRODUCTION` fails the build with `secret DEVON not found`, and a
trailing space in `DEVON_GITHUB_TOKEN ` fails it with
`secret DEVON_GITHUB_TOKEN not found`, naming the variable you meant rather
than the one you typed.

## The chain was closed by the only person who could close it

On 2026-08-27, after the six pull requests of this arc and the two that
followed it were live, Tee signed in to the Command Center, spoke to DEVON,
and DEVON read a file for him. He reported it in three words and then in
five. That is the acceptance test this document was written to leave owed,
and it is now performed.

What that exchange proves, and it is most of the chain:

- The Command Center is served, reachable, and current.
- The CORS allowlist actually contains the front end's hostname. This is
  worth stating separately because the failure it replaced looked exactly
  like a rejected credential from the browser and exactly like a healthy
  service from the API, which is what made it cost an afternoon.
- Sign in works against the live database, on the recovery path built in
  PR #84 and given a door in PR #85.
- The conversation path reaches a real model, and the model reaches a real
  adapter against a real backend rather than a mock.
- The GitHub token and the repository allowlist are correct in production,
  the adapter honours them, and the presence ruling admits the call.

What it does not prove, and the distinction matters more than it looks:

**A read does not spend an approval.** Approvals gate WRITE and
HIGH_IMPACT tools. A read is neither, so it passes the capability boundary
without ever minting or consuming an approval row. This document previously
described the read as the acceptance test for "an approval that now gets
spent when the effect runs", and that sentence was wrong: the two things
travel different paths through the same boundary. Migration
`013_approval_consumption` is applied to the live database and the consume
call is covered by tests with a negative control, but no effect in
production has yet spent an approval in front of Tee. The first governed
write he approves and watches run is a separate acceptance test, and it is
the one still owed.

The honest summary is that the estate can now be talked to and can act on
what it is told, and that the governance layer sitting between those two
facts has been proven everywhere except in production.

## What is still owed, and by whom

- **Tee, and only Tee. Done on 2026-08-27.** See the section below. What it
  left standing is narrower and is stated there: no live effect has yet spent
  an approval, because the exchange that closed the chain was a read.
- **Tee.** Retire the duplicate Vercel project `meta-supreme-apex-genesis`.
  It is paused, and it posts a failing commit status on every pull request
  that is red identically on main. No delete or disconnect tool exists in
  the Vercel MCP surface, so this is a dashboard action.
- `browser.navigate` opens no browser and loads no page. Its output now says
  so plainly, having previously read "Navigation recorded for ...", which a
  model reads as done and then answers questions about a page it never saw.
  The tool is kept because it is the estate's only registered reversible
  WRITE reaching a real adapter, which several presence tests depend on.
  A real navigation capability remains unbuilt.

## Verification discipline used

Every change was validated to CI parity before push, per the steward skill:
the full pytest suite against PostgreSQL 16 with pgvector, ruff clean, and
the alembic upgrade / downgrade / upgrade round trip. Web changes passed
`tsc --noEmit` and a production `next build`, with the exit code captured
directly rather than through a pipe.

Every security relevant change got a negative control, because a fix without
one is not proven. Disabling the argument guard fails four tests. Removing
the consume call lets a second identical governed write succeed. Lowering
the recovery key length floor fails the short key test. Moving the account
lookup ahead of the key check fails the enumeration test.

Two corrections to the steward skill were needed mid arc, both of lines
written earlier the same day. CI is five jobs, not four: `web-ci.yml` is
path filtered to the web workspace and never appears on a run of Python only
pull requests. And a new migration touches `ci.yml` in three places, not
two; the third is an `assert revision == "<head>"` inside the Fresh Alembic
deploy heredoc, which turned the api job red on
`AssertionError: 013_approval_consumption` after 1043 tests had already
passed.
