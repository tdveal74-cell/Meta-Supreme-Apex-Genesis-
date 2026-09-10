# The n8n telemetry adversary: DO NOT SHIP, with nine reproductions

Tee ruled on 2026-09-10, from four inline choices, that the staged n8n execution
telemetry should get the adversarial pass it never had and that the decision would
follow the verdict. The verdict is DO NOT SHIP. This doc exists because the
findings were produced in an ephemeral worktree against work that is not on any
branch, so without it the whole pass dies with the container.

**Nothing from this piece is integrated.** No route is mounted, no panel is
rendered, no test file is in CI. The estate is unchanged by it.

## Why the pass was commissioned

The piece was built by a worktree agent and Tee stopped that agent mid run, so it
never got a critic. The one bug class known to be unexamined was the execution
`id`: n8n returns it as a STRING, and real observed ids are non contiguous, with
6669, 6666 and 6662 seen adjacent in one response. The whole month to date table,
every rate and every projection rest on an assumption the module itself calls
`ID_DELTA_ASSUMPTION`. The adversary was aimed there first.

That aim was correct. F1 below is exactly that class.

## Recovery, and a mutation that nearly shipped as real work

Three of the eight staged files turned out to be POINTERS to a worktree rather
than source: a description ending "full text is on disk at ...". The real content
was recovered from `.claude/worktrees/`, where three separate worktrees carried
it.

Two of those three agreed byte for byte. The third, `agent-a8c5735b7075cbbab`,
differed in `app/services/n8n_telemetry.py` by exactly one key:
`not_saved_in_span` had become `unsaved_in_span`. That is an unreverted adversary
mutation, and it is the failure CLAUDE.md's "Running a critic" section warns
about: a critic that stops mid mutation leaves dirt with no owner.

It was settled by reading the consumers rather than by picking the newer file.
The test asserts `window["not_saved_in_span"] == 116`, NOTES.md names
`not_saved_in_span`, and the web reader's type declares `not_saved_in_span`. So
the two agreeing copies are correct and the odd one out is the mutant. Had it
been recovered instead, the web field would have read `undefined` forever without
crashing anything.

## The nine findings

Every one below was executed. Locations are in the staged files, which are not in
the repository.

**F1. The rate's denominator is not corrected for the rows dropped from its
numerator.** `measure_window` takes ids only from rows whose id parses, and takes
`span_hours` from the `startedAt` of ALL rows, so a rate divides an id delta over
one subset by a span over another. Adding one row with an unparseable id, five
days older, moved `per_day` from 120 to 20 and the projected plan wall from
2026-09-19 to 2026-11-03. A thirty day older row moved it to 2027-06-18. The
panel renders that as a confident projection with a full basis block, because
every `REQUIRED_BASIS` field is present. Six to thirty one times understated, in
the falsely reassuring direction, which is the worst direction for a cost panel.
The payload does carry `ids_read` beside `executions_read`, and the panel renders
it nowhere and no check asserts it.

**F2. Pagination does not terminate on a 2xx page whose `data` holds no objects.**
The loop exits on `data`'s truthiness, not on whether any row was consumed. A page
of `["not-a-dict", 7, None]` with a repeating cursor produced 2000 requests to the
identical URL and was still going when the adversary's own bail out fired. One
panel load would hang an API worker and issue an unbounded outbound loop at the
instance. One clause closes it. Separately, a repeating cursor with real rows
reported 500 executions read for 10 actual ones, because rows are never deduped.

**F3. The panel's central law is defeated by destructuring, with every guard
green.** The check that forbids a bare projected date visits property and string
element access, and not binding patterns. Sixteen lines of idiomatic TSX
destructuring `cap.projection` rendered a wall date with no basis and no
assumptions, and returned `21 checks passed` with `tsc` exit 0. No live defect,
a real hole in the invariant the panel's docstring calls its first refusal.

**F4. A degraded read that knows nothing renders a good tone and asserts "none of
them failed".** `failed` falls back to 0, so a payload reporting
`status_unreported: 100` produced a cyan dot and the sentence "100 saved
executions read, none of them failed". `counts: null` reads good too. The trigger
is the `status` field name, which is on the builder's own unverified list: if n8n
names it anything else, every row lands in `status_unreported` and the whole panel
goes green asserting no failures.

**F5. An unbounded `days_left` produces an absurd date or an HTTP 500 that blanks
both instances.** With a cap of 30000 and two rows one id apart across 100 days,
`_iso` raised `OverflowError: date value out of range` and the route answered 500.
Below the crash threshold it prints a date instead: a cap of 2500 at 0.01 per day
gave `exhausts_at 2710-11-24`. `read_all` builds both instances in one
comprehension, so a healthy primary plus an overflowing secondary loses BOTH
columns. Caps in the tens of thousands are ordinary plan values.

**F6. The id parser crashes on some inputs and coerces others it claims to
refuse.** `isdigit()` with no `try` around `int()`: `"--5"` and `"^2"` both
answered HTTP 500, while the Arabic indic digit three was coerced to 3 and became
part of an id delta. The docstring says anything else "is refused rather than
coerced". Both halves fail for non ASCII decimal digits. Low severity, since real
n8n ids are ASCII serials, and the fix is one `try` plus an `isascii()` test.

