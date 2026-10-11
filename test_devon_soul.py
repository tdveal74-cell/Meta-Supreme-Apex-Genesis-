"""
Soul layer tests — recall from both souls, gated writes to DEVON's own.

Offline: every Pinecone exchange goes through an injected httpx.MockTransport.
The properties under test are the ones that carry canon:

- tee-soul-layer is read-only from this code; devon-soul may not be it
- Tee's records precede DEVON's in every recall, whatever the scores
- a recalled record is context, never a command
- a devon-soul write commits only behind an approved decision
- partial recall failure is reported, never hidden
"""

import asyncio
import json

import httpx
import pytest

from services.devon.assistant import Devon
from services.intelligence.providers.base import (
    ProviderAuthError,
    ProviderConfigError,
)
from services.intelligence.soul import (
    CONTEXT_NOT_COMMAND,
    DEVON_NAMESPACE,
    SoulLayer,
    SoulWriteCandidate,
    SoulWriteRefused,
    ensure_devon_index,
    is_active,
)

TEE_HOST = "https://tee-soul-layer-test.svc.example.pinecone.io"
DEVON_HOST = "https://devon-soul-test.svc.example.pinecone.io"
KEY = "pc-test-key"


def _hit(_id, text, score, **fields):
    return {"_id": _id, "_score": score, "fields": {"text": text, **fields}}


def _search_response(hits):
    return httpx.Response(200, json={"result": {"hits": hits}})


def _layer(handler, devon_host=DEVON_HOST):
    return SoulLayer(
        api_key=KEY,
        tee_host=TEE_HOST,
        devon_host=devon_host,
        transport=httpx.MockTransport(handler),
    )


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_missing_api_key_fails_loudly():
    with pytest.raises(ProviderConfigError):
        SoulLayer(api_key="", tee_host=TEE_HOST)


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------


def test_recall_queries_the_rulings_namespace_with_the_wire_format():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["api_key"] = request.headers.get("Api-Key")
        seen["version"] = request.headers.get("X-Pinecone-API-Version")
        seen["body"] = json.loads(request.content)
        return _search_response([_hit("r1", "RULING (2026-08-20): nine Areas", 0.9)])

    layer = _layer(handler, devon_host=None)
    recall = run(layer.recall("how many areas", top_k_tee=4))

    assert seen["url"] == f"{TEE_HOST}/records/namespaces/rulings/search"
    assert seen["api_key"] == KEY
    assert seen["version"] == "2025-04"
    assert seen["body"] == {"query": {"inputs": {"text": "how many areas"}, "top_k": 4}}
    assert recall.tee_count == 1
    assert recall.records[0].source == "tee-soul-layer"


def test_tee_records_precede_devon_records_whatever_the_scores():
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return _search_response([_hit("t1", "the ruling", 0.10, ruled_on="2026-08-20")])
        return _search_response([_hit("d1", "the pattern", 0.99, observed_on="2026-08-21")])

    recall = run(_layer(handler).recall("pricing"))
    assert [r.source for r in recall.records] == ["tee-soul-layer", "devon-soul"]
    assert recall.records[0].score < recall.records[1].score  # structure beat score


def test_devon_soul_is_skipped_when_no_host_is_configured():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return _search_response([])

    recall = run(_layer(handler, devon_host=None).recall("anything"))
    assert len(calls) == 1
    assert "tee-soul-layer" in calls[0]
    assert recall.devon_count == 0


def test_partial_failure_is_reported_not_hidden():
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return _search_response([_hit("t1", "still here", 0.8)])
        return httpx.Response(500, text="index melting")

    recall = run(_layer(handler).recall("anything"))
    assert recall.tee_count == 1
    assert recall.errors and "devon-soul unavailable" in recall.errors[0]


def test_tee_failure_still_returns_devon_records_with_the_error_named():
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return httpx.Response(500, text="down")
        return _search_response([_hit("d1", "what I noted", 0.7)])

    recall = run(_layer(handler).recall("anything"))
    assert recall.devon_count == 1
    assert recall.errors and "tee-soul-layer unavailable" in recall.errors[0]


