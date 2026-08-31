"""Operator memory is the receipted Live State Ledger.

I do not store memory in localStorage or devon.learning.v1. Those are
Area/phrase hints in a browser, not memory. This package does not open
sockets. The app layer fetches receipted PostgreSQL artifacts and hands
them here as inert dicts. Notion, Drive, and n8n are missing. Pinecone
recall is a different lane, off unless SOUL_RECALL_ENABLED and
PINECONE_API_KEY.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

STORE = "postgresql"
SOURCE = "live-state-ledger"
NOT_MEMORY_KEYS = ("devon.learning.v1", "localStorage")

OPERATIONAL_KINDS = frozenset(
    {"task", "project", "thread", "brief", "plate", "episode"}
)
RULING_KIND = "ruling"


def rank_kind(kind: str | None) -> int:
    """Tee rulings first, then operator files, then notes. No Pinecone."""
    k = (kind or "").strip().lower()
    if k == RULING_KIND:
        return 0
    if k in OPERATIONAL_KINDS:
        return 1
    return 2


def rank_label(kind: str | None) -> str:
    k = (kind or "").strip().lower()
    if k == RULING_KIND:
        return "tee-ruling"
    if k in OPERATIONAL_KINDS:
        return "operator-file"
    return "devon-note"


def from_receipted_artifacts(hits: Iterable[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    """Point a memory read at receipted ledger hits. Does not invent a store."""
    pointed: List[Dict[str, Any]] = []
    for hit in hits or []:
        row = dict(hit)
        kind = row.get("kind") or "lesson"
        row["kind"] = kind
        row["store"] = STORE
        row["source"] = row.get("source") or SOURCE
        row["rank"] = row.get("rank") or rank_label(kind)
        row["localStorage"] = False
        row["learning_v1"] = False
        pointed.append(row)
    return pointed
