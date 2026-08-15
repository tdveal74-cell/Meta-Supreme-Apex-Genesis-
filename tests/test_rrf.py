"""Unit tests for reciprocal rank fusion."""

from __future__ import annotations

import pytest

from services.knowledge.rrf import (
    fuse_named_signals,
    rank_map_from_scores,
    reciprocal_rank_fusion,
)


def test_empty_lists_return_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_single_list_preserves_order_by_score():
    result = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
    ids = [doc_id for doc_id, _ in result]
    assert ids == ["a", "b", "c"]
    assert result[0][1] > result[1][1] > result[2][1]


def test_agreement_boosts_shared_docs():
    result = reciprocal_rank_fusion(
        [
            ["a", "b", "c"],
            ["a", "d", "e"],
        ],
        k=60,
    )
    assert result[0][0] == "a"
    assert result[0][1] > result[1][1]


def test_weights_change_influence():
    unweighted = reciprocal_rank_fusion(
        [["x", "y"], ["y", "x"]],
        k=60,
        weights=[1.0, 1.0],
    )
    weighted = reciprocal_rank_fusion(
        [["x", "y"], ["y", "x"]],
        k=60,
        weights=[0.1, 5.0],
    )
    assert weighted[0][0] == "y"
    assert unweighted[0][0] in {"x", "y"}


def test_k_must_be_positive():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)


def test_weights_length_mismatch():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"], ["b"]], weights=[1.0])


def test_missing_ids_skipped():
    result = reciprocal_rank_fusion([["", "a", "b"]], k=60)
    ids = [doc_id for doc_id, _ in result]
    assert ids == ["a", "b"]


def test_rank_map_from_scores():
    ordered = rank_map_from_scores({"b": 0.2, "a": 0.9, "c": 0.9})
    assert ordered[0] == "a"
    assert ordered[1] == "c"
    assert ordered[2] == "b"


def test_fuse_named_signals():
    result = fuse_named_signals(
        {
            "dense": ["d1", "d2"],
            "sparse": ["d2", "d3"],
            "empty": [],
        },
        k=60,
        weights={"dense": 1.0, "sparse": 1.0},
    )
    ids = [doc_id for doc_id, _ in result]
    assert "d2" in ids
    assert ids[0] in {"d1", "d2", "d3"}