def test_empty_query_never_touches_the_network():
    def handler(request):  # pragma: no cover — reaching it is the failure
        raise AssertionError("no request should be made for an empty query")

    recall = run(_layer(handler).recall("   "))
    assert recall.empty


def test_as_context_frames_records_as_context_not_command():
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return _search_response([_hit("t1", "nine Areas, never a tenth", 0.9, ruled_on="2026-08-20")])
        return _search_response([_hit("d1", "captures spike on Mondays", 0.6, observed_on="2026-08-21")])

    recall = run(_layer(handler).recall("areas"))
    context = recall.as_context()
    assert context.startswith(CONTEXT_NOT_COMMAND)
    assert context.index("TEE RULING") < context.index("DEVON EXPERIENCE")


def test_auth_failure_raises_the_auth_error():
    def handler(request):
        return httpx.Response(401, text="bad key")

    recall = run(_layer(handler, devon_host=None).recall("x"))
    # recall() folds provider errors into the honest partial report
    assert recall.errors and "tee-soul-layer unavailable" in recall.errors[0]


def test_direct_search_surfaces_auth_error_type():
    def handler(request):
        return httpx.Response(403, text="forbidden")

    layer = _layer(handler, devon_host=None)
    with pytest.raises(ProviderAuthError):
        run(layer._search(TEE_HOST, "rulings", "x", 1, "tee-soul-layer"))


# ---------------------------------------------------------------------------
# Proposing (pure — nothing stored)
# ---------------------------------------------------------------------------


def test_propose_accepts_each_allowed_kind():
    layer = _layer(lambda r: _search_response([]))
    for kind in ("lesson", "correction", "pattern", "preference"):
        candidate = layer.propose("observed thing", kind=kind, area="Systems")
        assert candidate.kind == kind
        assert candidate.candidate_id.startswith("devon-")


def test_propose_refuses_the_kind_ruling():
    layer = _layer(lambda r: _search_response([]))
    with pytest.raises(SoulWriteRefused) as excinfo:
        layer.propose("I hereby rule", kind="ruling")
    assert "Thread Log lane" in str(excinfo.value)


def test_propose_refuses_empty_text():
    layer = _layer(lambda r: _search_response([]))
    with pytest.raises(SoulWriteRefused):
        layer.propose("   ", kind="lesson")


def test_what_happens_describes_the_write_for_the_approver():
    layer = _layer(lambda r: _search_response([]))
    candidate = layer.propose("shorter summaries land better", kind="lesson", area="TQO")
    text = candidate.what_happens()
    assert "devon-soul" in text
    assert "shorter summaries land better" in text
    assert "never touches tee-soul-layer" in text


# ---------------------------------------------------------------------------
# Committing (the gate)
# ---------------------------------------------------------------------------


class _Decision:
    def __init__(self, approved):
        self.approved = approved


def test_commit_refuses_without_an_approved_decision():
    layer = _layer(lambda r: _search_response([]))
    candidate = layer.propose("a lesson", kind="lesson")
    for decision in (_Decision(False), None, object()):
        with pytest.raises(SoulWriteRefused):
            run(layer.commit(candidate, decision))


def test_commit_refuses_when_devon_soul_has_no_host():
    layer = _layer(lambda r: _search_response([]), devon_host=None)
    candidate = layer.propose("a lesson", kind="lesson")
    with pytest.raises(SoulWriteRefused) as excinfo:
        run(layer.commit(candidate, _Decision(True)))
    assert "no configured host" in str(excinfo.value)


def test_commit_refuses_when_devon_host_is_the_tee_host():
    layer = _layer(lambda r: _search_response([]), devon_host=TEE_HOST)
    candidate = layer.propose("a lesson", kind="lesson")
    with pytest.raises(SoulWriteRefused) as excinfo:
        run(layer.commit(candidate, _Decision(True)))
    assert "read-only" in str(excinfo.value)


