# Company layer: six function queues, built and read back

Date: 2026-10-12. The pull requests of this arc ended with #334 (slice 3 was #330, slices 5 to 7
were #332 to #334), all merged on Tee's standing merge approval (2026-10-11).
Main at the end of the arc: d9766be.

## What this is

Tee shared a document he says is Anthropic Engineering Note #04, an architecture
of six business agents under one coordinator, and ruled "Build the company",
then "Build it all". This arc made that architecture real in the repository as
a separate layer, `services/company`, beside the Council of Reason and not
inside it. The Council keeps its nine seats. A test pins that no company slug
overlaps the registry, because the spend cap arithmetic and `full_council`
assume nine.

The rule the whole layer obeys is the repository's own: agents recommend, humans
decide. Every queue stores a draft, records one human decision, and does nothing
else. No route in the layer sends, posts, publishes, fetches, builds or runs.

## The six functions, measured

Status below is read from `services/company/functions.py` and the migrations,
not from memory.

| Function | State | Migration | What exists | What does not |
|---|---|---|---|---|
| Ops and Finance | built | none | scoreboard: spend, cap, calls, tokens, gap to the 10,000 USD target | revenue reads "not measured" until a source is connected |
| Marketing | partial | 022 | draft and approve queue for posts | reading Blotato; scheduling and publishing, by ruling |
| Sales | partial | 023 | qualify and draft queue for leads | reading the inbox or form; sending |
| Support | partial | 024 | draft queue for replies to YouTube comments | reading comments; the episode knowledge base; posting |
| Research | partial | 025 | findings log, each declaring source, measured or unverified | the search itself |
| Product | partial | 026 | change proposal log with acceptance check and reference artifact | anything that writes code or opens a pull request |

Every queue shares one shape: a pure rules module with no network import (an AST
test enforces it), a migration with CHECK constraints, a storage service that
applies the rules before any write and scopes every query to the owning account,
a SQL update guarded by `status = 'drafted'` with a rowcount check, and routes
that record the signed-in account as the decider. A second decision on the same
row is a 409.

## Rules Tee ruled, as built

Marketing is draft and queue only. Dash look-alikes are refused in anything we
deliver, with the minus sign U+2212 allowed. An AI disclosure needs at least 10
visible characters. The approver rule is unchanged: any signed-in account may
decide a draft it owns, and Tee is the only account.

Beyond those rulings the build added guards of its own, each tied to the house
standard of "unverified beats a plausible invention": a Support reply must name
its basis; a Research finding must say how it is known and an unverified one
cannot be adopted without a note saying so; a Product proposal must carry a
measurable acceptance check and a named reference artifact, and a large one
cannot be approved without a note. A comment, claim or title is recorded once
per owner.

## Verification

Each slice ran the full api suite alone, ruff, a real `alembic upgrade head` on
a scratch database, and a mutation pass that removes one guard at a time and
requires the tests to fail. The final suite on main's last slice: 3881 passed.
Mutation passes on the last two slices: 23 and 9 guards, every one failing the
tests, files restored byte for byte.

An independent worktree critic reviewed slices 3, 5, 6 and 7. It found and the
build fixed: a Marketing note that could be NUL and return a 500; a lax email
shape on Sales; and, on Support, a `$` anchor that matches before a trailing
newline, which stored an id the platform never issued and let one comment past
the once-only key. Slice 7's critic found no blocker; its cheap findings (the
once-only keys did not fold Unicode, a claim could hold control characters, a
NUL in a decision note reached the database) were reproduced first and fixed.

Slices 1, 2 and 4 had no independent critic. The scoreboard and the Marketing
queue have only the author's own checks and the mutation passes.

## Deploy read-back for d9766be, 2026-10-12 about 22:25Z

Surfaces were counted from `list-services` and `list_projects`, not from the
skill's table. Railway project devon-api has four services: api, presence,
scheduler-cron, Postgres. The Vercel team has nine projects, two of them
deployed from this repository.

