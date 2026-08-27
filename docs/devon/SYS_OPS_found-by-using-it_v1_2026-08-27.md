# Found by using it (v1, 2026-08-27)

Status doc for the second arc of 2026-08-27. Supersedes nothing. Companion to
`SYS_OPS_presence-hardening-and-recovery_v1_2026-08-27.md`, which closes the
earlier arc of the same day; that one began as an adapter proof and ended in
four merged pull requests. This one began the moment Tee first used what those
four had built.

Tee authorized merging and delegated in-arc decisions under the same standing
grant.

## What makes this arc worth its own doc

Four defects, four pull requests, and not one of them was found by a test.

Every one surfaced because Tee used the estate and said what he saw: a
screenshot, a sentence mangled by dictation, "I can't hear him". In each case
the code did exactly what it said it would do, the tests passed, CI was green,
and the software was wrong anyway. Two of them had been shipping silently for
as long as the features existed.

That is the finding. The rest of this doc is the receipts.

## Scoreboard

| Item | State | Receipt |
|---|---|---|
| CORS says what it allows | DONE | PR #87, merged `de0da1b`; `test_cors_configuration.py` |
| A cut result says it was cut | DONE | PR #88, merged `4a5fbba`; `test_devon_read_continuation.py` |
| DEVON knows which repo he can reach | DONE | PR #89, merged `1be63e9`; `test_devon_repo_scope.py` |
| DEVON can be heard on iPhone | DONE | PR #90, merged `490c131`; confirmed by Tee, not by a test |
| Production CORS allowlist | FIXED | Railway variable, live 20:30; startup log now prints 8 origins |
| Passkey relying party | FIXED | `PASSKEY_RP_ID` and `PASSKEY_ORIGIN` repointed at the host in use |

## The four, in the terms worth remembering

**Every browser call was refused, and the server looked healthy.** The API
logged 200 for the reads and 400 for the preflights, which is what a working
service looks like from the server side. The screen said "Load failed", which is
Safari's wording for a fetch that never completed and says nothing about why.
Diagnosis meant pulling Railway's HTTP stream and reasoning from a 400 on an
OPTIONS back to an allowlist that did not contain the front end's hostname. The
project serves under three hostnames and only one had ever been considered.

Two consequences worth separating. The lockout that produced the whole recovery
path in the earlier arc was probably never a forgotten password: login is a
preflighted POST and would have failed identically whatever Tee typed. And the
UI was repeating the browser's own wording, so a CORS refusal read on screen as
a rejected credential. The API now states its allowlist at startup and warns
about the two states that look correct and are not: an entry no Origin header
can ever equal, since a trailing slash or a stray space is present, plausible
and dead under exact string comparison; and an allowlist that is entirely
loopback on a deployed API.

**A truncated result that would not admit it.** Minutes after the GitHub adapter
first worked end to end, DEVON called `github.read_file` three times in one turn
and got an identical body each time, ending mid token. Nothing was broken.
`Observation.from_result` cut every successful result to 1000 characters and
said nothing, so the model saw content stopping mid word, correctly concluded it
was missing the rest, and asked again. The retry was the right instinct served
by the wrong information. Both halves had to change: a note without an offset is
an apology, and an offset without a note is a feature nobody discovers. Since
approvals became single use earlier the same day, each of those three calls also
burned one.

**A required argument with no discoverable value.** DEVON asked Tee which
repository to read. There was exactly one on the allowlist and he had no way to
know it: the catalog handed to the model carries name, description, risk,
parameters and blast radius, while the allowlist lives in a separate structure
that only the Command Center reads. Asking was correct behaviour on the
information available, which is what made it worth fixing rather than tuning a
prompt. The estate knew the answer and had not told him.

**Speech that was never going to be heard.** iOS Safari refuses to produce sound
from `speechSynthesis` until the page has spoken once inside a genuine user
gesture, and it refuses silently. Every `speak` call ran after an await, so on
iPhone the engine stayed locked and every line was dropped without a trace. The
voice toggle would have unlocked it and defaults to on, so nobody ever taps it.
Ruling out the mute switch was Tee's, and it was the step that made the rest
diagnosable.

## What this arc did not verify the usual way

PR #90 shipped without the evidence the other three carry. There is no iPhone in
the build environment and no browser that reproduces Safari's gesture rule, so
the case rested on the code path, documented platform behaviour, and Tee's
report. That was said in the pull request, in the commit, and to Tee before he
was asked to try it. He confirmed it afterwards. The confirmation is worth
recording precisely because the claim was made without it: an unverifiable fix
labelled as unverifiable is a different object from one quietly presented as
proven.

## Verification discipline, and where it caught its own author

Every change was validated to CI parity before push: full suite against
PostgreSQL 16 with pgvector, ruff, and the alembic round trip; web changes
through `tsc --noEmit` and a production `next build` with exit codes captured
directly. The suite went 1055, 1074, 1100, 1110, each rise matching exactly the
tests added.

Negative controls were run on every change, and twice they failed against the
tests rather than the code:

- On #88, removing the windowing call from the handler left all 23 tests
  passing, because the first draft tested the helper and never proved the
  handler called it. That is precisely how a fix gets reverted unnoticed months
  later. Wiring tests were added, and the control then bit.
- On #89, a deliberately broken build differing only by a capital letter passed,
  because the assertion was case sensitive. It now compares lowercased.

A negative control that finds nothing has told you nothing. Two of eighteen here
found a hole in the test rather than the fix.

## Corrections made to the steward skill

- CI is five jobs. `web-ci.yml` is path filtered to the web workspace and never
  appears on a run of Python only pull requests, which makes CI look like
  exactly four until the first web change.
- The local Postgres cluster lives at `/var/lib/pgtest`. The Debian skeleton at
  `/var/lib/postgresql/16/main` also exists, and pointing `pg_ctl` there fails
  with a message that reads like a broken install rather than a wrong path.
- Piping `pytest` into `tail` reports tail's exit code, the same trap already
  recorded for `tsc`. A run with 154 collection errors exits 0 through a pipe.

## What is still owed

- **Tee.** Retire the duplicate Vercel project `meta-supreme-apex-genesis`. It is
  paused and posts a failing status on every pull request that is red identically
  on main. No delete tool exists in the Vercel MCP surface, so it is a dashboard
  action.
- **Tee.** Register a fresh passkey at the Command Center. Changing the relying
  party id invalidated any credential registered under the old one, which is
  what he asked for; the new one has to be created on the host now in use.
- Preview deployments still cannot reach the API. Vercel mints a hashed hostname
  per branch, so no fixed allowlist covers them. The fix is an origin regex
  scoped to the team suffix, which is a security decision rather than a bug fix
  and was deliberately left to Tee: with `allow_credentials` on, a pattern that
  is too loose would admit any deployment on the platform.
- `browser.navigate` still opens no browser. Its output says so; the capability
  remains unbuilt.

## The lesson, stated once

Tests prove that code does what its author believed. They cannot prove the
belief was right. Every defect in this arc lived in the gap between those two
things, and the only instrument that reached the gap was a person using the
software and describing what happened. Four times in one evening the fastest
path to a real bug was a screenshot.