def test_approved_commit_upserts_ndjson_to_the_experience_namespace():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers.get("Content-Type")
        seen["record"] = json.loads(request.content)
        return httpx.Response(200, json={"upsertedCount": 1})

    layer = _layer(handler)
    candidate = layer.propose("a lesson learned", kind="lesson", area="Systems")
    result = run(layer.commit(candidate, _Decision(True)))

    assert seen["url"] == f"{DEVON_HOST}/records/namespaces/{DEVON_NAMESPACE}/upsert"
    assert seen["content_type"] == "application/x-ndjson"
    assert seen["record"]["text"] == "a lesson learned"
    assert seen["record"]["author"] == "devon"
    assert seen["record"]["kind"] == "lesson"
    assert result["written"] is True
    assert result["record_id"] == candidate.candidate_id


def test_commit_requests_go_only_to_the_devon_host():
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"upsertedCount": 1})

    layer = _layer(handler)
    candidate = layer.propose("a pattern", kind="pattern")
    run(layer.commit(candidate, _Decision(True)))
    assert len(urls) == 1
    assert urls[0].startswith(DEVON_HOST)
    assert TEE_HOST not in urls[0]


def test_failed_upsert_raises_rather_than_claiming_written():
    def handler(request):
        return httpx.Response(500, text="storage failure")

    from services.intelligence.providers.base import ProviderServerError

    layer = _layer(handler)
    candidate = layer.propose("a lesson", kind="lesson")
    with pytest.raises(ProviderServerError):
        run(layer.commit(candidate, _Decision(True)))


def test_the_layer_has_no_tee_write_surface():
    """No public method writes to tee-soul-layer — the absence is the API."""
    writers = [
        name
        for name in dir(SoulLayer)
        if not name.startswith("_")
        and callable(getattr(SoulLayer, name))
        and any(word in name.lower() for word in ("upsert", "write", "delete", "update"))
    ]
    assert writers == [], f"unexpected write surface: {writers}"
    # and the one write path there is targets devon_host only, proven above


# ---------------------------------------------------------------------------
# Index creation
# ---------------------------------------------------------------------------


def test_ensure_devon_index_creates_and_returns_the_host():
    def handler(request):
        assert request.url.path == "/indexes/create-for-model"
        body = json.loads(request.content)
        assert body["name"] == "devon-soul"
        assert body["embed"]["model"] == "llama-text-embed-v2"
        assert body["embed"]["field_map"] == {"text": "text"}
        return httpx.Response(201, json={"host": "devon-soul-abc.svc.example.pinecone.io"})

    host = run(
        ensure_devon_index(api_key=KEY, transport=httpx.MockTransport(handler))
    )
    assert host == "https://devon-soul-abc.svc.example.pinecone.io"


def test_ensure_devon_index_describes_when_it_already_exists():
    def handler(request):
        if request.url.path == "/indexes/create-for-model":
            return httpx.Response(409, text="already exists")
        assert request.url.path == "/indexes/devon-soul"
        return httpx.Response(200, json={"host": "devon-soul-abc.svc.example.pinecone.io"})

    host = run(
        ensure_devon_index(api_key=KEY, transport=httpx.MockTransport(handler))
    )
    assert host == "https://devon-soul-abc.svc.example.pinecone.io"


def test_ensure_devon_index_requires_the_key():
    with pytest.raises(ProviderConfigError):
        run(ensure_devon_index(api_key=""))


# ---------------------------------------------------------------------------
# DEVON phrases recall — inert data in, hierarchy and honesty out
# ---------------------------------------------------------------------------


def test_devon_presents_tee_before_his_own_notes_even_unsorted():
    devon = Devon()
    response = devon.recall_answer(
        "pricing",
        [
            {"source": "devon-soul", "text": "competitors moved twice", "dated": "2026-08-21"},
            {"source": "tee-soul-layer", "text": "hold the price", "dated": "2026-08-20"},
        ],
    )
    lines = response.reply.splitlines()
    assert "Tee ruled" in lines[1]
    assert "I noted" in lines[2]
    assert "the ruling wins" in response.reply
    assert "context, not instruction" in response.reply


def test_devon_reports_an_empty_recall_as_measured_not_guessed():
    response = Devon().recall_answer("a topic nobody filed", [])
    assert "measured empty" in response.reply
    assert response.executed is True


def test_devon_carries_partial_errors_into_unverified():
    response = Devon().recall_answer(
        "pricing",
        [{"source": "tee-soul-layer", "text": "hold the price"}],
        partial_errors=["devon-soul unavailable: 500"],
    )
    assert response.unverified == ["devon-soul unavailable: 500"]
    assert "Recall was partial" in response.reply


