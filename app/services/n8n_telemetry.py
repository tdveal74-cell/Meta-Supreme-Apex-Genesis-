"""Read only telemetry over the configured n8n instance or instances.

WHY THIS EXISTS

`apps/web/components/control/ExecutionHubPanel.tsx` said, honestly, that no
route in this repository reads the n8n instance, so tier 3 of the control plane
rendered the API's own health instead of inventing execution data. This module
is the read the panel was missing. It reads and only reads.

WHAT IS STRUCTURALLY FORBIDDEN HERE

n8n's API can trigger, retry, delete and resume executions. None of that is
reachable from this module: the only transport verb it can speak is GET.
`_httpx_get` is the single request function, it hard codes `client.get`, and
`test_n8n_telemetry.py` walks this file's syntax tree and fails the run if any
mutating HTTP verb appears in it, whether as an attribute (`client.po` + `st`),
as a verb string handed to a generic dispatcher (`client.request("DELETE", ...)`,
`httpx.Request("POST", ...)`), or as a `methods=` list on a route registration.
That walk is a first line, and this paragraph used to call it the guarantee.
That was wrong, and it was proved wrong on 2026-09-10: an adversary put
`object.__setattr__(request, "method", _v)` in the fetcher with the verb
assembled by `"".join(("PO", "ST"))`, so NO verb string existed anywhere in this
file, the walk reported zero offences, and a capture server logged POST on the
wire.

The guarantee is therefore an EXECUTED one, and it has a scope.
`test_the_request_that_reaches_the_wire_carries_get` installs a recording
transport under this very function and asserts on the request object the
transport is handed, so it does not care how the verb got there. What it cannot
see is a request that never passes through here, and that paragraph used to read
as though it could. A fourth adversary walked around the side of it on
2026-09-10 by appending a second fetcher built on `urllib.request.urlopen`,
where the verb is not a token at all: `urllib` promotes GET to POST purely
because `data=` is not None. The walk found no verb to fold, the recorder was
never called, and a capture server logged POST against a retry endpoint with the
API key attached.

So the guarantee is four claims and it needs all four.

`test_the_audited_fetcher_is_the_only_door` is the first. These files may import
only a measured allowlist of modules; `urllib.request`, `socket`, `subprocess`
and their kind are refused whatever that allowlist later says; `httpx` may be
imported only inside `_httpx_get`; members of the two local packages are pinned;
and the dynamic code that would hide any of that is refused by shape rather than
by value. One door.

`test_the_audited_fetcher_cannot_tell_it_is_being_watched` is the second, and it
is here because a fifth adversary walked through its absence on 2026-09-10 while
the suite reported 210 passed. Its fetcher branched:

    if "includeData" in url:
        <a POST, assembled so that no verb string exists>
    else:
        response = await client.get(url, headers=headers)

Every production read is built by `_executions_url`, which always appends
`&includeData=false`. The executed check drove one hand written URL that carried
no such token, so the recorder was handed the GET branch while a capture server
logged POST on the URL this module itself builds. `_httpx_get` may therefore
contain no branch: no `If`, no `IfExp`, no `Match`, no `While`, no `BoolOp` and
no `Compare`. It has none today. And because that is another enumeration, the
executed check is now driven with the URLs `_executions_url` produces rather
than with hand written ones, so the two halves fail in different directions.

`test_the_production_read_path_sends_only_gets` is the third, and it is here
because a sixth adversary found that the check above hands `_httpx_get` a
headers dict of its own making while the real headers are assembled one frame up
in `_read_pages`. So the three method override header names this module forbids
were unenforced on the only path production uses, and a capture server logged

    GET /api/v1/executions?limit=100&includeData=false
    X-HTTP-Method-Override: DELETE

with the suite at 215 passed. Graded before it was written up: the verb on the
wire is GET, so nothing mutates unless an intermediary honours the override, and
n8n on Express does not by default. The defect was a guard credited for a check
it never performed on the path that matters. `read_all` is now driven with no
fake at all, across two pages so the cursor URL is built too, and what left is
read by one shared definition of a bad request: a verb other than GET, any
override header, or any path but `/api/v1/executions`.

The syntax walk is the fourth and is kept because it is cheap and names the
offence precisely. All of them are proved against synthetic bypasses that each
reached a real socket once, in
`test_the_mutating_verb_detector_catches_the_ways_around_it`,
`test_the_egress_detector_catches_the_second_doors` and
`test_the_driven_urls_are_the_production_ones`.

THE API SHAPE WAS MEASURED ON 2026-09-10

Thirty two real executions were read through this session's n8n connector.
What is now MEASURED rather than assumed:

* the fields present on a row are id, workflowId, status, mode, startedAt,
  stoppedAt and waitTill.
* `id` is a STRING, for example "6679". Ids are non contiguous: 6679, 6675,
  6671, 6669, 6666, 6662, with gaps of two to four, which is exactly the shape
  the id delta method is for.
* across all thirty two sampled rows, descending id tracked descending
  startedAt. No inversion was observed. That makes the monotonicity assumption
  supported for this instance today, which is not the same as guaranteed, so
  `measure_window` compares id order against startedAt order every read and
  refuses the rate when they disagree.
* `status` is the real field name and its values are lower case. The full value
  set the API documents is canceled, crashed, error, new, running, success,
  unknown and waiting. "unknown" is a status the instance itself reports and is
  NOT the same as a row that carried no status field: the first lands in
  `other`, the second in `status_unreported`, and neither is ever counted as a
  pass.
* `mode` takes trigger, manual, webhook and also "error", which names an error
  handler workflow and is NOT a status. Nothing here reads mode as one.
* `workflowData.name` DOES NOT EXIST in the response. Only `workflowId` comes
  back. So a row carries no workflow name, and rather than leave a reader
  looking at a blank where a name was promised, `read_row` reports a
  `workflow_label` together with `workflow_label_kind`, which says whether the
  label is a name or an id.

WHAT IS STILL UNSETTLED, AND IS THEREFORE NOT LOAD BEARING

* The pagination envelope. The measurement went through a connector that may
  normalise, so whether the raw REST endpoint answers `{"data": [...],
  "nextCursor": ...}`, a nested cursor, or a bare list is UNSETTLED.
  `_page_shape` accepts all of them and depends on none of them.
* Which instance the connector reached. The module reads a Cloud primary and a
  self hosted secondary and the shape above is confirmed for at least one of
  them. Nothing extra is assumed about the other beyond it being the same
  software, which is why every instance is read and reported on its own.

WHAT IS MEASURED AND WHAT IS ONLY STATED

The plan cap is a property of an n8n Cloud plan. It is not a fact about
executions and nothing in the executions API reports it, so it arrives from
configuration or not at all. A self hosted instance has no cap and this module
must never invent one for it: `cap.state` is `not_stated` unless an operator
set the cap variable for that instance, and the payload labels a stated cap as
`stated_by_configuration` every time it reports one.

The month to date spend is the same shape of problem, worse. A set of organs
stopped saving successful executions on 2026-09-05, recorded in
docs/devon/SYS_OPS_devon-autonomy-driver_v1_2026-09-05.md, so counting the rows
the executions API returns undercounts the spend by however many runs were never
saved. The count of organs is not repeated here: on this estate that count has
been taken from a dependency list rather than from the workflows twice already,
and nothing in this module needs the number.

The one method that survives that undercount is the one
docs/devon/SYS_OPS_n8n-cloud-to-vps-cutover_v2_2026-09-06.md section 2 used by
hand: execution ids are global and monotonic, so the gap between two ids is the
number of executions between them, saved or not. This module carries that method
and every assumption under it, anchored on a spend an operator read off the
provider's usage page. The usage page stays the truth. This is an estimate and
says so in the field name.

THE ARITHMETIC RULES THIS MODULE OBEYS

1. A ratio's numerator and its denominator come from the SAME rows. The rate is
   an id gap over a time span, so both are taken from the rows that carry both
   an id and a startedAt, and the count of rows that carry neither travels on
   the payload so the divergence is visible rather than silently absorbed.
2. A basis is coherent or it is withheld. The id a spend was carried forward to
   and the moment that spend was counted from come from the SAME execution, not
   from whichever row happened to be newest by each measure.
3. One instance's failure never blanks the other.

WHAT WAS CUT ON 2026-09-10, SO NOBODY REBUILDS IT

This module used to project a date the plan cap would be exhausted on. Tee
ruled the projection out: it was the least valuable number the panel carried
and the most expensive one to be right about, it had consumed three adversary
cycles and failed two of them, and the read it sat on already answers the
question an operator actually asks. `exhausts_at` was the only DERIVED date on
the wire; every date that remains here is observed from a row or stated by
configuration. The burn against the cap survives, because that was the number
genuinely missing, and every guard whose subject is the burn survives with it:
`id_delta_refusal` above all, since the burn is still an id gap.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, NamedTuple, Optional, Set, Tuple
from urllib.parse import urlparse

# One page of the executions list. `_paged_workflows` in scripts/n8n_migrate.py
# asks for 100 at a time and this matches it.
PAGE_SIZE = 100

# Default and ceiling on how many saved executions one read walks. The ceiling
# exists so a caller cannot turn a panel refresh into a long crawl of a
# thousand pages.
DEFAULT_LIMIT = 100
MAX_LIMIT = 500

# A hard ceiling on pages walked, independent of the row limit. A 2xx page that
# yields no new execution, or a cursor the walk has already followed, both stop
# the walk on their own; this is the backstop for a shape neither of those
# catches. Comfortably above the five full pages MAX_LIMIT can need.
MAX_PAGES = 40

TIMEOUT_SECONDS = 10.0

# An execution id is a sequence number. Anything past this is not one, and
# admitting it would put an id delta into the arithmetic that no timedelta can
# carry. Refused rather than coerced, like every other unreadable id.
MAX_EXECUTION_ID = 10 ** 15


def _ID_DOMAIN(value: int) -> bool:
    """The accepted set for an execution id, stated once.

    A sequence number is not negative. This exists as a function rather than as
    two inline comparisons because the version of `_row_id` that wrote the
    bound out twice used `abs()` in one place and stripped a leading `-` in the
    other, and so admitted -1000000 into the id delta. One statement of the
    domain cannot disagree with itself.
    """
    return 0 <= value <= MAX_EXECUTION_ID

# Buckets over n8n's execution status strings. The raw counts travel beside
# these, under `status_counts`, so a status this map has never seen cannot be
# hidden by the bucketing: it lands in `other` and its own label is still there
# to read. The value set below was MEASURED on 2026-09-10; "unknown" is
# deliberately NOT given a bucket of its own, because an instance reporting
# "unknown" has told us it does not know, which is `other`, not a pass.
_FAILED = ("error", "crashed")
_SUCCEEDED = ("success",)
_CANCELED = ("canceled", "cancelled")
_RUNNING = ("running", "new")
_WAITING = ("waiting",)

# What every derived number on this payload rests on. Rendered by the panel
# beside the burn, because a number with no basis is the thing this estate has
# been burned by. It travelled beside a projected date until that was cut; the
# burn is still derived, so it still travels.
ID_DELTA_ASSUMPTION = (
    "Execution ids on this instance are global and monotonic, so the gap between two ids "
    "is the number of executions between them, saved or not. Measured true on 32 sampled "
    "executions on 2026-09-10, and re-checked against startedAt order on every read."
)
CAP_ASSUMPTION = (
    "The cap and the anchor spend are stated by configuration, read off the provider's usage "
    "page by a human. Nothing here measures either, and the usage page stays the truth on both "
    "the count and the reset date."
)
WINDOW_ASSUMPTION = (
    "The rate is the rate over the window actually read, which is short. A build session inside "
    "that window overstates a quiet day and a quiet window understates a build day."
)


class Unreachable(RuntimeError):
    """The request never reached the instance. Distinct from a bad answer."""


class Fetched(NamedTuple):
    """One answered GET. `final_url` is where the answer actually came from."""

    status: int
    payload: Any
    final_url: str


# A fetcher takes an absolute URL and headers and either answers or raises
# Unreachable. Injected so the tests can drive every state with no network.
Fetcher = Callable[[str, Dict[str, str]], Awaitable[Fetched]]


@dataclass(frozen=True)
class InstanceConfig:
    """Where one instance's settings live in the environment.

    The variable names are data, not literals scattered through the code, so
    the secondary instance is the primary's shape with one prefix changed and
    a reader can see there is no third path.
    """

    role: str
    url_var: str
    key_var: str
    cap_var: str
    anchor_id_var: str
    anchor_spent_var: str
    anchor_at_var: str
    resets_at_var: str


def _config(role: str, prefix: str) -> InstanceConfig:
    return InstanceConfig(
        role=role,
        url_var=f"{prefix}API_URL",
        key_var=f"{prefix}API_KEY",
        cap_var=f"{prefix}EXECUTION_CAP",
        anchor_id_var=f"{prefix}EXECUTION_CAP_ANCHOR_ID",
        anchor_spent_var=f"{prefix}EXECUTION_CAP_ANCHOR_SPENT",
        anchor_at_var=f"{prefix}EXECUTION_CAP_ANCHOR_AT",
        resets_at_var=f"{prefix}EXECUTION_CAP_RESETS_AT",
    )


PRIMARY = _config("primary", "N8N_")
SECONDARY = _config("secondary", "N8N_SECONDARY_")
INSTANCES: Tuple[InstanceConfig, ...] = (PRIMARY, SECONDARY)


# ---------------------------------------------------------------------------
# environment reading, all of it refusing rather than defaulting
# ---------------------------------------------------------------------------

def _env(name: str, environ: Optional[Dict[str, str]] = None) -> str:
    source = os.environ if environ is None else environ
    return (source.get(name) or "").strip()


def _int_env(
    name: str,
    environ: Optional[Dict[str, str]],
    minimum: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """An integer variable, or None with the reason it could not be read.

    A variable that is set to something unparseable is a configuration error
    and is reported as one. Falling back to a default here would put a number
    on the panel that no one configured, which is the failure this whole module
    is shaped around.

    `minimum` is the second half of that. A cap of zero and a spend of minus a
    billion parse perfectly well and are still not numbers anybody meant: the
    first divided into a used fraction and the second drove the arithmetic that
    then answered HTTP 500. A value below the floor is
    refused and named, exactly like an unparseable one, rather than carried
    into arithmetic that cannot survive it.
    """
    raw = _env(name, environ)
    if not raw:
        return None, None
    try:
        value = int(raw)
    except ValueError:
        return None, f"{name} is set to {raw!r}, which is not a whole number"
    if minimum is not None and value < minimum:
        return None, (
            f"{name} is set to {raw!r}, which is below {minimum}. It is not read, and nothing "
            "is derived from it."
        )
    return value, None


def _parse_moment(value: Any) -> Optional[datetime]:
    """An ISO 8601 instant from n8n or from configuration, as aware UTC.

    The exact form n8n stamps an execution with was not read field by field
    while this was written, so the parser takes whatever Python 3.11's
    fromisoformat accepts, which includes a trailing Z and a bare date, and
    returns None for anything else rather than guessing at a format. A naive
    value is read as UTC rather than as the container's local zone, because the
    container's zone is not a fact about the instance.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat().replace("+00:00", "Z") if moment else None