- Railway api: deployment 6a4991c9 SUCCESS on d9766be. The deploy log carries
  `Running upgrade 024_company_comment_drafts -> 025_company_findings` and
  `Running upgrade 025_company_findings -> 026_company_proposals`, which is the
  proof the schema moved. `GET /api/v1/health` answered 200, healthy.
- Railway presence: deployment 9f393594 SUCCESS on d9766be. `GET /health`
  answered 200 with speech cartesia, livekit_configured true,
  audio_over_websocket false and the breaker closed with zero breaches. That
  pair is the working state on a build carrying the LiveKit publisher.
- Railway scheduler-cron: deployment a6db8bb1 SUCCESS on d9766be.
- Vercel meta-supreme-apex-genesis-web and devon-soul: production records for
  d9766be are CANCELED, which is the ignore rule skipping. Checked by hand
  rather than trusted: the last READY production builds are ac9bb36 for web and
  e8a72b7 for soul, and `git diff` from each to main over that project's own
  watched paths is empty. Nothing is owed to either surface.

What this proves: the code and schema are live on the three Railway services.
What it does not prove: that any company route has been exercised in production,
because none has been called there. The queues have never held a real row.

## Open

- Revenue source: Stripe needs Tee's authorization in claude.ai connector
  settings. Until then the scoreboard says "not measured", not zero.
- Blotato: the subscription is expired. The Marketing read-in is blocked until
  Tee reactivates it, and should read first and show Tee before wiring.
- vidIQ comment reads cost 5 credits each and the account showed 0 on
  2026-10-12, refilling to 150 on 2026-10-17. Support has nothing to draft from
  until then.
- Sales: whether a one to one email needs the AI disclosure is Tee's call. The
  queue requires it, which is the safe direction.
- The shared visible length counter treats blank-looking characters such as
  U+2800 as visible, so the 10 character floors can be dodged by a signed-in
  human. It lives in the Marketing module and touches every queue.
- Decision notes, acceptance checks, reference artifacts and measured references
  are not dash checked.
- A lone surrogate in raw JSON likely returns a 500, app wide.
- The 10 character floors are enforced in code only. The databases check
  non-blank.
- Research and Product source and artifact fields are shape checks. The URL rule
  is not a fetch-safety filter; whatever fetches a source later must resolve the
  host and refuse private ranges at connect time.
- The source of Engineering Note #04 is stated by Tee as Anthropic and was not
  opened by this session; the artifact banner says "per Tee".

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_company-layer-six-function-queues_v1_2026-10-12-2225.md
DATE: 2026-10-12
DECISIONS: Tee ruled on 2026-10-12: build the company as a layer beside the Council, then build all functions; Marketing is draft and queue only; revenue source is Stripe; Sales leads arrive as email or form replies; Support questions arrive as YouTube comments; the approver rule is unchanged; dash look-alikes are refused; an AI disclosure needs 10 visible characters; build Sales while Blotato is sorted. Standing merge approval from 2026-10-11 covered every merge in the arc.
FINDINGS: Six function queues built and merged, migrations 022 to 026, main at d9766be, last suite 3881 passed. Critic found and fixes landed for a NUL note 500, a lax email shape, and a trailing newline hole in the Support ids and once-only key. Deploy read back: api migrations 025 and 026 logged, api and presence health 200, scheduler-cron SUCCESS, both Vercel skips verified empty by git diff.
OPEN: Stripe authorization; Blotato subscription; vidIQ credits (0 on 2026-10-12, 150 on 2026-10-17); Sales disclosure on one to one email; blank-looking characters pass the visible length floor; dash check on notes and checks; lone surrogate 500; no company route has been exercised in production; no critic ran on slices 1, 2 and 4.
STATUS: All six functions have an approval queue and none of them acts. Intake for Marketing, Sales and Support is blocked on Tee's accounts. Revenue reads not measured.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