**F7. The non monotonicity guard cannot fire.** `newest_id` is `max(ids)` and
`oldest_id` is `min(ids)` over the same list, so `newest_id < oldest_id` is
arithmetically impossible. Proved by replacing the branch's return with a raise,
confirming the mutation landed, and getting 41 passed: no test reaches it. Fed the
real observed 6669, 6666, 6662 shape out of time order, and reversed ids, and a
newest row carrying the smallest id: every one printed NOT REACHED with a real
rate. So the one thing `ID_DELTA_ASSUMPTION` warns about is undetectable, and
NOTES.md's claim that the window "drops not_saved_in_span rather than printing a
negative if the ids contradict the assumption" cannot happen. On that real shape
it reported a rate of 7 a day and a projection of 2027-01-07, treating the window
as monotonic, and paired `counted_from_id` with a DIFFERENT row's moment.

**F8. `N8N_EXECUTION_CAP_RESETS_AT` is read, carried, and rendered nowhere.** From
configuration alone the module projected a wall of 2027-01-07 with a stated reset
of 2026-10-01, three months earlier. Nothing compares them, nothing renders the
reset, no check asserts it. Falsely alarming rather than falsely reassuring, which
is why it sits below F1.

**F9. The web readers validate presence, not type or sanity.** With all six
required fields present, `per_day` of NaN and of the string "one hundred and
twenty" both returned a confident date, one of them reading "At NaN executions a
day". A cap of 0 rendered "1088 of 0 left"; a cap of -100 rendered a 100 percent
red bar and "-110 left". `N8N_EXECUTION_CAP=-100` is accepted by the env reader
with no reported problem, so the negative cap sentence is reachable from a typo.

## Two of the builder's own negative controls do not hold as written

The builder claimed ten controls with actual output. Seven reproduced, two of them
harder than reported. Two did not hold:

- Control 1 and 5 both rest on an AST walk for mutating verbs that is NAME based.
  `router.add_api_route(..., methods=["POST"])` is caught by the route table walk
  but not by the AST walk. Worse, `client.request("DELETE", url)` and
  `client.send(httpx.Request("POST", url))` inside the production fetcher returned
  41 passed: two live mutating verbs, fully green. The route table walk is the
  load bearing guard; the AST walk is not the structural guarantee it looks like.

The builder was right about which guard is load bearing on the network refusal: an
obfuscated URL literal defeated the AST check and
`test_nothing_configured_never_reaches_the_network` still failed.

## What still cannot be checked from here, and by whom

The real `/api/v1/executions` response shape is the single dependency under F1,
F2 and F4. There is no route to the instance from this container and no
credentials, and there must not be: a live key never enters a session transcript.
Tee can settle it with the one curl in the builder's notes, holding
`N8N_API_URL` and `N8N_API_KEY` himself. Whether ids are monotonic on the self
hosted instance is the same, and F7 means the module cannot answer it either way.

## Recommendation

Leave it staged. F1 alone is disqualifying for a cost panel: it is wrong in the
reassuring direction, it is reachable from an input the builder never measured,
and the payload already carries the evidence that would expose it. F2 and F5 can
take down an API worker and both instances.

None of the nine is hard. They are roughly a session's work with its own controls,
and the honest sequencing is to settle the response shape first, because F1, F2
and F4 all turn on a field name that was copied from a different endpoint rather
than measured. Fixing arithmetic against a guessed contract is how this piece got
here.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_n8n-telemetry-adversary_v1_2026-09-10.md
DATE: 2026-09-10
DECISIONS: Ruled by Tee to run the adversary and let the verdict decide; verdict
is DO NOT SHIP and the recommendation is to leave the piece staged and unmerged;
nothing from it is integrated, no route mounted and no test registered; the real
executions response shape is to be settled by Tee with his own credentials before
any fix round, because three of the nine findings turn on a field name copied
from a different endpoint rather than measured.
FINDINGS: A burn rate whose denominator is not corrected for the rows dropped
from its numerator, understating six to thirty one times and moving a plan wall
months later in the reassuring direction; pagination that never terminates on a
2xx page carrying no objects, measured at 2000 identical requests; the panel's
central refusal defeated by destructuring with 21 checks and tsc green; a payload
of entirely unreported statuses rendered as a good tone asserting none failed; an
unbounded projection raising OverflowError into an HTTP 500 that blanks both
instances; an id parser that crashes on two inputs and coerces non ASCII digits
it documents as refused; a non monotonicity guard that is arithmetically
unreachable, so the one assumption the module warns about is undetectable; a
configured reset date read and rendered nowhere while a wall is projected past
it; web readers validating presence rather than type, printing a confident date
from a NaN rate. Separately, two of the builder's ten negative controls do not
hold as written, because a name based AST walk misses add_api_route and
client.request. Separately again, three staged files were pointers rather than
source, and one recovered copy carried an unreverted adversary mutation renaming
not_saved_in_span, settled by reading the three consumers rather than by trusting
the newer file.
OPEN: Every one of the nine, none integrated; the real n8n executions response
shape and whether self hosted ids are monotonic, both for Tee with his own
credentials; whether to fund the fix round now.
STATUS: staged and unmerged, adversarially reviewed, DO NOT SHIP standing
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
