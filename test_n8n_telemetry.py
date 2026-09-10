"""app/services/n8n_telemetry.py and the route over it: read only, and honest.

No network and no database. Every instance is driven by a fake fetcher, so the
states that matter most and are hardest to reach live (unreachable, a rotated
key, a secondary pointed at the source by mistake) are the ones exercised
hardest.

Five of these are guards on structure rather than on behaviour, and each was
written to be able to fail:

* the router's live route table carries no verb but GET and HEAD
* the running application answers 405 to POST, PUT, PATCH and DELETE
* neither new module contains a mutating HTTP call or a mutating decorator
* neither new module contains a URL literal or a live n8n host
* neither new module can reach a socket except through `_httpx_get`

The load bearing one is not any of those. It is
`test_nothing_configured_never_reaches_the_network`: the fake fetcher raises if
it is called at all, so a default URL added anywhere in the module turns that
test red. A default URL is the failure the whole design is shaped against,
because an unconfigured instance that quietly reads a real host is exactly the
"quietly reassuring" reading this panel exists to refuse.
"""

from __future__ import annotations

import ast
import inspect
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import pytest

from app.api.v1 import n8n_executions as route_module
from app.services import n8n_telemetry as tel

PRIMARY_HOST = "primary.invalid"
SECONDARY_HOST = "secondary.invalid"
PRIMARY_KEY = "primary-key-not-a-real-one"
SECONDARY_KEY = "secondary-key-not-a-real-one"

REPO = pathlib.Path(__file__).resolve().parent
SERVICE_FILE = REPO / "app" / "services" / "n8n_telemetry.py"
ROUTE_FILE = REPO / "app" / "api" / "v1" / "n8n_executions.py"


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------

def _row(
    execution_id: Any,
    status: Optional[str],
    started: str,
    stopped: Optional[str] = None,
    workflow: str = "wf1",
    name: str = "Driver Poll",
    mode: str = "trigger",
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "id": execution_id,
        "startedAt": started,
        "workflowId": workflow,
        "workflowData": {"name": name},
        "mode": mode,
    }
    if status is not None:
        row["status"] = status
    if stopped is not None:
        row["stoppedAt"] = stopped
    return row


# One window, reused, with every number in it worked out by hand in the tests
# that assert on it. ids 6292..6412 over exactly 24 hours.
WINDOW_ROWS = [
    _row(6412, "success", "2026-09-10T12:00:00.000Z", "2026-09-10T12:00:03.500Z"),
    _row(6400, "error", "2026-09-10T06:00:00.000Z", "2026-09-10T06:00:01.000Z"),
    _row(6350, "crashed", "2026-09-10T00:00:00.000Z", "2026-09-10T00:00:02.000Z"),
    _row(6300, None, "2026-09-09T18:00:00.000Z"),
    _row(6292, "waiting", "2026-09-09T12:00:00.000Z"),
]


# The moment a read is taken at, for every test that calls `read_cap` directly.
# One hour after WINDOW_ROWS' newest execution. It is still pinned after the
# projection was cut, because the configured cycle reset is still compared with
# it and the cap block still records which clock it was judged against.
_NOW = datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)


class Fake:
    """A fetcher standing in for one or more instances, keyed by host.

    A handler is either a list of pages (walked in order), an `Unreachable` to
    raise, or a `Fetched` to answer with.
    """

    def __init__(self, **handlers: Any) -> None:
        self.handlers = handlers
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, url: str, headers: Dict[str, str]) -> tel.Fetched:
        self.calls.append({"url": url, "headers": dict(headers)})
        host = urlparse(url).hostname or ""
        handler = self.handlers.get(host.replace(".", "_"))
        if handler is None:
            raise AssertionError(f"the fake was asked for {host!r}, which no test configured")
        if isinstance(handler, tel.Unreachable):
            raise handler
        if isinstance(handler, tel.Fetched):
            return handler
        pages: List[Dict[str, Any]] = list(handler)
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        index = 0 if cursor is None else int(cursor)
        return tel.Fetched(200, pages[index], url)


class Refuse:
    """A fetcher that must never be called. Any call is the failure."""

    def __init__(self) -> None:
        self.calls: List[str] = []

    async def __call__(self, url: str, headers: Dict[str, str]) -> tel.Fetched:
        self.calls.append(url)
        raise AssertionError(
            f"a request was made to {url!r} with nothing configured. Something in the module "
            "carries a default URL, which is the one thing it must never do."
        )


def _page(rows: List[Dict[str, Any]], cursor: Optional[str] = None) -> Dict[str, Any]:
    return {"data": rows, "nextCursor": cursor}


def _env(**over: str) -> Dict[str, str]:
    base = {
        "N8N_API_URL": f"https://{PRIMARY_HOST}",
        "N8N_API_KEY": PRIMARY_KEY,
    }
    base.update(over)
    return base


def _only(payload: Dict[str, Any], role: str) -> Dict[str, Any]:
    for instance in payload["instances"]:
        if instance["role"] == role:
            return instance
    raise AssertionError(f"no {role} instance in the payload")


# ---------------------------------------------------------------------------
# structure: the surface cannot mutate anything
# ---------------------------------------------------------------------------

def test_route_table_carries_no_verb_but_get() -> None:
    """The live route table, not the prose above it.

    FastAPI derives HEAD from GET, so both are allowed and nothing else is. A
    `@router.post` added to the module puts POST in this set and fails here.
    """
    seen = set()
    for route in route_module.router.routes:
        seen.update(getattr(route, "methods", set()) or set())
    assert seen, "the router registered no routes at all, so this guard proves nothing"
    assert seen <= {"GET", "HEAD"}, f"a mutating verb reached the n8n router: {sorted(seen)}"
    paths = sorted(getattr(route, "path", "") for route in route_module.router.routes)
    assert paths == ["/n8n/executions"], f"the read only surface grew a route: {paths}"


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


_MUTATING_VERBS = {"post", "put", "patch", "delete"}

# Callables that take the HTTP verb as data rather than as their own name. This
# set is the whole of the hardening: the walk used to look only at the callee's
# NAME, so `client.request("DELETE", url)` and
# `client.send(httpx.Request("POST", url))` sat inside the production fetcher
# and the suite returned 41 passed. Two live mutating verbs, fully green.
_VERB_CARRYING_CALLABLES = {
    # httpx and requests generic dispatchers
    "request",
    "send",
    "stream",
    "build_request",
    "Request",
    # FastAPI and Starlette route registration that bypasses the decorator
    "add_api_route",
    "api_route",
    "add_route",
    "route",
    "add_websocket_route",
    "APIRoute",
    "Route",
    # the ways an attribute name can be assembled at runtime
    "getattr",
    "setattr",
    # The dunders behind them. `setattr` was listed and `__setattr__` was not,
    # so `object.__setattr__(request, "method", "POST")` put a live POST on the
    # wire on 2026-09-10 with this suite at 185 passed. An allowlist is only as
    # good as the author's imagination, which is why the runtime guard below
    # exists; these are here so the cheap walk catches the cheap spelling.
    "__setattr__",
    "__getattr__",
    "__getattribute__",
    "update",
    "__setstate__",
    "partial",
    "methodcaller",
    "attrgetter",
}


