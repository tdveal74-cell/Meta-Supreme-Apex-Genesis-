"""The show registry is traced into the nodes it was lifted from.

`services/devon/show_registry.py` carries, as data, what five `Show Context`
nodes and `Series Addendum` in TQO FINAL V5 carry as code. These tests read
the export under `n8n/tqo-v5/exports/` and prove every registry value is
still in the node that owns it, so a live edit that is not carried back fails
the build instead of drifting. They also pin the one disagreement the lift
found between the nodes, in a map that may only shrink.
"""

from __future__ import annotations

import json

from services.devon.show_registry import (
    EXPORT,
    KNOWN_NODE_DRIFT,
    NODE_FIELDS,
    SHOWS,
    SOURCE,
    TEE_CLONE,
    VOICE,
    export_nodes,
    field_value,
    get_show,
    js_literal,
    registry_rows,
    series_rows,
    show_for_table,
)


def _traces(value: object, code: str) -> bool:
    return any(form in code for form in js_literal(value))


def test_the_source_names_the_workflow_and_the_export():
    assert SOURCE["workflow_id"] == "qEkGOUsNyVaRAmm6"
    assert EXPORT.exists(), "the export this registry is traced against is missing"
    payload = json.loads(EXPORT.read_text(encoding="utf-8"))
    assert payload["workflowId"] == SOURCE["workflow_id"]
    assert SOURCE["export"].endswith(EXPORT.name)


def test_every_show_context_node_is_in_the_export():
    nodes = export_nodes()
    missing = sorted(name for name in NODE_FIELDS if name not in nodes)
    assert not missing, f"nodes gone from the export: {missing}"
    assert "Series Addendum" in nodes


def test_every_registry_value_traces_into_the_node_that_carries_it():
    nodes = export_nodes()
    failures = []
    for node_name, fields in NODE_FIELDS.items():
        code = nodes[node_name]
        for show in SHOWS.values():
            for js_key, path in fields.items():
                drift = KNOWN_NODE_DRIFT.get((node_name, show.key, path))
                value = drift if drift is not None else field_value(show, path)
                if not _traces(value, code):
                    failures.append(f"{node_name} [{show.key}] {js_key}: {value!r}")
    assert not failures, "registry values no longer in their node:\n" + "\n".join(failures)


def test_the_known_drift_is_still_in_the_node_and_only_shrinks():
    nodes = export_nodes()
    for (node_name, show_key, path), stale in KNOWN_NODE_DRIFT.items():
        code = nodes[node_name]
        current = field_value(get_show(show_key), path)
        assert _traces(stale, code), (
            f"{node_name} no longer carries {stale!r} for {show_key}.{path}; "
            "remove the entry from KNOWN_NODE_DRIFT"
        )
        assert not _traces(current, code), (
            f"{node_name} now carries the registry value {current!r} for {show_key}.{path}; "
            "remove the entry from KNOWN_NODE_DRIFT"
        )


def test_the_brief_sections_trace_into_the_brief_node():
    code = export_nodes()["Show Context: Brief"]
    for show in SHOWS.values():
        for section in show.brief.sections:
            assert _traces(section, code), f"{show.key} brief section {section!r} is not in the node"


def test_the_voice_lane_traces_into_the_render_node():
    code = export_nodes()["Show Context: Render"]
    assert f"'{TEE_CLONE}'" in code
    for show in SHOWS.values():
        assert show.voice is VOICE, "both shows narrate in the owned clone"
    assert f"'{VOICE.eleven_model}'" in code
    assert f"'{VOICE.speechify_voice_id}'" in code
    assert f"'{VOICE.speechify_model}'" in code
    assert f"staleClaimHours: {VOICE.stale_claim_hours}" in code
    assert f"VOICE_READY = {'true' if VOICE.voice_ready else 'false'}" in code
    for key, value in VOICE.settings.items():
        assert key in code, f"voice setting {key} is not in the render node"
        assert str(value).lower() in code.lower()


def test_youtube_readiness_follows_the_publish_node():
    code = export_nodes()["Show Context: Publish"]
    assert "ncoYouTubeReady: false" in code
    assert get_show("nco").youtube_ready is False
    assert get_show("tqo").youtube_ready is True


def test_the_content_tables_are_the_ones_the_lane_reads():
    assert show_for_table("2GtmrFcTNqVMbddh").key == "tqo"
    assert show_for_table("DSH1tn4TZjzAEKxp").key == "nco"
    assert show_for_table("nope") is None
    payload = json.loads(EXPORT.read_text(encoding="utf-8"))
    idea_rows = next(node for node in payload["nodes"] if node["name"] == "Get Idea Rows")
    assert "tableRef" in json.dumps(idea_rows["parameters"]["dataTableId"])


def test_every_series_and_alias_traces_into_series_addendum():
    code = export_nodes()["Series Addendum"]
    for show in SHOWS.values():
        for series in show.series:
            for value in (series.canon, series.role, series.tier, series.mandate):
                assert _traces(value, code), f"{show.key} series {series.key}: {value!r} is not in the node"
            assert f"'{series.key}':" in code
        for alias, (target, segment) in show.aliases.items():
            assert f"'{alias}': {{ alias: '{target}'" in code, f"alias {alias!r} is not in the node"
            if segment:
                assert f"segment: '{segment}'" in code


def test_series_resolve_the_way_the_node_resolves_them():
    nco = get_show("nco")
    resolved = nco.resolve_series(" NCO After Action ")
    assert resolved is not None and resolved[0].key == "after action" and resolved[1] is None
    resolved = nco.resolve_series("Before You Pin")
    assert resolved is not None and resolved[0].key == "nco school" and resolved[1] == "Before You Pin"
    assert nco.resolve_series("The Forge")[0].canon == "THE FORGE"
    assert nco.resolve_series("Resume to Robot") is None, "an unknown show resolves to nothing, never silently to a default"
    tqo = get_show("tqo")
    assert tqo.aliases == {}
    assert tqo.resolve_series("I Built It With AI")[0].canon == "I BUILT IT WITH AI"


def test_the_rows_are_flat_json_and_keyed_once():
    rows = registry_rows()
    assert [row["key"] for row in rows] == ["tqo", "nco"]
    json.dumps(rows)
    for row in rows:
        assert all(not isinstance(value, (tuple, set)) for value in row.values())
        assert row["voice_voice_id"] == TEE_CLONE
        assert row["brief_reach_profile_uuid"] == "af497848-65de-40f7-82ac-b0f4f162a141"
    series = series_rows()
    json.dumps(series)
    keys = [(row["show"], row["key"]) for row in series]
    assert len(keys) == len(set(keys)), "a series key is registered twice"
    assert sum(1 for row in series if row["show"] == "nco" and not row["alias_of"]) == 6
    assert sum(1 for row in series if row["show"] == "nco" and row["alias_of"]) == 6
    assert sum(1 for row in series if row["show"] == "tqo") == 4


def test_the_limits_match_what_plan_batch_defaults_to():
    """Package: Plan Batch falls back to 2 scripts and 3 packages when the
    context carries nothing; the registry carries the same numbers on purpose."""
    code = export_nodes()["Package: Plan Batch"]
    assert "Number(ctx.scriptLimit) > 0 ? Number(ctx.scriptLimit) : 2" in code
    assert "Number(ctx.packageLimit) > 0 ? Number(ctx.packageLimit) : 3" in code
    for show in SHOWS.values():
        assert show.script_limit == 2 and show.package_limit == 3
