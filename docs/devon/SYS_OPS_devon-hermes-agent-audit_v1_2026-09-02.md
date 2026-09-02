---
title: DEVON and Hermes Agent Audit
type: SYS_OPS
version: 1
date: 2026-09-02
area: Systems
status: audited-not-fixed
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
head: cf0d7ef
branch: claude/devon-hermes-agent-audit-0pob3j
supersedes: none
---

# DEVON and Hermes Agent Audit v1

## Verdict in one paragraph

The build is real and most of what it claims about itself holds under attack. All four CI jobs pass locally at head, 1196 tests, ruff clean, Alembic round trip clean. The core runtime gate (approval bound to exact arguments, consumed once, races resolved to one winner, tokens hashed) held every attack thrown at it. All three production surfaces serve main head as of 2026-09-01 18:51Z. Against that, this audit confirmed three critical defects and a cluster of high ones that sit exactly where the docs say the product is strongest. The in-estate knowledge loop that PR #108 called closed can be driven end to end by the proposing JWT with no human ruling, its approval is not bound to the candidate that commits, and the columns it writes have no Alembic migration, so the production database very likely cannot commit a capture at all. The shared approval queue is readable and rulable with no login. The EditForge execute route never spends its approval. None of this is hidden by dishonest docs, but the docs are stale in a way that hides it: three status documents (FLAGSHIP.md, COMPLETION.md, docs/GAUNTLET.md), seven lines between them, still say production is at d2aff6d, and the Hermes status doc still says the deployed database is at Alembic head 010. Recommendation: do not call the knowledge loop live, do not call Hermes operator-live, and work section 9 in the order given, items 1 to 5 first, before the next honesty recut.

Gauntlet verdict on the DEVON and Hermes stack as a deliverable: not shippable as a second brain yet, cycle 1 of 3, route the findings and re-audit. Security scores 2 of 5 on confirmed, reproduced governance bypasses. Verification is 5 of 5 for sections 1 to 3, where every finding was run by a second agent, not read. Section 2b carries the completeness critic's two high findings, one run once and one read, and they are scored as finder-only. The full score block is in section 11.

## Method

Scope: DEVON (services/devon, the doctrine compiled into code) and the Hermes-style agent runtime around it (services/agent_runtime, the capability adapters, the app layer under app/, the Alembic and SQL schemas, CI, the operator surfaces, and every status document that makes a claim about them). Repo head at audit time: `cf0d7ef` on main, checked out on `claude/devon-hermes-agent-audit-0pob3j`.

Three layers of evidence, in this order:

1. Measured: every CI job reproduced locally against a fresh Postgres 16 + pgvector cluster, exit codes captured to files, never through a pipe.
2. Read back: the three production surfaces read through the Railway and Vercel connectors, deployment id, state, target and commit recorded. No production credential was handled.
3. Attacked: eleven independent finders, one per dimension, each given only its surface and the product's claims, told to break them and to reproduce before reporting. Every finding then went to adversarial verifiers told to refute it by running the reproduction. High and critical findings got two lenses (reproduce, consequence) and a tie-break lens (tests and docs) on a split. A finding appears below only with its verifier status. Refuted findings are listed separately so the reader can see what was tried and did not hold.

Rules held throughout: read-only on the repository. Scratch tests ran against their own database names, never the shared test database. Nothing was marked live without a deployment id. Nothing was scored that was not measured.

## Measured receipts (this session, HEAD cf0d7ef, 2026-09-01)

Environment: Python 3.11.15, fastapi 0.141.1, pydantic 2.13.5, SQLAlchemy 2.0.52, asyncpg 0.31.0, alembic 1.19.1, pytest 9.1.1, pytest-asyncio 1.4.0, PostgreSQL 16.13 + pgvector 0.6.0, ruff 0.16.5. Postgres cluster initialised fresh at /var/lib/pgtest, and both databases created empty with the vector extension.

| CI job (as .github/workflows/ci.yml runs it) | Command shape | Result | Exit |
|---|---|---|---|
| 1 standalone (no PYTHONPATH, no DATABASE_URL) | `import standalone_api` then pytest over the 10 listed files | 133 passed in 2.30s | 0 |
| 2 container contract (import check, image not built here) | `from app.main import app; passkey_login_options; CerebrasProvider` | Meta Supreme Apex Genesis passkey_login_options cerebras | 0 |
| 3 engine | test_council, test_phase4_council, test_security with the two stream deselects | 21 passed, 2 deselected in 1.24s | 0 |
| 4 api (PostgreSQL 16 + pgvector) | `python -m pytest -q --tb=short` (77 test files collected from repo root) | 1196 passed, 5 warnings in 119.56s | 0 |
| 4 lint | `ruff check .` | All checks passed | 0 |
| 4 Alembic | `upgrade head; downgrade 004_federated_knowledge_waist; upgrade head` | head = 013_approval_consumption, matches the ci.yml pin at line 177 | 0 |

