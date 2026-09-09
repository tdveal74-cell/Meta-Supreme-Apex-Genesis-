# SYS_OPS: DEVON control plane foundations, four files mapped onto the estate and four gauntlet passes (v1, 2026-09-08)

Date: 2026-09-08
Branch: `claude/dreamy-wright-pv1f3l`, PR #176 into `main` at `e466347`, head
`732493c`; ten commits (`git log` from base to head), 55 files changed, 10521
insertions, 72 deletions (`git diff --stat`; the PR record says the same).
PR record as read for this revision: state closed, draft false, merged true,
merged_at 2026-09-08T22:18:11Z, merged_by `tdveal74-cell` (the account that
owns the repository, per the remote URL), mergeable_state "unknown".
The draft half of an earlier reading is confirmed rather than withdrawn: the
issue timeline endpoint (`issues/176/timeline`, HTTP 200, twenty events)
carries exactly one `ready_for_review`, by `tdveal74-cell` at
2026-09-08T22:18:05Z, so the PR was a draft until that instant and was merged
six seconds later. Two readings are withdrawn: the clean mergeable state,
which the record no longer keeps (`mergeable_state` reads "unknown" after a
merge and carries no history), and a clock reading given for the moment of
the fetch, which no captured command in this session records. A `date -u`
capture beside the fetch would supply the second.
The same timeline carries no `reviewed` event, and the reviews endpoint
returns an empty list. That is the record's own answer on the spec's
"Tee reviews the draft PR" gate at spec line 436: no review was submitted
through GitHub, on this PR, by anyone. What authorized the merge is treated
below as unverified from the repository.
Merged as `2b09dbd6613ac0f874478afefe9be6b0672d5743` at 2026-09-08T22:18:11Z.
Both values are read from the record rather than assumed: they were
placeholders while the merge was pending and were filled once it landed.
`git log -1 origin/main` reads `2b09dbd6613ac0f874478afefe9be6b0672d5743`,
a merge commit with parents `e466347` and `732493c`, committed
2026-09-08T18:18:11-04:00 (22:18:11Z, the PR record's merged_at), whose tree
is identical to `732493c` (`git diff --stat 732493c 2b09dbd` prints nothing).
Supersedes: nothing. Complements `SYS_SPEC_devon-control-plane-workspace_v1_2026-09-08`,
the arc's map, whose gauntlet tables and receipts table this document cites and
does not restate in full.

No ruling from Tee on the open items is recorded in this arc's commits or in
the spec; the items the spec puts to him are listed below. The merge itself is
recorded: the PR record shows it made by the `tdveal74-cell` account at
2026-09-08T22:18:11Z. Whether that merge was Tee's explicit SHIP authorization
under CLAUDE.md's ship discipline (merge only with Tee's explicit
authorization) is unverified from the repository: no commit body between
`e466347` and `732493c` records one (`git log --format=%B`, the only match on
"ruling" is `a875659` recording the session key as an open ruling), and the
spec's receipt names Tee's review of the draft PR as the next gate (spec line
436). It is unverified from the PR record too: PR #176 carries two comments
and both are from bots (`vercel[bot]`, `coderabbitai[bot]`, read from the PR
comments record in this session). The item stays unverified until Tee states
the authorization, in a comment on PR #176 or directly, and the receipt's next
gate line below carries it.

Every number below names where it came from: a file in the tree, a command run
in this session on the `732493c` tree (the checkout is the merge commit
`2b09dbd`, same tree), the Actions record for the branch and for `main`, the
PR record, or the spec's receipts table.

## What the arc was asked for and what it delivered