@dataclass(frozen=True)
class Plan:
    """The cap statement for one instance, as configuration gave it."""

    cap: Optional[int]
    anchor_id: Optional[int]
    anchor_spent: Optional[int]
    anchor_at: Optional[str]
    resets_at: Optional[str]
    problems: Tuple[str, ...]


def read_plan(config: InstanceConfig, environ: Optional[Dict[str, str]] = None) -> Plan:
    # The floors are the sanity half of reading configuration. A cap must be a
    # real ceiling, so at least 1. An id and a spend are counts, so at least 0.
    # Every rejection is reported by name rather than silently defaulted.
    cap, cap_problem = _int_env(config.cap_var, environ, minimum=1)
    anchor_id, id_problem = _int_env(config.anchor_id_var, environ, minimum=0)
    anchor_spent, spent_problem = _int_env(config.anchor_spent_var, environ, minimum=0)
    problems = tuple(p for p in (cap_problem, id_problem, spent_problem) if p)
    return Plan(
        cap=cap,
        anchor_id=anchor_id,
        anchor_spent=anchor_spent,
        anchor_at=_env(config.anchor_at_var, environ) or None,
        resets_at=_env(config.resets_at_var, environ) or None,
        problems=problems,
    )


# ---------------------------------------------------------------------------
# transport. GET is the only verb in this file.
# ---------------------------------------------------------------------------