def _folded_strings(node: ast.AST) -> List[str]:
    """Every string this expression can evaluate to, with concatenation folded.

    `"po" + "st"` beats a name based walk and beats a grep. Folding it here is
    what makes the check about the verb rather than about how it was spelled.
    Lists and tuples are walked because `methods=["POST"]` is where a route
    registration keeps its verb. DICTS are walked because an adversary on
    2026-09-10 wrote `client.request(**{"method": "DELETE", "url": url})` and
    this function returned nothing: the verb was spelled in full, at a callee
    this walk explicitly tracks, and was invisible because the container was a
    dict. That is the whole lesson of enumerating containers, so keys are
    folded as well as values, and a `**` splat arrives as a keyword whose value
    is the dict.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return [
            left + right
            for left in _folded_strings(node.left)
            for right in _folded_strings(node.right)
        ]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        found: List[str] = []
        for element in node.elts:
            found.extend(_folded_strings(element))
        return found
    if isinstance(node, ast.Dict):
        found = []
        for key, value in zip(node.keys, node.values, strict=False):
            if key is not None:
                found.extend(_folded_strings(key))
            found.extend(_folded_strings(value))
        return found
    if isinstance(node, ast.JoinedStr):
        literal = "".join(
            part.value
            for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
        return [literal] if literal else []
    return []


def _callee_name(func: ast.AST) -> Optional[str]:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _mutating_verb_offences(tree: ast.AST) -> List[str]:
    """Every reach for a mutating HTTP verb in this syntax tree.

    Four forms, because the name based version of this walk was beaten by the
    second and third while reporting green, and the fourth beat all of those:

    1. an attribute or call NAMED for the verb: `client.post(...)`,
       `@router.delete(...)`, or the bare attribute `client.patch`.
    2. a generic dispatcher handed the verb as DATA: `client.request("DELETE",
       url)`, `client.send(httpx.Request("POST", url))`,
       `router.add_api_route(..., methods=["POST"])`, `getattr(client, "po" +
       "st")`.
    3. either of those with the verb assembled from pieces.

    `test_the_mutating_verb_detector_catches_the_ways_around_it` feeds this
    function each of those forms as source and fails if any goes unseen, and
    `..._does_not_fire_on_a_read` feeds it the read shape and fails if it does.
    A guard nobody has watched fire is not a guarantee.
    """
    offences: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.lower() in _MUTATING_VERBS:
            offences.append(f"attribute {node.attr} at line {node.lineno}")
        # 5. THE VERB AS OBJECT STATE. Added 2026-09-10 after an adversary put a
        # live POST into the module's only fetcher and this suite reported 183
        # passed. Its bypass was three lines:
        #
        #     request = httpx.Request("GET", url, headers=headers)
        #     request.method = "POST"
        #     response = await client.send(request)
        #
        # Every rule above reasons about a CALL: the callee's own name, or a
        # string folded out of its arguments. This one puts the verb nowhere
        # near a call site. `httpx.Request.__init__` stores `self.method` as a
        # plain str and the transport reads it at send time, so the wire really
        # carries POST; the adversary proved that against a capture server
        # rather than by reading the library. Of the three tracked sites,
        # `Request("GET", ...)` folds to GET, `.method` is not a verb name, and
        # `send(request)` carries a Name that folds to nothing.
        #
        # Closed two ways on purpose. Closing only the literal would leave
        # `request.method = _v` open and the next tick would find it in
        # seconds, so (b) refuses the SHAPE, which is the same answer rule 4
        # gave for the same reason.
        #
        #   (a) BY VALUE: an assignment whose value folds to EXACTLY a verb.
        #       Exactly, not by substring, because the read shape control
        #       assigns "this route cannot trigger, retry, delete or resume an
        #       execution" and that sentence must stay legal.
        #   (b) BY SHAPE: an assignment targeting `.method`, or a subscript
        #       whose key folds to "method", whatever the value. Measured
        #       before it was chosen: neither guarded file assigns `.method`
        #       anywhere, while plain subscript assignment appears 38 times in
        #       the service alone, which is why the key is read rather than the
        #       shape of the target alone.
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            written = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in written:
                if isinstance(target, ast.Attribute) and target.attr.lower() == "method":
                    offences.append(
                        f"assignment to .method at line {node.lineno} sets an HTTP "
                        "verb as object state. Refused by shape whatever the value, "
                        "because a verb reached this way sits at no call site"
                    )
                elif isinstance(target, ast.Subscript):
                    for key in _folded_strings(target.slice):
                        if key.strip().lower() == "method":
                            offences.append(
                                f'assignment to ["method"] at line {node.lineno} '
                                "sets an HTTP verb as object state"
                            )
            if node.value is not None:
                for text in _folded_strings(node.value):
                    if text.strip().lower() in _MUTATING_VERBS:
                        offences.append(
                            f"assignment of {text!r} at line {node.lineno} puts a "
                            "mutating verb into a name, and no later call site has "
                            "to spell it"
                        )
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node.func)
        if name is None:
            continue
        if name.lower() in _MUTATING_VERBS:
            offences.append(f"call {name} at line {node.lineno}")
            continue
        if name not in _VERB_CARRYING_CALLABLES:
            continue
        # 4. THE VERB THE WALK CANNOT READ AT ALL. Added 2026-09-10 after an
        # adversary put a live DELETE into the module's only fetcher and this
        # guard reported 181 passed. Its bypass was two lines:
        #
        #     _verb = "de" + "lete"
        #     response = await getattr(client, _verb)(url, headers=headers)
        #
        # Folding the strings cannot see it, because the string is not at the
        # call site: it is in a name. NO analysis of the argument's VALUE can
        # close that, so this closes the SHAPE instead. A dynamic verb handed to
        # a dispatcher is refused whether or not this walk can work out what it
        # says, which makes the module docstring's claim ("a comment saying read
        # only is not a guarantee; an absent verb is") true again.
        #
        # The cost is real and accepted: a legitimate dynamic dispatch in these
        # two files would now have to be written as an explicit literal. Both
        # files speak exactly one verb, so that cost is zero today.
        if name == "getattr":
            resolvable = node.args[1:2] and _folded_strings(node.args[1])
            if not resolvable:
                offences.append(
                    f"getattr(...) at line {node.lineno} reaches for a verb this "
                    "walk cannot read. A dynamic verb handed to a client is "
                    "refused by shape, because no value analysis can see one "
                    "assembled in a variable"
                )
                continue
        carried: List[str] = []
        for argument in list(node.args) + [keyword.value for keyword in node.keywords]:
            carried.extend(_folded_strings(argument))
        for text in carried:
            if text.strip().lower() in _MUTATING_VERBS:
                offences.append(f"{name}(...{text!r}...) at line {node.lineno}")
    return offences


@pytest.mark.parametrize("path", [SERVICE_FILE, ROUTE_FILE])
def test_no_mutating_call_or_decorator_in_the_source(path: pathlib.Path) -> None:
    """Parsed, not grepped, and not name based either.

    A text search for "post" hits the word in a comment and misses
    `getattr(client, "po" + "st")`. A NAME based syntax walk misses
    `client.request("DELETE", url)`, which is what this guard used to be and
    why the adversary got two live mutating verbs past it while it reported
    green. `_mutating_verb_offences` is the detector, and it is itself under
    test in both directions below.
    """
    offences = _mutating_verb_offences(_tree(path))
    assert not offences, f"{path.name} reaches for a mutating verb: {offences}"


# Each of these was executed against the shipped modules and each one is a way
# a mutating verb reached production code while the suite stayed green. The
# first three are the adversary's, verbatim.
_BYPASSES = {
    "a generic dispatcher taking the verb as a string": 'await client.request("DELETE", url)',
    "a prebuilt request object handed to send": 'await client.send(httpx.Request("POST", url))',
    "a route registered through the table rather than a decorator": (
        'router.add_api_route("/executions/retry", handler, methods=["POST"])'
    ),
    "a verb assembled from pieces": 'getattr(client, "po" + "st")(url)',
    "a lower case verb string in a methods list": 'router.add_api_route("/x", h, methods=["delete"])',
    "the plain attribute call the old walk did catch": "await client.delete(url)",
    "the decorator the old walk did catch": "@router.post('/x')\ndef handler():\n    return None",
    "a bare attribute reference with no call": "verb = client.patch",
    # The adversary's 2026-09-10 bypass, verbatim. It put a live DELETE into the
    # production fetcher and this suite reported 181 passed.
    "a verb assembled in a variable and handed to getattr": (
        '_verb = "de" + "lete"\nresponse = await getattr(client, _verb)(url, headers=headers)'
    ),
    "a verb read off a mapping and handed to getattr": (
        'response = await getattr(client, VERBS["write"])(url)'
    ),
    # The adversary's second 2026-09-10 bypass, verbatim. It put a live POST
    # into the production fetcher and this suite reported 183 passed. Proved on
    # the wire against a local capture server, which logged POST, rather than by
    # reading httpx's source.
    "the verb set as object state on a request that is then sent": (
        'request = httpx.Request("GET", url, headers=headers)\n'
        'request.method = "POST"\n'
        "response = await client.send(request)"
    ),
    # The same shape with the verb in a name, which a value analysis cannot see.
    # This is what rule 5(b) exists for.
    "the verb set as object state from a name": (
        '_v = VERBS["write"]\nrequest.method = _v\n'
        "response = await client.send(request)"
    ),
    # The 2026-09-10 tick two bypasses, verbatim. Both were carried to a real
    # socket, not argued: a raw capture server logged the request line. The
    # first is the worst of the set, because the verb is spelled in full at a
    # callee this walk explicitly tracks and was still invisible; the container
    # was a dict and `_folded_strings` had no dict branch.
    "the verb splatted into a tracked dispatcher from a dict": (
        'await client.request(**{"method": "DELETE", "url": url, "headers": headers})'
    ),
    "the verb set through the dunder rather than the builtin": (
        'request = client.build_request("GET", url, headers=headers)\n'
        'object.__setattr__(request, "method", "POST")\n'
        "response = await client.send(request)"
    ),
    "the same dunder bound on the instance": 'request.__setattr__("method", "POST")',
    # Not a verb at all on the wire. The server is told to treat the GET as a
    # write, so the method stays honest and the effect does not.
    "a method override header carried in a dict": (
        '_h = {"X-HTTP-Method-Override": "DELETE"}\n'
        "response = await client.get(url, headers=_h)"
    ),
}


@pytest.mark.parametrize("label, source", sorted(_BYPASSES.items()))
def test_the_mutating_verb_detector_catches_the_ways_around_it(label: str, source: str) -> None:
    offences = _mutating_verb_offences(ast.parse(source))
    assert offences, (
        f"the detector did not see {label}. That is the shape that reached the production "
        f"fetcher and returned 41 passed: {source!r}"
    )


# ---------------------------------------------------------------------------
# THE SECOND DOOR
#
# Every rule above, and the transport check below, asks about A VERB. On
# 2026-09-10 an adversary stopped arguing about verbs and appended a second
# egress path to the service instead:
#
#     import urllib.request
#     outbound = urllib.request.Request(endpoint, data=b"{}", headers={...})
#     answer = urllib.request.urlopen(outbound, timeout=TIMEOUT_SECONDS)
#
# A capture server logged `POST /api/v1/executions/6679/retry` carrying the API
# key. `_mutating_verb_offences` returned [] and the suite returned 191 passed.
#
# Both layers missed it for the same reason, and neither reason is a missing
# location in a list:
#
# * the syntax walk assumes the verb exists as a token somewhere. `urllib`
#   promotes GET to POST purely because `data=` is not None, so the verb is a
#   runtime property of body presence and is spelled nowhere at all.
# * the transport check drives `tel._httpx_get` and patches `httpx.AsyncClient`.
#   `urllib.request.urlopen` never touches httpx, so the recorder saw nothing
#   and its silence read as a pass.
#
# That is the honest limit of the check below: it audits ONE FUNCTION, not the
# module's egress surface. Its coverage claim is only worth the separate claim
# that no other code path in these two files can reach a socket, and nothing
# was making that claim. This section makes it, structurally:
#
#   1. an IMPORT ALLOWLIST of exact dotted module names, measured off the two
#      files on 2026-09-10 rather than imagined. `urllib.parse` is on it twice
#      over (`urlparse` at line 130, `quote` at line 381) because it is pure
#      string work; `urllib.request` is a different module and is not.
#   2. a BANLIST that the allowlist cannot relax. A one word edit widening the
#      allowlist to `urllib.request` still fails here, which is the difference
#      between a rule and a speed bump.
#   3. CONTAINMENT: `httpx` may be imported only inside `_httpx_get`. That is
#      what turns "the audited function is read only" into "the module is read
#      only", because it makes the audited function the only door.
#   4. a refusal of DYNAMIC CODE by shape: `__import__`, `eval`, `exec`,
#      `compile`, and the process spawning members of `os`. An import walk that
#      can be defeated by `__import__("urllib.request")` is not a walk.
#
# The cost is real and stated: a new import in either file fails this test until
# somebody adds it to the allowlist deliberately. Both files import eleven
# modules between them and speak one verb, so that cost is a few seconds on the
# rare occasion, against a door that stayed open through three hardening passes.
# ---------------------------------------------------------------------------

#: The exact dotted module names these two files import, measured with an AST
#: walk on 2026-09-10 (service: math, os, dataclasses, datetime, typing,
#: urllib.parse, httpx; route: typing, fastapi, app.security.deps,
#: app.services). `httpx` is deliberately absent: it is governed by the
#: containment rule below rather than by membership here.
_ALLOWED_IMPORTS = {
    "__future__",
    "math",
    "os",
    "dataclasses",
    "datetime",
    "typing",
    "urllib.parse",
    "fastapi",
    "app.security.deps",
    "app.services",
}

#: Modules whose presence in either file is refused whatever the allowlist says.
#: Every one of them can open a socket or run code that does, and none of them
#: has a string only use the way `urllib.parse` does. Matched by dotted prefix,
#: so `urllib.request.urlopen` is caught through `import urllib.request` and
#: through `from urllib import request` alike.
_NETWORK_CAPABLE_MODULES = (
    "urllib.request",
    "socket",
    "ssl",
    "http.client",
    "http.server",
    "requests",
    "aiohttp",
    "httplib2",
    "urllib3",
    "pycurl",
    "ftplib",
    "smtplib",
    "imaplib",
    "poplib",
    "nntplib",
    "telnetlib",
    "xmlrpc",
    "websocket",
    "websockets",
    "subprocess",
    "ctypes",
    "importlib",
)

#: The only function permitted to import httpx, and the one the transport check
#: below actually drives. The two must stay the same name or the coverage claim
#: quietly stops meaning anything.
_THE_ONE_FETCHER = "_httpx_get"

#: Builtins that turn any import walk into a suggestion.
_DYNAMIC_CODE_BUILTINS = {"__import__", "eval", "exec", "compile"}

#: Members of `os` that hand the work to another process. `os` is on the
#: allowlist for `os.environ`, which is the only thing either file uses it for.
_OS_PROCESS_CALLS = {
    "system",
    "popen",
    "fork",
    "forkpty",
    "execv",
    "execve",
    "execl",
    "execle",
    "execlp",
    "execvp",
    "execvpe",
    "spawnv",
    "spawnve",
    "spawnl",
    "spawnlp",
    "posix_spawn",
}


def _banned_module(dotted: str) -> Optional[str]:
    """The banlist entry this dotted module name falls under, if any."""
    for banned in _NETWORK_CAPABLE_MODULES:
        if dotted == banned or dotted.startswith(banned + "."):
            return banned
    return None


def _egress_offences(tree: ast.AST) -> List[str]:
    """Every way this syntax tree could reach a socket other than through
    `_httpx_get`.

    Deliberately not a verb check. The bypass this exists for spelled no verb
    anywhere: `urllib.request.urlopen(Request(url, data=b"{}"))` is a POST
    because the body is not None. So this asks the structural question instead,
    which is the one the transport check cannot ask about itself: how many doors
    does this module have?
    """
    offences: List[str] = []

    def visit(node: ast.AST, scope: Tuple[str, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = scope + (node.name,)
        if isinstance(node, ast.Import):
            for alias in node.names:
                _judge_module(alias.name, node.lineno, scope, offences)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            if node.level:
                # A relative import cannot name a stdlib network module and is
                # inside this repository, which the rest of the suite covers.
                pass
            elif module in _ALLOWED_IMPORTS or module == "httpx":
                _judge_module(module, node.lineno, scope, offences)
            else:
                for alias in node.names:
                    _judge_module(f"{module}.{alias.name}", node.lineno, scope, offences)
        elif isinstance(node, ast.Call):
            name = _callee_name(node.func)
            if name in _DYNAMIC_CODE_BUILTINS:
                offences.append(
                    f"{name}(...) at line {node.lineno} can name a module this walk "
                    "never sees. Refused by shape: an import allowlist that "
                    f"{name} can step around is not an allowlist"
                )
            elif (
                name in _OS_PROCESS_CALLS
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
            ):
                offences.append(
                    f"os.{name}(...) at line {node.lineno} hands the work to another "
                    "process, which can carry any verb to any host"
                )
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, ())
    return offences


def _judge_module(
    dotted: str, lineno: int, scope: Tuple[str, ...], offences: List[str]
) -> None:
    banned = _banned_module(dotted)
    if banned is not None:
        offences.append(
            f"import of {dotted} at line {lineno} opens a second egress path. "
            f"{banned} is refused whatever the allowlist says, because the "
            "transport check audits one function and cannot see this one"
        )
        return
    if dotted == "httpx":
        if _THE_ONE_FETCHER not in scope:
            offences.append(
                f"httpx imported at line {lineno} outside {_THE_ONE_FETCHER}. Every "
                "client in this module has to be built inside the one function the "
                "transport check drives, or that check stops covering the module"
            )
        return
    if dotted not in _ALLOWED_IMPORTS:
        offences.append(
            f"import of {dotted} at line {lineno} is not on the measured allowlist. "
            "If it is legitimate, add it deliberately and say why; the allowlist is "
            "what makes the one audited fetcher the module's whole egress surface"
        )


@pytest.mark.parametrize("path", [SERVICE_FILE, ROUTE_FILE])
def test_the_audited_fetcher_is_the_only_door(path: pathlib.Path) -> None:
    """One egress path, proved off the source rather than assumed.

    This is the claim the transport check below depends on and does not make.
    It fails on a second network import, on an httpx client built anywhere but
    `_httpx_get`, and on the dynamic code that would hide either.
    """
    offences = _egress_offences(_tree(path))
    assert not offences, f"{path.name} opens an egress path outside the audited fetcher: {offences}"


def test_the_audited_fetcher_exists_and_imports_httpx_itself() -> None:
    """The containment rule above is vacuous if nothing imports httpx at all.

    A guard nobody has watched fire is not a guarantee, and a guard that would
    pass over a module with no fetcher in it is worse: it would be credited for
    the silence.
    """
    tree = _tree(SERVICE_FILE)
    inside: List[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != _THE_ONE_FETCHER:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Import) and any(a.name == "httpx" for a in inner.names):
                inside.append(inner.lineno)
    assert inside, (
        f"{_THE_ONE_FETCHER} does not import httpx in its own body, so the "
        "containment rule is guarding nothing and the transport check may be "
        "driving a function that is no longer the fetcher"
    )


# Each of these reached a real socket from inside the guarded module while the
# verb walk reported zero offences. They sit in their own corpus rather than in
# `_BYPASSES` on purpose: none of them spells a verb, so `_mutating_verb_offences`
# is right not to fire on them and a shared corpus would only teach the wrong
# lesson about which layer owns which question.
_EGRESS_BYPASSES = {
    # The adversary's 2026-09-10 tick three bypass, verbatim, minus the body of
    # the function it sat in. Wire capture logged POST /executions/6679/retry
    # with the API key attached, on a suite reporting 191 passed.
    "a second egress module whose verb is implied by a body": (
        "import urllib.request\n"
        'outbound = urllib.request.Request(endpoint, data=b"{}", headers=headers)\n'
        "answer = urllib.request.urlopen(outbound, timeout=TIMEOUT_SECONDS)"
    ),
    "the same module reached through from": (
        "from urllib import request\nrequest.urlopen(endpoint, data=b'{}')"
    ),
    "a raw socket": ("import socket\ns = socket.create_connection((host, 443))"),
    "the stdlib http client": ("import http.client\nc = http.client.HTTPSConnection(host)"),
    "a third party client": ("import requests\nrequests.request(verb, url)"),
    "shelling out to curl": (
        "import subprocess\nsubprocess.run(['curl', '-XPOST', url])"
    ),
    "shelling out through os": ('os.system("curl -XPOST " + url)'),
    "a dynamic import the walk cannot read": (
        '__import__("urllib.request").urlopen(endpoint, data=b"{}")'
    ),
    "an httpx client built outside the audited fetcher": (
        "async def refresh(url):\n"
        "    import httpx\n"
        "    async with httpx.AsyncClient() as client:\n"
        "        return await client.get(url)"
    ),
}


@pytest.mark.parametrize("label, source", sorted(_EGRESS_BYPASSES.items()))
def test_the_egress_detector_catches_the_second_doors(label: str, source: str) -> None:
    offences = _egress_offences(ast.parse(source))
    assert offences, (
        f"the detector did not see {label}. A path like this reached a real socket "
        f"from inside the module while the suite reported 191 passed: {source!r}"
    )


def test_the_egress_detector_does_not_fire_on_the_real_shape() -> None:
    """The other half of the control, and the one that stops this rule becoming
    unmaintainable: the module's actual imports, plus the fetcher's own httpx
    import in its own scope, must all stay legal.
    """
    legitimate = "\n".join(
        [
            "import math",
            "import os",
            "from dataclasses import dataclass",
            "from datetime import datetime, timezone",
            "from typing import Any, Dict",
            "from urllib.parse import urlparse",
            "async def _httpx_get(url, headers):",
            "    import httpx",
            "    from urllib.parse import quote",
            "    async with httpx.AsyncClient() as client:",
            "        return await client.get(url, headers=headers)",
            "source = os.environ",
        ]
    )
    assert _egress_offences(ast.parse(legitimate)) == []


def test_the_banlist_survives_a_widened_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """The banlist's only job, and the only check that watches it do it.

    Measured on 2026-09-10: with `_NETWORK_CAPABLE_MODULES` emptied, all nine
    probes above still passed, because the allowlist catches every one of them
    on its own. So the banlist was decorative under test while being described
    as the rule the allowlist cannot relax. This is that description, executed:
    widen the allowlist by one word, the way a future contributor would, and the
    second door must still be refused.
    """
    import sys

    module = sys.modules[__name__]
    monkeypatch.setattr(module, "_ALLOWED_IMPORTS", _ALLOWED_IMPORTS | {"urllib.request"})
    offences = _egress_offences(ast.parse("import urllib.request"))
    assert offences, (
        "widening the allowlist by one entry reopened the second egress door. The "
        "banlist exists so that a one word edit cannot do that"
    )
    assert "refused whatever the allowlist says" in offences[0]


# ---------------------------------------------------------------------------
# THE GUARANTEE, EXECUTED
#
# Everything above is a SYNTAX walk, and on 2026-09-10 an adversary showed in
# one run that a syntax walk can never be the guarantee. Six of eight shapes it
# tried reported zero offences, and two of them it carried to a real socket:
#
#     await client.request(**{"method": "DELETE", "url": url})
#     object.__setattr__(request, "method", "POST")
#
# The first spells DELETE in full, at a callee the walk explicitly tracks. It
# was invisible because the container was a dict. The second works because
# `setattr` was on the allowlist and `__setattr__` was not.
#
# Both holes are now closed above, and closing them changes nothing about the
# real problem, which the adversary stated better than the previous four rules
# did: the enumeration of places a verb can sit is FINITE, and the ways to set
# one string field on one object are not. Every rule so far was another
# location added after somebody found a location outside it.
#
# So this is the check that does not care how the verb got there. It installs a
# recording transport under the REAL production fetcher and asserts on the
# request object that actually reaches the wire. It would have caught all eight
# of that run's shapes, including the six the walk cannot see, and it will
# catch the next one without anybody having imagined it first.
#
# The syntax walk is kept because it is cheap, it names the offence precisely,
# and it fails at collection rather than at runtime. It is the first line.
#
# This is the guarantee FOR THE ONE FUNCTION IT DRIVES, and that qualifier was
# missing here until a fourth adversary walked around the side of it with
# `urllib.request.urlopen`, which never touches httpx. What makes this cover the
# module is the egress rule above: one door, and this is the check standing in
# it. Neither half is the guarantee alone.
# ---------------------------------------------------------------------------

#: Headers that make a server treat a GET as a write. The verb on the wire is
#: honest and the effect is not, so asserting the method alone is not enough.
_METHOD_OVERRIDE_HEADERS = (
    "x-http-method-override",
    "x-method-override",
    "x-http-method",
)


async def _requests_the_real_fetcher_sends(monkeypatch: pytest.MonkeyPatch) -> List[Any]:
    """Drive `_httpx_get` itself and return every request that reached transport.

    `_httpx_get` does `import httpx` in its own body, so patching the attribute
    on the module object is enough; there is no cached reference to dodge. The
    client is subclassed rather than replaced so that every argument the real
    fetcher passes still applies and only the transport is ours.
    """
    import httpx

    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    real_client = httpx.AsyncClient

    class Recording(real_client):  # type: ignore[misc, valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", Recording)
    await tel._httpx_get(
        f"https://{PRIMARY_HOST}/api/v1/executions?limit=1",
        {"X-N8N-API-KEY": "not-a-real-key"},
    )
    return seen


async def test_the_request_that_reaches_the_wire_carries_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one check that does not enumerate anything.

    A syntax walk asks where the verb is written. This asks what the transport
    was handed, which is the only question the module docstring's promise is
    actually about.
    """
    sent = await _requests_the_real_fetcher_sends(monkeypatch)
    assert sent, (
        "the production fetcher never reached the transport, so this test proved "
        "nothing. A guard that cannot fire is worse than no guard, because it is "
        "credited"
    )
    for request in sent:
        assert request.method == "GET", (
            f"the production fetcher put {request.method} on the wire. This module "
            "is read only by construction and the transport says otherwise"
        )
        for header in _METHOD_OVERRIDE_HEADERS:
            assert header not in request.headers, (
                f"the fetcher sent {header}, which makes a server treat this GET as "
                "a write. The verb on the wire is honest and the effect is not"
            )


