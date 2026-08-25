"""
Behavioural probe for the Build 12 conflict policy, run as its own process.

Same containment rule as _selftest.py: this file is executed by
test_deploy_soul_conflict_policy.py in a subprocess, never imported.
Importing it in-process would pin the vendored (trimmed) `services` tree
on sys.path for the rest of the pytest session.

A stub layer stands in for Pinecone, so the probe proves the policy bands,
the status:active filter, and the fail-closed guards without a network.
Prints one JSON object of findings on stdout; asserts nothing itself, so
the failure messages live with the tests.
"""

import asyncio
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import os  # noqa: E402

os.environ["CONSOLE_TOKEN"] = "probe-token"
os.environ["PINECONE_API_KEY"] = "probe-key"

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from services.intelligence.providers.base import ProviderError  # noqa: E402
from services.intelligence.soul import SoulRecall, SoulRecord  # noqa: E402

client = TestClient(main.app, raise_server_exceptions=False)
AUTH = {"Authorization": "Bearer probe-token"}
CLAIM = {"claim": "Ledger completion events should start learning automatically."}


def record(id_, score, text, source="tee-soul-layer", **metadata):
    return SoulRecord(
        id=id_,
        text=text,
        score=score,
        source=source,
        kind=metadata.pop("kind", "ruling"),
        heading=metadata.pop("heading", ""),
        area=metadata.pop("area", ""),
        dated=metadata.pop("dated", "2026-08-20"),
        metadata=metadata,
    )


def recall_of(*records, errors=()):
    tee = [r for r in records if r.source == "tee-soul-layer"]
    devon = [r for r in records if r.source == "devon-soul"]
    return SoulRecall(
        query="probe",
        records=list(records),
        tee_count=len(tee),
        devon_count=len(devon),
        errors=list(errors),
    )


class StubLayer:
    def __init__(self, result=None, exc=None, delay=0.0):
        self._result = result if result is not None else recall_of()
        self._exc = exc
        self._delay = delay

    async def recall(self, text, *, top_k_tee=4, top_k_devon=3):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc:
            raise self._exc
        return self._result


REAL_LAYER = main._layer


def receipt_for(layer, headers=AUTH, body=None):
    main._layer = lambda: layer
    try:
        return client.post(
            "/api/v1/soul/conflict-search", json=body or CLAIM, headers=headers
        )
    finally:
        main._layer = REAL_LAYER


def digest(response):
    body = response.json()
    return {
        "status_code": response.status_code,
        "complete": body.get("complete"),
        "conflict_status": body.get("conflict_status"),
        "bands": [m.get("band") for m in body.get("matched_records", [])],
        "matched_ids": [m.get("id") for m in body.get("matched_records", [])],
        "decision": (body.get("policy") or {}).get("decision"),
        "notes": body.get("notes"),
    }


# The live close-out shape: five real tee rulings at 0.10-0.22, none of them
# a contradiction. One deliberately carries "never" — prohibition language in
# a weak match is someone else's rule about someone else's territory.
WEAK_FIVE = [
    record("r-boundary", 0.22, "Soul Layer Boundary: world knowledge stays in pgvector, never in tee-soul-layer."),
    record("r-voice", 0.20, "Voice rulings describe how DEVON phrases an answer."),
    record("r-filing", 0.18, "Captures are filed through the Thread Log lane."),
    record("r-naming", 0.13, "Naming follows the SYS_ prefix convention."),
    record("r-areas", 0.10, "Areas group rulings by the part of the estate they govern."),
]

out = {}

out["weak_only"] = digest(receipt_for(StubLayer(recall_of(*WEAK_FIVE))))

out["adjacent"] = digest(
    receipt_for(StubLayer(recall_of(WEAK_FIVE[0], record("r-adj", 0.45, "Learning starts from ledger events after review."))))
)

out["adjacent_boundary"] = digest(
    receipt_for(StubLayer(recall_of(record("r-edge", 0.35, "Plainly related ruling text."))))
)

out["strong_no_cue"] = digest(
    receipt_for(StubLayer(recall_of(record("r-strong", 0.72, "The write-back lane feeds tee-soul-layer from the Thread Log."))))
)

out["strong_cue"] = digest(
    receipt_for(StubLayer(recall_of(record("r-nowrite", 0.72, "DEVON must not write to tee-soul-layer; that path stays closed."))))
)

out["strong_boundary"] = digest(
    receipt_for(StubLayer(recall_of(record("r-sixty", 0.60, "A ruling squarely about the claim's ground."))))
)