async def _httpx_get(url: str, headers: Dict[str, str]) -> Fetched:
    """The production fetcher. One verb, and a raise for never having arrived.

    A connect failure, a DNS failure, a TLS failure and a timeout are all the
    same answer to the question the panel asks: the instance was not reached.
    They are NOT the same as an instance that answered with an empty list, and
    collapsing the two is how a dead instance reads as a quiet one.
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
    except Exception as exc:
        # Deliberately broad. Every way httpx can fail to arrive is the same
        # answer to the panel's question, and naming a subset here would let a
        # new httpx error class escape as a 500 instead of as "unreachable".
        raise Unreachable(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
    try:
        payload = response.json()
    except ValueError:
        payload = None
    return Fetched(response.status_code, payload, str(response.url))


def _executions_url(base: str, limit: int, cursor: Optional[str]) -> str:
    from urllib.parse import quote

    query = f"?limit={limit}&includeData=false"
    if cursor:
        query += f"&cursor={quote(cursor)}"
    return f"{base.rstrip('/')}/api/v1/executions{query}"


# ---------------------------------------------------------------------------
# pure readers over the rows n8n returns
# ---------------------------------------------------------------------------

def _row_id(value: Any) -> Optional[int]:
    """An integer id, or None. Refused rather than coerced, and never raising.

    MEASURED 2026-09-10: the API returns `id` as a STRING of digits, so the
    string path below is the live one and the integer path is tolerance for an
    instance that answers otherwise.

    Three things this refuses that the first version of it did not, each one
    found by feeding it the input:

    * `"--5"` passed `lstrip("-").isdigit()` and then raised ValueError out of
      `int()`, which reached the route as HTTP 500. There is a try around the
      conversion now, and the sign is checked at most once.
    * `"²"`, a superscript two, is `isdigit()` in Python and is not a
      digit `int()` accepts. Same 500.
    * `"٣"`, an Arabic indic three, is `isdigit()` AND `int()` reads it as
      3, so it was silently COERCED into the id delta while the docstring said
      anything else "is refused rather than coerced". `isascii()` is what makes
      the docstring true.

    A bool is not an id, a value past `MAX_EXECUTION_ID` is not one either, and
    an id that silently became 1 would corrupt every id delta on the payload.

    THE DOMAIN. An execution id is a sequence number, so the accepted set is
    exactly the integers `0 <= id <= MAX_EXECUTION_ID`. `_ID_DOMAIN` below is
    the ONE place that set is stated and both branches go through it, because
    the version of this function with the bound written out twice bounded one
    branch with `abs()` and stripped a leading `-` before parsing, and so
    ADMITTED `-1000000`. Reproduced through the mounted route on 2026-09-10:
    two rows, ids "6412" at 12:00 and "-1000000" the day before, cap 2500 with
    anchor 6000/1000, answered HTTP 200 with `per_day` 1006412.0,
    `not_saved_in_span` 1006411 and `exhausts_at` 93 seconds after the read,
    rendered as a good-toned wall with every basis field present and no flag.
    The truth from those two rows is 120.0 a day and a wall nine days out.

    A negative id is now refused at the sign rather than stripped: there is no
    path from a `-` to an `int()` call here, so no sign form can reach the
    arithmetic. `test_the_id_parser_admits_exactly_the_documented_domain`
    drives the whole sign and boundary table through it.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if _ID_DOMAIN(value) else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or not text.isascii():
        return None
    # No sign stripping. A leading "-" or "+" is not a digit and this refuses
    # here rather than parsing and bounding afterwards.
    if not text.isdigit():
        return None
    try:
        parsed = int(text)
    except ValueError:
        # Unreachable given the two tests above, and kept anyway: the whole
        # point of this function is that no row shape can turn a panel refresh
        # into a 500, and a guard that rests on my reading of isdigit() is a
        # guard that rests on my reading of isdigit().
        return None
    return parsed if _ID_DOMAIN(parsed) else None


def _row_status(row: Dict[str, Any]) -> Optional[str]:
    value = row.get("status")
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def read_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """One execution, flattened, with nothing guessed.

    A row with no `status` is reported as unreported rather than inferred from
    `finished`. An older n8n that omits the field would otherwise have every
    unfinished run counted as a success or as a failure depending on which way
    the guess went, and a wrong failure count during a cutover is worse than an
    absent one.

    The workflow label is the shape correction of 2026-09-10. The response
    carries `workflowId` and NO `workflowData.name`, so `workflow_name` is null
    on a live row. Rather than render a blank where a name was promised, the
    row carries `workflow_label` with `workflow_label_kind` beside it saying
    whether that label is a name, an id, or nothing at all. The panel renders
    the kind, so a reader looking at "workflow id 42" knows it is an id.
    """
    started = _parse_moment(row.get("startedAt"))
    stopped = _parse_moment(row.get("stoppedAt"))
    duration_ms: Optional[int] = None
    if started and stopped:
        delta = (stopped - started).total_seconds() * 1000
        # A stoppedAt before startedAt is not a duration. Report nothing.
        duration_ms = int(round(delta)) if delta >= 0 else None

    workflow = row.get("workflowData")
    workflow_name = workflow.get("name") if isinstance(workflow, dict) else None
    if isinstance(workflow_name, str) and workflow_name.strip():
        workflow_name = workflow_name.strip()
    else:
        candidate = row.get("workflowName")
        workflow_name = candidate.strip() if isinstance(candidate, str) and candidate.strip() else None

    workflow_id_raw = row.get("workflowId")
    workflow_id = str(workflow_id_raw) if workflow_id_raw not in (None, "") else None

    if workflow_name:
        workflow_label, workflow_label_kind = workflow_name, "name"
    elif workflow_id:
        workflow_label, workflow_label_kind = f"workflow id {workflow_id}", "id"
    else:
        workflow_label, workflow_label_kind = "no workflow identified", "unidentified"

    return {
        "id": _row_id(row.get("id")),
        "status": _row_status(row),
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "workflow_label": workflow_label,
        "workflow_label_kind": workflow_label_kind,
        # MEASURED: mode takes "error" for an error handler workflow. That is
        # not a status and nothing here reads it as one.
        "mode": row.get("mode") if isinstance(row.get("mode"), str) else None,
        "started_at": _iso(started),
        "stopped_at": _iso(stopped),
        "duration_ms": duration_ms,
    }