async def test_the_wire_check_fails_when_the_fetcher_mutates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The control on the control. A recording transport that records nothing
    would let the test above pass over a silent fetcher, so this proves the
    recorder actually sees a non GET when one is sent.
    """
    import httpx

    seen: List[Any] = []

    def handler(request: Any) -> Any:
        seen.append(request)
        return httpx.Response(200, json={"data": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await client.request(**{"method": "DELETE", "url": f"https://{PRIMARY_HOST}/x"})
    assert [r.method for r in seen] == ["DELETE"], (
        "the recording transport did not see a DELETE it was handed, so the test "
        "above cannot be trusted to see one either"
    )


def test_the_mutating_verb_detector_does_not_fire_on_a_read() -> None:
    """The other half of the control. A detector that flags everything is no
    detector, and would make the guard above unmaintainable rather than sound.
    """
    read_shapes = "\n".join(
        [
            "response = await client.get(url, headers=headers)",
            'router.add_api_route("/executions", handler, methods=["GET"])',
            '@router.get("/executions")',
            "def handler():",
            "    return None",
            'note = "this route cannot trigger, retry, delete or resume an execution"',
        ]
    )
    assert _mutating_verb_offences(ast.parse(read_shapes)) == []


@pytest.mark.parametrize("path", [SERVICE_FILE, ROUTE_FILE])
def test_no_url_or_live_host_literal_in_the_source(path: pathlib.Path) -> None:
    """No instance address is baked in, in code or in a docstring.

    Every string constant in the module is checked, so a default URL cannot
    hide in a docstring either. The point is not tidiness: a literal host is
    how an unconfigured instance comes to report someone's real numbers.
    """
    offenders = []
    live = re.compile(r"n8n\.cloud|editforge|\.app\.n8n\b", re.IGNORECASE)
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "://" in node.value:
                offenders.append(f"URL literal at line {node.lineno}")
            if live.search(node.value):
                offenders.append(f"live n8n host at line {node.lineno}")
    assert not offenders, f"{path.name} hardcodes an address: {offenders}"


def test_the_only_fetcher_takes_no_body() -> None:
    """A read has a URL and headers. A body would mean something else."""
    import inspect

    parameters = list(inspect.signature(tel._httpx_get).parameters)
    assert parameters == ["url", "headers"], parameters


# ---------------------------------------------------------------------------
# unconfigured, misconfigured: report it, read nothing
# ---------------------------------------------------------------------------

async def test_nothing_configured_never_reaches_the_network() -> None:
    fetch = Refuse()
    payload = await tel.read_all(fetch=fetch, environ={})
    assert fetch.calls == []
    assert payload["configured"] == 0
    assert payload["reachable"] == 0
    for instance in payload["instances"]:
        assert instance["state"] == "unconfigured"
        assert instance["window"] is None
        assert instance["cap"] is None
        assert instance["recent"] == []
        assert "N8N" in instance["reason"]


async def test_a_url_without_a_key_is_misconfigured_not_unconfigured() -> None:
    fetch = Refuse()
    payload = await tel.read_all(fetch=fetch, environ={"N8N_API_URL": f"https://{PRIMARY_HOST}"})
    primary = _only(payload, "primary")
    assert primary["state"] == "misconfigured"
    assert "N8N_API_KEY" in primary["reason"]
    assert primary["configured_host"] == PRIMARY_HOST
    assert fetch.calls == []


async def test_a_url_that_is_not_http_is_refused_before_any_request() -> None:
    fetch = Refuse()
    payload = await tel.read_all(
        fetch=fetch, environ=_env(N8N_API_URL="not-a-url", N8N_API_KEY=PRIMARY_KEY)
    )
    assert _only(payload, "primary")["state"] == "misconfigured"
    assert fetch.calls == []


# ---------------------------------------------------------------------------
# reached, and the ways it can go wrong
# ---------------------------------------------------------------------------

async def test_unreachable_is_its_own_state_not_an_empty_one() -> None:
    fake = Fake(primary_invalid=tel.Unreachable("ConnectTimeout: timed out"))
    payload = await tel.read_all(fetch=fake, environ=_env())
    primary = _only(payload, "primary")
    assert primary["state"] == "unreachable"
    assert primary["window"] is None, "an unreachable instance must report no window at all"
    assert primary["counts"] is None
    assert "timed out" in primary["reason"]
    assert payload["reachable"] == 0


async def test_configured_and_empty_is_ok_and_says_it_is_an_answered_read() -> None:
    fake = Fake(primary_invalid=[_page([])])
    payload = await tel.read_all(fetch=fake, environ=_env())
    primary = _only(payload, "primary")
    assert primary["state"] == "ok"
    assert primary["window"]["executions_read"] == 0
    assert primary["counts"]["failed"] == 0
    assert "answered read, not a" in primary["reason"]
    assert primary["rate"]["basis"] == "unavailable"


async def test_a_rotated_key_reads_as_refused_with_the_status_code() -> None:
    fake = Fake(primary_invalid=tel.Fetched(401, {"message": "unauthorized"}, f"https://{PRIMARY_HOST}/api/v1/executions"))
    primary = _only(await tel.read_all(fetch=fake, environ=_env()), "primary")
    assert primary["state"] == "refused"
    assert primary["status_code"] == 401
    assert "401" in primary["reason"]
    assert primary["window"] is None


async def test_a_two_hundred_that_is_not_the_executions_shape_is_malformed() -> None:
    fake = Fake(primary_invalid=tel.Fetched(200, {"nope": True}, f"https://{PRIMARY_HOST}/api/v1/executions"))
    primary = _only(await tel.read_all(fetch=fake, environ=_env()), "primary")
    assert primary["state"] == "malformed"
    assert primary["window"] is None, "a malformed answer must not read as an empty instance"


async def test_the_request_carries_the_estate_s_header_convention() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    await tel.read_all(fetch=fake, environ=_env())
    call = fake.calls[0]
    assert call["headers"]["X-N8N-API-KEY"] == PRIMARY_KEY
    assert call["headers"]["Accept"] == "application/json"
    assert "/api/v1/executions" in call["url"]
    assert "includeData=false" in call["url"]


async def test_the_key_is_never_anywhere_in_the_payload() -> None:
    fake = Fake(
        primary_invalid=[_page(WINDOW_ROWS)],
        secondary_invalid=[_page(WINDOW_ROWS)],
    )
    payload = await tel.read_all(
        fetch=fake,
        environ=_env(
            N8N_SECONDARY_API_URL=f"https://{SECONDARY_HOST}",
            N8N_SECONDARY_API_KEY=SECONDARY_KEY,
        ),
    )
    body = json.dumps(payload)
    assert PRIMARY_KEY not in body
    assert SECONDARY_KEY not in body
    # The variable NAMES are useful on a panel; the values never are.
    assert "N8N_API_KEY" in body


# ---------------------------------------------------------------------------
# what the window actually says
# ---------------------------------------------------------------------------

async def test_counts_durations_and_the_unsaved_gap() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    primary = _only(await tel.read_all(fetch=fake, environ=_env()), "primary")

    assert primary["counts"] == {
        "failed": 2,
        "succeeded": 1,
        "canceled": 0,
        "running": 0,
        "waiting": 1,
        "other": 0,
        "status_unreported": 1,
    }
    assert primary["status_counts"] == {"crashed": 1, "error": 1, "success": 1, "waiting": 1}

    window = primary["window"]
    assert window["executions_read"] == 5
    assert window["newest_id"] == 6412
    assert window["oldest_id"] == 6292
    assert window["span_hours"] == 24.0
    # 6412 - 6292 + 1 = 121 ids in the span, 5 of them saved.
    assert window["ids_in_span"] == 121
    assert window["not_saved_in_span"] == 116
    assert window["truncated"] is False

    newest = primary["recent"][0]
    assert newest["id"] == 6412
    assert newest["duration_ms"] == 3500
    assert newest["workflow_name"] == "Driver Poll"
    # A row with no stoppedAt has no duration, and none is invented for it.
    assert primary["recent"][4]["duration_ms"] is None


def test_a_row_with_no_status_is_unreported_never_inferred() -> None:
    rows = [tel.read_row(_row(1, None, "2026-09-10T12:00:00Z", "2026-09-10T12:00:01Z"))]
    buckets, raw = tel.count_statuses(rows)
    assert buckets["status_unreported"] == 1
    assert buckets["succeeded"] == 0
    assert buckets["failed"] == 0
    assert raw == {}


def test_a_stopped_before_started_is_not_a_negative_duration() -> None:
    read = tel.read_row(_row(1, "success", "2026-09-10T12:00:05Z", "2026-09-10T12:00:00Z"))
    assert read["duration_ms"] is None


def test_a_string_id_is_read_and_a_junk_id_is_not() -> None:
    assert tel.read_row(_row("6412", "success", "2026-09-10T12:00:00Z"))["id"] == 6412
    assert tel.read_row(_row("abc", "success", "2026-09-10T12:00:00Z"))["id"] is None
    assert tel.read_row(_row(True, "success", "2026-09-10T12:00:00Z"))["id"] is None


# ---------------------------------------------------------------------------
# the rate, and its refusals
# ---------------------------------------------------------------------------

def test_the_rate_is_the_id_delta_over_the_span() -> None:
    rows = [tel.read_row(row) for row in WINDOW_ROWS]
    rate = tel.measure_rate(tel.measure_window(rows, False))
    # 120 ids over exactly 24 hours is 120 a day.
    assert rate["basis"] == "id_delta"
    assert rate["per_day"] == 120.0
    assert rate["executions_in_span"] == 120
    assert rate["span_hours"] == 24.0
    assert rate["from_id"] == 6292 and rate["to_id"] == 6412
    assert tel.ID_DELTA_ASSUMPTION in rate["assumptions"]
    assert tel.WINDOW_ASSUMPTION in rate["assumptions"]


@pytest.mark.parametrize(
    "rows, expect",
    [
        ([], "numeric id"),
        ([_row(10, "success", "2026-09-10T12:00:00Z")], "one execution"),
        (
            [
                _row(10, "success", "2026-09-10T12:00:00Z"),
                _row(9, "success", "2026-09-10T12:00:00Z"),
            ],
            "same instant",
        ),
        ([_row("x", "success", "2026-09-10T12:00:00Z")], "numeric id"),
    ],
)
def test_a_rate_that_cannot_be_measured_says_so(rows: List[Dict[str, Any]], expect: str) -> None:
    rate = tel.measure_rate(tel.measure_window([tel.read_row(r) for r in rows], False))
    assert rate["basis"] == "unavailable"
    assert rate["per_day"] is None
    assert expect in rate["reason"]


# ---------------------------------------------------------------------------
# the cap: stated, never invented
# ---------------------------------------------------------------------------

async def test_no_cap_configured_means_no_cap_number_anywhere() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    primary = _only(await tel.read_all(fetch=fake, environ=_env()), "primary")
    cap = primary["cap"]
    assert cap["state"] == "not_stated"
    assert cap["cap"] is None
    assert cap["spent_estimate"] is None
    assert cap["remaining_estimate"] is None
    assert cap["reason"] == "no cap is stated for this instance"
    # The number this estate would most plausibly have invented.
    assert "2500" not in json.dumps(cap)


async def test_a_cap_with_no_anchor_has_no_spend_and_says_why() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    primary = _only(
        await tel.read_all(fetch=fake, environ=_env(N8N_EXECUTION_CAP="2500")), "primary"
    )
    cap = primary["cap"]
    assert cap["state"] == "stated"
    assert cap["cap"] == 2500
    assert cap["source"] == "stated_by_configuration"
    assert cap["spent_estimate"] is None
    assert "no source" in cap["reason"]
    assert cap["counted_from_id"] is None


async def test_a_cap_with_an_anchor_estimates_a_spend_and_carries_its_basis() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    primary = _only(
        await tel.read_all(
            fetch=fake,
            environ=_env(
                N8N_EXECUTION_CAP="2500",
                N8N_EXECUTION_CAP_ANCHOR_ID="6265",
                N8N_EXECUTION_CAP_ANCHOR_SPENT="1212",
                N8N_EXECUTION_CAP_ANCHOR_AT="2026-09-06T13:00:00Z",
                N8N_EXECUTION_CAP_RESETS_AT="2026-10-01",
            ),
        ),
        "primary",
    )
    cap = primary["cap"]
    # 1212 spent at id 6265; the newest id read is 6412, so 147 more ids have
    # passed and the spend is 1359 of 2500, leaving 1141.
    assert cap["state"] == "estimated"
    assert cap["spent_estimate"] == 1359
    assert cap["spent_basis"] == "anchor_plus_id_delta"
    assert cap["remaining_estimate"] == 1141
    assert cap["used_fraction"] == 0.5436
    assert cap["resets_at"] == "2026-10-01"
    assert cap["reset_readable"] is True
    assert cap["reset_in_the_past"] is False
    assert cap["reason"] is None

    # THE BASIS OF THE BURN, on the payload rather than only inside a
    # projection block. The spend is carried forward TO a named id and that id's
    # OWN moment, which is the F1 rule: the id a spend is carried to and the
    # moment it is counted from come from the same execution.
    assert cap["anchor"] == {
        "id": 6265,
        "spent": 1212,
        "at": "2026-09-06T13:00:00Z",
        "source": "stated_by_configuration",
    }
    assert cap["counted_from_id"] == 6412
    assert cap["counted_from_moment"] == "2026-09-10T12:00:00Z"
    assert tel.ID_DELTA_ASSUMPTION in cap["assumptions"]
    assert tel.CAP_ASSUMPTION in cap["assumptions"]
    # THE PROJECTION IS GONE. There is no derived date left on this payload.
    assert "projection" not in cap


async def test_an_anchor_above_the_newest_id_is_inconsistent_not_negative() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    primary = _only(
        await tel.read_all(
            fetch=fake,
            environ=_env(
                N8N_EXECUTION_CAP="2500",
                N8N_EXECUTION_CAP_ANCHOR_ID="99999",
                N8N_EXECUTION_CAP_ANCHOR_SPENT="1212",
            ),
        ),
        "primary",
    )
    cap = primary["cap"]
    assert cap["state"] == "inconsistent"
    assert cap["spent_estimate"] is None
    assert "different instance" in cap["reason"]


async def test_a_spend_past_the_cap_is_still_an_estimate_with_its_basis() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    primary = _only(
        await tel.read_all(
            fetch=fake,
            environ=_env(
                N8N_EXECUTION_CAP="1300",
                N8N_EXECUTION_CAP_ANCHOR_ID="6265",
                N8N_EXECUTION_CAP_ANCHOR_SPENT="1212",
            ),
        ),
        "primary",
    )
    cap = primary["cap"]
    assert cap["remaining_estimate"] == -59
    assert cap["state"] == "estimated"
    assert cap["reason"] is None
    # No date is derived from being over the cap, because no date is derived
    # from anything on this payload any more.
    assert "projection" not in cap
    assert "exhausts_at" not in json.dumps(cap)


async def test_a_cap_variable_that_is_not_a_number_is_a_reported_problem() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    payload = await tel.read_all(fetch=fake, environ=_env(N8N_EXECUTION_CAP="two thousand"))
    primary = _only(payload, "primary")
    assert primary["cap"]["state"] == "not_stated"
    assert primary["cap"]["cap"] is None
    assert any("not a whole number" in problem for problem in primary["cap"]["problems"])
    assert any("N8N_EXECUTION_CAP" in finding for finding in payload["findings"])


# ---------------------------------------------------------------------------
# two instances, side by side
# ---------------------------------------------------------------------------

async def test_both_instances_are_reported_separately_and_never_merged() -> None:
    fake = Fake(
        primary_invalid=[_page(WINDOW_ROWS)],
        secondary_invalid=[_page([_row(4, "success", "2026-09-10T11:00:00Z")])],
    )
    payload = await tel.read_all(
        fetch=fake,
        environ=_env(
            N8N_SECONDARY_API_URL=f"https://{SECONDARY_HOST}",
            N8N_SECONDARY_API_KEY=SECONDARY_KEY,
            N8N_EXECUTION_CAP="2500",
        ),
    )
    primary, secondary = _only(payload, "primary"), _only(payload, "secondary")
    assert primary["host"] == PRIMARY_HOST
    assert secondary["host"] == SECONDARY_HOST
    assert primary["window"]["executions_read"] == 5
    assert secondary["window"]["executions_read"] == 1
    assert payload["configured"] == 2
    assert payload["reachable"] == 2
    # The cap is the primary plan's. A self hosted target must not inherit it.
    assert primary["cap"]["state"] == "stated"
    assert secondary["cap"]["state"] == "not_stated"
    assert secondary["cap"]["cap"] is None
    assert payload["findings"] == []
    # Nothing in the payload is a merged total of the two.
    assert set(payload) == {
        "read_only",
        "read_at",
        "limit",
        "instances",
        "configured",
        "reachable",
        "findings",
        "note",
    }


async def test_a_secondary_left_pointing_at_the_source_is_called_out() -> None:
    """The quietest cutover failure there is, so it gets a finding of its own."""
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    payload = await tel.read_all(
        fetch=fake,
        environ=_env(
            N8N_SECONDARY_API_URL=f"https://{PRIMARY_HOST}",
            N8N_SECONDARY_API_KEY=SECONDARY_KEY,
        ),
    )
    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert PRIMARY_HOST in finding
    assert "one instance read twice" in finding


async def test_the_host_reported_is_the_one_actually_reached() -> None:
    """A redirect moves the answer. The label follows the answer, not the config."""
    fake = Fake(
        primary_invalid=tel.Fetched(200, _page(WINDOW_ROWS), f"https://{SECONDARY_HOST}/api/v1/executions"),
    )
    primary = _only(await tel.read_all(fetch=fake, environ=_env()), "primary")
    assert primary["configured_host"] == PRIMARY_HOST
    assert primary["host"] == SECONDARY_HOST


# ---------------------------------------------------------------------------
# paging and bounds
# ---------------------------------------------------------------------------

async def test_pages_are_walked_by_cursor_and_truncation_is_reported() -> None:
    fake = Fake(
        primary_invalid=[
            _page(WINDOW_ROWS[:3], cursor="1"),
            _page(WINDOW_ROWS[3:], cursor="2"),
        ]
    )
    primary = _only(await tel.read_all(fetch=fake, environ=_env(), limit=5), "primary")
    assert len(fake.calls) == 2
    assert "cursor=1" in fake.calls[1]["url"]
    assert primary["window"]["executions_read"] == 5
    # A cursor was still in hand at the limit, so the window is cut off.
    assert primary["window"]["truncated"] is True


async def test_a_last_page_with_no_cursor_is_not_truncated() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS, cursor=None)])
    primary = _only(await tel.read_all(fetch=fake, environ=_env(), limit=500), "primary")
    assert primary["window"]["truncated"] is False


async def test_the_limit_is_bounded_and_echoed() -> None:
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    payload = await tel.read_all(fetch=fake, environ=_env(), limit=99999)
    assert payload["limit"] == tel.MAX_LIMIT
    first = parse_qs(urlparse(fake.calls[0]["url"]).query)
    assert int(first["limit"][0]) <= tel.PAGE_SIZE


async def test_the_payload_says_it_is_read_only() -> None:
    fake = Fake(primary_invalid=[_page([])])
    payload = await tel.read_all(fetch=fake, environ=_env())
    assert payload["read_only"] is True
    assert "cannot trigger, retry, delete or resume" in payload["note"]


# ---------------------------------------------------------------------------
# the route, mounted on its own app: no database, no network
# ---------------------------------------------------------------------------

def _client():
    """The router on a throwaway app, with authentication stood in for.

    Mounted here rather than on `app.main.app` because this file belongs to the
    offline job, which has no database, and `get_current_user` would want one.
    Overriding the gate exercises everything after it, which is the part this
    piece owns.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.security.deps import get_current_user

    app = FastAPI()
    app.include_router(route_module.router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: object()
    return TestClient(app)


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "N8N_API_URL",
        "N8N_API_KEY",
        "N8N_SECONDARY_API_URL",
        "N8N_SECONDARY_API_KEY",
        "N8N_EXECUTION_CAP",
        "N8N_EXECUTION_CAP_ANCHOR_ID",
        "N8N_EXECUTION_CAP_ANCHOR_SPENT",
        "N8N_SECONDARY_EXECUTION_CAP",
    ):
        monkeypatch.delenv(variable, raising=False)


