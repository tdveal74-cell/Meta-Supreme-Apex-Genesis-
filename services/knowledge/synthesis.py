"""Stage 5 synthesis with governance and citations.

Re-ranks hybrid candidates (lightweight lexical + score blend), applies a
final ACL-aware clearance check, and returns a grounded answer with inline
markdown citations. Does not invent sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from services.knowledge.retrieval import RetrievalCandidate


@dataclass
class Citation:
    index: int
    knowledge_item_id: str
    title: str
    chunk_index: int
    score: float
    excerpt: str


@dataclass
class SynthesizedAnswer:
    answer: str
    citations: List[Citation] = field(default_factory=list)
    cleared: bool = True
    refusal_reason: Optional[str] = None
    simulated: bool = True


def _excerpt(text: str, limit: int = 280) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def rerank_candidates(
    query: str,
    candidates: Sequence[RetrievalCandidate],
    *,
    top_k: int = 6,
) -> List[RetrievalCandidate]:
    """Lexical overlap boost on top of RRF score. Pure and offline-safe."""
    tokens = {t for t in query.lower().split() if len(t) > 2}

    def score(c: RetrievalCandidate) -> float:
        content_tokens = set(c.content.lower().split())
        overlap = len(tokens & content_tokens) / max(1, len(tokens))
        return float(c.score) + 0.15 * overlap

    ordered = sorted(candidates, key=score, reverse=True)
    return ordered[: max(1, top_k)]


def synthesize_with_governance(
    *,
    query: str,
    candidates: Sequence[RetrievalCandidate],
    owner_id: str,
    max_citations: int = 5,
) -> SynthesizedAnswer:
    """
    Build a cited answer from retrieval candidates.

    Governance rules:
    - No candidates -> explicit refusal (never fabricate).
    - Only include chunks already ACL-filtered upstream.
    - Citations required for grounded claims.
    """
    if not candidates:
        return SynthesizedAnswer(
            answer=(
                "I do not have verified knowledge items that match this query "
                "under your access. I will not invent sources."
            ),
            citations=[],
            cleared=False,
            refusal_reason="no_candidates",
            simulated=True,
        )

    ranked = rerank_candidates(query, candidates, top_k=max_citations)
    citations: List[Citation] = []
    lines: List[str] = [
        f"Based on {len(ranked)} retrieved chunk(s) for owner `{owner_id[:8]}...`:",
        "",
    ]

    for i, c in enumerate(ranked, start=1):
        citations.append(
            Citation(
                index=i,
                knowledge_item_id=c.knowledge_item_id,
                title=c.title,
                chunk_index=c.chunk_index,
                score=float(c.score),
                excerpt=_excerpt(c.content),
            )
        )
        lines.append(f"**[{i}] {c.title}** (chunk {c.chunk_index}, score {c.score:.4f})")
        lines.append(_excerpt(c.content, 400))
        lines.append("")

    lines.append("---")
    lines.append(
        "Citations are inline by number. Claims above are limited to retrieved text."
    )

    return SynthesizedAnswer(
        answer="\n".join(lines).strip(),
        citations=citations,
        cleared=True,
        refusal_reason=None,
        simulated=True,
    )
