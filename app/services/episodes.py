"""What Tee has already said on air, and whether a new idea repeats it.

The estate could not answer one question before this: "have I covered this
already?" Three shows shipping weekly means the failure mode is not forgetting
an idea, it is making the same episode twice without noticing. Nothing watched
for that. Measured 2026-09-16: three rendered episodes landed in Drive inside
48 hours and not one carried a transcript beside it, so there was nothing to
ask the question against even in principle.

An episode transcript is stored as an ordinary ``KnowledgeItem`` with
``source_type`` of ``episode_transcript``, so it is chunked, embedded and
searched by machinery that already exists and is already tested. Nothing new
holds the text.

Two rules here carry the weight:

1. **Coverage is asked of episodes only.** A draft outline and a published
   episode live in the same table. Matching the outline and answering "yes,
   you covered that" sends Tee looking for an episode that does not exist,
   which is worse than answering nothing. ``already_covered`` passes
   ``source_types`` and never searches wider.

2. **A weak match is not coverage.** Past ``COVERAGE_FLOOR`` the answer is
   "not covered", with the nearest miss reported as a nearest miss. This is
   the same discipline as the parser's 0.78 floor: declining is a legitimate
   answer and guessing is not.

3. **A mock embedding cannot answer this question at all.** Measured
   2026-09-16 against ``MockEmbeddingProvider``, which is a normalised hashed
   bag-of-words: a genuinely on topic question scored 0.6170 against the jobs
   episode, and a SOURDOUGH RECIPE scored 0.6406 against the same episode.
   Two hundredths apart, because shared English function words swamp the
   signal at that length. No floor separates those, so any floor that admits
   the real match admits the recipe. A deployment whose embedding provider
   falls back to mock would therefore answer "yes, you covered that" about an
   episode that does not exist, confidently and in the feature's own voice.
   ``already_covered`` refuses outright rather than returning a number it
   cannot stand behind. Search still works on the mock; a VERDICT does not.

Deduplication is by transcript fingerprint, not by title. Renders repeat: the
same episode was exported three times on 2026-09-15 under one title, and
ingesting all three would have let one episode outvote the rest of the
catalogue on every query.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeItem
from app.services.knowledge import ingest_knowledge, search_knowledge

#: The one source_type this module reads and writes. A literal, because a
#: typo here would silently search an empty set and answer "never covered"
#: to everything, which is a confident wrong answer rather than an error.
EPISODE_SOURCE_TYPE = "episode_transcript"

#: pgvector returns COSINE DISTANCE, so smaller is closer and this is a
#: ceiling rather than a threshold. 0.45 is roughly "clearly about the same
#: subject" for the normalised bag-of-words and the hosted embedding models
#: this estate uses; an unrelated question lands far above it.
#:
#: UNVERIFIED against a real embedding model. It has never been measured
#: against hosted embeddings from this repository, because the tests run on
#: the mock and the mock cannot tell a matching episode from a recipe (see
#: point 3 above). The first real transcripts through a hosted provider are
#: what sets it; until then it is a starting point, and `decide_coverage`
#: takes it as an argument so moving it is one call rather than an edit here.
COVERAGE_FLOOR = 0.45

#: The ONLY embedding providers whose distances may answer a yes or no
#: question about what was said on air. An allowlist, not a denylist, and the
#: inversion was earned rather than chosen.
#:
#: Measured 2026-09-17. The provider that actually embeds is resolved by
#: `app/services/knowledge.py:34-48`, and it reads `DEFAULT_AI_PROVIDER`, not
#: `EMBEDDING_PROVIDER`, because `DEFAULT_EMBEDDING_PROVIDER` is not a field
#: on settings at all. `app/services/knowledge_graph.py:204-218` had already
#: written that down and verified it by running it. Only `mock` and `openai`
#: can embed; every other value raises ProviderConfigError.
#:
#: So `DEFAULT_AI_PROVIDER` on this estate is a CHAT provider name, and a
#: denylist of ("mock",) let `cerebras` or `anthropic` sail straight through
#: the guard into a search that then raised, turning a clear "these distances
#: cannot carry a verdict" into a 503 about provider configuration. Same
#: outcome for the caller, a worse answer for the reader.
#:
#: An allowlist fails closed: anything not named here refuses, and a new
#: provider has to be measured before it is trusted rather than trusted until
#: it is caught.
TRUSTED_FOR_COVERAGE = ("openai",)

#: Kept as the inverse view for readers and for the test that pins the
#: mock's exclusion. Derived, never edited by hand.
UNTRUSTED_FOR_COVERAGE = ("mock",)

#: How many passages a coverage answer will carry back at most.
MAX_COVERAGE_HITS = 5


def transcript_fingerprint(transcript: str) -> str:
    """A stable id for one transcript's text, whitespace normalised.

    Renders repeat. Three exports of one episode landed in Drive on
    2026-09-15 under a single title with three different byte counts, and
    three copies in the store would let one episode outvote the catalogue.
    Fingerprinting the TEXT rather than the file catches a re-render whose
    container changed and whose words did not.
    """
    normalised = " ".join((transcript or "").split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


async def find_by_fingerprint(
    db: AsyncSession, *, owner_id: str, fingerprint: str
) -> Optional[KnowledgeItem]:
    """The owner's episode already holding this text, if there is one."""
    result = await db.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.owner_id == owner_id,
            KnowledgeItem.source_type == EPISODE_SOURCE_TYPE,
            KnowledgeItem.external_id == fingerprint,
        )
    )
    return result.scalars().first()


