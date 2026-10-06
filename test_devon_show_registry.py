"""The show registry is traced into the nodes it was lifted from.

`services/devon/show_registry.py` carries, as data, what five `Show Context`
nodes and `Series Addendum` in TQO FINAL V5 carry as code. These tests read
the export under `n8n/tqo-v5/exports/` and prove every registry value is
still in the node that owns it, keyed on the node's own field name and inside
the branch that builds this show's object, so a live edit that is not carried
back fails the build instead of drifting, and a value borrowed from the other
show's branch does not pass. They also pin the one disagreement the lift
found between the nodes, in a map whose keys are listed here so it can only
shrink.
"""

from __future__ import annotations

import json
import re

from services.devon.show_registry import (
    EXPORT,
    KNOWN_NODE_DRIFT,
    NODE_FIELDS,
    SHOW_BRANCH_SPELLINGS,
    SHOWS,
    SOURCE,
    TEE_CLONE,
    V5_SHOW_BRANCHES,
    VOICE,
    export_nodes,
    field_value,
    get_show,
    js_pattern,
    keyed,
    registry_rows,
    series_rows,
    show_for_table,
    show_segment,
)

#: The drift the module may still carry. Adding a key here is a visible test
#: edit; the map in the module may only carry keys listed here, and only while
#: the node still carries the stale value. The two the lift found, the NCO
#: tagline on Promote and Publish, were repaired on 2026-10-06 and left.
EXPECTED_DRIFT: set = set()


def _traces(js_key: str, value: object, code: str) -> bool:
    return re.search(keyed(js_key, value), code) is not None


def _payload() -> dict:
    return json.loads(EXPORT.read_text(encoding="utf-8"))


def test_the_source_names_the_export_it_was_traced_against():
    assert SOURCE["workflow_id"] == "qEkGOUsNyVaRAmm6"
    assert EXPORT.exists(), "the export this registry is traced against is missing"
    payload = _payload()
    assert payload["workflowId"] == SOURCE["workflow_id"]
    assert payload["versionId"] == SOURCE["version_id"], (
        "the export was regenerated at a new version; re-trace the registry and update SOURCE"
    )
    assert payload["readAt"].startswith(SOURCE["read"])
    assert SOURCE["export"].endswith(EXPORT.name)


def test_every_show_context_node_is_in_the_export():
    nodes = export_nodes()
    missing = sorted(name for name in NODE_FIELDS if name not in nodes)
    assert not missing, f"nodes gone from the export: {missing}"
    assert "Series Addendum" in nodes


def test_every_show_context_node_builds_one_object_per_show():
    nodes = export_nodes()
    for node_name in NODE_FIELDS:
        for show in SHOWS.values():
            segment = show_segment(nodes[node_name], show.show)
            assert segment.startswith(f"show: '{show.show}'")
            other = [entry.show for entry in SHOWS.values() if entry is not show]
            assert not any(f"show: '{label}'" in segment for label in other)


def test_every_registry_value_traces_into_the_branch_that_builds_its_show():
    nodes = export_nodes()
    failures = []
    for node_name, fields in NODE_FIELDS.items():
        for show in SHOWS.values():
            segment = show_segment(nodes[node_name], show.show)
            for js_key, path in fields.items():
                drift = KNOWN_NODE_DRIFT.get((node_name, show.key, path))
                value = drift if drift is not None else field_value(show, path)
                if not _traces(js_key, value, segment):
                    label = "known drift" if drift is not None else "registry value"
                    failures.append(f"{node_name} [{show.show}] {js_key}: {value!r} ({label})")
    assert not failures, "values no longer in the branch that builds their show:\n" + "\n".join(failures)


def test_a_value_from_the_other_show_does_not_trace():
    """The guard the keyed, branch scoped trace exists for."""
    nodes = export_nodes()
    tqo = show_segment(nodes["Show Context: Script"], "TQO")
    nco = get_show("nco")
    assert not _traces("kicker", nco.kicker, tqo)
    assert not _traces("channel", nco.channel, tqo)
    assert not _traces("requiredTags", nco.required_tags, tqo)
    assert not _traces("promoteLimit", 4, tqo)
    assert not _traces("scriptLimit", 20, tqo), "digits must match whole, 20 is not 2"


