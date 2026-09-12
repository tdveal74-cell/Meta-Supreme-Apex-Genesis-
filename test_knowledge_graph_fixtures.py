"""The committed graph fixtures must still be what the route produces.

WHY THIS FILE EXISTS

The graph panel was pulled on 2026-09-10 because it and the route were built to
two different contracts and BOTH test suites were green: `test_knowledge_graph.py`
pinned the flat payload the route really sends, while `control-check.ts`'s graph
fixtures were written by hand in a nested shape that no route ever produced. Two
suites, each internally consistent, agreeing about nothing.

The cure was to generate the TypeScript side's fixtures from `assemble_graph`
instead of writing them (scripts/gen_knowledge_graph_fixtures.py). That moves the
failure rather than removing it: a COMMITTED generated file goes stale the moment
the payload changes, and a stale fixture is a hand written one again.

So this file closes the loop. It regenerates in memory and compares. Change the
payload shape and this goes red until somebody runs the generator, which is the
only state in which the TypeScript checks are testing the real thing.

The fixture has to be committed rather than generated at check time because
`web-ci.yml` runs the TypeScript checks in a Node only job with no Python
interpreter and no repository install, so nothing there can call assemble_graph.
"""

from __future__ import annotations

import json

from scripts.gen_knowledge_graph_fixtures import FIXTURE_PATH, build


def test_the_committed_fixture_is_exactly_what_the_route_produces_today():
    assert FIXTURE_PATH.exists(), (
        f"{FIXTURE_PATH} is missing. apps/web/scripts/control-check.ts reads it, so the "
        "web checks cannot run. Regenerate with "
        "python3 scripts/gen_knowledge_graph_fixtures.py"
    )
    committed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    fresh = build()

    assert committed["scenarios"].keys() == fresh["scenarios"].keys(), (
        "the fixture's scenario names have drifted from the generator's. Regenerate with "
        "python3 scripts/gen_knowledge_graph_fixtures.py"
    )

    for name in fresh["scenarios"]:
        assert committed["scenarios"][name]["payload"] == fresh["scenarios"][name]["payload"], (
            f"scenario {name!r} in {FIXTURE_PATH.name} is NOT what assemble_graph produces "
            "today, so every TypeScript check reading it is green about a payload the route "
            "no longer sends. That is the exact failure that got the graph panel pulled. "
            "Regenerate with python3 scripts/gen_knowledge_graph_fixtures.py"
        )


def test_the_fixture_covers_the_states_the_panel_has_to_tell_apart():
    """A fixture set that cannot reach a branch certifies nothing about it.

    Named states rather than a count, because a count grows by accident and says
    nothing about coverage.
    """
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["scenarios"]

    required = {
        "empty_corpus",
        "items_none_embedded",
        "embedded_no_edges",
        "drawable_varying_degree",
        "drawable_flat_degree",
        "capped_and_truncated",
        "provider_unavailable",
        "provider_real",
    }
    missing = sorted(required - set(scenarios))
    assert not missing, f"the fixture no longer covers {missing}"

    # And each one must actually exhibit the condition it is named for, or the
    # name is the only thing carrying the claim.
    empty = scenarios["empty_corpus"]["payload"]
    assert empty["items_total"] == 0 and empty["nodes"] == []

    unembedded = scenarios["items_none_embedded"]["payload"]
    assert unembedded["items_embedded"] == 0
    assert unembedded["nodes"], "items_none_embedded must still carry nodes"
    assert unembedded["edges"] == [], "the route skips the edge query with nothing embedded"

    edgeless = scenarios["embedded_no_edges"]["payload"]
    assert edgeless["items_embedded"] >= 2 and edgeless["edges"] == []

    capped = scenarios["capped_and_truncated"]["payload"]
    assert capped["nodes_capped"] is True, "node_cap must actually have bitten"
    assert capped["edges_capped"] is True, "edge_cap must actually have bitten"
    assert capped["chunks_truncated"] is True, "chunk_cap must actually have bitten"
    assert any(edge["distance_is_upper_bound"] for edge in capped["edges"]), (
        "at least one drawn edge must carry distance_is_upper_bound, or the panel's "
        "per-edge ceiling notice is unreachable in the fixtures"
    )

    unavailable = scenarios["provider_unavailable"]["payload"]
    assert unavailable["embedding_provider"] == "unavailable"
    assert unavailable["embedding_provider_simulated"] is True, (
        "the unavailable provider must arrive with the simulated flag RAISED. That "
        "combination, a name no allowlist knows plus a raised flag, is what made the "
        "panel read a failed provider as real"
    )

    real = scenarios["provider_real"]["payload"]
    assert real["embedding_provider"] == "openai"
    assert real["embedding_provider_simulated"] is False


def test_no_scenario_carries_a_nested_counts_object():
    """The original defect, pinned so it cannot come back through the fixture.

    The pulled panel read `raw.counts` as a nested member. The route has never
    sent one: every count sits at the top level. A fixture that grew a nested
    `counts` key would let that reader pass again.
    """
    scenarios = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["scenarios"]
    for name, entry in scenarios.items():
        payload = entry["payload"]
        assert "counts" not in payload, (
            f"scenario {name!r} carries a nested 'counts' object. The route sends a FLAT "
            "payload and reading a nested one is what got the panel pulled"
        )
        assert "items_total" in payload, f"scenario {name!r} lost its top level counts"