def test_the_route_answers_a_get_with_nothing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    response = _client().get("/api/v1/n8n/executions")
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert [i["state"] for i in body["instances"]] == ["unconfigured", "unconfigured"]


def test_the_route_reads_the_process_environment_and_its_own_fetcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`environ=None` means os.environ and the default fetcher is the httpx one.

    The route calls `read_all()` with neither argument, so if either default
    were wired to something else every other test in this file would be proving
    a path production does not take. The fetcher is swapped for the fake at the
    module attribute the production code reaches for, so nothing here touches
    the network or the resolver.
    """
    _clear(monkeypatch)
    monkeypatch.setenv("N8N_API_URL", f"https://{PRIMARY_HOST}")
    monkeypatch.setenv("N8N_API_KEY", PRIMARY_KEY)
    monkeypatch.setattr(tel, "_httpx_get", Fake(primary_invalid=[_page(WINDOW_ROWS)]))

    body = _client().get("/api/v1/n8n/executions", params={"limit": 5}).json()
    primary = _only(body, "primary")
    assert primary["state"] == "ok"
    assert primary["host"] == PRIMARY_HOST
    assert primary["window"]["executions_read"] == 5
    assert body["limit"] == 5
    assert PRIMARY_KEY not in json.dumps(body)


def test_every_mutating_verb_on_the_route_is_a_405() -> None:
    """The claim the docstrings make, made by the running application.

    A 405 is the app saying the path exists and the method does not. Registering
    a POST handler turns one of these into a 200 or a 422 and fails here, which
    is the same guard as the route table walk from a different direction.
    """
    client = _client()
    # `request` rather than the per verb helpers: TestClient.delete takes no
    # json argument, and the point is the verb, not the body.
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
        response = client.request(verb, "/api/v1/n8n/executions")
        assert response.status_code == 405, f"{verb} was accepted on a read only route"


def test_the_limit_is_validated_by_the_route_rather_than_silently_clamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear(monkeypatch)
    client = _client()
    assert client.get("/api/v1/n8n/executions", params={"limit": 0}).status_code == 422
    over = {"limit": tel.MAX_LIMIT + 1}
    assert client.get("/api/v1/n8n/executions", params=over).status_code == 422


# ===========================================================================
# REGRESSIONS. One block per finding a fresh adversary produced on 2026-09-10,
# each with an executed reproduction recorded beside it, plus the shape
# corrections measured against a live instance the same day.
#
# F3, F4 and F9's reader half live in apps/web/scripts/n8n-telemetry-check.ts,
# which is where the readers they concern live. Nothing here duplicates them.
# ===========================================================================

CAP_ENV = {
    "N8N_EXECUTION_CAP": "2500",
    "N8N_EXECUTION_CAP_ANCHOR_ID": "6000",
    "N8N_EXECUTION_CAP_ANCHOR_SPENT": "1000",
}


async def _read_primary(
    rows: List[Dict[str, Any]], read_at: Optional[datetime] = None, **env_over: str
) -> Dict[str, Any]:
    """The primary instance's payload, read at a PINNED instant.

    `read_at` defaults to `_NOW` rather than to the wall clock. The configured
    cycle reset is compared with the moment of the read, so a test that let the
    clock run would answer differently in a month: the fixture resets are
    stamped 2026-10-01, and once real time is past that a reset this file calls
    ahead of the read is legitimately behind it. Pinning it is what makes these
    assert on a comparison rather than on a calendar.
    """
    fake = Fake(primary_invalid=[_page(rows)])
    payload = await tel.read_all(
        fetch=fake, environ=_env(**env_over), read_at=read_at or _NOW
    )
    return _only(payload, "primary")


# ---------------------------------------------------------------------------
# MEASURED SHAPE, 2026-09-10, 32 real executions read through this session's
# n8n connector. These are not assumptions any more and the tests say so.
# ---------------------------------------------------------------------------

def test_the_measured_row_shape_carries_no_workflow_name() -> None:
    """The fields MEASURED on a real row, and the one the builder invented.

    id is a STRING, status and mode are real field names, and
    `workflowData.name` DOES NOT EXIST in the response. The builder assumed it,
    so a reader would have been shown a blank where a name was promised. The
    label falls back to the id and says which it is.
    """
    measured = {
        "id": "6679",
        "workflowId": "kQ2t",
        "status": "success",
        "mode": "trigger",
        "startedAt": "2026-09-10T12:00:00.000Z",
        "stoppedAt": "2026-09-10T12:00:03.500Z",
        "waitTill": None,
    }
    read = tel.read_row(measured)
    assert read["id"] == 6679, "the measured id is a string of digits"
    assert read["status"] == "success"
    assert read["workflow_id"] == "kQ2t"
    assert read["workflow_name"] is None, "workflowData.name is not in the response"
    assert read["workflow_label"] == "workflow id kQ2t"
    assert read["workflow_label_kind"] == "id"
    assert read["workflow_label"].strip(), "a reader must never be shown a blank"
    assert read["duration_ms"] == 3500


def test_the_measured_status_value_set_buckets_and_unknown_is_not_a_pass() -> None:
    """The full value set the API reports, MEASURED: canceled, crashed, error,
    new, running, success, unknown, waiting.

    "unknown" is the instance saying it does not know. It lands in `other` and
    is never counted as a pass, which is a different thing from a row that
    carried no status field at all.
    """
    values = ["canceled", "crashed", "error", "new", "running", "success", "unknown", "waiting"]
    rows = [
        tel.read_row(_row(str(100 + index), value, "2026-09-10T12:00:00Z"))
        for index, value in enumerate(values)
    ]
    buckets, raw = tel.count_statuses(rows)
    assert buckets == {
        "failed": 2,
        "succeeded": 1,
        "canceled": 1,
        "running": 2,
        "waiting": 1,
        "other": 1,
        "status_unreported": 0,
    }
    assert raw == {value: 1 for value in values}
    assert buckets["succeeded"] == 1, "'unknown' must never be counted as a pass"


def test_mode_error_is_a_mode_and_is_never_read_as_a_status() -> None:
    """MEASURED: `mode` takes the value "error", naming an error handler
    workflow. It is not a status and confusing the two would invent failures.
    """
    read = tel.read_row(
        {
            "id": "6675",
            "workflowId": "kQ2t",
            "mode": "error",
            "status": "success",
            "startedAt": "2026-09-10T12:00:00Z",
        }
    )
    assert read["mode"] == "error"
    assert read["status"] == "success"
    buckets, _ = tel.count_statuses([read])
    assert buckets["failed"] == 0 and buckets["succeeded"] == 1


@pytest.mark.parametrize(
    "label, envelope",
    [
        ("data with a top level cursor", lambda rows: {"data": rows, "nextCursor": None}),
        ("data with no cursor key at all", lambda rows: {"data": rows}),
        ("a bare list", lambda rows: list(rows)),
        ("a cursor nested under meta", lambda rows: {"data": rows, "meta": {"nextCursor": None}}),
        ("results rather than data", lambda rows: {"results": rows}),
    ],
)
async def test_no_single_pagination_envelope_is_load_bearing(label: str, envelope: Any) -> None:
    """UNSETTLED on 2026-09-10 and therefore not depended on.

    The shape measurement went through a connector that may normalise, so
    whether the raw endpoint answers {data, nextCursor} or something else was
    NOT confirmed. All of these are read and none of them is required.
    """
    fake = Fake(
        primary_invalid=tel.Fetched(
            200, envelope(list(WINDOW_ROWS)), f"https://{PRIMARY_HOST}/api/v1/executions"
        )
    )
    primary = _only(await tel.read_all(fetch=fake, environ=_env()), "primary")
    assert primary["state"] == "ok", f"{label} was not read"
    assert primary["window"]["executions_read"] == 5, label


# ---------------------------------------------------------------------------
# F1  the rate's denominator was not corrected for the rows dropped from its
#     numerator. REPRODUCED: two rows, ids 6412 and 6292, 24h apart, cap 2500,
#     anchor 6000/1000, gave per_day 120 and a wall of 2026-09-19. Adding ONE
#     row five days older whose id does not parse moved per_day to 24 and the
#     wall to 2026-10-25; a thirty day older one moved it to 2027-06-09. Six to
#     thirty times understated, in the reassuring direction, and rendered as a
#     confident figure because every basis field was present. The wall was cut
#     on 2026-09-10; the RATE it was derived from is still here and is still the
#     subject of this finding, so the test keeps it and drops the date.
# ---------------------------------------------------------------------------

TWO_ROW_WINDOW = [
    _row("6412", "success", "2026-09-10T12:00:00Z"),
    _row("6292", "success", "2026-09-09T12:00:00Z"),
]


@pytest.mark.parametrize(
    "label, older_at",
    [("five days older", "2026-09-05T12:00:00Z"), ("thirty days older", "2026-08-11T12:00:00Z")],
)
async def test_a_row_with_an_unreadable_id_cannot_move_the_rate_or_the_spend(
    label: str, older_at: str
) -> None:
    clean = await _read_primary(list(TWO_ROW_WINDOW), **CAP_ENV)
    assert clean["rate"]["per_day"] == 120.0
    assert clean["rate"]["span_hours"] == 24.0
    spend = clean["cap"]["spent_estimate"]
    assert spend is not None

    widened = await _read_primary(
        list(TWO_ROW_WINDOW) + [_row("not-an-id", "success", older_at)], **CAP_ENV
    )
    window = widened["window"]
    # The window a reader is SHOWN does widen, and that is honest.
    assert window["executions_read"] == 3
    assert window["span_hours"] > 24.0
    # The arithmetic does not, because both halves of the ratio come from the
    # rows that carry both an id and a startedAt.
    assert window["ids_read"] == 2
    assert window["rows_without_id"] == 1
    assert window["rate_span_hours"] == 24.0
    assert widened["rate"]["per_day"] == 120.0, f"a {label} row moved the rate"
    assert widened["cap"]["spent_estimate"] == spend, f"a {label} row moved the spend"


async def test_the_divergence_between_the_window_and_its_arithmetic_is_on_the_payload() -> None:
    """Fixing the arithmetic is half of it. The other half is that a reader can
    see the window they are shown is wider than the window that was measured.
    """
    widened = await _read_primary(
        list(TWO_ROW_WINDOW) + [_row("not-an-id", "success", "2026-08-11T12:00:00Z")], **CAP_ENV
    )
    assert widened["window"]["rows_without_id"] == 1
    assert widened["rate"]["rows_outside_the_rate"] == 1
    # The divergence lived in the projection's basis block as well as on the
    # window. That block went with the projection, and the window is where it
    # always belonged: `readWindow` in the web layer renders all three.
    assert widened["window"]["executions_read"] == 3
    assert widened["window"]["ids_read"] == 2
    assert widened["window"]["dated_ids_read"] == 2


async def test_a_row_with_no_timestamp_cannot_move_the_rate_either() -> None:
    """The mirror of the same defect. An id with no startedAt widens the
    numerator's reach without widening the denominator.
    """
    dateless = dict(_row("9999", "success", "2026-09-10T12:00:00Z"))
    dateless.pop("startedAt")
    widened = await _read_primary(list(TWO_ROW_WINDOW) + [dateless], **CAP_ENV)
    assert widened["window"]["rows_without_started_at"] == 1
    assert widened["window"]["newest_id"] == 9999
    assert widened["rate"]["per_day"] == 120.0
    assert widened["rate"]["to_id"] == 6412, "the rate must not reach an id it has no clock for"


# ---------------------------------------------------------------------------
# F2  pagination did not terminate on a 2xx page whose data list held no
#     objects. REPRODUCED: a fetcher answering {"data": ["not-a-dict", 7, None],
#     "nextCursor": "same"} produced 2000 requests to the identical URL and was
#     still going. Also: a repeating cursor with real rows reported
#     executions_read 500 for 10 actual executions, because rows were never
#     deduped by id.
# ---------------------------------------------------------------------------

class _Budgeted:
    """A fetcher that fails the test rather than the container if it loops."""

    def __init__(self, answer: Any, budget: int = 60) -> None:
        self.answer = answer
        self.budget = budget
        self.calls = 0
        self.urls: List[str] = []

    async def __call__(self, url: str, headers: Dict[str, str]) -> tel.Fetched:
        self.calls += 1
        self.urls.append(url)
        if self.calls > self.budget:
            raise AssertionError(
                f"the walk made {self.calls} requests to {len(set(self.urls))} distinct URL(s). "
                "It is looping, which is one panel load hanging an API worker."
            )
        return tel.Fetched(200, self.answer(self.calls), url)


async def test_a_page_whose_entries_are_not_objects_stops_the_walk() -> None:
    fetch = _Budgeted(lambda _n: {"data": ["not-a-dict", 7, None], "nextCursor": "same"})
    primary = _only(await tel.read_all(fetch=fetch, environ=_env(), limit=500), "primary")
    assert fetch.calls == 1, "a page that yielded no execution must not be asked again"
    assert primary["state"] == "ok"
    assert primary["window"]["executions_read"] == 0
    assert any("none of them was an execution" in problem for problem in primary["read_problems"])


async def test_a_repeating_cursor_with_real_rows_dedupes_rather_than_multiplying() -> None:
    ten = [
        _row(str(6400 - offset), "success", f"2026-09-10T{12 - offset:02d}:00:00Z")
        for offset in range(10)
    ]
    fetch = _Budgeted(lambda _n: {"data": ten, "nextCursor": "same"})
    primary = _only(await tel.read_all(fetch=fetch, environ=_env(), limit=500), "primary")
    assert fetch.calls == 2
    # Ten real executions are ten, not 500.
    assert primary["window"]["executions_read"] == 10
    assert primary["window"]["ids_read"] == 10


async def test_a_cursor_the_walk_already_followed_stops_it() -> None:
    fetch = _Budgeted(
        lambda n: {
            "data": [
                _row(str(7000 + n * 10 + i), "success", "2026-09-10T12:00:00Z") for i in range(3)
            ],
            "nextCursor": "same",
        }
    )
    primary = _only(await tel.read_all(fetch=fetch, environ=_env(), limit=500), "primary")
    assert fetch.calls == 2
    assert primary["window"]["truncated"] is True
    assert any("already followed" in problem for problem in primary["read_problems"])


async def test_the_walk_is_bounded_by_a_page_ceiling() -> None:
    """The backstop, exercised. One new row and one fresh cursor per page slips
    past both of the other two conditions, so this is the only thing that stops
    it.
    """
    fetch = _Budgeted(
        lambda n: {
            "data": [_row(str(9000 + n), "success", "2026-09-10T12:00:00Z")],
            "nextCursor": f"c{n}",
        },
        budget=tel.MAX_PAGES + 5,
    )
    primary = _only(await tel.read_all(fetch=fetch, environ=_env(), limit=500), "primary")
    assert fetch.calls == tel.MAX_PAGES
    assert primary["window"]["truncated"] is True
    assert any("page ceiling" in problem for problem in primary["read_problems"])


async def test_a_walk_problem_reaches_the_payload_findings() -> None:
    fetch = _Budgeted(lambda _n: {"data": ["not-a-dict"], "nextCursor": "same"})
    payload = await tel.read_all(fetch=fetch, environ=_env(), limit=500)
    assert any("none of them was an execution" in finding for finding in payload["findings"])


# ---------------------------------------------------------------------------
# F5  an unbounded days_left produced an absurd date or an HTTP 500 that
#     blanked BOTH instances. REPRODUCED: cap 30000 with two rows 1 id apart
#     across 100 days raised OverflowError: date value out of range and the
#     route answered HTTP 500. Bisected through the mounted route at per_day
#     120: cap 349,462,859 answered 200, cap 349,462,860 answered 500. A
#     negative anchor spend reached the same crash at cap 2500. Below the
#     threshold it printed a date instead: cap 2500 at 0.01/day gave
#     exhausts_at 2710-11-24.
# ---------------------------------------------------------------------------

SLOW_ROWS = [
    _row("6001", "success", "2026-09-10T12:00:00Z"),
    _row("6000", "success", "2026-06-02T12:00:00Z"),
]


@pytest.mark.parametrize("cap", ["30000", "2500", "349462860"])
async def test_the_input_that_overflowed_a_date_now_produces_no_date_to_overflow(
    cap: str,
) -> None:
    """F5's own inputs, re-measured after the projection was cut.

    The horizon and the `try/except OverflowError` around the `timedelta` both
    existed to bound a projected date, and the date is gone, so both went with
    it. What must not go with them is the PROOF, so the three caps that reached
    the crash are still driven here: 30000 and 2500 over a 100 day one id
    window, and 349,462,860, the cap that answered HTTP 500 while 349,462,859
    answered 200 when this was bisected through the mounted route.

    The route answers, the remaining count and the rate still stand, and there
    is no date anywhere on the payload to be absurd or to raise.
    """
    primary = await _read_primary(
        list(SLOW_ROWS),
        N8N_EXECUTION_CAP=cap,
        N8N_EXECUTION_CAP_ANCHOR_ID="6000",
        N8N_EXECUTION_CAP_ANCHOR_SPENT="0",
    )
    assert primary["state"] == "ok"
    assert primary["cap"]["state"] == "estimated"
    assert primary["cap"]["remaining_estimate"] == int(cap) - 1
    assert primary["rate"]["per_day"] == 0.01
    assert "projection" not in primary["cap"]
    assert "exhausts_at" not in json.dumps(primary)


async def test_one_instance_failing_never_blanks_the_other(monkeypatch: pytest.MonkeyPatch) -> None:
    """The F5 amplifier. `read_all` built its instance list in ONE
    comprehension, so a healthy primary plus an overflowing secondary raised
    out of the whole call and BOTH columns were lost.
    """
    original = tel.read_instance

    async def explode(config: tel.InstanceConfig, **kwargs: Any) -> Dict[str, Any]:
        if config.role == "secondary":
            raise OverflowError("date value out of range")
        return await original(config, **kwargs)

    monkeypatch.setattr(tel, "read_instance", explode)
    fake = Fake(primary_invalid=[_page(WINDOW_ROWS)])
    payload = await tel.read_all(
        fetch=fake,
        environ=_env(
            N8N_SECONDARY_API_URL=f"https://{SECONDARY_HOST}",
            N8N_SECONDARY_API_KEY=SECONDARY_KEY,
        ),
    )
    primary, secondary = _only(payload, "primary"), _only(payload, "secondary")
    assert primary["state"] == "ok", "the healthy instance must survive the other one"
    assert primary["window"]["executions_read"] == 5
    assert secondary["state"] == "errored"
    assert "OverflowError" in secondary["reason"]
    assert secondary["window"] is None and secondary["cap"] is None
    assert payload["reachable"] == 1


# ---------------------------------------------------------------------------
# F6  the id parser crashed on some inputs and coerced others it documented as
#     refused. REPRODUCED through the mounted route: "--5" and the superscript
#     two both answered HTTP 500. The Arabic indic digit three was COERCED to 3
#     and entered the id delta; a mixed string became 135.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("6412", 6412),
        (" 6412 ", 6412),
        (6412, 6412),
        ("--5", None),
        ("²", None),
        ("٣", None),
        ("1٣5", None),
        ("⁵", None),
        ("abc", None),
        ("+5", None),
        ("", None),
        ("  ", None),
        (True, None),
        (False, None),
        (None, None),
        (6412.0, None),
        (10 ** 16, None),
        ("1" * 20, None),
    ],
    ids=repr,
)
def test_the_id_parser_refuses_rather_than_crashing_or_coercing(raw: Any, expected: Any) -> None:
    read = tel.read_row({"id": raw, "startedAt": "2026-09-10T12:00:00Z"})
    assert read["id"] == expected


def test_a_coerced_non_ascii_digit_cannot_enter_the_id_delta() -> None:
    """The consequence, not just the parse. Read as 3, the Arabic indic digit
    put a delta of 6409 across one hour into the rate: 153,816 executions a day.
    """
    rows = [
        tel.read_row(_row("٣", "success", "2026-09-10T12:00:00Z")),
        tel.read_row(_row("6412", "success", "2026-09-10T13:00:00Z")),
    ]
    window = tel.measure_window(rows, False)
    assert window["ids_read"] == 1
    assert window["rows_without_id"] == 1
    assert tel.measure_rate(window)["basis"] == "unavailable"


def test_no_configuration_or_row_shape_can_turn_the_route_into_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every input that answered HTTP 500, through the mounted route.

    The route is registered on app/api/v1/router.py now, so this walks the real
    handler rather than the service in isolation.
    """
    _clear(monkeypatch)
    monkeypatch.setenv("N8N_API_URL", f"https://{PRIMARY_HOST}")
    monkeypatch.setenv("N8N_API_KEY", PRIMARY_KEY)
    client = _client()
    cases: List[Any] = [
        # F5: unbounded date arithmetic raised OverflowError out of the route.
        (
            "cap 30000 over a 100 day span",
            {
                "N8N_EXECUTION_CAP": "30000",
                "N8N_EXECUTION_CAP_ANCHOR_ID": "6000",
                "N8N_EXECUTION_CAP_ANCHOR_SPENT": "0",
            },
            list(SLOW_ROWS),
        ),
        (
            "the bisected cap one past the threshold",
            {
                "N8N_EXECUTION_CAP": "349462860",
                "N8N_EXECUTION_CAP_ANCHOR_ID": "6412",
                "N8N_EXECUTION_CAP_ANCHOR_SPENT": "0",
            },
            list(WINDOW_ROWS),
        ),
        (
            "a negative anchor spend at cap 2500",
            {
                "N8N_EXECUTION_CAP": "2500",
                "N8N_EXECUTION_CAP_ANCHOR_ID": "6412",
                "N8N_EXECUTION_CAP_ANCHOR_SPENT": "-999999999",
            },
            list(WINDOW_ROWS),
        ),
        # F6: two id shapes that raised ValueError out of int().
        ("a double minus id", {}, [_row("--5", "success", "2026-09-10T12:00:00Z")]),
        ("a superscript two id", {}, [_row("²", "success", "2026-09-10T12:00:00Z")]),
        # F2: a page of entries that are not executions.
        ("a page of non objects", {}, ["not-a-dict", 7, None]),
    ]
    cap_variables = (
        "N8N_EXECUTION_CAP",
        "N8N_EXECUTION_CAP_ANCHOR_ID",
        "N8N_EXECUTION_CAP_ANCHOR_SPENT",
    )
    for label, env_over, rows in cases:
        for variable in cap_variables:
            monkeypatch.delenv(variable, raising=False)
        for variable, value in env_over.items():
            monkeypatch.setenv(variable, value)
        monkeypatch.setattr(tel, "_httpx_get", Fake(primary_invalid=[_page(rows)]))
        response = client.get("/api/v1/n8n/executions")
        assert response.status_code == 200, f"{label} answered {response.status_code}"
        body = response.json()
        assert body["read_only"] is True, label
        assert PRIMARY_KEY not in json.dumps(body), label