def test_the_known_drift_is_pinned_here_and_only_shrinks():
    assert set(KNOWN_NODE_DRIFT) <= EXPECTED_DRIFT, (
        "a new drift entry is a test edit, not a data edit: list it in EXPECTED_DRIFT"
    )
    nodes = export_nodes()
    for (node_name, show_key, path), stale in KNOWN_NODE_DRIFT.items():
        show = get_show(show_key)
        js_key = next(key for key, value in NODE_FIELDS[node_name].items() if value == path)
        segment = show_segment(nodes[node_name], show.show)
        current = field_value(show, path)
        assert _traces(js_key, stale, segment), (
            f"{node_name} no longer carries {stale!r} for {show_key}.{path}; "
            "remove the entry from KNOWN_NODE_DRIFT and from EXPECTED_DRIFT"
        )
        assert not _traces(js_key, current, segment), (
            f"{node_name} now carries the registry value {current!r} for {show_key}.{path}; "
            "remove the entry from KNOWN_NODE_DRIFT and from EXPECTED_DRIFT"
        )


def test_the_voice_lane_traces_into_the_render_node():
    code = export_nodes()["Show Context: Render"]
    for show in SHOWS.values():
        assert show.voice is VOICE, "both shows narrate in the owned clone"
    assert re.search(rf"const TEE_CLONE = {js_pattern(TEE_CLONE)};", code)
    assert re.search(r"const TQO_VOICE = TEE_CLONE;", code)
    assert re.search(r"const NCO_VOICE = TEE_CLONE;", code)
    for show in SHOWS.values():
        segment = show_segment(code, show.show)
        assert re.search(rf"\.\.\.VOICE,\s*voiceId:\s*{show.show}_VOICE,", segment), (
            f"the {show.show} object no longer spreads VOICE and assigns voiceId: {show.show}_VOICE"
        )
    assert re.search(rf"const SPEECHIFY_VOICE = {js_pattern(VOICE.speechify_voice_id)};", code)
    assert re.search(rf"const SPEECHIFY_MODEL = {js_pattern(VOICE.speechify_model)};", code)
    assert re.search(rf"const VOICE_READY = {js_pattern(VOICE.voice_ready)};", code)
    assert _traces("elevenModel", VOICE.eleven_model, code)
    assert _traces("providerEleven", VOICE.provider_eleven, code)
    assert re.search(
        r"providerSpeechify:\s*'speechify ' \+ SPEECHIFY_VOICE \+ ' STOPGAP VOICE, not for publish'", code
    ), "the node composes the Speechify narrator string from its voice id"
    assert VOICE.provider_speechify == f"speechify {VOICE.speechify_voice_id} STOPGAP VOICE, not for publish"
    settings = re.search(r"const VOICE_SETTINGS = \{(.*?)\};", code, re.S)
    assert settings, "the Render node no longer declares VOICE_SETTINGS"
    block = settings.group(1)
    for key, value in VOICE.settings.items():
        match = re.search(rf"(?<![\w$]){re.escape(key)}:\s*([\w.]+),", block)
        assert match, f"voice setting {key} is not in VOICE_SETTINGS"
        written = match.group(1)
        if isinstance(value, bool):
            assert written == ("true" if value else "false"), f"{key}: node {written}, registry {value}"
        else:
            assert float(written) == float(value), f"{key}: node {written}, registry {value}"
    assert len(re.findall(r"(?<![\w$])\w+:\s*[\w.]+,", block)) == len(VOICE.settings), (
        "VOICE_SETTINGS carries a setting the registry does not"
    )


def test_youtube_readiness_follows_the_publish_node():
    code = export_nodes()["Show Context: Publish"]
    assert _traces("ncoYouTubeReady", False, show_segment(code, "NCO"))
    assert "ncoYouTubeReady" not in show_segment(code, "TQO")
    assert get_show("nco").youtube_ready is False
    assert get_show("tqo").youtube_ready is True