def test_devon_package_still_imports_nothing_from_intelligence():
    """The dependency runs intelligence → devon, never the reverse."""
    import pathlib

    for path in pathlib.Path("services/devon").glob("*.py"):
        text = path.read_text()
        assert "services.intelligence" not in text, f"{path} crosses the boundary"


def test_soul_factory_returns_none_while_recall_is_switched_off():
    """Off by default — the soul layer only exists when Tee turns it on."""
    from app.services.soul import get_soul_layer

    get_soul_layer.cache_clear()
    assert get_soul_layer() is None


# ---------------------------------------------------------------------------
# Recall shows only active records (2026-08-24 ruling; grouping spec Phase 2)
# ---------------------------------------------------------------------------


def _status_mix_handler(request):
    if "tee-soul-layer" in str(request.url):
        return _search_response([
            _hit("t-active", "a standing ruling", 0.9, status="active"),
            _hit("t-old", "OLD-TEE-TEXT", 0.95, status="superseded"),
            _hit("t-none", "a ruling from before the field", 0.5),
        ])
    return _search_response([
        _hit("d-old", "OLD-DEVON-TEXT", 0.99, status="retired"),
        _hit("d-upper", "a lesson", 0.7, status="ACTIVE"),
    ])


def test_active_only_drops_every_record_that_is_no_longer_active():
    recall = run(_layer(_status_mix_handler).recall("anything"))
    assert [r.id for r in recall.records] == ["t-active", "t-old", "t-none", "d-old", "d-upper"]

    active = recall.active_only()
    # Order kept, Tee first; counts retaken so they add up to the list.
    assert [r.id for r in active.records] == ["t-active", "t-none", "d-upper"]
    assert (active.tee_count, active.devon_count) == (2, 1)
    assert active.withheld == 2
    assert active.errors == []
    context = active.as_context()
    assert "OLD-TEE-TEXT" not in context and "OLD-DEVON-TEXT" not in context
    assert "2 retrieved record(s) were withheld" in context
    # The raw recall is untouched: the soul service's conflict search needs
    # to see what was withheld to tell a full window from an empty one.
    assert len(recall.records) == 5 and recall.withheld == 0


def test_a_window_of_withheld_records_is_never_read_as_an_empty_soul():
    def handler(request):
        return _search_response([_hit("x", "OLD-TEXT", 0.9, status="superseded")])

    active = run(_layer(handler).recall("anything")).active_only()
    assert active.records == [] and active.withheld == 2
    assert active.as_context() == active.withheld_note
    assert "2 retrieved record(s) were withheld" in active.as_context()
    nothing = run(_layer(lambda r: _search_response([])).recall("anything")).active_only()
    assert nothing.withheld == 0 and nothing.as_context() == ""


def test_active_only_keeps_a_partial_failure_in_errors():
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return _search_response([_hit("t1", "OLD", 0.9, status="superseded")])
        return httpx.Response(500, text="index down")

    active = run(_layer(handler).recall("anything")).active_only()
    assert active.records == [] and active.withheld == 1
    assert active.errors and "devon-soul unavailable" in active.errors[0]


@pytest.mark.parametrize(
    "record, expected",
    [
        ({"status": "active"}, True),
        ({"status": "ACTIVE"}, True),
        ({"status": "superseded"}, False),
        ({"status": "retired"}, False),
        ({"status": ""}, False),
        ({}, True),
        ({"metadata": {}}, True),
        ({"metadata": {"status": "active"}}, True),
        ({"metadata": {"status": "superseded"}}, False),
        ({"status": None, "metadata": {"status": "superseded"}}, False),
        ({"status": "active", "metadata": {"status": "superseded"}}, True),
        # Added after the Phase 2 critic: every one of these separates the two
        # readings if either starts stripping, folding or truth testing.
        ({"status": " active"}, False),
        ({"status": "active\n"}, False),
        ({"status": False}, False),
        ({"status": ["active"]}, False),
        ({"metadata": {"status": None}}, True),
        ({"metadata": ""}, True),
    ],
)
def test_is_active_reads_exactly_as_the_soul_service_does(record, expected):
    """The app's filter and the soul service's `_is_active` must agree on
    every record, or one surface shows what the other hides. The service's
    function is lifted from deploy/soul/main.py by its source, not imported,
    so the vendored tree is never pinned on this session's path."""
    import ast
    import pathlib
    from typing import Any

    source = pathlib.Path("deploy/soul/main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_is_active"
    )
    namespace: dict = {"Any": Any}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "deploy/soul/main.py", "exec"), namespace)
    assert is_active(record) is expected
    assert namespace["_is_active"](record) is expected