# ---------------------------------------------------------------------------
# F7  the non-monotonicity guard could not fire. `newest_id >= oldest_id` over
#     max(ids) and min(ids) of the SAME list is arithmetically impossible to
#     falsify. PROVED: replacing the branch's return with a raise ran the suite
#     to 41 passed. Fed the real 6669/6666/6662 shape out of time order,
#     reversed ids, and a newest row carrying the smallest id, every one
#     printed NOT REACHED. Also from that run: counted_from_id was paired with
#     a DIFFERENT row's counted_from_moment.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label, rows",
    [
        (
            "the real 6669/6666/6662 shape out of time order",
            [
                _row("6669", "success", "2026-09-10T12:00:00Z"),
                _row("6666", "success", "2026-09-10T14:00:00Z"),
                _row("6662", "success", "2026-09-10T10:00:00Z"),
            ],
        ),
        (
            "ids reversed against the clock",
            [
                _row("100", "success", "2026-09-10T12:00:00Z"),
                _row("200", "success", "2026-09-10T11:00:00Z"),
                _row("300", "success", "2026-09-10T10:00:00Z"),
            ],
        ),
        (
            "the newest row carrying the smallest id",
            [
                _row("1", "success", "2026-09-10T18:00:00Z"),
                _row("6412", "success", "2026-09-10T12:00:00Z"),
                _row("6292", "success", "2026-09-09T12:00:00Z"),
            ],
        ),
    ],
)
def test_the_monotonicity_guard_actually_fires(label: str, rows: List[Dict[str, Any]]) -> None:
    window = tel.measure_window([tel.read_row(row) for row in rows], False)
    assert window["id_order_matches_time"] is False, f"the guard did not fire on {label}"
    assert window["id_order_inversions"] >= 1
    assert "smaller id" in window["id_order_note"]
    # A gap that is not a count is not reported as one.
    assert window["ids_in_span"] is None
    assert window["not_saved_in_span"] is None
    rate = tel.measure_rate(window)
    assert rate["basis"] == "unavailable"
    assert rate["per_day"] is None
    # The rate REFUSES and says so in the short form. The 40 word note naming
    # the offending pair lives on the window and is rendered once, on the
    # instance's card: the version of this that put the full note in the rate
    # reason as well as in the window note and again in payload.findings made a
    # two instance panel carry the same paragraph six times.
    assert rate["reason"] == tel.ID_ORDER_SHORT
    assert "smaller id" not in rate["reason"]
    assert window["id_order_summary"] == tel.ID_ORDER_SHORT