out["strong_cue_typographic"] = digest(
    receipt_for(StubLayer(recall_of(record("r-typo", 0.72, "Don’t write to that index from this path."))))
)

out["adjacent_cue_is_not_a_conflict"] = digest(
    receipt_for(StubLayer(recall_of(record("r-adjcue", 0.45, "That lane must not be used for canon."))))
)

out["mixed_strong_and_adjacent"] = digest(
    receipt_for(
        StubLayer(
            recall_of(
                record("r-mixs", 0.72, "The write-back lane feeds tee-soul-layer."),
                record("r-mixa", 0.45, "A related operational note."),
            )
        )
    )
)

out["zero_score"] = digest(
    receipt_for(StubLayer(recall_of(record("r-zero", 0.0, "A hit whose score never arrived."))))
)

out["superseded_strong_filtered"] = digest(
    receipt_for(
        StubLayer(
            recall_of(
                record("r-old", 0.90, "An old ruling that must not bind anyone.", status="superseded"),
                record("r-live", 0.15, "A live but merely adjacent ruling.", status="active"),
            )
        )
    )
)

out["no_matches"] = digest(receipt_for(StubLayer(recall_of())))

# Five superseded near-duplicates fill the whole tee window (top_k_tee=5)
# above the weak line: the live active revision could rank sixth, unseen.
out["saturated_window"] = digest(
    receipt_for(
        StubLayer(
            recall_of(
                *[
                    record(f"r-old-{i}", 0.90 - i * 0.01, "A superseded revision of the ruling.", status="superseded")
                    for i in range(5)
                ]
            )
        )
    )
)

# The same shape with a weak floor conceals only weaker hits: everything
# unretrieved scores at or below 0.12, so nothing non-weak can be hiding.
out["saturated_window_weak_floor"] = digest(
    receipt_for(
        StubLayer(
            recall_of(
                record("r-old-top", 0.90, "A superseded revision.", status="superseded"),
                *[
                    record(f"r-low-{i}", 0.12 - i * 0.01, "A weak adjacent ruling.")
                    for i in range(4)
                ],
            )
        )
    )
)

out["whitespace_claim"] = receipt_for(
    StubLayer(recall_of()), body={"claim": "        "}
).status_code

out["unexpected_error"] = digest(
    receipt_for(StubLayer(exc=RuntimeError("wires crossed")))
)

REAL_TIMEOUT = main.CONFLICT_SEARCH_TIMEOUT_S
main.CONFLICT_SEARCH_TIMEOUT_S = 0.05
try:
    out["timeout"] = digest(receipt_for(StubLayer(recall_of(), delay=0.5)))
finally:
    main.CONFLICT_SEARCH_TIMEOUT_S = REAL_TIMEOUT

out["provider_error"] = digest(
    receipt_for(StubLayer(exc=ProviderError("pinecone down", provider="pinecone")))
)

out["failed_both"] = digest(
    receipt_for(
        StubLayer(
            recall_of(
                errors=[
                    "tee-soul-layer unavailable: boom",
                    "devon-soul unavailable: boom",
                ]
            )
        )
    )
)

out["partial_weak"] = digest(
    receipt_for(
        StubLayer(recall_of(*WEAK_FIVE, errors=["devon-soul unavailable: boom"]))
    )
)

out["anonymous"] = receipt_for(StubLayer(recall_of()), headers={}).status_code

shape = receipt_for(StubLayer(recall_of(*WEAK_FIVE))).json()
out["receipt_keys"] = sorted(shape.keys())
out["matched_record_keys"] = sorted(shape["matched_records"][0].keys())
out["policy_keys"] = sorted(shape["policy"].keys())

out["bands"] = {
    "-0.10": main._score_band(-0.1),
    "0.00": main._score_band(0.0),
    "0.01": main._score_band(0.01),
    "0.3499": main._score_band(0.3499),
    "0.35": main._score_band(0.35),
    "0.5999": main._score_band(0.5999),
    "0.60": main._score_band(0.60),
    "1.00": main._score_band(1.0),
}
out["cues"] = {
    "nevertheless": main._opposing_cue("Nevertheless, this is fine."),
    "must_not_upper": main._opposing_cue("This MUST NOT happen again."),
    "plain": main._opposing_cue("A plain descriptive ruling."),
    "read_only": main._opposing_cue("That index is read-only from here."),
    "donot_joined": main._opposing_cue("donotmatchinsideotherwords"),
    "typographic": main._opposing_cue("Don’t write there."),
}

print(json.dumps(out))
