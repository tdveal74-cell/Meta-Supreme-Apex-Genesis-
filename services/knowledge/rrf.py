"""Reciprocal Rank Fusion (RRF) for hybrid retrieval.

Pure function. No I/O. k defaults to 60 (Cerebras / Cormack convention).
Missing documents contribute 0 for that signal.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]],
    *,
    k: int = 60,
    weights: Optional[Sequence[float]] = None,
) -> List[Tuple[str, float]]:
    """
    Fuse multiple ranked id lists into a single score-ordered list.

    Args:
        ranked_lists: Each list is best-first document/chunk ids.
        k: RRF constant (default 60).
        weights: Optional per-list weights (default 1.0 each).

    Returns:
        List of (doc_id, score) sorted by score descending, then id ascending
        for stable ties.
    """
    if k < 1:
        raise ValueError("k must be >= 1")

    lists = [list(lst) for lst in ranked_lists if lst is not None]
    if not lists:
        return []

    if weights is None:
        weight_values: List[float] = [1.0] * len(lists)
    else:
        weight_values = list(weights)
        if len(weight_values) != len(lists):
            raise ValueError("weights length must match ranked_lists length")

    scores: Dict[str, float] = {}
    for weight, ranked in zip(weight_values, lists, strict=True):
        if weight == 0:
            continue
        for rank, doc_id in enumerate(ranked, start=1):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + float(weight) * (1.0 / (k + rank))

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def rank_map_from_scores(
    scored: Mapping[str, float],
    *,
    reverse: bool = True,
) -> List[str]:
    """Turn a score map into a best-first id list for RRF input."""
    return [
        doc_id
        for doc_id, _ in sorted(
            scored.items(),
            key=lambda item: (-item[1], item[0]) if reverse else (item[1], item[0]),
        )
    ]


def fuse_named_signals(
    signals: Mapping[str, Sequence[str]],
    *,
    k: int = 60,
    weights: Optional[Mapping[str, float]] = None,
) -> List[Tuple[str, float]]:
    """
    Convenience wrapper: named signals (dense, sparse, rarity, age) to RRF.

    Unknown weight keys are ignored. Missing signal keys are skipped.
    """
    names = [name for name, ranked in signals.items() if ranked]
    ranked_lists = [list(signals[name]) for name in names]
    weight_list: Optional[List[float]] = None
    if weights is not None:
        weight_list = [float(weights.get(name, 1.0)) for name in names]
    return reciprocal_rank_fusion(ranked_lists, k=k, weights=weight_list)