def test_a_monotonic_window_is_confirmed_so_the_guard_is_two_sided() -> None:
    window = tel.measure_window([tel.read_row(row) for row in WINDOW_ROWS], False)
    assert window["id_order_matches_time"] is True
    assert window["id_order_inversions"] == 0
    assert tel.measure_rate(window)["basis"] == "id_delta"


def test_the_measured_descending_shape_reads_as_monotonic() -> None:
    """MEASURED 2026-09-10: the executions came back newest first with ids
    descending, 6679, 6675, 6671, 6669, 6666, 6662, gaps of two to four. No
    inversion was observed in any of the 32 sampled rows.
    """
    ids = [6679, 6675, 6671, 6669, 6666, 6662]
    rows = [
        tel.read_row(_row(str(value), "success", f"2026-09-10T{12 - index:02d}:00:00Z"))
        for index, value in enumerate(ids)
    ]
    window = tel.measure_window(rows, False)
    assert window["ids_read"] == 6
    assert window["id_order_matches_time"] is True
    assert window["newest_id"] == 6679 and window["oldest_id"] == 6662
    # 18 ids across the span, 6 of them saved.
    assert window["ids_in_span"] == 18
    assert window["not_saved_in_span"] == 12


def test_too_few_dated_ids_claims_monotonicity_in_neither_direction() -> None:
    single = tel.measure_window(
        [tel.read_row(_row("10", "success", "2026-09-10T12:00:00Z"))], False
    )
    assert single["id_order_matches_time"] is None
    assert "neither confirmed nor denied" in single["id_order_note"]
    assert tel.measure_rate(single)["basis"] == "unavailable"


def test_executions_stamped_with_the_same_instant_are_not_an_inversion() -> None:
    """Two rows at one instant have no order between them, so neither ordering
    of their ids is evidence either way.

    NF-D, CLOSED. This asserted `True`, which was a claim that a comparison had
    passed when no comparison had been made: every pair hit the `continue` in
    `_id_order` and `inversions` stayed 0. The answer is `None`, the vocabulary
    for "neither confirmed nor denied" that the one row branch already used.
    """
    window = tel.measure_window(
        [
            tel.read_row(_row("10", "success", "2026-09-10T12:00:00Z")),
            tel.read_row(_row("9", "success", "2026-09-10T12:00:00Z")),
        ],
        False,
    )
    assert window["id_order_matches_time"] is None
    assert window["id_order_inversions"] == 0
    assert "share one instant" in window["id_order_note"]
    assert "neither confirmed nor denied" in window["id_order_note"]
    assert "same instant" in tel.measure_rate(window)["reason"]


@pytest.mark.parametrize("rows_at_one_instant", [3, 8, 20])
def test_a_window_entirely_inside_one_instant_confirms_nothing(
    rows_at_one_instant: int,
) -> None:
    """NF-D at width. Twenty executions all stamped with one instant compared
    NINETEEN pairs of which every one was skipped, and the note said "id order
    matches startedAt order across the 20 executions carrying both".
    """
    window = tel.measure_window(
        [
            tel.read_row(_row(str(6400 + index), "success", "2026-09-10T12:00:00Z"))
            for index in range(rows_at_one_instant)
        ],
        False,
    )
    assert window["id_order_matches_time"] is None
    assert f"all {rows_at_one_instant} executions" in window["id_order_note"]
    # The gate refuses only on False, so an unusable delta is still not claimed
    # here: what changed is that no PASS is claimed either.
    assert tel.id_delta_refusal(window) is None
    assert tel.measure_rate(window)["basis"] == "unavailable"


def test_a_genuine_comparison_still_reports_how_many_pairs_it_made() -> None:
    """The other side of NF-D. A window that really was compared says over how
    many ordered pairs, so a `True` with a pair count of zero cannot recur
    silently.
    """
    window = tel.measure_window([tel.read_row(row) for row in WINDOW_ROWS], False)
    assert window["id_order_matches_time"] is True
    assert "over the 4 consecutive pairs" in window["id_order_note"]


async def test_a_non_monotonic_window_is_a_finding_not_only_a_field() -> None:
    payload = await tel.read_all(
        fetch=Fake(
            primary_invalid=[
                _page(
                    [
                        _row("100", "success", "2026-09-10T12:00:00Z"),
                        _row("200", "success", "2026-09-10T11:00:00Z"),
                    ]
                )
            ]
        ),
        environ=_env(),
    )
    primary = _only(payload, "primary")
    # The finding is raised, in the short form, and it points at the card.
    assert any(tel.ID_ORDER_SHORT in finding for finding in payload["findings"])
    assert any("instance card" in finding for finding in payload["findings"])
    # And the 40 word note naming the offending pair is on the payload exactly
    # once, on the window, so the panel renders it once. The count is taken over
    # the whole serialised payload rather than over the fields this test happens
    # to remember.
    assert "smaller id" in primary["window"]["id_order_note"]
    assert json.dumps(payload).count("smaller id") == 1, (
        "the full note is rendered once, on the instance card. Every extra copy of it "
        "is a red findings block diluted by one caveat."
    )


async def test_the_spend_counts_from_the_moment_of_the_id_it_used() -> None:
    """counted_from_id and counted_from_moment come from the SAME execution.

    They were `max(ids)` and `max(moments)` over the same rows, which are
    different rows the moment any row carries one half and not the other. The
    basis read coherent and was not.
    """
    rows = [
        _row("6420", "success", "2026-09-10T10:00:00Z"),
        _row("6400", "success", "2026-09-09T10:00:00Z"),
        _row("not-an-id", "success", "2026-09-10T12:00:00Z"),
    ]
    primary = await _read_primary(
        rows,
        N8N_EXECUTION_CAP="2500",
        N8N_EXECUTION_CAP_ANCHOR_ID="6400",
        N8N_EXECUTION_CAP_ANCHOR_SPENT="100",
    )
    window = primary["window"]
    assert window["newest_id"] == 6420
    assert window["newest_started_at"] == "2026-09-10T12:00:00Z"
    assert window["newest_id_started_at"] == "2026-09-10T10:00:00Z"
    cap = primary["cap"]
    assert cap["counted_from_id"] == 6420
    assert cap["counted_from_moment"] == "2026-09-10T10:00:00Z"
    assert cap["counted_from_moment"] != window["newest_started_at"]


async def test_an_id_with_no_clock_of_its_own_still_carries_the_spend() -> None:
    """The pairing rule, after the cut.

    The moment was REQUIRED while a date was counted forward from it: with no
    coherent moment there was no date. There is no date now, and the spend does
    not need one, so the spend stands and the payload says the id it was
    carried to has no clock rather than pairing it with another row's.
    """
    dateless = dict(_row("9999", "success", "2026-09-10T12:00:00Z"))
    dateless.pop("startedAt")
    primary = await _read_primary(
        list(TWO_ROW_WINDOW) + [dateless],
        N8N_EXECUTION_CAP="20000",
        N8N_EXECUTION_CAP_ANCHOR_ID="6000",
        N8N_EXECUTION_CAP_ANCHOR_SPENT="1000",
    )
    cap = primary["cap"]
    assert cap["state"] == "estimated"
    assert cap["counted_from_id"] == 9999
    assert cap["counted_from_moment"] is None
    assert cap["reason"] is None


# ---------------------------------------------------------------------------
# F8  N8N_EXECUTION_CAP_RESETS_AT was read, carried, and rendered nowhere.
#     REPRODUCED from configuration alone: cap 2500, anchor 6400/100,
#     resets_at 2026-10-01, rate 20/day gave exhausts_at 2027-01-07, a wall
#     THREE MONTHS past the stated reset. Nothing compared them.
#
#     THE WALL WAS CUT ON 2026-09-10, so the comparison between a wall and the
#     reset goes with it: there is nothing left to compare the reset WITH. What
#     survives is the reset itself, which is configuration that still reaches
#     the screen, so it must still be reported, still be judged against the
#     moment of the read, and still be refused when it is not a date. That last
#     one is the guard that would have been LOST with the projection: the only
#     statement that a configured reset is unreadable lived inside the
#     projection's reset note.
# ---------------------------------------------------------------------------

RESET_ROWS = [
    _row("6420", "success", "2026-09-10T12:00:00Z"),
    _row("6400", "success", "2026-09-09T12:00:00Z"),
]
RESET_ENV = {
    "N8N_EXECUTION_CAP": "2500",
    "N8N_EXECUTION_CAP_ANCHOR_ID": "6400",
    "N8N_EXECUTION_CAP_ANCHOR_SPENT": "100",
}


async def test_the_exact_f8_configuration_reports_the_reset_and_no_wall() -> None:
    """F8's own reproduction, re-measured after the cut.

    Same rows, same cap, same anchor, same reset. The rate that produced the
    wall is still 20 a day and the remaining count that fed it is still 2380.
    There is simply no date to be three months on the wrong side of the reset.
    """
    primary = await _read_primary(
        list(RESET_ROWS), **RESET_ENV, N8N_EXECUTION_CAP_RESETS_AT="2026-10-01"
    )
    cap = primary["cap"]
    assert primary["rate"]["per_day"] == 20.0
    assert cap["remaining_estimate"] == 2380
    assert cap["resets_at"] == "2026-10-01"
    assert cap["reset_readable"] is True
    assert cap["reset_in_the_past"] is False
    assert "projection" not in cap
    assert "2027-01-07" not in json.dumps(primary)


async def test_a_reset_ahead_of_the_read_and_one_behind_it_are_told_apart() -> None:
    """The reset is still judged against the moment of the read, because a
    cycle boundary that has already turned over is stale configuration and the
    panel says so beside it.
    """
    ahead = await _read_primary(
        list(RESET_ROWS), **RESET_ENV, N8N_EXECUTION_CAP_RESETS_AT="2027-06-01"
    )
    assert ahead["cap"]["reset_in_the_past"] is False
    behind = await _read_primary(
        list(RESET_ROWS), **RESET_ENV, N8N_EXECUTION_CAP_RESETS_AT="2026-09-01"
    )
    assert behind["cap"]["reset_in_the_past"] is True


async def test_no_stated_reset_states_nothing_and_invents_nothing() -> None:
    primary = await _read_primary(list(RESET_ROWS), **RESET_ENV)
    cap = primary["cap"]
    assert cap["resets_at"] is None
    assert cap["reset_readable"] is None
    assert cap["reset_in_the_past"] is None
    assert cap["orphan_reset"] is None


async def test_a_reset_that_is_not_a_date_is_refused_and_named() -> None:
    """THE GUARD THE CUT WOULD HAVE TAKEN WITH IT.

    "the first of the month" is not a date. The only place that was ever said
    was the projection's reset note, so deleting the projection without this
    would have left `resets_at` travelling to the panel and being printed
    verbatim as a cycle boundary.
    """
    primary = await _read_primary(
        list(RESET_ROWS), **RESET_ENV, N8N_EXECUTION_CAP_RESETS_AT="the first of the month"
    )
    cap = primary["cap"]
    assert cap["reset_readable"] is False
    assert cap["reset_in_the_past"] is None
    assert any("could not be read as a date" in problem for problem in cap["problems"])


async def test_the_reset_travels_even_when_no_spend_was_estimated() -> None:
    primary = await _read_primary(
        list(WINDOW_ROWS), N8N_EXECUTION_CAP="2500", N8N_EXECUTION_CAP_RESETS_AT="2026-10-01"
    )
    assert primary["cap"]["state"] == "stated"
    assert primary["cap"]["resets_at"] == "2026-10-01"


