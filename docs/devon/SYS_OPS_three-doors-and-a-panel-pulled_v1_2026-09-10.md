# Three doors opened, one panel pulled, and seven adversaries

    status: skill proposal gate, learning store and knowledge graph API on main;
            graph panel pulled before shipping; two subsystems still stranded
    date: 2026-09-10
    supersedes: nothing. Extends
            SYS_OPS_devon-audible-and-reachable_v1_2026-09-09.md, which closed
            the voice and capture arc and recorded four stranded subsystems.

## What shipped

Two merges. `90c3e84` closed the fourth critic's five conditions on the voice
and capture guards. `1f2a607` opened three of the four doors Tee ruled.

**The skill proposal gate.** CLAUDE.md's invariant reads "Skill promotion is
human gated". It was gated with no door. Every agent task reaching COMPLETED
drafts a skill proposal and saves it, `DEVON_AUTO_SKILL_PROPOSE` defaults on,
and the two routes that would let a person rule on one had no caller anywhere
under `apps/web`. Proposals accumulated where nobody could read them and nothing
failed. Tier 1 now carries a panel where approve and promote stay two separate
rulings, because `SkillDecideBody` declares `promote: bool = True` and a body
that omits the key promotes.

**The learning store.** Every planning context carries `devon_learning`, and
before this nothing a person could open wrote to either table or read it back.
The payload now distinguishes stored, no_match, empty and unavailable, because
`memories: []` meant three things at once and the search is token overlap only.
A failed read draws as unreadable, never as empty. No seed data: a memory DEVON
was never told is a fabricated ruling in his planning context.

**The knowledge graph API.** `GET /knowledge/graph`, read only, every edge a
pgvector cosine distance taken as the minimum over chunk pairs. Registered
before `GET /knowledge/{item_id}`, which matches the literal segment "graph",
and that ordering is asserted by a test rather than described in a comment.

## The bug forty two green tests could not see

The graph API arrived with 42 passing tests, all offline, and its edge query
could not execute against a real database at all.

`_uuid_array_param` built a Postgres array literal, `"{uuid,uuid}"`, and asyncpg
binds array parameters natively rather than parsing a literal, so the driver
raised before Postgres saw the statement:

    asyncpg.exceptions.DataError: invalid input for query argument $1:
    '{5d5dee42-...}' (a sized iterable container expected (got type 'str'))

So the route raised for every owner with two or more items carrying vectors,
which is the only case it exists to serve. One of the 42 tests asserted the
literal's exact shape and another proved it refuses an injection attempt, so the
suite confirmed the helper did what it said while nothing checked whether that
was what the driver accepts. Green is not correct, with a receipt.

`test_knowledge_graph_pgvector.py` exists because of it: six tests against real
pgvector, and reverting the fix reds all of them plus two offline ones.

## Why the graph panel is not on main

Its adversary returned DO-NOT-SHIP on a finding that needed no mutation. The
panel and the route were built to two different contracts: the route returns one
flat object, and `parseGraphPayload` read `raw.counts` as a nested member, so the
counts were null on every real payload and every node reported as having no
degree because the route sends `embedded_chunk_count` and never `degree`.

Measured with a payload built by the route's own `assemble_graph`, carrying
`items_embedded: 0` and an edge query the route skips below two vector bearing
nodes, the panel rendered:

    Embedded nodes, no pair close enough to connect.
    10 embedded nodes came back and zero edges. Every pair sits further apart
    than the threshold of 0.65, so this picture is genuinely edgeless rather
    than truncated or broken.

Nothing was embedded. No pair was ever compared. That is a fabricated
measurement asserted as fact, on the one surface in this estate whose entire
justification is refusing to make them.

Neither suite caught it because each was green about a different payload.
`test_knowledge_graph.py` pins the flat shape and carries a comment saying it
exists "so a field that is quietly renamed or dropped fails here instead of in a
panel that then has no way to tell an empty graph from a broken one". The
control plane guard's graph fixtures were hand written nested. The panel had
exactly the blindness that comment was written to prevent, which is why the
follow up must generate its fixture from `assemble_graph` rather than by hand.

The contract, the degree derivation and three wrong verdict clauses are fixed in
the staged work, and the verdict on that same payload is now "Items exist, none
of them are embedded", which is true of it. It stopped there because the rest
needs a browser and its own critic. Five items remain, the largest being that
`classifyProvider` reads the provider NAME rather than the route's own
`embedding_provider_simulated` flag, so `unavailable`, the value the route emits
when it cannot build a provider, reads as real with no notice. That is the state
a default `start-devon.sh` launch produces.