def count_statuses(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    """(buckets, raw counts). Every row lands in exactly one bucket."""
    buckets = {
        "failed": 0,
        "succeeded": 0,
        "canceled": 0,
        "running": 0,
        "waiting": 0,
        "other": 0,
        "status_unreported": 0,
    }
    raw: Dict[str, int] = {}
    for row in rows:
        status = row.get("status")
        if not status:
            buckets["status_unreported"] += 1
            continue
        raw[status] = raw.get(status, 0) + 1
        if status in _FAILED:
            buckets["failed"] += 1
        elif status in _SUCCEEDED:
            buckets["succeeded"] += 1
        elif status in _CANCELED:
            buckets["canceled"] += 1
        elif status in _RUNNING:
            buckets["running"] += 1
        elif status in _WAITING:
            buckets["waiting"] += 1
        else:
            buckets["other"] += 1
    return buckets, dict(sorted(raw.items()))


def measure_window(rows: List[Dict[str, Any]], truncated: bool) -> Dict[str, Any]:
    """What the read actually covered, how much of it was never saved, and
    whether the ids and the clock agree.

    `not_saved_in_span` is the number the cutover cares about: the ids between
    the oldest and newest row that have no row of their own. On this estate
    that is not a fault, it is the 2026-09-05 setting that stopped a set of
    organs saving successful executions, and it is exactly the reason a count
    of returned rows must never be presented as the spend.

    TWO THINGS THIS FUNCTION GOT WRONG AND NOW DOES NOT

    1. It took the id delta from the rows whose id parsed and the time span
       from the startedAt of ALL rows, so a single row with an unreadable id
       widened the denominator without touching the numerator. One extra row
       five days older moved a measured 120 a day to 24, and a thirty day old
       one to 4: six to thirty times understated, in the reassuring direction,
       and rendered as a confident figure because every basis field was
       present. The rate window below is taken from the rows carrying BOTH an
       id and a startedAt, so the numerator and the denominator are the same
       rows, and `rows_without_id` travels on the payload so the divergence is
       visible instead of absorbed.

    2. It claimed to guard non-monotonic ids with `newest_id >= oldest_id`,
       where `newest_id` is `max(ids)` and `oldest_id` is `min(ids)` over the
       same list. That comparison cannot be false. Replacing the branch it
       guarded with a raise ran the whole suite green, which is what a guard
       that cannot fire looks like. The real question is whether ID ORDER
       matches STARTEDAT ORDER, and `id_order_matches_time` below answers it by
       walking the rows in time order and looking for a later execution
       carrying a smaller id.
    """
    parsed: List[Tuple[Optional[int], Optional[datetime]]] = []
    for row in rows:
        candidate = row.get("id")
        parsed.append((
            candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None,
            _parse_moment(row.get("started_at")),
        ))

    distinct_ids = sorted({rid for rid, _ in parsed if rid is not None})
    moments = sorted(at for _, at in parsed if at is not None)
    # The rows the rate may be measured over: both halves of the ratio present.
    paired = sorted(
        ((rid, at) for rid, at in parsed if rid is not None and at is not None),
        key=lambda pair: (pair[1], pair[0]),
    )

    ids_read = len(distinct_ids)
    newest_id = distinct_ids[-1] if distinct_ids else None
    oldest_id = distinct_ids[0] if distinct_ids else None
    newest_at = moments[-1] if moments else None
    oldest_at = moments[0] if moments else None

    # The moment belonging to the row that CARRIES newest_id, which is not the
    # newest moment in the window unless the ids and the clock agree. The cap
    # carries a spend forward to newest_id, so the moment that spend was
    # counted from has to be this one. Pairing it with the other produced a
    # basis that read coherent and was not.
    newest_id_at = next((at for rid, at in paired if rid == newest_id), None)
    oldest_id_at = next((at for rid, at in paired if rid == oldest_id), None)

    span_hours: Optional[float] = None
    if newest_at and oldest_at:
        span_hours = round((newest_at - oldest_at).total_seconds() / 3600.0, 3)

    monotonic, order_note, inversions = _id_order(paired)

    rate_from = paired[0] if paired else None
    rate_to = paired[-1] if paired else None
    # BOTH forms, and they have different jobs. `rate_span_seconds` is exact and
    # is what the rate divides by. `rate_span_hours` is rounded to three places
    # and is for display only.
    #
    # They used to be one field, rounded, used as the denominator. A four second
    # window rounds 0.001111 hours to 0.001, which overstates the rate by 11
    # percent; a 3.6 second window rounds 0.001 to 0.001 and a 1.0 second window
    # rounds 0.000278 to 0.0, at which point `span_hours <= 0` and the rate was
    # REFUSED on a window that had one. Rounding before dividing is the defect
    # whichever direction it lands in.
    rate_span_seconds: Optional[float] = None
    rate_span_hours: Optional[float] = None
    if rate_from and rate_to:
        rate_span_seconds = (rate_to[1] - rate_from[1]).total_seconds()
        rate_span_hours = round(rate_span_seconds / 3600.0, 3)

    ids_in_span: Optional[int] = None
    not_saved: Optional[int] = None
    if newest_id is not None and oldest_id is not None and monotonic is not False:
        ids_in_span = newest_id - oldest_id + 1
        # More saved rows than ids in the span cannot happen if the ids are
        # global and monotonic. If it does, the assumption is wrong for this
        # instance and the derived number is dropped rather than shown negative.
        not_saved = ids_in_span - ids_read if ids_in_span >= ids_read else None

    return {
        "executions_read": len(rows),
        "ids_read": ids_read,
        # The divergence F1 hid. `executions_read` minus `ids_read` is how many
        # rows contributed to the window a reader sees and to nothing the
        # arithmetic uses, and the panel renders it.
        "rows_without_id": sum(1 for rid, _ in parsed if rid is None),
        "rows_without_started_at": sum(1 for _, at in parsed if at is None),
        "dated_ids_read": len(paired),
        "newest_id": newest_id,
        "oldest_id": oldest_id,
        "newest_id_started_at": _iso(newest_id_at),
        "oldest_id_started_at": _iso(oldest_id_at),
        "newest_started_at": _iso(newest_at),
        "oldest_started_at": _iso(oldest_at),
        "span_hours": span_hours,
        "rate_from_id": rate_from[0] if rate_from else None,
        "rate_to_id": rate_to[0] if rate_to else None,
        "rate_from_moment": _iso(rate_from[1]) if rate_from else None,
        "rate_to_moment": _iso(rate_to[1]) if rate_to else None,
        "rate_span_hours": rate_span_hours,
        "rate_span_seconds": rate_span_seconds,
        "id_order_matches_time": monotonic,
        "id_order_inversions": inversions,
        "id_order_note": order_note,
        # The short form, for the places that must say it rather than explain
        # it. See ID_ORDER_SHORT.
        "id_order_summary": ID_ORDER_SHORT if monotonic is False else None,
        "ids_in_span": ids_in_span,
        "not_saved_in_span": not_saved,
        # How much of the id span has a saved row of its own. `not_saved_in_span`
        # is the count; this is the fraction, and it is what tells a reader
        # whether "none of them failed" is a statement about the instance or
        # about a small sample of it. None when the span could not be measured.
        "span_coverage": (
            round(ids_read / ids_in_span, 4)
            if isinstance(ids_in_span, int) and ids_in_span > 0
            else None
        ),
        "truncated": truncated,
    }


def _id_order(
    paired: List[Tuple[int, datetime]],
) -> Tuple[Optional[bool], str, int]:
    """Does id order match startedAt order? True, False, or not enough to say.

    This is the detector the vacuous `newest_id >= oldest_id` comparison
    pretended to be. `paired` arrives sorted by (moment, id); an inversion is a
    strictly later execution carrying a strictly smaller id. Two executions
    stamped with the same instant have no order between them, so they are
    skipped rather than counted either way.

    MEASURED 2026-09-10: across 32 sampled executions, descending id tracked
    descending startedAt with no inversion. So this is latent on this instance
    today, not live. It still must not claim a protection it does not have,
    which is why it is computed on every read rather than asserted once.

    NF-D, CLOSED 2026-09-10. `True` used to be returned for a window where
    every pair was SKIPPED. Twenty executions all stamped with one instant have
    no order between any two of them, every pair hit the `continue` below,
    `inversions` stayed 0 and this returned True with the note "id order matches
    startedAt order across the 20 executions carrying both". That is a claim
    that a comparison passed when no comparison was made, in a function whose
    whole job is to say whether a comparison can be made. The vocabulary for
    "neither confirmed nor denied" already existed one branch up and was not
    used. `compared` counts the pairs that actually had an order, and zero of
    them lands in `None` with its own reason.
    """
    if len(paired) < 2:
        return None, (
            "fewer than two executions carry both an id and a startedAt, so id order cannot be "
            "compared with time order and monotonicity is neither confirmed nor denied here"
        ), 0
    inversions = 0
    compared = 0
    example: Optional[Tuple[Tuple[int, datetime], Tuple[int, datetime]]] = None
    # strict=False is deliberate: the two sequences differ in length by one by
    # construction, which is what makes them consecutive pairs.
    for earlier, later in zip(paired, paired[1:], strict=False):
        if later[1] == earlier[1]:
            continue
        compared += 1
        if later[0] < earlier[0]:
            inversions += 1
            if example is None:
                example = (earlier, later)
    if compared == 0:
        return None, (
            f"all {len(paired)} executions carrying both an id and a startedAt share one instant, "
            "so no two of them have an order between them. Id order is neither confirmed nor "
            "denied against time order here"
        ), 0
    if inversions and example is not None:
        first, second = example
        return False, (
            f"{inversions} execution(s) carry a smaller id than one that started earlier: id "
            f"{second[0]} started {_iso(second[1])}, after id {first[0]} at {_iso(first[1])}. "
            "An id gap is not a count of executions on this instance, so no rate is derived "
            "from one."
        ), inversions
    return True, (
        f"id order matches startedAt order across the {len(paired)} executions carrying both, over "
        f"the {compared} consecutive pairs that have an order between them, so the id gap is "
        "usable as a count over this window"
    ), 0


# ---------------------------------------------------------------------------
# THE ONE GATE ON THE ID DELTA METHOD
# ---------------------------------------------------------------------------

# The short form of a non-monotonic window, for the places that must SAY it
# rather than explain it. The 40 word note is rendered once, in the instance's
# own card; a panel that repeated it under the window, under the rate and again
# in the findings block drowned the findings block in one caveat.
ID_ORDER_SHORT = (
    "id order and startedAt order disagree over the window read, so no id gap is used as a count "
    "on this instance"
)


def id_delta_refusal(window: Dict[str, Any]) -> Optional[str]:
    """Why the id delta method may NOT be used on this window, or None.

    THIS IS THE ONLY PLACE THAT QUESTION IS ANSWERED, and it exists because
    answering it in each consumer separately is how one consumer got missed.

    `read_cap` computed the month to date spend as
    `anchor_spent + (newest_id - anchor_id)` and never consulted
    `id_order_matches_time` at all. Reproduced through the mounted route on
    2026-09-10 with rows 6669@12:00, 6666@14:00 and 6662@16:00: ONE payload
    reported `id_order_matches_time` False with 2 inversions, dropped
    `ids_in_span` and `not_saved_in_span` to null, refused the rate with the
    reason "An id gap is not a count of executions on this instance" AND
    reported cap state estimated, spent 1669 of 2500, 831 left, used_fraction
    0.6676. The panel drew a 67 percent burn bar an operator would act on, out
    of a gap the same column had just called unusable.

    Every id delta consumer routes through here now, and
    `test_no_consumer_reads_the_id_order_column_outside_the_gate` walks this
    file's syntax tree and fails if a new one reads the column directly.
    """
    if window.get("id_order_matches_time") is False:
        return str(window.get("id_order_note") or ID_ORDER_SHORT)
    return None


def measure_rate(window: Dict[str, Any]) -> Dict[str, Any]:
    """Executions a day across the window, by the id delta method.

    Unavailable is a first class answer here. A window with one row, a window
    inside one instant, a window whose ids do not parse, and a window whose ids
    contradict its clock all produce no rate and say why, because a rate
    invented from one of those feeds a projected date that reads like a
    measurement.

    Both halves of the ratio come from `rate_from_id`/`rate_to_id` and
    `rate_span_hours`, which `measure_window` takes from the SAME rows. That is
    the whole of the F1 fix: an id delta over one subset divided by a span over
    another is not a rate.
    """
    def unavailable(reason: str) -> Dict[str, Any]:
        return {"basis": "unavailable", "per_day": None, "reason": reason, "assumptions": []}

    # THE GATE. Same call as read_cap's, so the two cannot disagree about
    # whether an id gap means anything on this window. The SHORT form is used
    # here: the 40 word note is rendered once, in the instance's own card.
    if id_delta_refusal(window) is not None:
        return unavailable(ID_ORDER_SHORT)

    from_id, to_id = window.get("rate_from_id"), window.get("rate_to_id")
    span_hours = window.get("rate_span_hours")
    span_seconds = window.get("rate_span_seconds")

    if from_id is None or to_id is None:
        return unavailable(
            "no execution in the window carried both a numeric id and a readable startedAt, so "
            "there is no pair to measure a rate between"
        )
    executions_in_span = to_id - from_id
    # Checked before the span, because a one id window has no rate whatever its
    # timestamps say, and "one execution" is the reason a reader can act on.
    if executions_in_span <= 0:
        return unavailable("the window holds one execution, which is not a rate")
    if span_seconds is None:
        return unavailable("no execution in the window carried a readable startedAt")
    if span_seconds <= 0:
        return unavailable(
            "every execution in the window carries the same instant, so there is no span to divide by"
        )
    # The EXACT span, never the rounded one. See measure_window.
    per_day = executions_in_span / (span_seconds / 86400.0)
    if not math.isfinite(per_day) or per_day <= 0:
        return unavailable(
            f"the id delta {executions_in_span} over {span_seconds} seconds does not produce a "
            "finite positive rate"
        )
    dropped = int(window.get("executions_read") or 0) - int(window.get("dated_ids_read") or 0)
    return {
        "basis": "id_delta",
        "per_day": round(per_day, 2),
        "executions_in_span": executions_in_span,
        "span_hours": span_hours,
        "span_seconds": span_seconds,
        "from_id": from_id,
        "to_id": to_id,
        "from_moment": window.get("rate_from_moment"),
        "to_moment": window.get("rate_to_moment"),
        # The rows that widened the window a reader sees and took no part in
        # this number. Rendered by the panel, not just carried.
        "rows_outside_the_rate": dropped,
        "reason": None,
        "assumptions": [ID_DELTA_ASSUMPTION, WINDOW_ASSUMPTION],
    }


def read_cap(
    plan: Plan,
    window: Dict[str, Any],
    read_at: datetime,
) -> Dict[str, Any]:
    """The cap block: stated, estimated, or absent, and never invented.

    THE PROJECTION WAS CUT FROM THIS FUNCTION ON 2026-09-10, ON TEE'S RULING.

    This function used to end in a projected exhaustion date, a `days_left`, a
    five state projection machine, a staleness comparison against the read, a
    skew branch and a comparison between the projected wall and the stated
    cycle reset. All of it is gone, and the reason is worth writing down so
    nobody rebuilds it: the wall was the least valuable number on the panel and
    the most expensive one to be right about. It consumed three adversary
    cycles and failed two of them, and on this estate what ran and what failed
    is already covered by an n8n error workflow that mails Tee. The number that
    was genuinely missing is the burn against the cap, and that survives here.

    What survives with it, and why each one is not projection scaffolding:

    * `read_at`, still REQUIRED rather than defaulted. A configured cycle reset
      is still reported by this block and still reaches the screen, so it is
      still a date that has to be judged against the moment of the read. A cap
      block computed against an unstated clock is the class NF3 named, and that
      class outlives the projection that first exposed it.
    * `reset_in_the_past`, which is that judgement, and `reset_readable`, which
      is whether the configured value is a date at all. Both are statements
      about a CONFIGURED date this block still carries, not about a derived one.
      Deleting them would put an unreadable or long expired reset on the panel
      with nothing beside it.
    * `orphan_reset`, a reset configured with no cap, which is a configuration
      error whatever is or is not projected from it.

    `rate` is no longer a parameter. It was read for `per_day` alone, and
    `per_day` was only ever used to divide the remaining count into days. A
    parameter with no reader is coupling, so it is gone rather than ignored.

    Five answers, each with its own reason, because they mean different things
    to whoever is reading the panel mid cutover:

    * not_stated: nobody configured a cap for this instance. A self hosted
      instance has none, and this is the state it must land in. There is no
      default anywhere in this function.
    * unusable: a cap arrived that is not a ceiling, so nothing is derived from
      it and the number is not drawn as though it were one.
    * stated: a cap is configured, so a ceiling exists, but the spend against
      it has no source and remaining is unknown.
    * estimated: a cap and an anchor are both configured, so the spend can be
      carried forward from the anchor by the id delta.
    * inconsistent: the anchor and the instance disagree in a way that means
      the anchor names a different instance or a spent cycle.

    `reason` says why no spend was derived, and is None exactly when one was.
    It replaces the reason that used to travel inside the projection block, so
    the sentences the panel reads are not lost with the wall they sat under.
    """
    base: Dict[str, Any] = {
        "state": "not_stated",
        "source": None,
        "cap": None,
        "resets_at": plan.resets_at,
        "anchor": None,
        "spent_estimate": None,
        "spent_basis": None,
        "remaining_estimate": None,
        "used_fraction": None,
        "reason": "no cap is stated for this instance",
        "problems": list(plan.problems),
        "note": (
            "No cap is configured for this instance, so none is reported. A self hosted instance "
            "has no plan cap; a capped one gets its number from configuration, never from here."
        ),
        # A reset stated for a cap nobody stated. Carried as its own field so
        # the panel renders ONE coherent sentence rather than two contradictory
        # adjacent ones: "No cap is configured for this instance" immediately
        # followed by "The plan cycle is stated by configuration to reset
        # 2026-10-01" is a panel arguing with itself.
        "orphan_reset": None,
        # None when no reset is configured at all. False when one is configured
        # and is not a date, which used to be reported only inside the
        # projection's reset note and would otherwise have been printed to the
        # panel verbatim as though it were a cycle boundary.
        "reset_readable": None,
        "reset_in_the_past": None,
        "read_at": _iso(read_at),
        # The burn is derived, so it travels with what it rests on, exactly as
        # the wall used to. These are the two assumptions under a spend that is
        # an id gap carried forward from a number a human read off a usage page.
        "assumptions": [ID_DELTA_ASSUMPTION, CAP_ASSUMPTION],
        # The id the spend was carried forward to, and the moment that id's own
        # execution started. Both None until a spend is actually derived.
        "counted_from_id": None,
        "counted_from_moment": None,
    }
    if plan.resets_at:
        reset_moment = _parse_moment(plan.resets_at)
        base["reset_readable"] = reset_moment is not None
        if reset_moment is None:
            base["problems"] = list(base["problems"]) + [
                f"the configured cycle reset {plan.resets_at!r} could not be read as a date, so it "
                "is not shown and nothing is derived from it."
            ]
        else:
            base["reset_in_the_past"] = reset_moment <= read_at
    if plan.cap is None:
        if plan.resets_at:
            base["orphan_reset"] = (
                f"{plan.resets_at} is configured as the cycle reset for this instance while no cap "
                f"is configured at all. A cycle with no ceiling states nothing: either set the cap "
                f"or unset the reset."
            )
            base["problems"] = list(base["problems"]) + [str(base["orphan_reset"])]
        return base

    if plan.cap <= 0:
        # `read_plan` refuses a cap below 1 before it gets here, so this is the
        # path a hand built Plan takes. It is still a branch rather than an
        # assumption: a zero cap divided into a used fraction, and a negative
        # one drew a full red bar reading "-110 left".
        base["state"] = "unusable"
        base["cap"] = plan.cap
        base["source"] = "stated_by_configuration"
        base["problems"] = list(plan.problems) + [
            f"the stated cap is {plan.cap}, which is not a ceiling. Nothing is derived from it."
        ]
        base["reason"] = (
            f"the stated cap is {plan.cap}, so there is nothing to measure a burn against"
        )
        base["note"] = (
            "A cap arrived that is not a usable ceiling, so no spend, no remaining count and no "
            "bar are derived from it."
        )
        return base

    base["state"] = "stated"
    base["source"] = "stated_by_configuration"
    base["cap"] = plan.cap
    base["note"] = CAP_ASSUMPTION

    anchor_ready = plan.anchor_id is not None and plan.anchor_spent is not None
    if anchor_ready:
        base["anchor"] = {
            "id": plan.anchor_id,
            "spent": plan.anchor_spent,
            "at": plan.anchor_at,
            "source": "stated_by_configuration",
        }
    # THE GATE, and it is the same call measure_rate makes. The spend below is
    # an id delta, so it may only be taken when an id delta means something on
    # this window. Without this the panel drew a 67 percent burn bar out of the
    # very gap the rate column beside it had just refused. `newest_id` is not
    # read at all when the gate refuses, so there is no path from the refused
    # column to the arithmetic.
    #
    # This gate is the reason the cut stops where it does. The projection is
    # gone; the burn is not, and the burn is still an id delta, so the gate that
    # refuses an unusable delta is still guarding a live subject.
    refusal = id_delta_refusal(window)
    newest_id = None if refusal is not None else window.get("newest_id")
    if refusal is not None:
        base["problems"] = list(base["problems"]) + [
            "the spend against this cap is an execution id gap, and " + ID_ORDER_SHORT
            + ". No spend, no remaining count and no burn bar are derived."
        ]
        base["reason"] = (
            "the cap is stated, but the only method for the spend against it is the execution id "
            f"gap and this window's ids contradict its clock. {refusal}"
        )
        return base
    if not anchor_ready:
        base["reason"] = (
            "the cap is stated but the spend against it has no source. Set the anchor id and "
            "anchor spend from the provider's usage page to carry the spend forward."
        )
        return base
    if newest_id is None:
        base["reason"] = "no execution was read, so there is no id to carry the anchor forward to"
        return base
    if newest_id < plan.anchor_id:
        base["state"] = "inconsistent"
        base["reason"] = (
            f"the newest id read is {newest_id}, below the configured anchor id "
            f"{plan.anchor_id}. The anchor names a different instance or an older cycle."
        )
        return base

    spent = plan.anchor_spent + (newest_id - plan.anchor_id)
    remaining = plan.cap - spent
    base["state"] = "estimated"
    base["spent_estimate"] = spent
    base["spent_basis"] = "anchor_plus_id_delta"
    base["remaining_estimate"] = remaining
    base["used_fraction"] = round(min(1.0, max(0.0, spent / plan.cap)), 4)
    base["reason"] = None
    # The id and the moment the spend was carried forward to, on the payload
    # rather than only inside a projection's basis block. They are the basis of
    # the burn, the burn is what survives the cut, so they travel with it.
    base["counted_from_id"] = newest_id
    base["counted_from_moment"] = window.get("newest_id_started_at")
    return base


# ---------------------------------------------------------------------------
# one instance, end to end
# ---------------------------------------------------------------------------

def _blank(config: InstanceConfig, state: str, reason: str, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "role": config.role,
        "state": state,
        "reason": reason,
        "configured_host": None,
        "host": None,
        "status_code": None,
        "variables": {"url": config.url_var, "key": config.key_var, "cap": config.cap_var},
        "window": None,
        "counts": None,
        "status_counts": None,
        "recent": [],
        "rate": None,
        "cap": None,
        "read_problems": [],
    }
    payload.update(extra)
    return payload


def _cursor_of(page: Dict[str, Any]) -> Optional[str]:
    """The next cursor, wherever this instance's envelope happens to keep it.

    UNSETTLED as of 2026-09-10: the shape measurement went through a connector
    that may normalise, so whether the raw endpoint answers a top level
    `nextCursor`, a nested one, or no cursor at all was NOT confirmed. All the
    forms are accepted here and none of them is load bearing, because the walk
    below terminates on rows consumed rather than on any of them.
    """
    for holder in (page, page.get("meta"), page.get("pagination")):
        if not isinstance(holder, dict):
            continue
        for name in ("nextCursor", "next_cursor", "nextPageToken"):
            value = holder.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _page_shape(payload: Any) -> Tuple[Optional[List[Any]], Optional[str], Optional[str]]:
    """(entries, cursor, problem). Tolerant of both envelopes, dependent on none.

    A bare list and a `{"data": [...]}` object are both read. Anything else is
    the `malformed` state rather than an empty one, which is the difference
    between a proxy answering with a login page and an instance with nothing
    saved.
    """
    if isinstance(payload, list):
        return payload, None, None
    if not isinstance(payload, dict):
        return None, None, "the instance answered without a data list"
    entries = payload.get("data")
    if entries is None and isinstance(payload.get("results"), list):
        entries = payload.get("results")
    if not isinstance(entries, list):
        return None, None, "the instance answered without a data list"
    return entries, _cursor_of(payload), None


def _identity(row: Dict[str, Any]) -> Tuple[Any, ...]:
    """What makes two returned rows the same execution.

    The id when there is one, and otherwise the shape of the row that would
    have to be identical for it to be the same run. Deduping matters because a
    cursor that repeats used to be walked to the row limit: ten real executions
    were reported as `executions_read` 500.
    """
    parsed = _row_id(row.get("id"))
    if parsed is not None:
        return ("id", parsed)
    return (
        "row",
        repr(row.get("id")),
        repr(row.get("startedAt")),
        repr(row.get("stoppedAt")),
        repr(row.get("workflowId")),
        repr(row.get("status")),
    )


async def _read_pages(
    base: str, key: str, limit: int, fetch: Fetcher
) -> Tuple[List[Dict[str, Any]], bool, str, Optional[int], Optional[str], List[str]]:
    """Walk executions newest first up to `limit`.

    Returns (rows, truncated, final_url, refused_status, refused_detail,
    problems). A refusal on the first page is returned rather than raised so
    the caller can report the status code the instance actually gave: a 401 on
    a rotated key and a 404 on a wrong base are different repairs.

    THE LOOP TERMINATES ON WORK DONE, NOT ON A TRUTHY LIST

    The version of this that shipped exited on `not data`, the truthiness of
    the list, rather than on whether any row in it was consumed. Handed
    `{"data": ["not-a-dict", 7, None], "nextCursor": "same"}` it made 2000
    requests to one identical URL and was still going: one panel load hanging
    an API worker and flooding the instance. Three separate conditions stop it
    now, and each one is reported rather than silently absorbed:

    * a page from which no NEW execution was taken,
    * a cursor this walk has already followed,
    * `MAX_PAGES`, as the backstop for a shape neither of those catches.
    """
    rows: List[Dict[str, Any]] = []
    seen_rows: Set[Tuple[Any, ...]] = set()
    seen_cursors: Set[str] = set()
    problems: List[str] = []
    cursor: Optional[str] = None
    final_url = base
    pages = 0

    while len(rows) < limit:
        if pages >= MAX_PAGES:
            problems.append(
                f"the walk stopped at the {MAX_PAGES} page ceiling with the row limit not reached. "
                "The window below is what was walked, not the whole saved history."
            )
            return rows, True, final_url, None, None, problems
        want = min(PAGE_SIZE, limit - len(rows))
        url = _executions_url(base, want, cursor)
        answer = await fetch(url, {"X-N8N-API-KEY": key, "Accept": "application/json"})
        pages += 1
        final_url = answer.final_url or url
        if answer.status < 200 or answer.status >= 300:
            detail = ""
            if isinstance(answer.payload, dict):
                detail = str(answer.payload.get("message") or "")[:200]
            return rows, False, final_url, answer.status, detail or None, problems
        entries, next_cursor, problem = _page_shape(answer.payload)
        if problem or entries is None:
            return rows, False, final_url, None, problem or "the instance answered without a data list", problems

        added = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            identity = _identity(entry)
            if identity in seen_rows:
                continue
            seen_rows.add(identity)
            rows.append(entry)
            added += 1

        if added == 0:
            if entries:
                problems.append(
                    f"a page answered with {len(entries)} entr(ies) and none of them was an "
                    "execution this walk had not already read. The walk stopped rather than "
                    "asking the same question again."
                )
            # No new work came back, so following the cursor asks the same
            # question. `truncated` stays false: what is below is everything
            # this walk could obtain, not a window cut off at the limit.
            return rows, False, final_url, None, None, problems

        if not next_cursor:
            # No further page exists, so the window is the whole saved history
            # the key can see. `truncated` stays false and the panel may say the
            # window is complete rather than cut off at the limit.
            return rows, False, final_url, None, None, problems
        if next_cursor in seen_cursors:
            problems.append(
                "the instance returned a pagination cursor this walk had already followed, so the "
                "walk stopped rather than looping on it. Older executions may be outside the "
                "window below."
            )
            return rows, True, final_url, None, None, problems
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    # The loop only ends here by reaching the limit with a cursor still in hand.
    return rows, cursor is not None, final_url, None, None, problems


async def read_instance(
    config: InstanceConfig,
    limit: int = DEFAULT_LIMIT,
    fetch: Optional[Fetcher] = None,
    environ: Optional[Dict[str, str]] = None,
    read_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Telemetry for one instance, or the honest reason there is none.

    Seven states, counted from the returns below and from `read_all` and not
    from memory: unconfigured, misconfigured, unreachable, refused, malformed,
    ok, and the `errored` one `read_all` produces when reading this instance
    raised. They are deliberately distinct. `unconfigured` and `ok` with an
    empty window are the pair most worth keeping apart: an instance nobody
    pointed at and an instance with nothing to report look identical on a panel
    that collapses them, and during a cutover the second is the answer to
    "is the target doing what the source is doing yet".

    `read_at` defaults to now for a caller that reads one instance on its own.
    `read_all` passes the SAME instant to both, so the two columns are judged
    against one clock and the payload's own `read_at` is that clock.
    """
    moment = read_at or datetime.now(timezone.utc)
    url = _env(config.url_var, environ)
    key = _env(config.key_var, environ)
    if not url and not key:
        return _blank(
            config,
            "unconfigured",
            f"{config.url_var} and {config.key_var} are both unset, so this instance is not read.",
        )
    if not url or not key:
        missing = config.url_var if not url else config.key_var
        return _blank(
            config,
            "misconfigured",
            f"{missing} is unset while the other half is set. Nothing is read on half a configuration.",
            configured_host=urlparse(url).hostname if url else None,
        )
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return _blank(
            config,
            "misconfigured",
            f"{config.url_var} is not an http or https URL with a host, so no request is attempted.",
        )

    fetcher = fetch or _httpx_get
    bounded = max(1, min(int(limit), MAX_LIMIT))
    try:
        raw, truncated, final_url, refused, detail, problems = await _read_pages(
            url, key, bounded, fetcher
        )
    except Unreachable as exc:
        return _blank(
            config,
            "unreachable",
            f"{parsed.hostname} was not reached: {exc}",
            configured_host=parsed.hostname,
        )

    reached_host = urlparse(final_url).hostname or parsed.hostname
    if refused is not None:
        return _blank(
            config,
            "refused",
            f"{reached_host} answered HTTP {refused}"
            + (f": {detail}" if detail else ". The instance is up and declined the read."),
            configured_host=parsed.hostname,
            host=reached_host,
            status_code=refused,
            read_problems=problems,
        )
    if detail:
        # Reached, answered 2xx, and the body was not the shape the executions
        # endpoint returns. That is its own repair (wrong base path, a proxy
        # answering with an HTML login page) and must not read as empty.
        return _blank(
            config,
            "malformed",
            f"{reached_host} answered 2xx but {detail}.",
            configured_host=parsed.hostname,
            host=reached_host,
            status_code=200,
            read_problems=problems,
        )

    rows = [read_row(row) for row in raw]
    window = measure_window(rows, truncated)
    buckets, raw_counts = count_statuses(rows)
    rate = measure_rate(window)
    cap = read_cap(read_plan(config, environ), window, moment)
    return {
        "role": config.role,
        "state": "ok",
        "reason": (
            f"{reached_host} answered with no saved executions. This is an answered read, not a "
            "failed one, and not a claim that nothing ran."
            if not rows
            else None
        ),
        "configured_host": parsed.hostname,
        "host": reached_host,
        "status_code": 200,
        "variables": {"url": config.url_var, "key": config.key_var, "cap": config.cap_var},
        "window": window,
        "counts": buckets,
        "status_counts": raw_counts,
        "recent": rows[:20],
        "rate": rate,
        "cap": cap,
        "read_problems": problems,
    }


def cross_findings(instances: List[Dict[str, Any]]) -> List[str]:
    """Things only visible with both readings side by side.

    The one that matters is two configured instances resolving to the same
    host. A secondary URL left pointing at the source is the quietest possible
    failure during a cutover: the panel shows two columns of matching numbers
    and reads as a target that has caught up.
    """
    findings: List[str] = []
    reached = [i for i in instances if i.get("host")]
    hosts: Dict[str, List[str]] = {}
    for instance in reached:
        hosts.setdefault(str(instance["host"]), []).append(str(instance["role"]))
    for host, roles in sorted(hosts.items()):
        if len(roles) > 1:
            findings.append(
                f"{' and '.join(sorted(roles))} both reached {host}. That is one instance read twice, "
                "not two instances, so any agreement between the columns proves nothing."
            )
    for instance in instances:
        cap = instance.get("cap") or {}
        for problem in cap.get("problems") or []:
            findings.append(f"{instance['role']}: {problem}")
        for problem in instance.get("read_problems") or []:
            findings.append(f"{instance['role']}: {problem}")
        window = instance.get("window") or {}
        # THE GATE again, and the SHORT form. The panel renders this list in a
        # red block above the cards; putting the 40 word note here as well as
        # under the window and again under the rate meant a two instance panel
        # carried the same paragraph six times and the findings block stopped
        # reading as findings. The full note is rendered once, on the card.
        if id_delta_refusal(window) is not None:
            findings.append(
                f"{instance['role']}: {ID_ORDER_SHORT}. The instance card carries which executions "
                "and by how much."
            )
    return findings


async def read_all(
    limit: int = DEFAULT_LIMIT,
    fetch: Optional[Fetcher] = None,
    environ: Optional[Dict[str, str]] = None,
    read_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Every configured instance, reported separately, never merged.

    Nothing here averages the two or falls back from one to the other. A
    cutover question is always about a specific instance, and a merged total
    would answer a question nobody asked.

    The loop is a loop rather than the comprehension it was, and each instance
    is read inside its own try. A single comprehension meant that one
    instance's OverflowError raised out of the whole call and BOTH columns went
    blank: a healthy primary lost because a secondary's cap arithmetic
    overflowed. The `except` is deliberately broad for the same reason
    `_httpx_get`'s is. Naming a subset here would let the next failure class
    take the healthy instance down with it, which is the exact behaviour being
    fixed. CancelledError is a BaseException in 3.11 and is not caught.
    """
    # ONE instant for the whole read, taken before any instance is walked, and
    # it is the instant the payload reports as `read_at`. Every date comparison
    # on this payload is made against this and no other, so a reader repeating
    # the comparison gets the same answer this service got.
    # `read_at` is injectable for the same reason `fetch` and `environ` are:
    # every date comparison on this payload is made against it, so a test that
    # cannot pin it is a test whose answer changes with the calendar. Production
    # passes nothing and gets now.
    moment = read_at or datetime.now(timezone.utc)
    instances: List[Dict[str, Any]] = []
    for config in INSTANCES:
        try:
            instances.append(
                await read_instance(
                    config, limit=limit, fetch=fetch, environ=environ, read_at=moment
                )
            )
        except Exception as exc:
            instances.append(
                _blank(
                    config,
                    "errored",
                    f"reading this instance raised {type(exc).__name__}: {str(exc)[:200]}. It is "
                    "reported as its own failure so the other instance is still readable. Nothing "
                    "below this instance is a measurement.",
                )
            )
    return {
        "read_only": True,
        "read_at": _iso(moment),
        "limit": max(1, min(int(limit), MAX_LIMIT)),
        "instances": instances,
        "configured": sum(1 for i in instances if i["state"] != "unconfigured"),
        "reachable": sum(1 for i in instances if i["state"] == "ok"),
        "findings": cross_findings(instances),
        "note": (
            "Read only telemetry. This surface cannot trigger, retry, delete or resume an "
            "execution: no route here accepts a method other than GET, and the client under it "
            "speaks no verb but GET."
        ),
    }