# ---------------------------------------------------------------------------
# F9  server half. readProjection and readCap validated presence, not type or
#     sanity, and `_int_env` accepted N8N_EXECUTION_CAP=-100 with no reported
#     problem. The reader half is in n8n-telemetry-check.ts; this is the
#     configuration that fed it.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", ["0", "-1", "-100"])
async def test_a_cap_below_one_is_refused_and_named(raw: str) -> None:
    primary = await _read_primary(list(WINDOW_ROWS), N8N_EXECUTION_CAP=raw)
    cap = primary["cap"]
    assert cap["state"] == "not_stated"
    assert cap["cap"] is None
    assert cap["spent_estimate"] is None
    assert cap["used_fraction"] is None
    assert any("below 1" in problem for problem in cap["problems"])


@pytest.mark.parametrize(
    "variable", ["N8N_EXECUTION_CAP_ANCHOR_ID", "N8N_EXECUTION_CAP_ANCHOR_SPENT"]
)
async def test_a_negative_anchor_number_is_refused_and_named(variable: str) -> None:
    environment = {
        "N8N_EXECUTION_CAP": "2500",
        "N8N_EXECUTION_CAP_ANCHOR_ID": "6265",
        "N8N_EXECUTION_CAP_ANCHOR_SPENT": "1212",
    }
    environment[variable] = "-999"
    primary = await _read_primary(list(WINDOW_ROWS), **environment)
    cap = primary["cap"]
    assert cap["state"] == "stated"
    assert cap["spent_estimate"] is None
    assert "no source" in cap["reason"]
    assert any("below 0" in problem for problem in cap["problems"])


async def test_a_refused_configuration_number_is_a_payload_finding() -> None:
    payload = await tel.read_all(
        fetch=Fake(primary_invalid=[_page(WINDOW_ROWS)]),
        environ=_env(N8N_EXECUTION_CAP="-100"),
    )
    assert any(
        "N8N_EXECUTION_CAP" in finding and "below 1" in finding for finding in payload["findings"]
    )


def test_a_hand_built_cap_that_is_not_a_ceiling_is_unusable_not_drawn() -> None:
    """`read_plan` refuses these before `read_cap` sees them, so this is the
    branch a direct caller takes. It is a branch rather than an assumption
    because cap 0 divided into a used fraction and cap -100 drew a full red bar
    reading "-110 left".
    """
    window = tel.measure_window([tel.read_row(row) for row in WINDOW_ROWS], False)
    for ceiling in (0, -100):
        cap = tel.read_cap(
            tel.Plan(
                cap=ceiling,
                anchor_id=6265,
                anchor_spent=1212,
                anchor_at=None,
                resets_at=None,
                problems=(),
            ),
            window,
            _NOW,
        )
        assert cap["state"] == "unusable", ceiling
        assert cap["spent_estimate"] is None
        assert cap["remaining_estimate"] is None
        assert cap["used_fraction"] is None
        assert "nothing to measure a burn against" in cap["reason"]
        assert any("not a ceiling" in problem for problem in cap["problems"])


def test_a_rate_that_is_not_a_finite_positive_number_states_no_rate() -> None:
    """The route's own gate on the rate, independent of the reader's.

    This used to drive a hand built rate into `read_cap` and prove no date came
    out of it. `read_cap` no longer takes a rate at all: the rate fed exactly
    one thing, the days the remaining count divided into, and that is cut. So
    the gate that survives is `measure_rate`'s own, and this drives the same
    impossible values through the function that still has to refuse them.
    """
    for seconds in (0.0, -3600.0):
        window = tel.measure_window([tel.read_row(row) for row in WINDOW_ROWS], False)
        window["rate_span_seconds"] = seconds
        rate = tel.measure_rate(window)
        assert rate["basis"] == "unavailable", seconds
        assert rate["per_day"] is None, seconds
    # And `read_cap` cannot be handed one by accident: it takes three arguments
    # and none of them is a rate.
    assert list(inspect.signature(tel.read_cap).parameters) == ["plan", "window", "read_at"]


# ===========================================================================
# CYCLE TWO. Three BLOCKING arithmetic findings from the 2026-09-10 arithmetic
# adversary, each reproduced through the mounted route before it was fixed, and
# each fixed at the CLASS rather than at the input that found it.
# ===========================================================================

# ---------------------------------------------------------------------------
# NF1  a NEGATIVE execution id was deliberately admitted, and one row moved the
#      wall to 93 seconds away.
#
#      REPRODUCED at HTTP 200 through the mounted route, cap 2500 / anchor 6000
#      / spent 1000, rows id "6412"@2026-09-10T12:00Z and id
#      "-1000000"@2026-09-09T12:00Z:
#        per_day 1006412.0, not_saved_in_span 1006411, days_left 0.0,
#        exhausts_at 2026-09-10T12:01:33Z, read_problems []
#      The truth from those two rows is per_day 120.0 and a wall nine days out.
#      The CLASS is the parser's domain: `_row_id` stripped a leading "-" and
#      bounded with abs(), so the accepted set and the documented set disagreed.
# ---------------------------------------------------------------------------

# The whole sign, whitespace, boundary and non-digit table, in one place, so the
# accepted set is asserted rather than described. `-5` is the case cycle one's
# table missed: it carried `+5` and `--5` and not the single minus between them.
_ID_DOMAIN_TABLE: List[Any] = [
    # (input, expected)
    ("6412", 6412),
    (" 6412 ", 6412),
    (6412, 6412),
    ("0", 0),
    (0, 0),
    # every sign form, refused at the sign rather than parsed and bounded
    ("-5", None),
    ("-1000000", None),
    ("+5", None),
    ("--5", None),
    ("- 5", None),
    ("-0", None),
    ("−5", None),     # U+2212 MINUS SIGN, not ASCII
    ("5-", None),
    (-5, None),
    (-1, None),
    (-(10 ** 15), None),
    # the upper boundary, both sides
    (10 ** 15, 10 ** 15),
    (10 ** 15 + 1, None),
    (str(10 ** 15), 10 ** 15),
    (str(10 ** 15 + 1), None),
    ("9" * 20, None),
    # not a digit string at all
    ("²", None),
    ("٣", None),
    ("1٣5", None),
    ("6412.0", None),
    ("6_412", None),
    ("", None),
    ("   ", None),
    (None, None),
    (True, None),
    (False, None),
    (6412.0, None),
    ([6412], None),
]


@pytest.mark.parametrize("value, expected", _ID_DOMAIN_TABLE)
def test_the_id_parser_admits_exactly_the_documented_domain(value: Any, expected: Any) -> None:
    """The accepted set is `0 <= id <= MAX_EXECUTION_ID` and nothing else.

    This is the class, not the instance. `_row_id('-1000000')` returned
    -1000000 because the bound was written out twice, once with `abs()` and once
    after stripping a sign, and the two statements of the domain disagreed.
    `_ID_DOMAIN` is now the only statement of it and both branches go through it,
    so a sign form cannot reach `int()` at all.
    """
    assert tel._row_id(value) == expected, f"{value!r} was read as {tel._row_id(value)!r}"


def test_the_id_domain_predicate_is_the_only_statement_of_the_bound() -> None:
    """The structural half. Two copies of a bound are how the first one drifted.

    `MAX_EXECUTION_ID` may be named inside `_ID_DOMAIN` and nowhere else in the
    module's executable code, so no second comparison can be written that
    disagrees with the first. A comment naming it is not an offence; an
    expression is.
    """
    tree = ast.parse(SERVICE_FILE.read_text())
    offences: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name == "_ID_DOMAIN":
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and inner.id == "MAX_EXECUTION_ID":
                offences.append(f"{node.name} at line {inner.lineno}")
    assert offences == [], (
        "the id bound is stated in _ID_DOMAIN and compared nowhere else: " + ", ".join(offences)
    )


async def test_a_negative_id_cannot_move_the_rate_the_span_or_the_spend() -> None:
    """The reproduction, through `read_all`, with the truth beside it.

    Not only the parse: the CONSEQUENCE. The negative row is dropped from the
    arithmetic, counted as a row without a usable id, and the two figures a
    reader acts on come out unchanged from the clean two row window.
    """
    hostile = await _read_primary(
        [
            _row("6412", "success", "2026-09-10T12:00:00Z"),
            _row("-1000000", "success", "2026-09-09T12:00:00Z"),
        ],
        **CAP_ENV,
    )
    window = hostile["window"]
    assert window["oldest_id"] == 6412
    assert window["newest_id"] == 6412
    assert window["ids_read"] == 1
    # The row is still SHOWN and still counted; it takes no part in any number.
    assert window["executions_read"] == 2
    assert window["rows_without_id"] == 1
    assert window["not_saved_in_span"] == 0
    assert hostile["rate"]["per_day"] is None
    # The spend is still carried forward, because it needs one id and not a
    # span, and the id it uses is the real one rather than the negative.
    assert hostile["cap"]["counted_from_id"] == 6412

    # And the same window with a real oldest id gives the numbers the negative
    # one displaced: 120 a day and 119 unsaved ids in the span, not a per_day of
    # 1006412 over a span of 1006413 ids.
    truth = await _read_primary(list(TWO_ROW_WINDOW), **CAP_ENV)
    assert truth["rate"]["per_day"] == 120.0
    assert truth["window"]["not_saved_in_span"] == 119
    assert truth["window"]["ids_in_span"] == 121


@pytest.mark.parametrize(
    "hostile_id", ["-1000000", "-1", "-999999999999999", "−5", "+6413"]
)
async def test_no_sign_form_on_an_id_can_reach_the_arithmetic(hostile_id: str) -> None:
    """Three more shapes than the one that found it, plus the unicode minus.

    Each one paired with a real id 6412: if any were admitted, `ids_in_span`
    would blow up and the rate with it. The assertion is on the derived numbers
    rather than on the parse, because the parse is only interesting for what it
    lets through.
    """
    primary = await _read_primary(
        [
            _row("6412", "success", "2026-09-10T12:00:00Z"),
            _row(hostile_id, "success", "2026-09-09T12:00:00Z"),
        ],
        **CAP_ENV,
    )
    assert primary["window"]["ids_read"] == 1, hostile_id
    assert primary["window"]["ids_in_span"] == 1, hostile_id
    assert primary["window"]["rows_without_id"] == 1, hostile_id
    assert primary["rate"]["basis"] == "unavailable", hostile_id


# ---------------------------------------------------------------------------
# NF2  the spend was computed from an id gap the SAME payload had just declared
#      unusable.
#
#      REPRODUCED, rows 6669@12:00, 6666@14:00, 6662@16:00 with cap 2500 and
#      anchor 6000/1000: ONE payload reported id_order_matches_time False,
#      2 inversions, ids_in_span None, not_saved_in_span None, the rate refused
#      AND cap state estimated with spent_estimate 1669, remaining 831 and
#      used_fraction 0.6676, drawn as a 67 percent burn bar.
#      The CLASS is that the question "may an id delta be used here" was
#      answered separately by each consumer, so one consumer was missed.
# ---------------------------------------------------------------------------

INVERTED_ROWS = [
    _row("6669", "success", "2026-09-10T12:00:00Z"),
    _row("6666", "success", "2026-09-10T14:00:00Z"),
    _row("6662", "success", "2026-09-10T16:00:00Z"),
]


async def test_a_refused_id_gap_cannot_become_a_spend_a_remaining_or_a_bar() -> None:
    primary = await _read_primary(list(INVERTED_ROWS), **CAP_ENV)
    window, cap = primary["window"], primary["cap"]
    # The payload still says WHY, in full, once.
    assert window["id_order_matches_time"] is False
    assert window["id_order_inversions"] == 2
    assert window["ids_in_span"] is None
    assert window["not_saved_in_span"] is None
    assert primary["rate"]["basis"] == "unavailable"
    # And now the cap agrees with the column beside it.
    assert cap["state"] == "stated", "an id gap that is not a count is not a spend"
    assert cap["spent_estimate"] is None
    assert cap["remaining_estimate"] is None
    assert cap["used_fraction"] is None
    assert cap["counted_from_id"] is None
    # The reason carries the FULL refusal, which is the note naming the pair.
    # The short form is what goes in `problems`, and from there into findings.
    assert "ids contradict its clock" in cap["reason"]
    assert "smaller id" in cap["reason"]
    assert any(tel.ID_ORDER_SHORT in problem for problem in cap["problems"])


def test_no_consumer_reads_the_id_order_column_outside_the_gate() -> None:
    """The structural half, and the actual class closer.

    `id_order_matches_time` may be read by `id_delta_refusal` and written by
    `measure_window`, and by nothing else. The finding was not that one
    comparison was missing; it was that the comparison was open coded in each
    consumer, so a new consumer could be written without one and nothing would
    say so. This test is what says so.
    """
    tree = ast.parse(SERVICE_FILE.read_text())
    allowed = {"id_delta_refusal", "measure_window"}
    offences: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name in allowed:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and inner.value == "id_order_matches_time":
                offences.append(f"{node.name} at line {inner.lineno}")
    assert offences == [], (
        "every id delta consumer goes through id_delta_refusal: " + ", ".join(offences)
    )


def test_the_id_delta_gate_is_not_vacuous() -> None:
    """Both directions, because a gate that always refuses is not a gate."""
    monotonic = tel.measure_window([tel.read_row(r) for r in WINDOW_ROWS], False)
    assert tel.id_delta_refusal(monotonic) is None
    inverted = tel.measure_window([tel.read_row(r) for r in INVERTED_ROWS], False)
    refusal = tel.id_delta_refusal(inverted)
    assert refusal is not None
    assert "smaller id" in refusal
    # None, meaning too few dated ids to say, is not a refusal either.
    thin = tel.measure_window(
        [tel.read_row(_row("6412", "success", "2026-09-10T12:00:00Z"))], False
    )
    assert thin["id_order_matches_time"] is None
    assert tel.id_delta_refusal(thin) is None


@pytest.mark.parametrize(
    "label, rows",
    [
        (
            "one inversion at the newest end only",
            [
                _row("6600", "success", "2026-09-10T16:00:00Z"),
                _row("6700", "success", "2026-09-10T14:00:00Z"),
                _row("6500", "success", "2026-09-10T12:00:00Z"),
            ],
        ),
        (
            "an inversion of exactly one id",
            [
                _row("6412", "success", "2026-09-10T13:00:00Z"),
                _row("6413", "success", "2026-09-10T12:00:00Z"),
            ],
        ),
        (
            "ids equal at both ends with a dip between",
            [
                _row("6500", "success", "2026-09-10T12:00:00Z"),
                _row("6400", "success", "2026-09-10T13:00:00Z"),
                _row("6600", "success", "2026-09-10T14:00:00Z"),
            ],
        ),
    ],
)
async def test_three_more_inversion_shapes_cannot_produce_a_spend(
    label: str, rows: List[Dict[str, Any]]
) -> None:
    """Three shapes the finding did not use, against the same gate."""
    primary = await _read_primary(list(rows), **CAP_ENV)
    assert primary["window"]["id_order_matches_time"] is False, label
    assert primary["cap"]["spent_estimate"] is None, label
    assert primary["cap"]["used_fraction"] is None, label
    assert primary["cap"]["state"] == "stated", label