## Five claims of mine that were false

Recorded because the first law is about the claiming, not the coding, and
because two of them were in shipped files rather than only in a commit message.

**The pgvector test's central assertion never executed.**
`DEFAULT_MAX_DISTANCE` is 0.65 and the edge query ends
`HAVING MIN(...) <= :max_distance`, so the distance 1.0 orthogonal pair was
filtered out before the test saw it. `orthogonal` was an empty list and the loop
body ran zero times. The only distance ever asserted was 0.0 for the identical
pair, and zero is the identity for cosine and L2 alike, so substituting the L2
operator passed all five tests. The file written to demonstrate that green is not
correct was itself green about nothing. Fixed with `max_distance=1.5` and the
count asserted before the loop.

**A reachability clause satisfied vacuously.** `conditionalAncestors` looped
`while (at && at !== stop)`, so a node outside `stop` walked to the file root,
collected nothing, and returned an empty array that every caller read as "no
gates". An adversary moved the skill gate's ruling fetch into a module level
function nothing calls and the guard reported 36 checks passed with typecheck and
build clean. Tee would have pressed Approve, seen the panel confirm the ruling,
and the row would never have changed. The helper now refuses an unreachable stop
node.

**A docstring measurement taken from a different statement.** The claim that a
list without the CAST fails as AmbiguousFunctionError does not reproduce:
removing the CAST passes every test and a direct probe returns rows, because
Postgres infers `uuid[]` from the column. That error was real and came from a
throwaway `SELECT unnest(:p)` probe, which has no column to infer from.

**And a fourth, narrower.** The learning store's write paths were called
unreachable. They are registered at `router.py:56` and exercised by
`test_devon_agent_tasks_api.py`. The true claim is that there was no web
surface, which is sufficient and is one grep from being right.

**The fifth was found while writing this document, and it was live on main.**
Pulling the graph panel rewrote `KnowledgePanel.tsx`'s file docstring to say the
edges are measured and nothing draws them, and rewrote `ControlPlane.tsx`'s tier
note to say the same. The paragraph at the bottom of `KnowledgePanel.tsx`'s own
render was not touched, and went on telling every reader that "the edges between
these items are drawn in the knowledge graph panel below", pointing at a
component that commit `8707362` had deleted. So the surface whose entire
justification is refusing to state an unmeasured thing spent a commit directing
people to a panel that was not there.

Twenty eight checks in this file's own guard passed over it, and so did 61 Python
voice tests, a typecheck and a production build, because every one of them reads
a literal, a symbol or an import. The method note written earlier in this same
arc was "a guard that reads a literal is not reading a rendering", and it was not
applied to the rendering.

The copy is now the honest statement. The guard added with it, check 29 in
`apps/web/scripts/control-check.ts`, reads the rendering: it resolves prose out
of the TypeScript AST, both `JsxText` and the string literals that JSX
expressions carry, and for every "the <name> panel below" it requires apps/web to
declare a matching component. Three negative controls, each confirmed to have
changed the file first. Restoring the exact sentence that was live fails the
check by name. Putting the same sentence in a line comment passes, which is
deliberate and is why `TierPanel.tsx` is not a false positive: a reader of the
source is not a reader of the page. Planting the reference in a JSX string
literal, the shape `ControlPlane.tsx` uses for its longest prose, also fails, so
the check is not limited to `JsxText`.

It needs no Python backstop, and the reason is worth stating rather than
assuming. The voice ban needed one because it reads served HTML under
`deploy/soul` and `docs/devon/assets`, which sat outside `web-ci.yml`'s path
filter. This check reads only `apps/web`, and that path is in the filter, so the
defect cannot be introduced without triggering the job that catches it. What it
still cannot do is resolve an unnamed reference: bare copy like "the panel below"
names nothing to look up, and is left alone rather than guessed at.

## What the adversaries were for

Seven ran, one whole PR critic and one per build, each mutating real source in
its own worktree on the exact SHA and echoing it back. They found the shipped
code sound almost everywhere and the guards weaker than their own commit
messages claimed. Every condition they raised on the merged work is closed and
each closure is proved by breaking it.

Worth keeping from the round, as method rather than as findings:

- A guard that reads a literal is not reading a rendering. The mode list was
  filtered before it rendered, and the gate's rulings sat in dead code with every
  button inert, both at a full green.
- A count is not a scope. `count_memories` carried a docstring calling the scope
  invariant load bearing and had no test anywhere.
- Absence is not disorder. The graph route could be deregistered entirely because
  the ordering helper returned True when the route was missing.
- A Python backstop can stop wrong rows and cannot put back the right ones it
  displaces. `<=` and `!=` on the self join both passed 47 tests because
  `assemble_graph` drops the bad pairs, while under the cap they cost 29 percent
  to 100 percent of the caller's edges.
- Two guards green about two different payloads is worse than one guard, because
  it reads as agreement.

## The suite numbers, including the ones that were not evidence

Two runs came back with four to five failures and about forty errors. Both
carried twelve duplicate key occurrences, the collision fingerprint this
repository documents for concurrent worktree agents, and the session had also
overlapped its own backgrounded runs, which the same file records as poisoning
the next one. Both causes at once. After the prescribed
`TRUNCATE users CASCADE` and a run alone: 1969 passed, zero failures, zero
duplicate key occurrences.

The delta reconciles rather than approximately matches: 1968 at the previous
head, minus four for the two removed panel files which each appear in the dash
and voice globs, plus three for the scope tests, plus one for the self join
predicate, plus one for route presence. Collected equals passed.

## Open

Two of the four subsystems are still stranded. `materialize_due_schedules` has
one caller, an HTTP route, and no cron, so scheduled goals do not run. The
workflow engine has ten routes, two migrations, a cron entrypoint and no
creation surface.

Two agent builds are integrated nowhere. The n8n execution telemetry has no
adversarial pass because that agent was stopped mid run. Its builder flagged the
executions response shape as unverified; measured against the live instance, the
per execution fields are real and `id` comes back as a STRING with gaps in the
sequence, which matters wherever the burn arithmetic orders or compares them.
The honesty fixes are ready and their adversary found an untrue claim still on
the landing page, "record the human final call so future decisions stay
accountable", where the handler is a `console.info` and nothing calls
`/decisions`.

`check:audio` runs in no workflow, now found by four separate passes. Playwright
is not a dependency of this repository and it works locally only because the
container ships a browser. Wiring it costs a devDependency, a lockfile change
and a browser install on every web CI run, which is Tee's ruling rather than a
silent addition.

Nobody has opened `/control` and seen the gate or the learning panel.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_three-doors-and-a-panel-pulled_v1_2026-09-10.md
DATE: 2026-09-10
DECISIONS: The rendered copy pointing at the deleted graph panel corrected and
guarded by a check that reads the AST's rendered prose, proved by three negative
controls, with no Python backstop because the path it reads is inside web-ci's
filter. Three of four ruled doors opened, the skill proposal gate first and
the learning store second; approve and promote kept as two rulings because the
API defaults promotion on; the knowledge graph router registered ahead of the
item lookup with the ordering asserted rather than commented; the graph panel
PULLED before shipping rather than repaired at pace, with its contract fix and
five open items staged; check:audio left unwired and referred to Tee because it
costs a dependency and a browser install per run.
FINDINGS: An edge query that could not execute against any real database while
forty two offline tests passed; a panel and its route built to two different
contracts, rendering a measurement over a query that never ran; a pgvector
assertion that executed zero times, so an L2 operator passed every test; a
reachability clause satisfied vacuously, so a ruling fetch in dead code reported
green; a docstring measurement taken from a different SQL statement than the one
it described; the learning write paths called unreachable when they were
registered and tested routes; the learning panel's adapter unguarded, so a failed
read rendered as an empty store; count_memories with no test while its docstring
called the scope invariant load bearing; two suite runs unusable as evidence
through a documented cluster collision; and, found while writing this document
and live on main for one commit, a rendered paragraph still sending readers to
the graph panel that had just been deleted, missed by every guard in the estate
because all of them read literals and symbols rather than renderings.
OPEN: Scheduler and workflow engine still stranded; n8n telemetry unintegrated
and without an adversarial pass, with string execution ids to check; honesty
fixes unintegrated and one landing page claim still untrue; check:audio in no
workflow; the graph panel's five items; nobody has opened /control and looked.
STATUS: three doors on main and unwatched by human eyes; the fourth deliberately
withheld
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