Docker image build (job 2's first step) was not run here. The import contract it checks was run directly against the same interpreter. With this document in the tree the api job collects 1197 tests, the extra case being test_devon_integrity's dash check on this file, which passes.

## Production readback (read-only, 2026-09-01, via Railway and Vercel connectors)

| Surface | Readback | Verdict |
|---|---|---|
| Railway `devon-api` / `api` (env production) | deployment `9e6c363e-059c-4aa2-96a8-232c790fd89d` SUCCESS, created 18:45:51Z, on commit `cf0d7ef` (main HEAD), trigger deploy. Deploy log at 18:51:06Z shows Alembic `Context impl PostgresqlImpl` / `Will assume transactional DDL` and no `Running upgrade` line, then `Application startup complete`, CORS allows 8 origins. HTTP log for this deployment: empty (no requests since deploy). | LIVE on main HEAD. Migration reported nothing pending at head 013. |
| Vercel `devon-soul` (prj_RTiwmhndbWFWf1KH7go43rs2Acxn) | `dpl_Ux9eEZAFxHLfo99U96SZiHLfz17C` READY, target `production`, on `cf0d7ef`, created 2026-09-01T18:45:54Z. | LIVE on main HEAD. Every repo doc saying production is still `d2aff6d` is now stale. |
| Vercel `meta-supreme-apex-genesis-web` (prj_tlXnTP7pZ2qzdDBdU0hNID7ystaw) | latest production `dpl_FvY3mCa7oi8U6k48qtWuvFbMq4NM` on `cf0d7ef` is CANCELED (ignoreCommand skip). Last READY production build: `dpl_B1JzaNq2UisgHHLTbyKyAunjaVQ8` on `797c15f` (#101), 2026-08-30. `git diff --stat 797c15f..cf0d7ef -- apps/web packages/ui package.json pnpm-lock.yaml pnpm-workspace.yaml` is empty. | LIVE at 797c15f, which equals main HEAD for every web-affecting path. Correct skip, not drift. |
| Vercel project `meta-supreme-web` | Not present in `list_projects` (10 projects listed, none by that name). | Surface named in deploy-readback SKILL.md, DEPLOY.md and the ecosystem spec table no longer exists. |

Not read from here, by design: the production `DATABASE_URL` and the production `artifacts` table. The deploy-readback rule forbids handling the production DSN. The migration question below is settled by one query the operator runs on the Railway Postgres shell.

Web CI parity (job 5, path filtered): the frontend finder ran `pnpm install --frozen-lockfile`, `pnpm --filter @meta-supreme/web typecheck` and `pnpm --filter @meta-supreme/web build` at this head and all three exited 0.

Verification coverage. Eleven finders returned 121 findings. By the strict rule (a finding's severity is the lowest any verifier gave it) the verified set is 2 critical, 16 high, 12 medium and 4 low, with 1 refuted and 86 finder-only. KLM-02 is counted high there and reported as critical in section 1, with the reason stated. First-round adversarial verification ran 31 verdicts before a usage limit cut the remaining verifiers off. A second round re-verified the twelve critical and high findings that were left without a vote. Every finding below carries one of three labels: verified (at least one independent refuter ran the reproduction and could not refute it), refuted (a refuter showed it does not hold as stated), or finder-only (the finder reproduced it and reported the command, but no second agent re-ran it). Finder-only items carry the finder's own command and output. For code findings that is a run. For the docs-drift class it is a read of the cited line, which is the only check a doc claim admits. None of them got the second pair of hands, so each is held at one severity notch of doubt.

## 1. Critical findings (verified)

Each item names the file and line, what was run, what was seen, the consequence, and the owner of the fix. "Verified" means an independent refuter re-ran the reproduction on a fresh database and could not refute it.

### C1. The proposing JWT can approve and commit its own capture, with or without DEVON_RULING_KEY (KLM-01)

Location: `app/api/v1/devon.py:324` (decide route), `app/api/v1/ledger.py:98` (generic event append), `app/services/knowledge_loop.py:468` (commit check).

What PR #108 says: approve demands a second credential out of band from the JWT, DEVON_RULING_KEY, so one credential can never run propose, approve and commit alone.

What the code does: `POST /api/v1/devon/approvals/decide` takes no CurrentUser and no ruling key. The knowledge loop's approval lives on the same shared queue that route rules. Commit checks only that the queue record is APPROVED and that an APPROVAL_GRANTED event exists on the intent. The owner-scoped `POST /api/v1/ledger/intents/{id}/events` accepts APPROVAL_GRANTED from the owner.

Run (two independent verifiers, fresh databases, DEVON_RULING_KEY both unset and set): propose with the JWT. `/soul/approve` without the key returns 403, as designed. `POST /devon/approvals/decide` with no Authorization header and the token the propose response returned: 200, state approved. Owner appends APPROVAL_GRANTED: 201. `POST /soul/commit`: 200, executed true, consumed true, artifact and receipt rows written, find returns the body. A garbage bearer token on decide also returns 200. `app.openapi()` shows security None for the decide path.

Consequence: a script holding one platform JWT runs the whole loop with no human. The ledger records the capture as ruled by "Tee" because decided_by is caller text (see H1). A stranger holding only the token can rule the queue entry but cannot forge the ledger event or commit, so the bypass needs the proposer's JWT.

Owner to fix: `app/api/v1/devon.py` (authenticate the decide route and bind it to the request's owner or to the ruling key), `app/services/knowledge_loop.py` (commit must verify the approvals row written by knowledge_loop.approve, never the event name), `app/api/v1/ledger.py` (refuse APPROVAL_GRANTED from the generic route). Status 2026-09-02: the decide route was authenticated and owner-scoped in PR #111 (57fdddb). Fix PR 2 closes the rest: propose binds the request to its intent on the ledger approvals row, approve rules that row after the ruling key, commit verifies the row and refuses when only the queue says approved, the generic event route refuses APPROVAL_GRANTED, and the shared decide route refuses knowledge-loop cards. Verified by test_devon_knowledge_loop_binding.py: on the code before the fix (e50fc1c) the builder's run failed three of its four tests and the critic's run failed all four, because the old unordered limit(1) resolver decides the forged-intent case by row order.

### C2. The approval is not bound to the candidate that commits (KLM-02)

Location: `app/services/live_state_ledger.py:641` (`intent_id_for_approval_request`), `app/services/knowledge_loop.py:496`.

What the code does: the intent for an approval is resolved by `events.payload->>'approval_request_id'` with `.limit(1)` and no ORDER BY, and nothing makes that payload key unique. The owner can create a second intent through the generic ledger routes whose PLAN_CREATED names the victim's approval_request_id with a different candidate.

Run (finder plus two verifiers): proposer creates a forged intent with candidate `FORGED, Tee ruled the opposite`, kind ruling, and appends PLAN_CREATED, APPROVAL_REQUESTED, APPROVAL_GRANTED. Approver approves the legitimate request with the real token and the ruling key. Commit returns 200 and the ledger body is the forged text with kind ruling, eight iterations of eight. The approver's stored what_happens still reads the legitimate text.

Consequence: the human ruling is decoupled from what executes. A Tee ruling, which outranks every note on find, can be minted by the proposer. One verifier rated this high rather than critical because it needs the owner's own JWT. It is listed as critical here because it defeats the one property the loop exists to provide.

Owner to fix: bind request_id to intent_id and to a hash of the candidate at propose time in the approvals table, resolve from there at approve and commit, and refuse PLAN_CREATED payloads that name an approval_request_id on the generic route. Status 2026-09-02: fix PR 2 binds request_id to intent_id on the ledger approvals row at propose (UNIQUE on approval_request_id, so the binding cannot be redirected), resolves approve and commit from that row, takes the candidate from the one PLAN_CREATED that names the request (single-occurrence by ledger law), and refuses a PLAN_CREATED naming an approval_request_id on the generic route. No candidate hash column was added: against the HTTP threat model the binding row, the single-occurrence law and the route refusal already make the plan the proposer's own, and a hash would guard only against direct database tamper, which no column survives either. The generic /approvals route also refuses a row for any knowledge-loop request id, so a request with no row (proposed before this fix, or whose propose transaction rolled back) cannot be bound by hand. Note on the negative control: the forged-intent test is order-dependent on the old code, passing in the builder's run and failing in the critic's; the route-refusal, decide-route and queue-only tests fail on the old code every time.

### C3. artifacts.body and artifacts.kind have no Alembic migration, so a database already at head 013 never gets them (SCD-01, duplicated by KLM-03 and DVC-01)

Location: `database/schemas/014_artifact_body.sql` (conftest only), `database/schemas/012_live_state_ledger.sql:116` (amended in place by cf0d7ef), no `database/migrations/versions/014_*.py`.

What happened: commit cf0d7ef added the two columns to the 012 SQL file and shipped a 014 SQL file for the test fixture. The 012 Alembic revision executes its SQL file only when a database steps from 011 to 012. A database already stamped 013 gets a zero-step no-op from `alembic upgrade head`.

Run (three finders and two verifiers agree): build a database at the pre-#108 shape (or drop the two columns from a fresh build), run `alembic upgrade head`, observe no upgrade steps and `artifacts` without body or kind. Exercise the loop: `record_artifact FAILED: UndefinedColumnError: column "body" of relation "artifacts" does not exist`, and find fails the same way. CI cannot see it because the suite runs against the SQL-file-built test database and the Alembic step asserts only 24 table names and the revision string.

Production: the Railway `devon-api` project was created 2026-08-26T03:11Z (list-projects readback) and its Postgres reached 013 before #108. The cf0d7ef deployment log shows Alembic connect lines and no `Running upgrade` line. This audit did not read the production table, by rule. One query on the Railway Postgres shell settles it:

```
select column_name from information_schema.columns where table_name = 'artifacts' order by ordinal_position;
```

If body and kind are absent, every remember, file, thread, plate and brief commit on production is a 500 today.

Outcome, 2026-09-02 08:35 UTC: the query was never run on the right host (section 10 has the detail). PR #111 merged as 57fdddb and Railway deployment 782b095d executed the 014 and 015 revisions: deploy log lines `Running upgrade 013_approval_consumption -> 014_artifact_body` and `Running upgrade 014_artifact_body -> 015_devon_approval_owner`, status SUCCESS, application started afterwards. Production now has both columns. The before-state was not captured and cannot be recovered from the log.

Owner to fix: add `014_artifact_body.py` executing the existing SQL (it is already `ADD COLUMN IF NOT EXISTS`), update the ci.yml presence loops and the head assertion, and add a CI step that runs the ledger and knowledge suites against an Alembic-built database. Status 2026-09-02: the revision, the ci.yml pins and the head assertion shipped in PR #111 (57fdddb). The CI step against an Alembic-built database is still open.

## 2. High findings (verified)

### H1. The shared approval queue's HTTP surface has no authentication

Location: `app/api/v1/devon.py:286` (`POST /devon/command`), `:299` (`GET /devon/approvals`), `:324` (`POST /devon/approvals/decide`). Reported independently by four finders (GG-3, GG-4, GG-5, AAT-02, DCD-01, FOS-1) and verified three times.

Run: anonymous `GET /api/v1/devon/approvals` returns every pending card with title, what_happens, blast radius and the tool arguments the runtime embeds. Anonymous `POST /devon/command` with an effect utterance inserts a durable pending card with a caller-chosen, unbounded, newline-injectable title. Anonymous `POST /devon/approvals/decide` with request_id and token rules the card, and `decided_by` (default "Tee", no length bound) is stored verbatim as the audit trail. `devon_approvals` has no owner column, so there is nothing to scope by even after auth is added.

Consequence: the Command Center's MissionAdvisor ranks these cards first. Anyone on the internet can fill Tee's approval rail, read what DEVON is about to do, and, holding a token, sign a ruling as Tee.

Owner to fix: CurrentUser on all three routes, an owner column on `devon_approvals` (schema 006 plus a migration), decided_by taken from the authenticated principal.

### H2. EditForge execute never spends its approval, and retry and cancel have no gate

Location: `app/api/v1/devon_editforge.py:185` (execute), `:237` (control). Reported as GG-2, CAP-01, AAT-05, CAP-02. Verified.

Run: approve one render. `POST /devon/editforge/execute` with the byte-identical draft three times: three accepted executes, three commands sent to EditForge, approval row still `approved`. A second registered user presenting the same draft is also accepted, because requested_by is never compared to the caller. `POST /executions/{id}/retry` and `/cancel` proxy straight to EditForge behind any valid JWT, while the runtime tool `editforge.control` for the same actions is HIGH_IMPACT and binding-checked.

Consequence: one human approval renders N times and spends provider credit N times. The runtime lane consumes correctly (verified), the HTTP lane does not.

Owner to fix: `_queue.consume` before the client call, compare requested_by to the caller, gate retry and cancel on the same approval record. Status 2026-09-02: fix PR 4 spends the approval before the command leaves EditForge's door, returns the unknown-id 404 to any account that did not raise the approval, and gates retry and cancel on the caller's spent approval for that command id (a body field approval_id, so the bare control call is 422). The fresh critic showed the first cut's gate could be satisfied by a second account authorizing a draft with the victim's caller-chosen command id; the command id is now minted by authorize and returned, a caller-chosen one is refused, and execute requires the minted id in the draft, where the intent hash already binds it. Residuals, named: a command the studio refuses leaves the approval spent with no record of the refusal, so retry on it reaches the studio for a command that never ran; and GET /executions/{id} stays readable by any signed-in account. Verified by test_devon_editforge_http_lane.py against a fake studio that counts commands, including the critic's attack.

### H3. SECRET_KEY defaults to a public string and nothing refuses to boot with it (AAT-03)

Location: `app/core/config.py:30`, `app/security/jwt.py:30`. Verified end to end.

Run: with SECRET_KEY unset, forge an HS256 token for an existing user id with the literal default. `GET /api/v1/auth/me` returns 200 as that user. No aud, no iss, no production guard anywhere in the repo. `infrastructure/docker/docker-compose.yml` ships the same literal inline.

Owner to fix: refuse to start when ENVIRONMENT is production and SECRET_KEY equals the default, and drop the literal from compose. Status 2026-09-02: fix PR 4 adds a settings validator that refuses to construct on a deployed process with the default or an empty SECRET_KEY. Deployed means ENVIRONMENT outside the local set (development, dev, test, local, empty), so staging counts, or a hosting platform's own marker present (RAILWAY_ENVIRONMENT_NAME, RAILWAY_PROJECT_ID, VERCEL_ENV), so a Railway service whose ENVIRONMENT was never set is still refused; the live value of ENVIRONMENT on Railway was not read and does not need to be. The compose file requires SECRET_KEY from the environment, both .env.example files carry an empty SECRET_KEY with the openssl hint, and the secondary apps/api tree carries the same guard on its own default. On Railway a refused boot fails the service's health check (healthcheckPath /api/v1/health, read from the service config on 2026-09-02) and the previous deployment keeps serving. Verified by test_secret_key_boot_guard.py. Deployed 2026-09-02: Railway deployment e911eedb of merge eba7320 reached SUCCESS at 19:46:10 UTC with "Application startup complete" in the deploy log, so the guard ran under the Railway markers and production's SECRET_KEY is not the public default; the value itself was not read.

### H4. The operator "read" lane reads any file the process can read, including the process environment, with no JWT and no approval

Location: `services/operator/bridge.py:48` and `:152`. Reported as AAT-01 and CAP-04. Verified.

Run: `OperatorBridge.plan('cat /proc/self/environ')` classifies as READ. `execute_read` returns the environment, which on the API host carries DATABASE_URL, DEVON_OPERATOR_KEY and DEVON_RULING_KEY when set. `printenv` is classified WRITE and gated, `cat /proc/self/environ` is not. Classification is by binary name only and validates only the cwd. A git-based write outside DEVON_OPERATOR_ROOT was also reproduced. tool_catalog already admits `cwd_confinement_is_os_sandbox: False`.

Owner to fix: classify by resolved path against the root for every argument, deny `/proc`, `/sys`, dotfiles and anything outside the root on the READ lane. Status 2026-09-02: fix PR 5 judges every path-like argument on the read lane, option values such as --git-dir= and rev:path forms included, after symlink resolution: outside the operator root, under /proc, /sys or /dev, or naming a dotfile in any component fails closed to human approval with the path in the reason. Verified by test_operator_bridge.py, including the audit's own `cat /proc/self/environ`.

### H5. Browser live fetch follows redirects off the allowlist (CAP-03, with CAP-05)

Location: `services/browser/http_fetcher.py:16` (`follow_redirects=True`), `services/browser/agent_adapter.py` (validates the initial URL only). Verified. Only reachable when DEVON_BROWSER_LIVE_FETCH is on, default off.

Run: an allowlisted host answering 302 to `http://169.254.169.254/` or `http://localhost:5432` is followed, the body returned to the model as a READ result, and metadata records the original URL. Userinfo in the URL is forwarded as an Authorization Basic header (CAP-05, finder-only).

Owner to fix: `follow_redirects=False`, or re-validate every hop against the allowlist and record the final URL. Status 2026-09-02: fix PR 5 sets follow_redirects=False and refuses any 3xx with the location named, so the model can ask for that URL explicitly where the allowlist judges it; a URL carrying credentials is refused before any request (CAP-05); fetch metadata records final_url, which equals the URL asked for. Verified by test_devon_browser_fetch_boundary.py against an httpx mock transport.

### H6. The runtime expansion tools write to process-local stores, so an approved effect with a succeeded receipt does not exist anywhere

Location: `app/services/agent_tasks.py:64`, `services/agent_runtime/expansion_tools.py:88`. Reported as HX-01, GG-1, SPI-1, HX-11. Verified with two lenses.

Run: a plan step `runtime.schedule_goal` stops at the card, a human approves, the effect ledger records a succeeded receipt with a provider_receipt_id, and `GET /agent-expansion/schedules/due` and `/materialize` return nothing, because the tool wrote to `InMemoryScheduleStore`, not `HermesExpansionRepository`. Same for `runtime.propose_skill` (the human decide route 404s on the id) and `runtime.spawn_subagent` (a private list). The three handlers also discard the approval metadata without calling `require_approved_runtime_binding`, so the approval row stays `approved` forever and a stale snapshot replays the tool (verified, rated medium because the stores are inert).

Consequence: the tool descriptions, blast_radius strings and tool_catalog flags (`scheduler: True`, `skill_proposals: True`, `durable_subagent_links: True`) promise a ledger the tools do not reach. The v1 handover stated this limit. The v2 status doc dropped it.

Owner to fix: route the three handlers to the durable repositories through an injected session factory (the pattern LeasedEffectRecorder already uses), call the binding helper, or unregister the runtime tools until they are durable and say so in the catalog. Status 2026-09-02: fix PR 3 routes the three handlers through injected writers that use HermesExpansionRepository, SubagentLinkRepository and the durable task service in their own committed sessions, and every handler calls require_approved_runtime_binding first, so the approval is spent (closes GG-1). The owner of each row comes from the approval card, never from the arguments. The catalog flag runtime_tools_durable is read from the adapter, true only when every tool has a durable writer, and a tool with no writer refuses outside tests instead of succeeding into a process-local store. Arguments are bounded to the HTTP routes' limits before the approval is spent, the schedule row carries the task, step and approval that raised it, and parent_task_id and the proposal's task_id are pinned to the running task. FLAGSHIP.md, GAUNTLET.md, the status v2 doc and the expansion handover v1 doc carry dated lines (HX-11, DVC-12). Verified by test_devon_expansion_tools_durable.py (the audit's run, per tool, through the HTTP surface) and the offline binding tests in test_devon_hermes_expansion.py.

### H7. The orphan check runs before the lease is taken, so a healthy in-flight effect is reported as ambiguous and the task row is clobbered (ELC-01)

Location: `app/services/agent_tasks.py:384`. Verified under six-worker concurrency.

Run: worker A holds a live lease and is inside an approved async WRITE whose intent is committed and whose receipt is not yet written. Worker B calls run. B sees an orphan, writes state failed with an unfenced upsert, commits, and raises 409 ambiguous_external_effect instead of the intended TaskExecutionBusy. A then completes and overwrites the row. Effect ran once, one intent, one receipt, so the crash invariant held, but the refusal fired on a task that was not orphaned and the row briefly lied.

Owner to fix: acquire the lease first, then check orphans filtered by execution generation.

### H8. The knowledge loop spends the approval on a separate autocommit connection before any ledger row is durable (KLM-04)

Location: `app/services/knowledge_loop.py:513`, `app/services/devon_approval_store.py:132`. Verified.

Run: consume runs inside `psycopg.connect(...)`, which commits on block exit. ACTION_STARTED, the artifact, ACTION_COMPLETED and the receipt are only flushed on the request session and commit at get_db teardown. The Pinecone and n8n effects run in between. A failure after consume leaves a spent approval, an n8n webhook already fired, and no ledger row. A retry is refused as already spent.

Owner to fix: write the ledger rows first inside the request transaction and spend the approval last, or make the spend part of the same transaction.

### H9. The FKR query route fails on every request (KLM-05)

Location: `services/knowledge/retrieval.py:44`. Verified.

Run: `POST /api/v1/knowledge/query` with or without project_id returns 500. asyncpg raises AmbiguousParameterError on the untyped `:project_id` bound three times. No test exercises the route or the SQL. `CAST(:project_id AS uuid)` fixes it.

### H10. knowledge_items.content exists only in the SQL twin, so knowledge ingest fails on every Alembic-built database (SCD-02)

Location: `database/migrations/versions/004_federated_knowledge_waist.py:40` versus `database/schemas/004_federated_knowledge_waist.sql:34`. Verified with two lenses.

Run: a fresh `alembic upgrade head` has no `content` column on knowledge_items. `app/models/knowledge.py:39` maps it and `app/services/knowledge.py:179` writes it. `POST /api/v1/knowledge` on that database is a masked 500. Production boots through `alembic upgrade head` (Dockerfile.api CMD), so this is the production shape unless someone applied the SQL twin by hand.

### H11. CI never runs a test against an Alembic-built schema (SCD-03)

Location: `.github/workflows/ci.yml:122` and `:126`. Verified.

The suite runs against conftest's SQL-file-built database. The later Alembic step asserts 24 table names and the head string. C3 and H10 are the two drifts that this shape cannot see. A single information_schema diff between the two builds, or running the ledger and knowledge suites against the migrated database, closes the gap.

### H12. `make up` cannot start the API container (SCD-04, and the completeness critic for start-devon.sh)

Location: `infrastructure/docker/docker-compose.yml:16` and `:59`. Verified.

compose seeds 001 through initdb, then the api command runs `alembic upgrade head`, whose 001_baseline re-executes the same non-idempotent DDL and fails with DuplicateTableError on `users`. The same class hits `start-devon.sh` step 5, which applies all fourteen SQL files raw and never stamps alembic_version, so the next documented step fails the same way (completeness critic, reproduced on a scratch database).

### H13. The documented dispatcher command does not exist (DVC-02)

Location: `OPERATING.md:167`, `RUNBOOK.md:270`, `HANDOVER_FOR_CLAUDE.md:297`. Verified.

`python -m app.cli.dispatch` has no `app/cli` in the root package, fails from the apps/api mirror too, and the shipped image contains neither it nor the working root `dispatch.py`. A scheduled-workflow deployment that follows the docs never dispatches.

## 2b. High findings from the completeness critic (finder-only, not verified by a second agent)

These two sit outside the verified count. H14 was run once, by the critic that found it. H15 is a read.

### H14. The workflow lane's approval binds to a step id, not to the previewed payload, and the definition can be edited while a run waits at the gate

Location: `app/api/v1/workflows.py` (update_workflow has no awaiting-run guard, delete does), `app/services/workflows.py` (_pending_view re-renders from the live definition). Found by the completeness critic with a scratch test, exit 0, two cases. Finder-only: no second verifier ran it.

Run: pause a run at a memory_write step with preview `Noted: EU pricing exposure`. `PATCH /workflows/{id}` with a swapped definition while the run is awaiting_approval returns 200. The pending view now shows the swapped text. Approve the step id: 200, completed, memory written with the swapped text. Second case retypes the same step id from memory_write to decision_draft and the approval executes the new type.

Why it matters: AUDIT.md section 3 item 2 asks reviewers to attempt exactly this attack and says the preview and the write cannot diverge because they are the same object. They diverge the moment the definition changes.

### H15. Registration is open and nothing caps provider spend per tenant

Location: `app/api/v1/auth.py:175`. Completeness critic, read and grepped, not run and not exercised against production.

No invite, flag or policy. `billing.py` limits are imported only by `standalone_api.py`. On the deployed API any internet user can mint a tenant, run councils against Tee's provider keys, and raise cards into the queue H1 already shows is shared. This is a policy gap, not a code defect, and needs Tee's ruling.

## 3. Medium and low findings (verified)

| Id | Severity | Where | What was run and seen |
|---|---|---|---|
| HX-02 | medium | `app/services/hermes_expansion_persistence.py:75` | Two concurrent materialize calls for one due schedule create two tasks. The schedule links only to the last commit. The orphan task's outcome never reaches the schedule. Owner-scoped, human-run, no automated caller today. |
| HX-04 | medium | `app/api/v1/agent_expansion.py:194` | Approving a proposal upserts by goal slug and silently replaces an operator-authored skill with the same name, bumping its version, with no conflict signal in the response. |
| HX-05 | medium | `services/agent_runtime/learning_loop.py:19` | Auto skill proposals copy up to 12 tool outputs verbatim at 500 chars each. One decide call promotes them. Every future plan for that owner loads all skills with no relevance filter. A prompt-injection path gated by a single click. |
| HX-06 | medium | `app/services/agent_tasks.py:258` | Subagent max_steps is stored in child context and read by nothing. A child spawned with max_steps 1 accepts a run with max_steps 100. |
| HX-07 | medium | `app/services/agent_tasks.py:260` | inherit_context_keys copies any parent key after the child identity keys are set, so a grandchild can carry its grandparent's parent_task_id while the link table records the truth. |
| HX-11 | medium | `docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md:35` | Status rows are true for the HTTP routes only. The runtime tool path is still process-local and the v1 limit was never closed. |
| GG-1 | medium | `services/agent_runtime/expansion_tools.py:88` | The three expansion handlers never verify the binding or consume the approval. Replay with the same or forged metadata runs them again. Approval row stays approved. |
| GG-4 | medium | `app/api/v1/devon.py:325` | decided_by is caller-supplied, unbounded text stored as the audit trail. Part of H1. |
| ELC-03 | medium | `services/operator/bridge.py:280` | The operator adapter runs subprocess.run synchronously on the event loop, so the lease heartbeat cannot renew during an approved command. Reachable only when the step passes a timeout above lease_seconds, up to the 300 second clamp. |
| SCD-05 | medium | `Makefile:37` | `make test` collects zero tests, `make api` serves the stale apps/api mirror, `make install` omits 12 packages the root app imports. |
| SCD-06 | medium | `VERIFY.md:24` | VERIFY.md and docker-compose.verify.yml call `scripts/verify.sh` and `scripts/verify-offline.sh`, which have never existed in the repository's history (checked through the GitHub commits API). |
| SCD-07 | medium | `HOW_TO_TEST.md:6` | The four-package offline recipe cannot start `uvicorn standalone_api:app` because the module chain imports psycopg. CI cannot notice because its standalone job installs the full requirements. |
| HX-03 | low | `app/api/v1/agent_expansion.py:193` | Approve with promote false is a dead end. No promote route exists and re-decide is 409. |
| HX-08 | low | `services/agent_runtime/expansion.py:293` | The goal slug keeps the first six purely alphanumeric words, so distinct goals collide, and one rejected proposal silences every future draft for that slug. |
| HX-09 | low | `app/api/v1/agent_expansion.py:142` | The HTTP propose route does not dedupe and accepts any task_id string, including another owner's. |
| HX-10 | low | `app/api/v1/agent_expansion.py:76` | `GET /schedules/due` flips pending rows to due and commits. A GET racing a materialize can overwrite running back to due (lost update, reproduced). |

Refuted: SCD-08 claimed `deploy/soul/app.py` is never imported by any test. A verifier showed `test_deploy_soul_operator.py` executes it in a subprocess against a fake vercel SDK with twelve probe tests, so import errors do fail CI. What CI never exercises is the real pinned vercel SDK. Dropped to low and recorded here so the attempt is visible.

## 4. What held

The finders were told to report the attacks that failed, with the command, so that the audit credits what the code actually does. Condensed here. The full list of 156 held claims with commands is in the audit's scratch record (`claims_held.md`), not committed.

Governance gate, agent runtime lane:
- Approve-what-you-see holds for the nine consuming adapters (operator.command, four GitHub writes, browser.navigate, editforge.render, editforge.control): the binding is recomputed at the boundary from task, step, tool and the arguments about to execute, and a tampered argument or an unknown key is refused without spending the approval (`test_devon_tool_arguments.py`, `test_devon_approval_consumption.py`, scratch replays).
- Consume-once holds on both stores: a second identical call is refused, two workers racing to consume on Postgres yield exactly one winner, two workers racing to decide yield one ruling.
- Tokens are never persisted in plaintext, comparison is constant time on the hash, and a wrong token is refused before the state check.
- The production default store when DEVON_APPROVAL_STORE is unset and DATABASE_URL is set is Postgres, and the in-memory store fails closed across two processes.
- BLOCKED tools are refused by the planner before a plan exists. A model-supplied `_devon_runtime_approval` block is stripped before decision, binding and handler under presence.
- rollback_agent_state refuses to rewind past a completed effectful step.

Effects, leases, crash safety:
- The intent is committed durably before the adapter runs on the production WRITE path. A seeded orphan refuses the run with 409 and the refusal survives an agent-state rollback.
- Only the live lease owner can commit results or receipts. Stale tokens are dead keys. Six staggered workers on one approved async WRITE produced one effect, one intent, one receipt.
- Replay of an idempotency key never re-executes. Cancel, rollback and delete are refused with 409 while a lease is held.
- `crash_atomic_external_effects: False` in tool_catalog is honest and no doc claims atomicity.

Tenancy and auth:
- Cross-tenant agent task, memory, schedule, skill proposal and subagent reads and mutations return 404 for the other user, on a live ASGI run with two registered users.
- Password recovery checks DEVON_RECOVERY_KEY with a constant-time compare before any account lookup and fails closed. Passkey login options issue only a challenge. Challenges cannot be reused.
- CORS default is loopback only and the soul host is deliberately absent. `GET /console` embeds no secret.
- The real shell websocket requires both a valid JWT and the distinct DEVON_SHELL_KEY, fails closed when the key is unset, opens a PTY only with both, and kills the bash process group when the socket closes (exercised under a live PTY).

Adapters:
- The browser allowlist rejects userinfo confusion, subdomain suffixes, trailing dots, uppercase, IP literals, IPv6, non-http schemes and undeclared keys. GitHub sends `follow_redirects=False`, enforces the repository allowlist on every method, and never places the token in a result. The EditForge runtime tools consume once and bind to the exact intent hash.
- The operator bridge blocks symlink escapes from the cwd, refuses WRITE-classified commands on the read lane, and never interprets shell metacharacters (shlex plus shell=False).

Knowledge loop, ledger, memory:
- Concurrent commits of one approved request: exactly one executes. Commit replay after success is refused. ILIKE metacharacters in a find query are escaped. Find is owner-isolated. Layer 1 Tee Soul returns 403 at propose and nothing writes it. Tee rulings outrank later notes. Emergency stop blocks commit after approval. Pending confirmation handles are random, single use, owner bound and expire.
- Connector honesty holds: notion.written false, drive.written false, n8n.routed false when unset, postgres.live only when proven by the request.

DEVON core:
- Every intent phrase, receipt path and prompt path was exercised and no module in `services/devon` imports a network or subprocess capability. The vendored `deploy/soul/services/devon` is byte-identical.
- Nine Areas including ACX, both vocabularies, a supplied Area never trusted, naming refusals (v0, decimals, unknown codes, non-ISO dates), precedence refusal when nothing wins, the 72 hour single-use token, the wake word stripped once and leading only, the ten hard rules and eight filing laws: all pinned by tests that pass.

Schema and CI:
- Alembic head is 013 and matches the ci.yml pin. Fresh upgrade, downgrade to 004 and upgrade succeed. conftest's schema list and truncate list cover every table. No test file escapes CI. No skip, xfail or deselect hides anywhere except the two stream tests the api job runs anyway.
- The frontend typechecks and builds at head. No `dangerouslySetInnerHTML`, `innerHTML` or `eval` in the React app. No credential is placed in a URL, query string or websocket subprotocol. The nine-Area map shows nine on every surface. No faceless framing in user-visible copy.

## 5. Finder-only findings

These carry the finder's command and output, but the second agent that would have re-run them was cut off by the usage limit. They are listed with the finder's severity and a one-line claim. Treat each as one notch less certain than the sections above until someone re-runs it.

Governance and API (GG, AAT, ELC, CAP):
- GG-6 low `services/devon/approval.py:444`: an APPROVED but unexecuted approval never expires.
- GG-7 low `services/editforge/agent_adapter.py:231`: editforge.control normalises arguments before recomputing the binding, so an approved non-canonical plan fails after approval.
- GG-8 low `services/agent_runtime/runtime.py:241`: a snapshot holding a CONSUMED request id is stuck behind the message "approval request is unavailable".
- GG-9 info `services/agent_runtime/governance.py:30`: binding canonicalisation is Python-only and the card marker does not strip goal or argument text.
- AAT-04 low `app/api/v1/auth.py:201`: no rate limit on login or any auth route.
- ELC-02 medium `app/services/agent_effect_receipts.py:124`: receipt and intent fence refusals are bare RuntimeError and surface as 500, not the typed 409 the crash-matrix method requires.
- ELC-04 medium `app/services/agent_tasks.py:458`: one transient heartbeat exception discards a receipt the process already holds and parks a completed effect as ambiguous.
- ELC-05 medium `.claude/skills/steward/SKILL.md:119`: "replay is byte-identical" is false for an approval-phase run, which replays with approval_token None.
- ELC-06 low `services/agent_runtime/effects.py:71`: the receipt sanitizer blocklist is dead code, receipts persist api_key and authorization values.
- ELC-07 low `app/services/agent_effect_receipts.py:128`: record_receipt accepts a receipt for an intent from a dead execution generation.
- ELC-08 low `app/services/agent_tasks.py:384`: the orphan check precedes the idempotency lookup, so a legitimate replay of a completed key is refused.
- ELC-09 low `test_devon_effect_receipts_orphan_crash.py:85`: the existing orphan regression accepts a 500 as success.
- CAP-05 low `services/browser/http_fetcher.py:16`: URL userinfo is forwarded as an Authorization Basic header.

Knowledge, ledger, memory (KLM):
- KLM-06 medium `app/services/memory.py:95`: recall considers only the 200 newest rows, so older important memories are silently buried.
- KLM-07 medium `app/services/knowledge.py:201`: ingest swallows ProviderConfigError and returns 201 with status failed, the route's 503 branch is dead.
- KLM-08 medium `app/services/knowledge.py:250`: a flush-time embedding dimension error is neither marked failed nor persisted.
- KLM-09 low `app/api/v1/soul.py:196`: concurrent approves of one request surface an unhandled LedgerConflict.
- KLM-10 low `app/services/knowledge_loop.py:468`: commit leaks another owner's approval state through distinct error messages.
- KLM-11 low `app/services/live_state_ledger.py:664`: find truncates at 20 with no truncation or total indicator.
- KLM-12 low `app/services/live_state_ledger.py:729`: any receipted intent surfaces on find as a devon-note memory with a defaulted kind.
- KLM-13 low `docs/GAUNTLET.md:43`: status docs claim services/memory performs ledger reads, and DEVON.md still says the approval queue is process-local.
- KLM-14 info `services/devon/ecosystem.py:635`: may_delete_index has no caller.

Schema, CI, docs (SCD, DVC):
- SCD-09 low `requirements.txt:30`: unpinned floors, and the pytest-asyncio floor predates the loop-scope options pytest.ini uses.
- SCD-10 low `.github/workflows/ci.yml:115`: presence loops stop at 013, the steward skill and Makefile offline lists disagree with CI's.
- SCD-11 low `app/models/__init__.py:22`: Alembic autogenerate reports 133 diffs, env.py's target_metadata omits the ledger and passkey models.
- SCD-12 low `.github/workflows/web-ci.yml:3`: web CI runs only on pull_request, never on push to main, and website/ has no CI.
- SCD-13 info `infrastructure/docker/Dockerfile.api:1`: the image runs Python 3.12 while CI tests on 3.11 and carries the dev toolchain.
- DVC-03 medium `VERIFY.md:8`: VERIFY.md and AUDIT.md cite five paths that do not exist.
- DVC-04 medium `VERIFY.md:35`: claims ci.yml runs the frontend typecheck and build on every push. It does not.
- DVC-05 medium `HOW_TO_TEST.md:28`: `make test` collects zero tests.
- DVC-06 medium `HANDOVER_FOR_CLAUDE.md:5`: the 2026-08-04 handover has no supersession and is still the README's critical reading.
- DVC-07 medium `REPOSITORY_STATUS.md:15`: says no production URL is required while the ecosystem spec of the same day records three production surfaces.
- DVC-08 medium `CHANGELOG.md:8`: stops at 0.5.1 on 2026-08-09 with an empty Unreleased section, sixty merges later.
- DVC-09 medium `SYNC_STATUS.md:21`: SYNC, BATCH_PROGRESS and IMPLEMENTATION_STATUS describe an August 10 partial sync as current.
- DVC-10 medium `docs/devon/DEVON.md:211`: carries a 2026-08-22 view of the package, console path and approval store.
- DVC-11 medium `docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md:56`: re-edited on 2026-09-01 and still says the deployed database is at Alembic head 010. It is 013.
- DVC-12 medium `docs/GAUNTLET.md:39`: FLAGSHIP, COMPLETION and GAUNTLET say Hermes expansion is in-memory and not durable. The HTTP routes persist schedules, proposals and links. Only the runtime tool path is in-memory (H6).
- DVC-13 medium `docs/GAUNTLET.md:44`: calls FKR schema only while a hybrid query route is mounted. Given H9 the route fails on every request, so the doc is closer to the truth than the code.
- DVC-14 medium `OPERATING.md:234`: sections 9 and 10 describe a system with no outbound calls and 49 tests.
- DVC-15 low `docs/devon/SYS_OPS_devon-unified-command-center-handover_v2_2026-08-26.md:7`: still reads final-head-pending-ci though PR #63 merged.
- DVC-16 low `docs/GAUNTLET.md:14`: law 6 bans em dashes in deliverables while 169 em and en dashes sit in the root status docs. The ban is enforced only for services/devon and docs/devon.
- DVC-17 low `OPERATOR.md:2`: stamped 2026-08-10 while citing a 2026-08-30 runbook.
- DVC-18 low `docs/devon/DEVON.md:154`: the zero-key path names test files that need Postgres.

DEVON core doctrine (DCD):
- DCD-02 medium `test_devon_integrity.py:128`: the effect-free tripwire is an import-root allowlist that `from os import system`, importlib, open(), shutil and ctypes would pass. The runtime check in the same file is what actually holds.
- DCD-03 medium `services/devon/commands.py:434`: capture verbs are hijacked by effect substrings, "remember to send a message to mom" raises a send_message approval instead of a capture.
- DCD-04 medium `services/devon/assistant.py:530`: DevonResponse.executed is True for empty-payload EFFECT and CAPTURE intents that did nothing.
- DCD-05 medium `services/devon/receipts.py:424`: render_standing turns an omitted files_opened into an explicit "none" that round-trips as a valid receipt.
- DCD-06 medium `docs/devon/DEVON.md:175`: claims a process-local approval queue and a Postgres-free zero-key runtime. The code defaults to the shared Postgres store.
- DCD-07 medium `docs/devon/DEVON.md:122`: documents ENRICHMENT_PROVIDER=cerebras as tagging captures. Nothing in the application calls enrich_capture.
- DCD-08 medium `services/devon/ecosystem.py:761`: emergency-stop release authority is caller-asserted. Any authenticated user names actor TEE.
- DCD-09 low `services/devon/persona.py:109`: the dash ban covers U+2014 and U+2013 only. Figure dash, horizontal bar, two-em dash and minus sign pass.
- DCD-10 low `services/devon/naming.py:375`: parse_filename accepts lowercase codes, v0, future dates and a missing version while build_filename refuses them.
- DCD-11 low `services/devon/filing.py:428`: law 6 leaves mixed-case Canonical in a withdrawn title, law 5 warnings never block a write.
- DCD-12 low `services/devon/precedence.py:219`: a lone canon or future-dated candidate is SUPERSEDE, and a future-dated candidate refuses the whole ruling.
- DCD-13 low `services/devon/ecosystem.py:477`: one APPROVAL_GRANTED admits unlimited ACTION_STARTED events.
- DCD-14 low `docs/devon/DEVON.md:211`: stale on the console path, command destinations and module layout.
- DCD-15 low `docs/devon/SYS_SPEC_presence-authority_v1_2026-08-26.md:196`: still records "no CONSUMED state" as open after CONSUMED shipped.
- DCD-16 info `services/devon/vault.py:31`: READ_ON says 2026-08-22 while entries were corrected on 2026-09-01.

Frontend and operator surface (FOS):
- FOS-2 medium `app/main.py:133`: `GET /console` serves the full estate-map console to anyone with no credential, no CSP and no Cache-Control.
- FOS-3 medium `app/api/v1/operator_shell.py:140`: the real shell's bash inherits the whole API process environment, so JWT plus shell key hands over every platform secret.
- FOS-4 low `apps/web/components/terminal/RealShell.tsx:39`: both shell factors and the operator key persist in the same origin's localStorage.
- FOS-5 medium `deploy/soul/console.html:1273`: the served console stamps its 2026-08-22 ID snapshot with the page-load time as "SNAPSHOT now UTC".
- FOS-6 medium `apps/web/components/command-center/UnifiedCommandCenter.tsx:79`: the Next.js command center is painted copper and teal, the palette the gauntlet scored 38 and repainted out of the console.
- FOS-7 medium `apps/web/components/devon/DevonChat.tsx:208`: em dashes in user-visible and spoken copy across the React app and the website demo.
- FOS-8 low `website/index.html:15`: the public site palette is a near miss of the house tokens.
- FOS-9 low `docs/devon/SYS_OPS_devon-unified-command-center-handover_v2_2026-08-26.md:198`: a string in the repo's own capture-token shape is committed verbatim in two handover docs. Rotate if it is live. Section 10 puts the same question to this report's own receipt line.
- FOS-10 low `apps/web/components/terminal/OperatorTerminal.tsx:99`: a comment claims /shell reads the same operator-key slot. It reads a different key.
- FOS-11 low `apps/web/components/command-center/UnifiedCommandCenter.tsx:104`: a localStorage read outside try/catch.

Soul, planner, intelligence (SPI):
- SPI-2 medium `deploy/soul/main.py:722`: the conflict-search receipt echoes caller-supplied sources that were never searched.
- SPI-3 low `services/intelligence/providers/cerebras_provider.py:116`: the local limiter refusal is retried with backoff, contradicting its stated purpose.
- SPI-4 low `app/api/v1/conversations.py:550`: the halt route is not bound to the conversation. Owning any conversation lets a user halt any turn id.
- SPI-5 low `services/agent_runtime/planner.py:308`: the planner path keeps a model-forged approval block, the human approves a card carrying it, and the effect then fails.
- SPI-6 low `services/intelligence/soul.py:146`: soul recall rendering does not neutralise newlines, so a devon-soul record can forge a TEE RULING line.
- SPI-7 low `services/agent_runtime/pending.py:203`: pending-confirmation eviction is global across users.
- SPI-8 low `services/agent_runtime/conversation.py:386`: model text carrying the approval-marker prefix lands verbatim in APPROVED rows and the task goal.
- SPI-9 info `services/intelligence/providers/mock_provider.py:196`: the mock planner selects a WRITE tool when the catalog has no read tool.
- SPI-10 info `services/intelligence/soul.py:298`: a comment overstates the trust-field filtering on recalled records.

## 6. What the finders did not check (completeness critic)

A final agent read the findings index and the held-claims list, walked the tree, and named surfaces nobody attacked. It spot-checked each by reading or running. Two of them became H14 and H15 above and one folded into H12. The rest:

- Dependency advisories. `pip-audit -r requirements.txt` reports ecdsa 0.19.2 PYSEC-2026-1325 via python-jose, the library that signs every JWT (HS256 in use, so the ECDSA path is not exercised, but it ships in every image). `pnpm audit` reports 4 high and 2 moderate advisories, all transitive through next 15.5.22 (sharp, postcss, nanoid). No CI job runs either audit.
- RUNBOOK.md and getting-started.md were outside the docs sweep. RUNBOOK.md:337 sends operators to `apps/api/app/services/workflows.py` and two siblings that do not exist. getting-started.md:36 copies an `apps/web/.env.example` that is not in git. CHANGELOG.md:26 claims `awaiting_dispatcher` was corrected so schedules dispatch, while `services/workflows/definition.py:93` returns True for every non-manual trigger and `test_workflows_api.py:158` pins the opposite of the changelog.
- `scripts/n8n_migrate.py` has zero tests, and its export writes the full workflow payload including pinData (captured execution payloads) to disk. It will run for the first time against the live estate of 33 active workflows.
- Agent tooling committed to the repo: `.claude/settings.json` enables three community plugins with no version pin, and `.agents/skills/unlazy` vendors 37 files including a Stop hook installer. `skills-lock.json` hashes SKILL.md only. The hook is not installed today. Nobody has said whether this is intended.
- Container hardening: Dockerfile.api has no USER instruction (root), compose hardcodes SECRET_KEY and POSTGRES_PASSWORD inline while `.env.example` asks the operator to set a password compose never reads, Dockerfile.web's CMD is `pnpm dev`, and `infrastructure/ci/github-actions.yml` is an inert placeholder outside `.github/workflows`.

## 7. Production readback versus the records

| Record | Says | Live read 2026-09-01 | Status |
|---|---|---|---|
| FLAGSHIP.md:47, COMPLETION.md:35, docs/GAUNTLET.md:23,34,35,48,58 | production devon-soul.vercel.app is still d2aff6d | `dpl_Ux9eEZAFxHLfo99U96SZiHLfz17C` READY production on cf0d7ef | stale since 18:45Z on 2026-09-01, amend |
| DEPLOY.md:132,162, `.claude/skills/deploy-readback/SKILL.md:25`, ecosystem spec table line 176 | a Vercel project `meta-supreme-web` serves apps/web | not in the project list. `meta-supreme-apex-genesis-web` serves apps/web. `docs/devon/SYS_OPS_presence-hardening-and-recovery_v1_2026-08-27.md:181` and `app/core/config.py:40` already record the retirement on 2026-08-27 | three records contradict two, amend the three |
| Railway production CORS (deploy log) | allows 8 origins including three `meta-supreme-web` hosts | project retired | environment hygiene, remove three origins |
| Hermes status v2 line 56 | deployed DB at Alembic head 010 | Alembic head 013 locally, Railway log shows nothing pending | stale, amend |
| Ecosystem spec "Deployment, read back" | Railway current at c0fa80c on 2026-08-26 | Railway `9e6c363e` SUCCESS on cf0d7ef, autodeploy working | superseded by its own later paragraph, fine |

## 8. Is DEVON a second brain today

The pass condition in docs/GAUNTLET.md is: would Tee run production decisions and knowledge answers through this stack without a second tool open. The honest answer at cf0d7ef is still no, and the reasons moved.

What the docs already admit: Notion, Drive and n8n are not written from this repo. Find is ILIKE, not recall at plan time. Layer 1 is never written. Soul recall is off by default. Hermes is CI-proven, not operator-live.

What this audit adds: the one loop the repo calls closed, remember to approve to commit to find, can be closed by the proposer alone (C1), can commit text the approver never saw (C2), and cannot write on a database migrated before 2026-09-01 (C3, pending one production query). The approval rail that the Command Center puts first is public (H1). The knowledge ingest route that feeds retrieval fails on every Alembic-built database (H10), and the FKR query route fails on every request (H9). On production, if C3 and H10 hold there, the second brain currently accepts nothing and answers from nothing except memories rows.

None of this is dishonesty in the code. It is a set of seams between lanes that were each built correctly and tested in isolation: the runtime approval lane consumes and binds, the HTTP lanes do not, the test database is built one way and production another, and the docs describe the lane that was tested.

## 9. Recommendations, in order

1. Authenticate and owner-scope the three `/devon` routes and give `devon_approvals` an owner column. Take decided_by from the principal. Closes H1 and half of C1. Small change, one migration, one day.
2. Make knowledge-loop commit verify the approvals row written by `knowledge_loop.approve`, not the event name. Refuse APPROVAL_GRANTED and PLAN_CREATED-with-approval_request_id on the generic ledger event route. Bind request_id to intent_id and a candidate hash at propose. Closes the rest of C1 and C2.
3. Ship `014_artifact_body.py` executing the existing idempotent SQL, add the 004 `content` column to a migration the same way, update the two ci.yml presence loops and the head assertion, and add one CI step that diffs information_schema between the Alembic build and the SQL build and runs the ledger and knowledge suites against the Alembic build. Closes C3, H10, H11. Then run the one production query in C3 and record the answer, dated.
4. EditForge HTTP lane: consume before send, compare requested_by to the caller, gate retry and cancel on the approval record. Closes H2.
5. Refuse to boot in production with the default SECRET_KEY. Remove the literal from compose. Closes H3.
6. Operator bridge: classify by resolved path for every argument, deny `/proc`, `/sys` and anything outside the root on the read lane. Closes H4.
7. Browser fetch: `follow_redirects=False` or re-validate each hop. Closes H5. Strip userinfo.
8. Expansion tools: call `require_approved_runtime_binding`, and either write through the durable repositories via an injected session factory or unregister the three runtime tools and remove the catalog flags until they are durable. Closes H6, GG-1, and the HX-11 doc drift.
9. Take the lease before the orphan check, filter orphans by execution generation. Closes H7. Map fence refusals to typed 409 (ELC-02).
10. Knowledge loop: write the ledger rows inside the request transaction first, spend the approval last. Closes H8.
11. Fix the untyped `:project_id` in retrieval.py with a CAST and add a test that calls the route. Closes H9.
12. Workflow lane: refuse PATCH while a run awaits approval and bind the approval to a hash of the rendered pending payload. Closes H14, which is the attack AUDIT.md invites.
13. Rule on registration policy (invite key or a closed-by-default flag) and on per-tenant provider spend. H15 is a decision, not a patch.
14. Write back the records: production SHA in FLAGSHIP, COMPLETION and GAUNTLET, retire `meta-supreme-web` from DEPLOY.md, the deploy-readback skill and the ecosystem spec table, Alembic head in Hermes v2, the dispatcher command, RUNBOOK paths, and the CHANGELOG dispatch claim. Run `scripts/estate_reconcile.py` afterwards and pin the corrected sentences.
15. Add `pip-audit` and `pnpm audit` to CI, and pin requirements.

Items 1 to 5 are the ones that change what a stranger on the internet can do. Items 6 to 11 change what an approved effect can do. Items 12 to 15 change what the records claim.

## 10. Rulings from Tee, 2026-09-02

Asked on an inline card and answered the same day.

| Question | Ruling | Consequence |
|---|---|---|
| Registration policy on the deployed API | Closed by default behind DEVON_REGISTRATION_KEY, checked with a constant-time compare, unset means refused | Lands in fix PR 1 with the approval route auth |
| The three runtime expansion tools | Make them durable now, through the same repositories the HTTP routes use | Section 9 item 8 becomes a real change, roughly a day |
| .agents/skills/unlazy and the unpinned community plugins | Remove unlazy, pin the three plugins by version | Small separate PR, no runtime effect |
| dcp_ receipt tokens | Identifiers, not credentials. The n8n capture webhook authenticates with x-devon-key | No rotation. One sentence added to the receipt convention |
| The C3 production query | Run it now, read-only, before the 014 migration ships | Not captured. On 2026-09-02 the query was run on the EditForge VPS srv1936199, which holds no DEVON database (the DEVON database is the Postgres service in the Railway devon-api project), and Tee then ruled "Merge" without the before-state. PR #111 merged as 57fdddb. Railway deployment 782b095d (SUCCESS, 08:35 UTC) logged `Running upgrade 013_approval_consumption -> 014_artifact_body` and `Running upgrade 014_artifact_body -> 015_devon_approval_owner`, so production now carries artifacts.body, artifacts.kind and devon_approvals.owner_id at head 015. Whether body and kind were missing before that deploy is unknown and stays unknown: Alembic surfaces no Postgres notices, so the log's silence proves nothing either way |

## 11. Gauntlet score block for the DEVON and Hermes stack

```
VERDICT: not yet a verdict (cycle 1 of 3): ROUTE the findings and re-audit
Deliverable: DEVON second brain and Hermes agent runtime at cf0d7ef | Type: code, config, data mutation, docs | Ask: audit DEVON, the second brain, and the Hermes-like agent
Critic mode: subagent (eleven independent finders, thirty-one first-round refuters, fourteen second-round refuters, one completeness critic)
Scores: scope fidelity 4 | correctness 3 | unverified claims 3 | security 2 | reversibility and blast radius 4 | silent failure resistance 3 | idempotency 3 | traceability 4 | observability 3 | completeness 3 | maintainability 3 | mean 3.2 | security 2 | verification 5 | flagship floor: MISSED
Findings: sections 1, 2, 3, 5 and 6 above, each with location, problem, consequence and owner
Receipts: four CI jobs reproduced locally with exit codes, 1196 tests passed, ruff clean, Alembic round trip clean, three production surfaces read back by deployment id, every listed finding carries the finder's command and output, H15 excepted, which is a read, every critical and high finding in sections 1 to 3 re-run by at least one independent refuter
Conditions: the C3 production query, the C1 and C2 fixes, and the H1 auth change must land before any doc calls the knowledge loop closed or Hermes operator-live
Recommendation: fix-then-ship, in the order of section 9. The human owns SHIP.
```

Scoring notes. Security is 2 because two governance bypasses on the loop the product calls its centre were reproduced by three agents each, and because the approval rail is public. Correctness is 3 because the runtime lane, the doctrine core and the tenancy model hold under attack while two deploy-path schema drifts break two routes. Verification is 5 because the score was set from sections 1 to 3 only, where every item was run at least twice. Flagship floor is missed on the "fixes the root" clause: the lanes were built and proven one at a time and the seams between them are where every critical sits.

## 12. Gauntlet of this report

A fresh critic was given this document, the ask, and the repository, and told to attack it. Its verdict and what changed are recorded here.

```
VERDICT: PASS-WITH-CONDITIONS
Deliverable: this document | Type: docs, plan that will be acted on | Ask: audit DEVON, the second brain, and the Hermes-like agent
Critic mode: subagent, fresh, given only the file, the ask and the repository
Scores: scope fidelity 4 | correctness 4 | unverified claims 3 | security 5 | reversibility 5 | silent failure 3 | idempotency 4 | traceability 3 | observability 4 | completeness 4 | maintainability 3 | mean 3.8 | verification 5 | flagship floor: MISSED narrowly, on handed off clean
Receipts: the critic reran CI jobs 1, 3 and 4 (133, 21 and 1197 passed), ruff, the Alembic round trip, the C3 simulation (zero upgrade steps, insert fails on body), and a scratch test reproducing H1, H3, H4 and H9, checked 45 file and line citations, reconciled the 34 verified, 1 refuted and 86 finder-only tally id by id against the workflow journals, confirmed no em or en dash and no non-ASCII byte in the file, confirmed the FOS-9 value is not reproduced here and no production credential appears
Recommendation: fix-then-ship. The conclusions stood. The fixes were to the report's own presentation.
```

What the critic found and what changed in this revision:

- The headline said seven files carry the stale production SHA. The evidence is three files and seven lines. Corrected in the verdict paragraph and in section 7, which now also lists docs/GAUNTLET.md line 34.
- The next step was stated three ways (eleven items, fifteen items, items 1 to 5). It is now one way: work section 9 in order, items 1 to 5 first.
- H14 and H15 sat under the verified header while their own text said finder-only and read. They now sit under section 2b with that label, and the verification claims in the verdict paragraph, the score notes and the receipt say which sections the 5 covers.
- Twelve headings in sections 1 and 2 did not name their finder ids, so a reader could not find the votes in the evidence files. Every heading now carries its ids.
- The FOS-9 ruling was under-scoped: the same dcp_ token shape sits in this report's own receipt by standing instruction. Section 10 now puts the question to the convention, not only to the two handovers.
- Six semicolons in prose were restructured. Five line citations drifted by one to five lines and were corrected. The claim that finder-only items are all runs was narrowed to what the docs class admits.
- The critic counted 1197 tests with this file in the tree against 1196 without it. The receipts table now says so.

Conditions the critic set, carried forward: treat H14 as finder-only and H15 as a read before acting on them, and read the section 10 ruling on dcp_ tokens together with the receipt convention.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: DEVON and Hermes Agent Audit v1, docs/devon/SYS_OPS_devon-hermes-agent-audit_v1_2026-09-02.md
HEAD: cf0d7ef, branch claude/devon-hermes-agent-audit-0pob3j
MEASURED: standalone 133 passed, engine 21 passed, api 1196 passed, ruff clean, alembic 013 round trip, web typecheck and build exit 0
READ BACK: Railway api 9e6c363e SUCCESS on cf0d7ef, Vercel devon-soul dpl_Ux9eEZAFxHLfo99U96SZiHLfz17C READY production on cf0d7ef, Vercel meta-supreme-apex-genesis-web READY production at 797c15f which equals head for every web path
FOUND: 34 verified (2 critical by the strict lowest-lens rule, KLM-01 and SCD-01, plus KLM-02 rated critical by one lens and high by the other and reported as critical in section 1, 16 high including KLM-02, 12 medium, 4 low), 1 refuted, 86 finder-only, 5 unchecked surfaces named
HELD: 156 attacks withstood, condensed in section 4
UNVERIFIED: the production artifacts table shape, production knowledge_items shape, whether dcp_ tokens (FOS-9 and this receipt's own TOKEN line) are live credentials
RULINGS NEEDED: section 10
NEXT GATE: items 1 to 5 of section 9, then re-audit the touched surfaces