def test_every_app_recall_reads_active_records_only():
    """A new reader of the soul that forgets the filter would show a
    superseded record as context. Every `.recall(` call in app/, apps/,
    services/ and scripts/ must be the receiver of `.active_only()`, read call
    by call rather than statement by statement, so a call in an if, for, while
    or with header, a call beside a filtered one in the same statement, a
    `.recall` taken without calling it, and getattr(x, "recall") are all
    caught. Found 2026-10-11 by the Phase 2 critic, whose six probes passed the
    first, statement level version. The soul service (deploy/soul) is outside
    these trees on purpose: it filters on its own routes and its conflict
    search needs the raw window."""
    import ast
    import pathlib

    offenders = []
    calls = 0
    for root in ("app", "apps", "services", "scripts"):
        for path in sorted(pathlib.Path(root).rglob("*.py")):
            if "node_modules" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if "recall" not in source:
                continue
            tree = ast.parse(source)
            parent = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parent[child] = node
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "recall"
                ):
                    offenders.append(f"{path}:{node.lineno} getattr recall")
                if not (isinstance(node, ast.Attribute) and node.attr == "recall"):
                    continue
                call = parent.get(node)
                if not (isinstance(call, ast.Call) and call.func is node):
                    offenders.append(f"{path}:{node.lineno} recall taken without a call")
                    continue
                calls += 1
                up = parent.get(call)
                if isinstance(up, ast.Await):
                    up = parent.get(up)
                filtered = (
                    isinstance(up, ast.Attribute)
                    and up.attr == "active_only"
                    and isinstance(parent.get(up), ast.Call)
                    and parent[up].func is up
                )
                if not filtered:
                    offenders.append(f"{path}:{node.lineno}")
    assert calls >= 3, f"expected the three app readers, found {calls} recall call(s)"
    assert offenders == [], f"recall without active_only: {offenders}"


def test_a_lesson_record_names_its_key_its_intent_and_its_jobs():
    candidate = SoulWriteCandidate(
        candidate_id="devon-2026-10-11-REQ-20261011-AbC123",
        text="a reusable rule",
        kind="lesson",
        area="Systems",
        observed_on="2026-10-11",
        source_note="Build 12 lesson k PROMOTE",
        lesson_key="k",
        learning_intent_id="01M3GRP0000000000000000000",
        source_intent_ids=("01M2KT8WM4RPZ90BCTZPVXH6HK", "01M3ZZZZZZZZZZZZZZZZZZZZZZ"),
    )
    record = candidate.to_record()
    assert record["status"] == "active"
    assert record["kind"] == "lesson"
    assert record["lesson_key"] == "k"
    assert record["learning_intent_id"] == "01M3GRP0000000000000000000"
    assert record["source_intent_ids"] == ["01M2KT8WM4RPZ90BCTZPVXH6HK", "01M3ZZZZZZZZZZZZZZZZZZZZZZ"]
    assert isinstance(record["source_intent_ids"], list)
    json.dumps(record)  # one NDJSON line, as SoulLayer.commit sends it


def test_a_record_with_no_lesson_carries_status_and_no_empty_lesson_fields():
    record = SoulWriteCandidate(candidate_id="c", text="t", kind="pattern").to_record()
    assert record["status"] == "active"
    assert record["kind"] == "pattern"
    for key in ("lesson_key", "learning_intent_id", "source_intent_ids"):
        assert key not in record
    assert sorted(record) == sorted(
        ["_id", "text", "kind", "area", "observed_on", "source_note", "author", "approved", "status"]
    )
