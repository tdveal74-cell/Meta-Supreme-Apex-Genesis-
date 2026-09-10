"""Generate the knowledge graph panel's test fixtures FROM the route itself.

WHY THIS EXISTS

On 2026-09-10 the graph panel was pulled before shipping because it and the route
had been built to two different contracts. The panel read `counts` as a nested
object; the route sends one flat payload. Both test suites were green, and that
is the whole point: `test_knowledge_graph.py` pinned the flat shape the route
really sends, while `control-check.ts`'s graph fixtures were written BY HAND in
the nested shape. Two suites, each correct about a different payload, agreeing
with each other about nothing.

A hand written fixture certifies a code path production never runs. So the
fixtures are generated here, by calling `assemble_graph` with the same argument
shapes the route passes it, and written to a JSON file that
`apps/web/scripts/control-check.ts` reads. The TypeScript side then cannot be
green about a shape the Python side does not produce.

The file is COMMITTED, because control-check runs in a web-only CI job with no
Python available. A committed generated file can go stale silently, so
`test_knowledge_graph_fixtures.py` regenerates and compares on every run: change
the payload shape and that test fails until the fixture is regenerated with

    python3 scripts/gen_knowledge_graph_fixtures.py

Run it from the repository root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_PATH = ROOT / "apps" / "web" / "components" / "mind" / "knowledge-graph-fixtures.json"

_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_C = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
_D = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"


def _counts(
    total: int = 0, ready: int = 0, embedded: int = 0, simulated: int = 0
) -> Dict[str, Any]:
    return {
        "items_total": total,
        "items_ready": ready,
        "items_embedded": embedded,
        "items_simulated": simulated,
    }


def _node(
    item_id: str,
    *,
    title: str = "A document",
    source: Optional[str] = "drive",
    source_type: str = "markdown",
    chunks: int = 3,
    embedded: Optional[int] = None,
    simulated: bool = True,
    created_at: str = "2026-09-01T12:00:00+00:00",
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "title": title,
        "source": source,
        "source_type": source_type,
        "created_at": created_at,
        "chunk_count": chunks,
        "embedded_chunk_count": chunks if embedded is None else embedded,
        "simulated_embeddings": simulated,
    }


def _edge(source: str, target: str, distance: float) -> Dict[str, Any]:
    return {"source_id": source, "target_id": target, "distance": distance}


MOCK = {
    "embedding_provider": "mock",
    "embedding_model": "mock-embed-v1",
    "embedding_provider_simulated": True,
    "embedding_provider_error": None,
}

# The state a DEFAULT `start-devon.sh` launch produces: it writes
# DEFAULT_AI_PROVIDER=cerebras, only mock and openai implement embed, so
# `_embedding_provider` raises and the route reports this block. The panel read
# the NAME and called it real until 2026-09-10, which is why this scenario is a
# fixture rather than a comment.
UNAVAILABLE = {
    "embedding_provider": "unavailable",
    "embedding_model": "unavailable",
    "embedding_provider_simulated": True,
    "embedding_provider_error": "ProviderConfigError: cerebras does not embed",
}

REAL = {
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "embedding_provider_simulated": False,
    "embedding_provider_error": None,
}


def _scenarios() -> List[Dict[str, Any]]:
    """Each entry is one call to assemble_graph, named for what it proves."""
    return [
        {
            "name": "empty_corpus",
            "why": "No items at all. The panel must say the corpus is empty, not that nothing is embedded.",
            "counts": _counts(),
            "node_rows": [],
            "edge_rows": [],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": MOCK,
        },
        {
            "name": "items_none_embedded",
            "why": (
                "Items exist and NONE carry a vector, so the route skips the edge query "
                "entirely. This is the payload the pulled panel rendered as 'no pair close "
                "enough to connect', a comparison that never ran."
            ),
            "counts": _counts(total=4, ready=4, embedded=0),
            "node_rows": [
                _node(_A, embedded=0, title="First"),
                _node(_B, embedded=0, title="Second", source="notion"),
            ],
            "edge_rows": [],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": MOCK,
        },
        {
            "name": "embedded_no_edges",
            "why": "Vectors exist on two or more items and no pair is inside the threshold. Genuinely edgeless.",
            "counts": _counts(total=2, ready=2, embedded=2, simulated=2),
            "node_rows": [_node(_A), _node(_B, source="notion")],
            "edge_rows": [],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": MOCK,
        },
        {
            "name": "drawable_varying_degree",
            "why": (
                "Degrees differ, so the ring's radius genuinely encodes degree and the "
                "screen reader description may say the connected are pulled inward."
            ),
            "counts": _counts(total=4, ready=4, embedded=4, simulated=4),
            "node_rows": [
                _node(_A, title="Hub"),
                _node(_B, title="Spoke one", source="notion"),
                _node(_C, title="Spoke two", source="notion"),
                _node(_D, title="Lonely", source="url"),
            ],
            "edge_rows": [
                _edge(_A, _B, 0.11),
                _edge(_A, _C, 0.22),
                _edge(_B, _C, 0.44),
            ],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": MOCK,
        },
        {
            "name": "drawable_flat_degree",
            "why": (
                "Every node has exactly one edge, so the radius encodes nothing and the "
                "description must NOT claim the connected are pulled inward."
            ),
            "counts": _counts(total=2, ready=2, embedded=2, simulated=2),
            "node_rows": [_node(_A), _node(_B)],
            "edge_rows": [_edge(_A, _B, 0.3)],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": MOCK,
        },
        {
            "name": "capped_and_truncated",
            "why": (
                "node_cap and edge_cap both bite, and one item has more chunks than "
                "chunk_cap so its edges carry distance_is_upper_bound. All three notices "
                "were parsed and never rendered before 2026-09-10."
            ),
            # Probe reads of cap + 1 rows: receiving the extra row is how the route
            # knows a cap bit, and assemble_graph drops it.
            "counts": _counts(total=9, ready=9, embedded=9, simulated=9),
            "node_rows": [
                _node(_A, chunks=9, title="Long document"),
                _node(_B, title="Second"),
                _node(_C, title="Third"),
            ],
            "edge_rows": [_edge(_A, _B, 0.12), _edge(_B, _C, 0.2)],
            "node_cap": 2,
            "edge_cap": 1,
            "chunk_cap": 4,
            "max_distance": 0.65,
            "provider": MOCK,
        },
        {
            "name": "provider_unavailable",
            "why": (
                "The provider could not be built at all. The route reports the name "
                "'unavailable' with embedding_provider_simulated True. Reading the NAME "
                "made this read as REAL, which is the defect this fixture pins."
            ),
            "counts": _counts(total=2, ready=2, embedded=2),
            "node_rows": [_node(_A, simulated=False), _node(_B, simulated=False)],
            "edge_rows": [_edge(_A, _B, 0.4)],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": UNAVAILABLE,
        },
        {
            "name": "provider_real",
            "why": "A genuine embedding provider. The only shape allowed to read as real.",
            "counts": _counts(total=2, ready=2, embedded=2, simulated=0),
            "node_rows": [_node(_A, simulated=False), _node(_B, simulated=False)],
            "edge_rows": [_edge(_A, _B, 0.18)],
            "node_cap": 60,
            "edge_cap": 240,
            "chunk_cap": 40,
            "max_distance": 0.65,
            "provider": REAL,
        },
    ]


def build() -> Dict[str, Any]:
    """Every scenario, run through the real assemble_graph, as JSON ready data."""
    from app.services.knowledge_graph import assemble_graph

    out: Dict[str, Any] = {
        "generated_by": "scripts/gen_knowledge_graph_fixtures.py",
        "how_to_regenerate": "python3 scripts/gen_knowledge_graph_fixtures.py",
        "why": (
            "Generated from app.services.knowledge_graph.assemble_graph so the "
            "TypeScript checks cannot be green about a payload shape the route does "
            "not produce. Do not edit by hand."
        ),
        "scenarios": {},
    }
    for spec in _scenarios():
        graph = assemble_graph(
            counts=spec["counts"],
            node_rows=spec["node_rows"],
            edge_rows=spec["edge_rows"],
            node_cap=spec["node_cap"],
            edge_cap=spec["edge_cap"],
            chunk_cap=spec["chunk_cap"],
            max_distance=spec["max_distance"],
            provider=spec["provider"],
        )
        out["scenarios"][spec["name"]] = {
            "why": spec["why"],
            "payload": graph.as_dict(),
        }
    return out


def main() -> int:
    data = build()
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE_PATH.relative_to(ROOT)} with {len(data['scenarios'])} scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
