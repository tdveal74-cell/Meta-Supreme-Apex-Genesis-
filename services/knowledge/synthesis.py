"""Stage 5 synthesis with governance, cross-encoder re-ranking, and citations.

Flow:
  hybrid candidates (RRF)
    → cross-encoder re-rank (LLM-as-judge or offline lexical fallback)
    → final clearance / empty-pool refusal
    → grounded answer with inline citations

Never invents sources. ACL filtering is assumed upstream; this stage
still refuses cleanly when the pool is empty.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

from services.knowledge.retrieval import RetrievalCandidate

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    index: int
    knowledge_item_id: str
    title: str
    chunk_index: int
    score: float
    excerpt: str
    rerank_score: Optional[float] = None


@dataclass
class SynthesizedAnswer:
    answer: str
    citations: List[Citation] = field(default_factory=list)
    cleared: bool = True
    refusal_reason: Optional[str] = None
    simulated: bool = True
    rerank_method: str = "none"


def _excerpt(text: str, limit: int = 280) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


# ---------------------------------------------------------------------------
# Cross-encoder re-ranking
# ---------------------------------------------------------------------------

_JUDGE_SYSTEM = """You are a precise relevance judge for a technical knowledge base.
Score how well the document answers or supports the query.
Return ONLY valid JSON: {"score": <float 0.0 to 10.0>, "reason": "<one short sentence>"}
Do not add any other text."""


def _lexical_boost(query: str, content: str) -> float:
    """Offline-safe overlap signal used as fallback and as a light prior."""
    q_tokens = {t for t in re.findall(r"[a-z0-9]{3,}", query.lower())}
    if not q_tokens:
        return 0.0
    c_tokens = set(re.findall(r"[a-z0-9]{3,}", (content or "").lower()))
    return len(q_tokens & c_tokens) / max(1, len(q_tokens))


def _offline_rerank(
    query: str,
    candidates: Sequence[RetrievalCandidate],
    *,
    top_k: int = 6,
) -> List[RetrievalCandidate]:
    """Deterministic fallback: RRF score + lexical overlap. Never calls a model."""

    def score(c: RetrievalCandidate) -> float:
        return float(c.score) + 0.18 * _lexical_boost(query, c.content)

    ordered = sorted(candidates, key=score, reverse=True)
    for c in ordered:
        c.rerank_score = score(c)
        c.rerank_reason = "offline-lexical"
    return ordered[: max(1, top_k)]


async def _llm_judge_score(
    query: str,
    content: str,
    provider: Any,
) -> tuple[float, str]:
    """Single (query, document) judgment. Returns (score, reason)."""
    user_msg = f"Query: {query}\n\nDocument:\n{(content or '')[:1800]}"
    try:
        if hasattr(provider, "complete"):
            raw = await provider.complete(
                system=_JUDGE_SYSTEM,
                user=user_msg,
                max_tokens=120,
            )
            text = raw if isinstance(raw, str) else getattr(raw, "text", str(raw))
        elif hasattr(provider, "chat"):
            raw = await provider.chat(
                messages=[
                    {"role": "system", "content": _JUDGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ]
            )
            text = raw if isinstance(raw, str) else getattr(raw, "content", str(raw))
        else:
            return 0.0, "provider-unsupported"

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return 0.0, "parse-failed"
        data = json.loads(match.group(0))
        score = float(data.get("score", 0.0))
        score = max(0.0, min(10.0, score))
        reason = str(data.get("reason", ""))[:200]
        return score, reason
    except Exception as exc:  # noqa: BLE001
        logger.warning("cross-encoder judge failed: %s", exc)
        return 0.0, f"error:{type(exc).__name__}"


async def cross_encoder_rerank(
    query: str,
    candidates: Sequence[RetrievalCandidate],
    *,
    top_k: int = 6,
    provider: Any = None,
) -> tuple[List[RetrievalCandidate], str]:
    """
    Cross-encoder style re-rank.

    Primary: LLM-as-judge (true cross-attention via the completion model).
    Fallback: offline lexical + RRF blend so the system never hard-fails.

    Returns (ordered_candidates, method_used).
    """
    if not candidates:
        return [], "empty"

    use_llm = False
    if provider is not None and getattr(provider, "name", "") not in ("mock", "", None):
        use_llm = True

    if not use_llm:
        return _offline_rerank(query, candidates, top_k=top_k), "offline-lexical"

    scored: List[tuple[float, RetrievalCandidate, str]] = []
    for c in candidates:
        score, reason = await _llm_judge_score(query, c.content, provider)
        # Light prior from original RRF so a zero judge score does not erase consensus
        blended = 0.85 * score + 0.15 * (float(c.score) * 10.0)
        c.rerank_score = blended
        c.rerank_reason = reason
        scored.append((blended, c, reason))

    scored.sort(key=lambda t: (-t[0], t[1].embedding_id))
    ordered = [c for _, c, _ in scored[: max(1, top_k)]]
    return ordered, "llm-judge"


# ---------------------------------------------------------------------------
# Public synthesis entry points
# ---------------------------------------------------------------------------

def synthesize_with_governance(
    *,
    query: str,
    candidates: Sequence[RetrievalCandidate],
    owner_id: str,
    max_citations: int = 5,
    reranked: Optional[Sequence[RetrievalCandidate]] = None,
    rerank_method: str = "offline-lexical",
) -> SynthesizedAnswer:
    """
    Build a cited answer from retrieval candidates.

    Governance rules:
    - No candidates -> explicit refusal (never fabricate).
    - Only include chunks already ACL-filtered upstream.
    - Citations required for grounded claims.
    """
    if not candidates and not reranked:
        return SynthesizedAnswer(
            answer=(
                "I do not have verified knowledge items that match this query "
                "under your access. I will not invent sources."
            ),
            citations=[],
            cleared=False,
            refusal_reason="no_candidates",
            simulated=True,
            rerank_method="none",
        )

    ranked = list(reranked) if reranked is not None else _offline_rerank(
        query, candidates, top_k=max_citations
    )
    ranked = ranked[: max(1, max_citations)]

    citations: List[Citation] = []
    lines: List[str] = [
        f"Based on {len(ranked)} retrieved chunk(s) for owner `{owner_id[:8]}...`:",
        "",
    ]

    for i, c in enumerate(ranked, start=1):
        rr = getattr(c, "rerank_score", None)
        citations.append(
            Citation(
                index=i,
                knowledge_item_id=c.knowledge_item_id,
                title=c.title,
                chunk_index=c.chunk_index,
                score=float(c.score),
                excerpt=_excerpt(c.content),
                rerank_score=float(rr) if rr is not None else None,
            )
        )
        score_note = f"rrf={c.score:.4f}"
        if rr is not None:
            score_note += f", rerank={float(rr):.2f}"
        lines.append(f"**[{i}] {c.title}** (chunk {c.chunk_index}, {score_note})")
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
        rerank_method=rerank_method,
    )


async def synthesize_with_cross_encoder(
    *,
    query: str,
    candidates: Sequence[RetrievalCandidate],
    owner_id: str,
    max_citations: int = 5,
    provider: Any = None,
) -> SynthesizedAnswer:
    """
    Full Stage 5 entry: cross-encoder re-rank then governed synthesis.

    Prefer this from the pipeline when a completion provider is available.
    Falls back safely when the provider is mock or missing.
    """
    ranked, method = await cross_encoder_rerank(
        query, candidates, top_k=max_citations, provider=provider
    )
    return synthesize_with_governance(
        query=query,
        candidates=candidates,
        owner_id=owner_id,
        max_citations=max_citations,
        reranked=ranked,
        rerank_method=method,
    )