# ---------------------------------------------------------------------------
# NF3  the wall could be in the PAST, and nothing compared any date with now.
#
#      REPRODUCED, rows 6412@2024-01-10T12:00Z and 6292@2024-01-09T12:00Z with
#      cap 2500 and anchor 6000/1000: state derived, exhausts_at
#      2024-01-19T13:36:00Z, twenty months behind the read. A year-1 startedAt
#      rendered exhausts_at 0001-01-19. Cycle two answered it with a `stale`
#      state and a one sided inequality, and a THIRD adversary walked through
#      the other side of it: a FUTURE dated basis rendered
#      "Projected exhaustion 2027-09-10 21:00:00 UTC, in about 0.38 days,
#      measured against a read at 2026-09-10 13:00:00 UTC" with tone GOOD, a
#      date and a day count 365 days apart on one line.
#
#      CLOSED BY CONSTRUCTION ON 2026-09-10. `exhausts_at` was the only derived
#      date on the wire and Tee cut it. There is no wall to be on the wrong
#      side of the read, so the finding has no subject rather than a fixed one.
#      The tests below drive the exact inputs of BOTH sides and assert the
#      absence rather than a corrected date.
# ---------------------------------------------------------------------------

STALE_ROWS = [
    _row("6412", "success", "2024-01-10T12:00:00Z"),
    _row("6292", "success", "2024-01-09T12:00:00Z"),
]

# The third adversary's exact input, verbatim from the finding: three rows an
# hour apart stamped a year AHEAD of the read, an anchor one id behind the
# newest, and 10 of the cap left.
NF3_FUTURE_ROWS = [
    _row("6412", "success", "2027-09-10T12:00:00Z"),
    _row("6411", "success", "2027-09-10T11:00:00Z"),
    _row("6410", "success", "2027-09-10T10:00:00Z"),
]
NF3_FUTURE_ENV = {
    "N8N_EXECUTION_CAP": "2500",
    "N8N_EXECUTION_CAP_ANCHOR_ID": "6411",
    "N8N_EXECUTION_CAP_ANCHOR_SPENT": "2490",
}


async def test_the_exact_nf3_future_basis_produces_no_wall_to_be_wrong_about(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NF3's own input, driven through the MOUNTED ROUTE at the pinned read.

    The numbers the wall was derived from all still come out, and every one of
    them is checked here so that "there is no wall" cannot be confused with
    "there is nothing": 2 ids across 2 hours is 24 a day, the anchor at 6411
    carries 2490 forward to 6412 for a spend of 2491 against 2500, and 9 remain.
    9 at 24 a day was the 0.38 days the finding quoted, and 0.38 days past a
    basis of 2027-09-10T12:00Z was the 2027-09-10 21:00 UTC it printed beside a
    read of 2026-09-10 13:00.

    What is asserted is that no date, no day count and no projection state
    appears anywhere in the serialised payload the route actually returns.
    """
    _clear(monkeypatch)
    monkeypatch.setenv("N8N_API_URL", f"https://{PRIMARY_HOST}")
    monkeypatch.setenv("N8N_API_KEY", PRIMARY_KEY)
    for name, value in NF3_FUTURE_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(tel, "_httpx_get", Fake(primary_invalid=[_page(NF3_FUTURE_ROWS)]))

    response = _client().get("/api/v1/n8n/executions")
    assert response.status_code == 200
    body = response.json()
    primary = _only(body, "primary")
    cap = primary["cap"]

    # Everything the wall rested on is still here and still correct.
    assert primary["rate"]["per_day"] == 24.0
    assert cap["state"] == "estimated"
    assert cap["spent_estimate"] == 2491
    assert cap["remaining_estimate"] == 9
    assert cap["counted_from_id"] == 6412
    assert cap["counted_from_moment"] == "2027-09-10T12:00:00Z"

    # And there is no wall.
    assert "projection" not in cap
    serialised = json.dumps(body)
    for gone in ("exhausts_at", "days_left", "2027-09-10T21:00", "Projected exhaustion", "0.38"):
        assert gone not in serialised, f"{gone} survived the cut"
    # AND EVERY DATE ON THE PAYLOAD IS ONE THE ROUTE DID NOT COMPUTE. Every
    # timestamp in the serialised body must be either an observed startedAt from
    # one of the three rows or the moment of the read itself. A date that is
    # neither is a date this route made up, which is the whole of NF3.
    observed = {row["startedAt"] for row in NF3_FUTURE_ROWS}
    allowed = observed | {body["read_at"], cap["read_at"]}
    seen = set(re.findall(r"\d{4}-\d{2}-\d{2}T[0-9:.]+(?:Z|\+00:00)", serialised))
    assert seen <= allowed, f"the route produced a date nothing observed: {sorted(seen - allowed)}"
    assert observed <= seen, "the observed row timestamps must still be reported"


@pytest.mark.parametrize(
    "label, started_newest, started_oldest",
    [
        ("the finding's own twenty month old window", "2024-01-10T12:00:00Z", "2024-01-09T12:00:00Z"),
        ("a year one clock", "0001-01-10T12:00:00Z", "0001-01-09T12:00:00Z"),
        ("the unix epoch", "1970-01-10T12:00:00Z", "1970-01-09T12:00:00Z"),
        ("ten days before the read", "2026-08-31T12:00:00Z", "2026-08-30T12:00:00Z"),
        ("a month before the read", "2026-08-10T12:00:00Z", "2026-08-09T12:00:00Z"),
        ("two hours after the read", "2026-09-10T15:00:00Z", "2026-09-09T15:00:00Z"),
    ],
)
async def test_no_window_on_either_side_of_the_read_produces_a_date(
    label: str, started_newest: str, started_oldest: str
) -> None:
    """Every shape either adversary used, plus the skew case, against the cut.

    Behind the read, absurdly behind it, and ahead of it. None of them can
    produce a wall, because the arithmetic that produced one is not in the
    module. The remaining count still comes out for every one of them, which is
    the half of the panel Tee kept.
    """
    primary = await _read_primary(
        [
            _row("6412", "success", started_newest),
            _row("6292", "success", started_oldest),
        ],
        **CAP_ENV,
    )
    cap = primary["cap"]
    assert cap["remaining_estimate"] == 1088, label
    assert "projection" not in cap, label
    assert "exhausts_at" not in json.dumps(primary), label


def test_the_module_can_no_longer_derive_a_date_at_all() -> None:
    """THE CLASS, structurally. NF3 was possible because a date was COMPUTED.

    Every date this payload carries must be observed from an execution row,
    stated by configuration, or the moment of the read. Producing a NEW datetime
    in Python needs a `timedelta`, so the guarantee is that `timedelta` is named
    nowhere in this module. Subtracting two datetimes to compare them yields a
    duration rather than a date and needs no import, which is what still tells a
    reader that a configured cycle reset has turned over.

    The whole projection vocabulary is named alongside it, so a partial revival
    fails here rather than in a review.
    """
    source = SERVICE_FILE.read_text()
    tree = ast.parse(source)
    # `timedelta` by SYNTAX rather than by substring: the module's own comment
    # about an id delta no timedelta can carry is prose, and a test that reads
    # prose as code is the shape of guard this estate keeps getting wrong.
    named = [
        node.lineno
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == "timedelta")
        or (isinstance(node, ast.Attribute) and node.attr == "timedelta")
        or (isinstance(node, ast.alias) and node.name == "timedelta")
    ]
    assert named == [], f"a timedelta is how a new date gets made, at line(s) {named}"
    # The rest of the projection vocabulary, also by syntax. A payload key is a
    # string CONSTANT that equals the key exactly, and an identifier is a Name
    # or an Attribute. The module docstring naming `exhausts_at` in the note
    # that records what was cut is prose, and prose is not a revival: reading it
    # as one is the same mistake as the timedelta comment one line up.
    gone = (
        "projection",
        "exhausts_at",
        "exhausts_before_reset",
        "reset_note",
        "MAX_PROJECTION_DAYS",
        "beyond_horizon",
        "days_left",
        "basis_age_hours",
    )
    offences: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in gone:
            offences.append(f'the key "{node.value}" at line {node.lineno}')
        if isinstance(node, ast.Name) and node.id in gone:
            offences.append(f"the name {node.id} at line {node.lineno}")
        if isinstance(node, ast.Attribute) and node.attr in gone:
            offences.append(f"the attribute {node.attr} at line {node.lineno}")
    assert offences == [], "the projection was cut: " + "; ".join(offences)


# ---------------------------------------------------------------------------
# The lower findings that live on the server side.
# ---------------------------------------------------------------------------

async def test_a_reset_stated_with_no_cap_is_a_configuration_problem() -> None:
    """The orphan reset. It rendered two contradictory adjacent sentences: "No
    cap is configured for this instance" and then "The plan cycle is stated by
    configuration to reset 2026-10-01".
    """
    primary = await _read_primary(
        list(WINDOW_ROWS), N8N_EXECUTION_CAP_RESETS_AT="2026-10-01"
    )
    cap = primary["cap"]
    assert cap["state"] == "not_stated"
    assert cap["orphan_reset"] is not None
    assert "no cap is configured at all" in cap["orphan_reset"]
    assert any("no cap is configured at all" in p for p in cap["problems"])
    # And it reaches the findings block, because it is a configuration error
    # rather than a caveat.
    payload = await tel.read_all(
        fetch=Fake(primary_invalid=[_page(list(WINDOW_ROWS))]),
        environ=_env(N8N_EXECUTION_CAP_RESETS_AT="2026-10-01"),
        read_at=_NOW,
    )
    assert any("unset the reset" in finding for finding in payload["findings"])


async def test_a_cap_with_a_reset_reports_no_orphan() -> None:
    primary = await _read_primary(
        list(TWO_ROW_WINDOW), None, **CAP_ENV, N8N_EXECUTION_CAP_RESETS_AT="2026-10-01"
    )
    assert primary["cap"]["orphan_reset"] is None
    assert primary["cap"]["problems"] == []


@pytest.mark.parametrize(
    "label, seconds, expected_per_day",
    [
        # NF6. `rate_span_hours` was round(..., 3) and was ALSO the denominator.
        # A four second span rounds 0.001111 to 0.001, which overstates by 11
        # percent; a one second span rounds to 0.0 and the rate was refused.
        ("one second", 1.0, 86400.0),
        ("four seconds", 4.0, 21600.0),
        ("thirty six seconds", 36.0, 2400.0),
        ("one hour", 3600.0, 24.0),
    ],
)
def test_the_rate_divides_by_the_exact_span_not_the_rounded_one(
    label: str, seconds: float, expected_per_day: float
) -> None:
    newest = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    oldest = newest - timedelta(seconds=seconds)
    window = tel.measure_window(
        [
            tel.read_row(_row("6413", "success", tel._iso(newest))),
            tel.read_row(_row("6412", "success", tel._iso(oldest))),
        ],
        False,
    )
    assert window["rate_span_seconds"] == seconds, label
    rate = tel.measure_rate(window)
    assert rate["basis"] == "id_delta", f"{label}: {rate.get('reason')}"
    assert rate["per_day"] == expected_per_day, label
    # The rounded form still travels, for display, and is not the denominator.
    assert window["rate_span_hours"] == round(seconds / 3600.0, 3), label


def test_the_span_coverage_fraction_is_on_the_payload() -> None:
    """What fraction of the id span has a saved row. The number `readInstance`
    needs to stop calling a two row read of a twenty one id span a clean bill of
    health.
    """
    window = tel.measure_window(
        [
            tel.read_row(_row("6400", "success", "2026-09-10T12:00:00Z")),
            tel.read_row(_row("6380", "success", "2026-09-09T12:00:00Z")),
        ],
        False,
    )
    assert window["ids_in_span"] == 21
    assert window["ids_read"] == 2
    assert window["not_saved_in_span"] == 19
    assert window["span_coverage"] == round(2 / 21, 4)
    complete = tel.measure_window(
        [
            tel.read_row(_row("6401", "success", "2026-09-10T12:00:00Z")),
            tel.read_row(_row("6400", "success", "2026-09-09T12:00:00Z")),
        ],
        False,
    )
    assert complete["not_saved_in_span"] == 0
    assert complete["span_coverage"] == 1.0


# The KEYS, not only the verdict column. `test_no_consumer_reads_the_id_order_
# column_outside_the_gate` above guards the column; this guards the numbers the
# column is about, and it exists because an adversarial pass against the fix
# found the hole: a consumer can derive a spend from `window["newest_id"]`
# WITHOUT ever naming `id_order_matches_time`, and the column guard would not
# fire. That is the same class arriving by the other door.
_ID_DELTA_KEYS = (
    "newest_id",
    "oldest_id",
    "rate_from_id",
    "rate_to_id",
    "ids_in_span",
)


def test_no_function_derives_from_an_id_key_without_calling_the_gate() -> None:
    """Any function that reads an id delta bearing window key must call
    `id_delta_refusal` in the same function.

    `measure_window` is the one exemption, because it BUILDS those keys: it is
    the measurement, not a consumer of it.
    """
    tree = ast.parse(SERVICE_FILE.read_text())
    offences: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "measure_window":
            continue
        keys_read = sorted(
            {
                inner.value
                for inner in ast.walk(node)
                if isinstance(inner, ast.Constant) and inner.value in _ID_DELTA_KEYS
            }
        )
        if not keys_read:
            continue
        calls_gate = any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "id_delta_refusal"
            for inner in ast.walk(node)
        )
        if not calls_gate:
            offences.append(f"{node.name} reads {', '.join(keys_read)} and never calls the gate")
    assert offences == [], (
        "an id gap is only a count when the gate says so, and the gate has to be asked in the "
        "same function that uses the gap: " + "; ".join(offences)
    )


def test_the_id_key_guard_is_not_vacuous() -> None:
    """The guard above, run against a source that violates it.

    A structural test that has never been shown to fire is a structural test that
    has never been shown to fire, and this one is cheap to prove: parse a
    synthetic module rather than mutating the real one.
    """
    hostile = (
        "def read_cap(plan, window, read_at):\n"
        "    spent = plan.anchor_spent + (window.get('newest_id') - plan.anchor_id)\n"
        "    return spent\n"
    )
    tree = ast.parse(hostile)
    offences: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "measure_window":
            continue
        keys_read = {
            inner.value
            for inner in ast.walk(node)
            if isinstance(inner, ast.Constant) and inner.value in _ID_DELTA_KEYS
        }
        if not keys_read:
            continue
        calls_gate = any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "id_delta_refusal"
            for inner in ast.walk(node)
        )
        if not calls_gate:
            offences.append(node.name)
    assert offences == ["read_cap"], f"the guard did not see the violation: {offences}"

    # And the real module's own read_cap, which DOES call the gate, must not be an
    # offence: a guard that flags the correct shape is no guard.
    clean = (
        "def read_cap(plan, window, read_at):\n"
        "    refusal = id_delta_refusal(window)\n"
        "    if refusal is not None:\n"
        "        return None\n"
        "    return window.get('newest_id')\n"
    )
    tree = ast.parse(clean)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "read_cap":
            assert any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "id_delta_refusal"
                for inner in ast.walk(node)
            )