def test_the_content_tables_are_the_ones_the_lane_reads():
    assert show_for_table("2GtmrFcTNqVMbddh").key == "tqo"
    assert show_for_table("DSH1tn4TZjzAEKxp").key == "nco"
    assert show_for_table("nope") is None
    idea_rows = next(node for node in _payload()["nodes"] if node["name"] == "Get Idea Rows")
    assert "tableRef" in json.dumps(idea_rows["parameters"]["dataTableId"])


def _series_table(code: str, show_label: str) -> str:
    match = re.search(rf"const {show_label}_SHOWS = \{{(.*?)\n\}};", code, re.S)
    assert match, f"Series Addendum no longer declares {show_label}_SHOWS"
    return match.group(1)


def test_every_series_and_alias_traces_into_its_table_in_series_addendum():
    code = export_nodes()["Series Addendum"]
    for show in SHOWS.values():
        table = _series_table(code, show.show)
        for series in show.series:
            pattern = (
                rf"'{re.escape(series.key)}':\s*\{{\s*canon:\s*{js_pattern(series.canon)}\s*,"
                rf"\s*role:\s*{js_pattern(series.role)}\s*,\s*tier:\s*{js_pattern(series.tier)}\s*,"
                rf"\s*mandate:\s*{js_pattern(series.mandate)}\s*\}}"
            )
            assert re.search(pattern, table), f"{show.key} series {series.key!r} is not in {show.show}_SHOWS as registered"
        for alias, (target, segment) in show.aliases.items():
            tail = rf",\s*segment:\s*{js_pattern(segment)}" if segment else ""
            pattern = rf"'{re.escape(alias)}':\s*\{{\s*alias:\s*{js_pattern(target)}{tail}\s*\}}"
            assert re.search(pattern, table), f"alias {alias!r} is not in {show.show}_SHOWS as registered"
        registered = set(re.findall(r"^\s*'([^']+)':\s*\{", table, re.M))
        assert registered == {series.key for series in show.series} | set(show.aliases), (
            f"{show.show}_SHOWS and the registry list different keys"
        )


def test_series_resolve_the_way_the_node_resolves_them():
    code = export_nodes()["Series Addendum"]
    assert "String(name || '').trim().toLowerCase()" in code
    assert "if (e && e.alias)" in code, "the node takes one alias hop"
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


def test_the_rows_hold_only_what_a_data_table_column_can_hold():
    """n8n data table columns are string, number, boolean or date."""
    rows = registry_rows()
    assert [row["key"] for row in rows] == ["tqo", "nco"]
    for row in rows:
        for name, value in row.items():
            assert isinstance(value, (str, int, float, bool)), f"{name} is a {type(value).__name__}"
        assert row["voice_id"] == TEE_CLONE
        assert "voice_voice_id" not in row
        assert row["brief_reach_profile_uuid"] == "af497848-65de-40f7-82ac-b0f4f162a141"
        assert json.loads(row["voice_settings"]) == dict(VOICE.settings)
        assert json.loads(row["brief_sections"]) == list(get_show(row["key"]).brief.sections)
    assert json.loads(rows[0]["required_tags"]) == []
    assert json.loads(rows[1]["required_tags"]) == ["NCO Forge"]
    series = series_rows()
    for row in series:
        assert all(isinstance(value, (str, int)) for value in row.values())
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


def test_the_branch_count_in_the_docstring_is_counted_from_the_export():
    nodes = export_nodes()
    branching = sorted(
        name for name, code in nodes.items()
        if any(re.search(spelling, code) for spelling in SHOW_BRANCH_SPELLINGS)
    )
    assert len(branching) == V5_SHOW_BRANCHES, (
        f"{len(branching)} Code nodes branch on the show, V5_SHOW_BRANCHES says {V5_SHOW_BRANCHES}: {branching}"
    )
    assert "Build Script Prompt" in branching and "Series Addendum" in branching
    assert sum(1 for code in nodes.values() if re.search(r"\bisNCO\b", code)) == 16, (
        "the docstring says sixteen Code nodes carry isNCO"
    )
    assert all(name in branching for name in NODE_FIELDS)