async def record_episode_transcript(
    db: AsyncSession,
    *,
    owner_id: str,
    title: str,
    transcript: str,
    show: Optional[str] = None,
    source_uri: Optional[str] = None,
    spoken_at: Optional[str] = None,
    transcript_confidence: Optional[float] = None,
    provider: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> tuple:
    """Store one episode transcript. Returns (item, created).

    ``created`` is False when this exact text was already held, and the
    existing item comes back untouched. Re-ingesting would spend the
    embedding call again and double that episode's weight in every later
    search, so the caller is told rather than quietly given a second copy.
    """
    text = (transcript or "").strip()
    if not text:
        raise ValueError("an episode transcript cannot be empty")

    fingerprint = transcript_fingerprint(text)
    existing = await find_by_fingerprint(db, owner_id=owner_id, fingerprint=fingerprint)
    if existing is not None:
        return existing, False

    payload: Dict[str, Any] = {
        "show": show or "",
        "spoken_at": spoken_at or "",
        "fingerprint": fingerprint,
        # Carried, never defaulted to a number. A confidence the transcriber
        # did not report is not a confidence of zero.
        "transcript_confidence": transcript_confidence,
        "transcriber": provider or "",
    }
    if meta:
        payload.update(meta)

    item = await ingest_knowledge(
        db,
        owner_id=owner_id,
        title=title,
        content=text,
        source_type=EPISODE_SOURCE_TYPE,
        source_uri=source_uri,
        meta=payload,
    )
    item.external_id = fingerprint
    try:
        await db.flush()
    except IntegrityError:
        # Another ingest of the same words won the unique index between our
        # read and our write. The read-then-write above is not atomic and
        # concurrent renders of one episode are the expected case, not a
        # corner: three exports of a single episode landed in Drive inside an
        # hour on 2026-09-15.
        #
        # This costs an embedding call that is then thrown away, which is the
        # honest price of losing the race and is cheaper than the duplicate.
        # The caller still gets the stored item and `created` False, so it
        # cannot tell a loss apart from an ordinary repeat, and does not need
        # to.
        await db.rollback()
        winner = await find_by_fingerprint(
            db, owner_id=owner_id, fingerprint=fingerprint
        )
        if winner is None:
            raise
        return winner, False
    return item, True


def embedding_provider_name() -> str:
    """The configured embedding provider's name, lowercased."""
    from app.core.config import settings

    configured = (
        getattr(settings, "DEFAULT_EMBEDDING_PROVIDER", None)
        or getattr(settings, "DEFAULT_AI_PROVIDER", "")
        or ""
    )
    return str(configured).strip().lower()


def decide_coverage(
    hits: List[Dict[str, Any]], *, question: str, floor: float
) -> Dict[str, Any]:
    """Turn ranked hits into a coverage verdict. Pure, so it can be tested.

    Split out from the query deliberately. The embedding provider decides
    whether the DISTANCES mean anything; this decides what a given set of
    distances implies, and those are two different failures with two
    different fixes. Keeping them together meant the floor logic could only
    be exercised through a provider that cannot rank these documents, which
    is how a threshold ends up tuned until the tests go green.
    """
    if not hits:
        return {
            "covered": False,
            "answerable": True,
            "question": question,
            "reason": (
                "there are no episode transcripts stored for this owner, so "
                "this is not an answer about the catalogue. It is an empty "
                "catalogue."
            ),
            "matches": [],
            "nearest": None,
            "floor": floor,
        }

    within = [h for h in hits if h["distance"] <= floor]
    nearest = min(hits, key=lambda h: h["distance"])

    if not within:
        return {
            "covered": False,
            "answerable": True,
            "question": question,
            "reason": (
                f"the closest passage is {nearest['title']!r} at a distance of "
                f"{nearest['distance']:.3f}, past the floor of {floor:.2f}. "
                "Declining rather than calling that coverage."
            ),
            "matches": [],
            "nearest": _shape(nearest),
            "floor": floor,
        }

    return {
        "covered": True,
        "answerable": True,
        "question": question,
        "reason": (
            f"{len(within)} passage(s) inside the floor of {floor:.2f}, the "
            f"closest at {nearest['distance']:.3f}."
        ),
        "matches": [_shape(h) for h in within],
        "nearest": _shape(nearest),
        "floor": floor,
    }


async def already_covered(
    db: AsyncSession,
    *,
    owner_id: str,
    question: str,
    floor: float = COVERAGE_FLOOR,
    limit: int = MAX_COVERAGE_HITS,
) -> Dict[str, Any]:
    """Has this been said on air, and where.

    Answers from episode transcripts alone, and only when the embedding
    provider's distances can carry a yes or no. ``answerable`` is False when
    they cannot, and that is not the same claim as "never covered".
    """
    asked = (question or "").strip()
    if not asked:
        return {
            "covered": False,
            "answerable": True,
            "question": "",
            "reason": "no question was asked, so nothing was searched.",
            "matches": [],
            "nearest": None,
            "floor": floor,
        }

    provider = embedding_provider_name()
    if provider not in TRUSTED_FOR_COVERAGE:
        detail = (
            "Measured 2026-09-16: an on topic question scored 0.617 against "
            "an episode and a sourdough recipe scored 0.641 against the same "
            "one, so no floor separates them."
            if provider in UNTRUSTED_FOR_COVERAGE
            else (
                "Only "
                + ", ".join(TRUSTED_FOR_COVERAGE)
                + " has been measured well enough to carry a verdict here."
            )
        )
        return {
            "covered": False,
            "answerable": False,
            "question": asked,
            "reason": (
                f"the embedding provider is {provider!r}, whose distances "
                f"cannot be trusted to separate a matching episode from an "
                f"unrelated one. {detail} Refusing to answer rather than "
                "returning a verdict built on that. This is not a claim "
                "about the catalogue."
            ),
            "matches": [],
            "nearest": None,
            "floor": floor,
        }

    hits = await search_knowledge(
        db,
        owner_id=owner_id,
        query=asked,
        limit=max(1, min(limit, MAX_COVERAGE_HITS)),
        source_types=[EPISODE_SOURCE_TYPE],
    )
    return decide_coverage(hits, question=asked, floor=floor)


def _shape(hit: Dict[str, Any]) -> Dict[str, Any]:
    """One search hit as a coverage answer carries it."""
    return {
        "knowledge_item_id": hit["knowledge_item_id"],
        "title": hit["title"],
        "passage": hit["content"],
        "chunk_index": hit["chunk_index"],
        "distance": hit["distance"],
    }