Tee's brief of 2026-09-08 named four foundational files. Each was mapped onto
what already stood rather than built beside it (spec, "The four foundational
files").

| Asked for | Delivered | Delivered in |
|---|---|---|
| Project structure | the spec itself: every path marked lives, built, or not built, opened and read rather than remembered | `9838313` |
| Production Docker Compose | `infrastructure/docker/docker-compose.prod.yml`. In `bd25fdd`: postgres, redis, api, presence, web, and n8n under the `executor` profile ("six services with the executor profile, five without", its commit body); every port bound to 127.0.0.1; seven secrets required (`grep -oE '\$\{[A-Z0-9_]+:\?'` on that revision, the header's `${VAR:?}` example excluded); the API connected as the `postgres` owner (that revision's line 41). In `0041cb9`: the one shot `migrate` service, the API connected as `devon_api` (compose line 146 at the head) and `API_DB_PASSWORD` as the eighth required secret (the earliest commit `git log -S` lists on the path is `0041cb9` for both `migrate:` and `devon_api`, which lists newest first and returns `0b7c36b` above it for `devon_api`); the rest defaulted (below) | `bd25fdd`, then `0041cb9` |
| Core React 3D canvas | `/presence`: a react-three-fiber canvas driven by ARKit blendshape frames, the WebSocket frame listener and sliding window buffer, the LiveKit audio hook, client VAD barge in; and the presence streaming service under `apps/presence/` that feeds it | `6f9f878`, `ab6aeff` |
| Postgres `schema.sql` for the Live State Ledger | `database/schemas/019_event_hash_chain.sql` with its Alembic twin: a SHA-256 chain over every event, an HMAC signed Universal Receipt, append only triggers, and `GET /api/v1/ledger/intents/{id}/provenance` | `6b5c613` |

The last column names the delivering commits only. Later commits in the arc
changed several of these files: `git log e466347..732493c --
infrastructure/docker/docker-compose.prod.yml` lists `bd25fdd`, `a875659`,
`0041cb9`, `0b7c36b` and `6f29aac`, so all four gauntlet closing commits
changed the compose file (`a875659` alone added 13 lines and removed 4 of it,
`git show --numstat`), with `0b7c36b` and `6f29aac` hardening it after the
`0041cb9` additions above. The same command on `database/schemas/019_event_hash_chain.sql`
lists `6b5c613` and the same four closing commits; on `apps/presence/` it lists
`ab6aeff`, `a875659`, `0041cb9` and `0b7c36b`.

On secrets, the compose header (line 42) says every secret is `${VAR:?}`, and
that overstates. `grep -n ':?'` on the file finds eight distinct variables the
stack refuses to start without: `SECRET_KEY` (line 52), `POSTGRES_PASSWORD`
(72, 128), `API_DB_PASSWORD` (75, 146), `PASSKEY_RP_ID` (155), `PASSKEY_ORIGIN`
(157), `NEXT_PUBLIC_API_URL` (212), `NEXT_PUBLIC_PRESENCE_URL` (213) and
`N8N_ENCRYPTION_KEY` (243). These default to empty with `:-`:
`RECEIPT_SIGNING_KEY` (151), `RECEIPT_SIGNING_KEYS_PREVIOUS` (152),
`DEVON_REGISTRATION_KEY` (153), `DEVON_SHELL_KEY` (154), `CARTESIA_API_KEY`
(191), `LIVEKIT_API_KEY` (193), `LIVEKIT_API_SECRET` (194), `N8N_DB_PASSWORD`
(78, 242) and the provider API keys (60, 62, 63). The receipt key's empty
default is by design: `app/services/live_state_ledger.py` lines 91 to 101 use
a dedicated `RECEIPT_SIGNING_KEY` when set and otherwise derive the receipt key
from `SECRET_KEY`, so a receipt is never signed under the JWT key itself. The
header sentence stands in the merged tree as written.

There is deliberately no second schema file. The ledger's ten tables and
`universal_receipts` have lived in `012_live_state_ledger.sql` and its increments
since 2026-08-26 (spec); a file restating them would be the second registry that
drifts. The schema is the ordered set under `database/schemas/`, applied by
`conftest.py` for tests and by Alembic for deploys, and the api job proves the
two builds produce the same database.

## The gauntlet, four passes

Four fresh critics with no build context attacked the branch in turn. Verdicts
and scores are as the spec's gauntlet section records them; the closing commit
and its time are from `git log`.

| Pass | Verdict and scores | Closed by | What the pass changed |
|---|---|---|---|
| 1 | QUARANTINE; correctness 2, security 3, flagship 2, mean 3.5 | `a875659`, 20:34:32Z | nine findings: the payload is hashed as PostgreSQL renders the jsonb, not as Python rendered it; a BEFORE DELETE trigger on `events` and `universal_receipts`; unhashed pre 019 rows count only as a prefix and the writer refuses to append to a chain that does not verify; the example env defaults to `mock` and a keyless provider refuses by naming `PRESENCE_INFERENCE`; receipts signed under a derived or dedicated key with a rotation ring, never `SECRET_KEY` itself; a LiveKit token only for the caller's own open session under the verified identity; a non finite synthesiser timeline fails the turn by name; `verified` requires a receipt; NaN in a payload is a 409 at the door |
| 2 | QUARANTINE; security 3, mean 3.8 | `0041cb9`, 21:00:29Z | six findings: BEFORE DELETE on `intents` admitting only the cascade from `users`; the API runs as `devon_api` with a one shot `migrate` service as the owner and every trigger `ENABLE ALWAYS`; the derived key of the current secret is always in the ring and `secret:<old>` entries derive an earlier one; a NUL string is refused at the door, 409; `verified` requires a complete chain and a pre 019 prefix is receipted on trust and says so; non finite wire numbers are refused by name and the socket stays up |
| 3 | QUARANTINE; security 2, mean 3.4 | `0b7c36b`, 21:26:22Z | seven findings: the delete guard asks whether the parent row is gone rather than how deep the trigger stack is, TEMP is revoked from PUBLIC, and the depth 2 temporary table attack is a negative control in the suite; DELETE is granted only where the application deletes and never on `users`, `intents`, `events` or receipts; the owner credential reaches `migrate` only, `presence` holds none, n8n has its own role and database; the opening event hashes the owner and the statement and a BEFORE UPDATE trigger on `intents` admits `state` and `updated_at` only; `alembic_version` is read only for the role; a 400 digit wire number is refused instead of overflowing `float()`; a written out NUL escape is ordinary text |
| 4 | PASS-WITH-CONDITIONS; security 5, verification 4, every dimension 4 or above, mean 4.5 | `6f29aac`, 22:01:10Z | four conditions: an event or receipt leaves with either of its two parents and is refused while both stand; the opening event hashes the effect flag and the verifier compares owner, channel, statement, effect flag and the derived state, naming each; the 019 header and trigger message state the id and creation time as trigger held, not hashed; the postgres healthcheck asks `pg_isready -h 127.0.0.1` with a 30 s start period (compose lines 90 and 94) |

The fourth critic ran its battery as a real `devon_api` login and found no path
from the shipped role to a verified rewrite or an erasure (spec). The three
revise cycles the gauntlet allows were spent on passes 1 to 3, so the pass 4
closure is author verified with reproducing tests and was not put before a
fifth critic.

One design residual is recorded, not fixed: a lawful late event after a receipt
reads to the verifier like growth past the receipt (spec, after the pass 2 table).

## The dependency audit incident

Read from the Actions record for `ci.yml`, at job and step level:

- Run 614 on `0b7c36b`: the `pnpm audit the locked workspace` step ran at 21:27:15Z and passed.
- Run 615 on `6f29aac`: the same step ran at 22:01:47Z and failed with exit code 1; the pip-audit step and the other four jobs in that run passed (job 102254277987 failure, the other four success, from the run's job record). The advisory the step log named is GHSA-p293-qw3h-jr36, package `next`, vulnerable `>=13.4.0 <15.5.24`, patched `>=15.5.24`, path `apps__web>next`, with `https://github.com/advisories/GHSA-p293-qw3h-jr36` as its More info line. That log lists exactly one advisory and ends `1 vulnerabilities found`, `Severity: 1 critical`, then `Process completed with exit code 1` at 22:01:48Z (job 102254277987 step log, read in this session through the GitHub job logs API; the raw log endpoint answers 302 to `productionresultssa17.blob.core.windows.net`, which this session's egress proxy refuses (`curl: (56) CONNECT tunnel failed, response 403`), so the log was read through the connector rather than with `curl`). Re-measured instead in this session: `6f29aac`'s own manifests staged into a throwaway directory (`git show 6f29aac:pnpm-lock.yaml`, `:package.json`, `:pnpm-workspace.yaml`, `:apps/web/package.json`, `:packages/ui/package.json`), then `pnpm audit --audit-level=moderate`, exits 1 with "2 vulnerabilities found" and "Severity: 2 critical". Both are `next` on path `apps__web>next` and both are patched at `>=15.5.24`: GHSA-p293-qw3h-jr36 above, and GHSA-2xp9-vwfh-vxw4, vulnerable `>=10.0.0 <15.5.24`, the Image Optimization AVIF path. The two counts are reconciled by when each was read, not by the tree: at 22:01:48Z the audit saw one advisory, and the same `6f29aac` manifests audited in this session see two, the extra one being GHSA-2xp9-vwfh-vxw4. Why that second advisory was absent at 22:01:48Z is unverified here: `pnpm audit` resolves advisories against the npm registry, and nothing captured in this session records when that endpoint began returning it; a registry advisory query with a timestamp either side of 22:01:48Z would settle it. Either way the single bump to 15.5.24 closes both, since both are patched at `>=15.5.24`.
- `6f29aac` changed five files (`git show --stat`): the ledger writer, the 019 script, the spec, the compose file and one test. No manifest and no lockfile, so the commit did not introduce the advisory; it reached the audit between the two runs. The More info page named above was fetched in this session and gives the dates: GHSA-p293-qw3h-jr36 was published upstream in `vercel/next.js` on 2026-08-25 and published to the GitHub Advisory Database on 2026-09-08, reviewed and last updated the same day, CVE-2026-75604, critical, CVSS 9.0; GHSA-2xp9-vwfh-vxw4 carries the same two dates, critical, CVSS 9.5, no known CVE. Upstream publication is fourteen days before both runs, so first publication is not what separates the 21:27Z pass from the 22:01Z failure. The page shows dates without a time of day, so it cannot place the Advisory Database entry inside or outside the gap between the two runs, and the mechanism stays as observed above rather than explained. Two other sources refuse from this session and were tried first: `https://api.github.com/advisories/GHSA-p293-qw3h-jr36` answers HTTP 403 and `api.osv.dev` is refused by the proxy.
- `732493c` at 22:05:29Z moves `apps/web/package.json` from `"next": "^15.1.0"` to `"^15.5.24"` and regenerates `pnpm-lock.yaml` (47 insertions, 42 deletions in the lockfile; 48 and 43 for the commit as a whole with the package.json line, `git show --numstat 732493c`); the lockfile now resolves `next@15.5.24`. Run 616 on `732493c` and Web CI run 48 on it both concluded success.
- Re-measured in this session on `732493c`: `pnpm audit --audit-level=moderate` exits 0, "No known vulnerabilities found".

`main` at `e466347` carries `"next": "^15.1.0"` (`git show e466347:apps/web/package.json`,
line 19) and a lockfile resolving `next@15.5.22` (`git show e466347:pnpm-lock.yaml`,
lines 541 and 1121), inside the vulnerable range; `git show origin/main:` no
longer returns those values, because `origin/main` is now the merge commit.
Its last `ci.yml` run before the merge, 610 on `e466347`, started 18:58:47Z
and was green, before the advisory reached the audit. "main is red" was never
observed: the first run on `main` after the merge, `ci.yml` run 617 (id
34285203474) on `2b09dbd`, started 22:18:14Z and concluded success with all
five jobs green, its `pnpm audit the locked workspace` step passing at
22:18:56Z (Actions record, job and step level). `main` met the advisory only
through this merge, which carries the fix.

## What was verified, and how

`6f29aac` is the last tree the spec was written on (`git log --format=%h
e466347..732493c -- <spec>` lists `6f29aac`, `0b7c36b`, `0041cb9`, `a875659`
and `9838313`; `732493c` does not touch it). Its commit body attributes these
Result (spec) rows to that tree and no others: the full suite (1544), the
ledger suites (74), standalone (137), presence (57), engine (25), the Alembic
round trip, the two builds identical at 687 shape lines, `compose config`
resolving the new healthcheck (not the service counts that row carries), and
ruff clean. The browser row was measured on the `a875659` tree, not on
`6f29aac`, as the section below states. The rest of the column, the pure
suites (232), soul host vendoring (112), the web build figures and
`check:presence`, is carried from the spec's receipts table with no per tree
attribution in any commit body, except that the `732493c` commit body names
what was measured on `732493c`: frozen install, `pnpm audit`, pip-audit, web
typecheck and build with `/presence` unchanged at 1.44 kB, and
`check:presence` (12 checks). The spec records each of its receipts with the
exit code captured directly rather than through a pipe (the sentence above its
receipts table); ci.yml run 616 is the CI evidence for the rest. The last
column is what this session re-ran on `732493c`.

| Check | Command | Result (spec) | Re-run here |
|---|---|---|---|
| Full API suite, presence included | `python3 -m pytest -q --tb=short` | 1544 passed, 170 s | not re-run; ci.yml run 616 green |
| Ledger against PostgreSQL 16, negative controls included | the three ledger files | 74 passed | 74 passed, exit 0 |
| Pure provenance, integrity, ecosystem | the three pure files | 232 passed | 232 passed, exit 0 |
| Standalone job, no PYTHONPATH, no database | the ten offline files | 137 passed | not re-run; run 616 green |
| Presence service, offline, same conditions | the four presence files | 57 passed | 57 passed, exit 0 |
| Engine job, two deselects | three files | 25 passed | not re-run; run 616 green |
| Soul host vendoring | the three deploy_soul files | 112 passed, `provenance.py` byte identical | not re-run |
| Two schema builds agree | `scripts/schema_shape.py`, diffed | identical at 687 shape lines | not re-run; the same database step passed in run 615 |
| Alembic round trip | up, down to 018, up | three exit 0, head `019_event_hash_chain` | `alembic heads` reads `019_event_hash_chain (head)` |
| Web typecheck and build | `tsc --noEmit`, `next build` | exit 0, `/presence` 1.44 kB, first load 107 kB | not re-run; Web CI run 48 green |
| Pure presence modules | `node --experimental-strip-types scripts/presence-check.ts` from `apps/web`, the `check:presence` script (`apps/web/package.json` line 11; the file is `apps/web/scripts/presence-check.ts`) | 12 checks passed (spec receipts table, line 399; the `732493c` commit message) | not re-run |
| Production compose | `docker compose config -q` | seven services with the profile, six without | `config -q` exit 0 here, the eight required secrets passed as environment variables; six services without the profile, seven with `--profile executor` (`config --services`); the postgres healthcheck resolves to `pg_isready -h 127.0.0.1 -U postgres -d meta_supreme` with `start_period: 30s` (Docker Compose v5.1.1; `config` needs no daemon, and none is reachable for `up`) |
| Headless browser through the live presence service | Playwright against `next start` and the mock service | `speaking` after 262 ms, interrupt acked in 0.7 ms with 823 frames flushed | not repeated, see below |
| Workspace audit | `pnpm audit --audit-level=moderate` | clean | exit 0 |
| Lint | `python3 -m ruff check .` | clean | not re-run; the lint step in run 615 passed |

## What is not live, or not verified, stated plainly

- No LiveKit server was reachable. The audio hook is typed against `livekit-client` 2.22.3, the browser SDK; the token route holds no SDK at all and mints a plain HS256 JWT with PyJWT (`apps/presence/livekit_token.py`: `import jwt` at line 30, `LIVEKIT_ALGORITHM = "HS256"` at line 32, and `jwt.encode(claims, api_secret, algorithm=LIVEKIT_ALGORITHM)` at line 74) against the claim layout LiveKit documents. Both are tested against mocks and the join path has never been exercised (spec, Tier 2). That module records its own limit: docs.livekit.io is blocked by this build's egress proxy, so the claim layout was read through a documentation index of the site rather than fetched, and whether a live LiveKit server accepts a token minted here is untested.
- No Cartesia key. `speech.py` carries the adapter seam and a mock that makes ARKit frames from text; the vendor response shape was not verified.
- No live Cerebras. The breaker is proved with an injected clock; the provider base class has no streaming API, so the streamer completes and then yields word tokens. Streaming against the vendor is a later gate.
- The 50 ms barge in figure is a target. The HUD measures the local reaction; the headless fake microphone delivered silence (rms 0.000), so only the manual interrupt path is proved.
- The compose stack has only been resolved with `docker compose config`. No daemon was available, so no image was built here and the first boot race the fourth critic named is plausible and unrun.
- The browser run was made on the `a875659` tree: the receipts row says "on the post gauntlet code", and `a875659` is the only commit `git log -S` returns for that wording on the spec. The three later fix commits and the `next` bump changed wire number validation and the framework patch level, and the browser run was not repeated on them; offline tests cover the validation change.
- The pass 4 closure in `6f29aac` is author verified and was not re-critiqued.
- The time of day of either advisory's publication, and when the npm registry began serving the second one. The dates themselves are read above.
- The avatar is a procedural placeholder head. Redis is provisioned and nothing opens it. Speech to text is not on the wire. The readiness matrix, knowledge graph, execution hub, cost widget, cockpit ledger card and secret vault are not built. The spec names where four of them go (readiness `apps/web/components/readiness/`, spec line 132; knowledge graph `apps/web/components/mind/`, line 134; execution hub `apps/web/components/execution/`, line 143; the ledger card under the command center, line 119); the cost widget rows (spec lines 144 and 162) and the vault row (line 153) name no location, the vault by design. The spec's own line 425 says each row names where it goes, and it overstates in the same way.

## The rulings the spec puts to Tee

None is recorded as ruled. Each is cited to the spec line that names it. The
PR #176 body records the first two as rulings for Tee and names anchoring,
listed under the next gate below, as a later gate.

1. One HS256 `SECRET_KEY` verifies DEVON sessions in both the API and the presence service, and with HS256 a verifier can also sign. Receipts no longer use it. Closing the rest means asymmetric tokens or the presence service asking the API to verify; the spec recommends asymmetric tokens (spec line 152, "open ruling for Tee"; line 318, "the shared session key is an open ruling").
2. A second receipt law for lawful late events: today `ACTION_FAILED` after a receipted `ACTION_COMPLETED` is accepted by the writer and reported by the verifier the same way as tampering (spec lines 341 to 344, "a ruling for Tee").
3. Whether the pass 4 closure, author verified after the three revise cycles were spent, needs a fifth critic before it is trusted (spec lines 368 to 371, "Tee rules whether that is enough").
4. The owned likeness: the avatar is a procedural placeholder until Tee supplies a rigged head with ARKit blendshapes; "the face is a ruling" (spec line 419).
5. The secret vault: nothing in the repository generates or stores secrets, on purpose; "a vault is a design decision for Tee, not a file to add quietly" (spec line 153).

## What the merge changes for main

- The audit lane: `main` inherits the `next` 15.5.24 floor and the regenerated lockfile. Observed, not inferred: run 617 on the merge commit audited clean (above), where `e466347` would have met the advisory on its next run.
- The migration head moves from `018_schema_convergence` to `019_event_hash_chain`. 019 adds columns, six triggers and three functions and creates no table (`grep -c "CREATE TABLE"` on the script returns 0), so `conftest.py` gains one entry, `019_event_hash_chain.sql` in `_INCREMENTAL_SCHEMAS` (line 79), and `_DATA_TABLES` is untouched. Per the `6f29aac` commit message, no database outside this branch is at 019 yet.
- `ci.yml` pins the head in four places: lines 164, 167, 227 and 253 (`grep -n 019_event_hash_chain`). `CLAUDE.md` and the steward skill (the paragraph at lines 193 to 205, whose fourth place is named at line 201) say four, corrected in `6b5c613`.
- The production stack runs the API as `devon_api`. The role is created on the first initialisation of the postgres volume by `infrastructure/docker/initdb/020-api-role.sh` from `infrastructure/docker/initdb/sql/api-role.sql`; the n8n role and database by `infrastructure/docker/initdb/010-n8n-database.sh` when `N8N_DB_PASSWORD` is set; the grants in `database/grants/devon_api.sql` are applied after every migration by the `migrate` service (`alembic upgrade head && python database/grants/apply_devon_api.py`, compose line 129). A volume that predates this revision does not rerun init: create the role by hand from `infrastructure/docker/initdb/sql/api-role.sql`, after which `migrate` grants on every run. `API_DB_PASSWORD` is required beside `POSTGRES_PASSWORD`.
- The spec's line 9 reads verbatim `canonical_ref: claude/dreamy-wright-pv1f3l until merged, then main`; after the merge that resolves to `main`, and the branch restarts from `origin/main` under the same name (CLAUDE.md, ship discipline).

## The next gate

- Tee stands up and reviews three surfaces. None of them is verified live here: the `/presence` page on the placeholder rig, whose evidence is Playwright against a local `next start` and a mock presence service (spec line 404); `GET /api/v1/ledger/intents/{id}/provenance`; and the production compose, which has only been resolved with `config` and never run under a daemon (above). The only deployment artifact on PR #176 is a Vercel preview, and CLAUDE.md's ship discipline says a green Vercel preview is not production, so whether either route is serving anywhere is unverified; the `deploy-readback` skill is what checks it. The merge is done; standing the surfaces up and reviewing them is what remains.
- The owned likeness: a rigged head with ARKit blendshapes supplied by Tee, loaded through `NEXT_PUBLIC_DEVON_AVATAR_URL`. No stock humanoid ships.
- A LiveKit and Cartesia lane proved end to end by a human listening, with the barge in figure read off the HUD by a human with a microphone.
- Anchoring chain heads outside the database, for a reader who does not trust the database at all: the spec records it as a later gate, not a ruling (spec lines 235 to 237). What the database cannot own is stated there as well: a role that can disable or drop the triggers, TRUNCATE the tables, or delete users can rewrite or erase history (spec lines 221 to 223), and the fourth critic found no path from the shipped `devon_api` role to either (spec).

## DEVON RECEIPT

The block below follows the shape the sibling status docs use, the same one
`SYS_SPEC_devon-control-plane-workspace_v1_2026-09-08` carries. It is not the
shape `services/devon/receipts.py` parses: that module reads a
`=== DEVON RECEIPT v1 ===` block with `DATE`, `PLATFORM`, `AREA`, `TITLE`,
`SUMMARY`, `DECIDED`, `BUILT`, `OPEN`, `NEXT`, `CANON` and `VERIFY` under a 250
word limit, and `detect_format` returns None for this file, so
`parse_receipt` raises on it (run here). `test_devon_integrity.py` passes with
this file in place, 150 tests, because it checks the banned dashes in
`docs/devon/*.md` and does not read receipts at all. So three shapes are in
use across the estate and nothing enforces any of them. Which one the status
docs should carry is a ruling for Tee, recorded here rather than settled by
converting this document alone.

```
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_control-plane-foundations_v1_2026-09-08
DATE: 2026-09-08
BUILT: migration 019 hash chain and signed receipt with the provenance route and append only triggers; the devon_api runtime role, its grants and the one shot migrate service; the presence streaming service with buffer, breaker, LiveKit token and wire protocol v1; the /presence surface with react-three-fiber canvas, frame buffer and VAD barge in; the production compose with loopback binds and eight required secrets; four gauntlet passes closed in a875659, 0041cb9, 0b7c36b and 6f29aac; the next floor moved to 15.5.24 in 732493c; PR #176 merged as 2b09dbd, its first run on main (617) green
PRESERVED: one ledger schema, 012 plus increments and no second schema file; approvals never granted by the ledger; services/devon effect free; no secret in the repository; no stock likeness; the human owns SHIP
UNVERIFIED: LiveKit join, Cartesia, live Cerebras streaming, the 50 ms barge in figure, the compose stack under a real daemon, the browser run on any tree after a875659, the pass 4 closure before a fifth critic, the time of day of either advisory's publication and when the npm registry began serving GHSA-2xp9-vwfh-vxw4 (the advisory page carries dates only), whether /presence or the provenance route is serving on any production surface, whether the merge was Tee's explicit SHIP authorization
NEXT GATE: Tee confirms whether the 2026-09-08T22:18:11Z merge by tdveal74-cell was his explicit SHIP authorization; Tee stands up and reviews the three surfaces, none of them verified live here; the rigged owned likeness; a LiveKit and Cartesia lane proved end to end by a human listening; chain heads anchored outside the database as a later gate
```
