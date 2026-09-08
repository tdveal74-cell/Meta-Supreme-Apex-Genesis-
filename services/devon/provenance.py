"""Provenance for the Live State Ledger: a hash chain over the Event Bus and a
signed Universal Receipt.

WHY THIS EXISTS

The ledger already refuses an event outside the thirteen and a second receipt on
an intent, and both refusals are owned by the database. What nothing owned was
the record's integrity after the fact. A row that was rewritten in place, a row
removed from the middle of an intent, or a receipt whose text was edited after
it was issued all read as perfectly legal history, because every check the
estate had was a check on the next write and none was a check on the past.

Tee's ecosystem spec asks for the missing half: every state transition on the
Event Bus carries an immutable SHA-256 hash, and the Universal Receipt closes
the intent with a signed verification payload. This module is that doctrine as
pure functions. It hashes, chains, verifies and signs. It reads nothing and
writes nothing; the ledger writer in ``app/services/live_state_ledger.py``
calls it on every append and on every receipt, and the database refuses an
UPDATE on either table so the chain can only grow.

WHAT THE HASH COVERS

Each event's hash is SHA-256 over a canonical JSON document holding the chain
version, the previous event's hash, the intent id, the sequence number, the
event name, the action id, the payload, and the time the event occurred. The
first event of an intent links to ``GENESIS``, the empty string.

The payload is hashed as the database will hand it back, never as Python first
serialised it. A gauntlet on 2026-09-08 fed the writer ``{"v": 1e16}`` and
``{"v": -0.0}``: Python renders those ``1e+16`` and ``-0.0``, JSONB stores
numerics and renders ``10000000000000000`` and ``0.0``, and the verifier,
reading the stored row, found every such event "altered". So the writer asks
PostgreSQL to render the payload through ``jsonb`` before hashing, decodes that
rendering the same way the ORM decodes the stored column, and hashes the
result; the verifier does the same to the stored row. Both sides now hash the
same bytes by construction. The canonical form sorts keys and uses the
tightest separators, and it refuses NaN and infinity, which JSON cannot carry
and PostgreSQL would reject at the insert.

WHAT THE SIGNATURE COVERS

The receipt digest is SHA-256 over the intent id, the head hash of the chain,
the chain length, the receipt's six fields and its issue time. The signature is
HMAC-SHA256 of that digest under the receipt signing key. A verifier holding the
key checks both; a reader without the key can still recompute the digest and
the chain, which is the point of keeping the two separate. ``key_id`` names the
key without revealing it, and a verifier may hold a ring of previous keys, so
a receipt signed before a rotation still verifies and reports which key it was
signed under rather than reading as forged.

The receipt key is not the JWT key. ``derive_receipt_key`` turns the estate
secret into a distinct signing key when no dedicated ``RECEIPT_SIGNING_KEY``
is set, so a service that only verifies tokens never needs to hold the key that
signs receipts. Derivation does not shrink the blast radius of a leaked estate
secret; a dedicated key that the presence service never receives does, and
that is the setting the compose stack passes only to the API.

ROWS THAT PREDATE THE CHAIN

Events written before migration 019 carry an empty hash. They are counted and
reported as ``unhashed`` rather than treated as broken: refusing every receipt
on every intent that was open at deploy time would be a false alarm, and
backfilling a hash would claim a provenance those rows never had. A verdict is
``complete`` only when every link is hashed.

The grace is a prefix, not a licence. Unhashed rows may only stand at the start
of an intent, where a pre 019 writer put them. An unhashed row after a hashed
one was written around the writer, and the verifier names it as a break rather
than letting the chain restart from genesis behind it. That was the second
gauntlet finding of 2026-09-08.

WHAT THE DATABASE OWNS

Migration 019 refuses UPDATE on events and receipts outright, and refuses a
direct DELETE while admitting the cascade from intents and users, because an
owner's right to be removed outranks the audit trail. A role that can disable
those triggers can rewrite anything; that is the table owner, and the
boundary is stated rather than pretended away.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

SOURCE = {
    "drive_id": None,
    "title": "DEVON Ecosystem control plane: cryptographic state ledger and provenance",
    "supplied_by": "Tee",
    "supplied": "2026-09-08",
    "file_as": "SYS_SPEC_devon-control-plane-workspace_v1_2026-09-08",
    "note": (
        "Compiled from the 2026-09-08 control plane brief, safeguard 3. "
        "When the brief is filed to the vault, record its Drive id here."
    ),
}

#: The first event of an intent links to nothing.
GENESIS = ""

#: Bumped only when the canonical material changes shape. A verifier that sees
#: a version it does not know reports it rather than guessing.
CHAIN_VERSION = 1

HASH_ALGORITHM = "sha256"
SIGNATURE_ALGORITHM = "hmac-sha256"


def canonical(value: Any) -> str:
    """The one serialisation both the writer and the verifier can reproduce.

    Keys sorted, no whitespace, non ASCII kept as is. Anything json cannot
    represent raises on purpose: an unserialisable object raises ``TypeError``
    and NaN or infinity raise ``ValueError``. Coercing either would produce a
    hash the verifier cannot recompute from the stored row, and PostgreSQL
    refuses NaN in jsonb anyway, so the refusal lands before the insert.
    """
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def check_payload(payload: Any) -> Optional[str]:
    """Why this payload cannot be hashed, or None when it can.

    A payload has to survive the trip through canonical JSON and UTF-8, which
    is what the database and the hash both need. A lone surrogate passes
    ``json.dumps`` and then fails to encode; NaN passes ``json.loads`` at the
    API door and then fails here. Naming the reason at the door turns a 500
    at the insert into a refusal the caller can read.
    """
    # UnicodeEncodeError is a ValueError, so it is caught first or never.
    try:
        rendered = canonical(payload)
        rendered.encode("utf-8")
    except UnicodeEncodeError as exc:
        return f"payload carries text UTF-8 cannot encode: {exc.reason}"
    except (TypeError, ValueError) as exc:
        return f"payload carries a value JSON cannot represent: {exc}"
    # json.dumps escapes a NUL as \u0000, which UTF-8 carries and jsonb does
    # not: PostgreSQL refuses it at the cast, mid transaction. Refuse it here.
    if "\\u0000" in rendered:
        return "payload carries a NUL character, which jsonb cannot store"
    return None


def format_time(moment: datetime) -> str:
    """UTC, ISO 8601, microsecond precision. The exact string that is hashed."""
    if moment.tzinfo is None:
        raise ValueError("a naive datetime cannot be hashed: its instant is ambiguous")
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds")


def event_hash(
    *,
    prev_hash: str,
    intent_id: str,
    sequence_no: int,
    name: str,
    action_id: Optional[str],
    payload: Mapping[str, Any],
    occurred_at: str,
) -> str:
    """SHA-256 over the canonical material of one event, linked to the one before."""
    material = canonical(
        {
            "v": CHAIN_VERSION,
            "prev": prev_hash,
            "intent_id": intent_id,
            "sequence_no": sequence_no,
            "name": name,
            "action_id": action_id,
            "payload": dict(payload),
            "occurred_at": occurred_at,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainLink:
    """One event as the verifier sees it: what was stored, nothing inferred."""

    sequence_no: int
    name: str
    prev_hash: str
    hash: str
    action_id: Optional[str]
    payload: Mapping[str, Any]
    occurred_at: str


@dataclass(frozen=True)
class ChainVerdict:
    """What a walk over the chain found. ``findings`` names every break."""

    intact: bool
    complete: bool
    length: int
    hashed: int
    unhashed: int
    head_hash: str
    findings: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intact": self.intact,
            "complete": self.complete,
            "length": self.length,
            "hashed": self.hashed,
            "unhashed": self.unhashed,
            "head_hash": self.head_hash,
            "findings": list(self.findings),
            "algorithm": HASH_ALGORITHM,
            "chain_version": CHAIN_VERSION,
        }


def verify_chain(intent_id: str, links: Sequence[ChainLink]) -> ChainVerdict:
    """Walk the chain and report every break, never just the first.

    A break is a sequence gap or reorder, a link whose ``prev_hash`` is not the
    hash before it, a link whose stored hash is not what its own material
    recomputes to, or an unhashed link standing after a hashed one. Unhashed
    links at the start of the chain (written before 019) are counted
    separately and do not break it; they only stop it being complete. The
    verdict's head hash is the last stored hash, which is what a receipt binds
    to.
    """
    findings: List[str] = []
    hashed = 0
    unhashed = 0
    expected_prev = GENESIS

    for position, link in enumerate(links, start=1):
        if link.sequence_no != position:
            findings.append(
                f"sequence {position} is missing or out of order: found "
                f"sequence {link.sequence_no} ({link.name}) in its place"
            )
        if not link.hash:
            unhashed += 1
            if hashed:
                findings.append(
                    f"sequence {link.sequence_no} ({link.name}) carries no hash but "
                    "stands after hashed events: it was written around the writer, "
                    "not before the chain"
                )
            expected_prev = GENESIS
            continue
        hashed += 1
        if link.prev_hash != expected_prev:
            findings.append(
                f"sequence {link.sequence_no} ({link.name}) does not link to the "
                f"event before it: prev_hash {link.prev_hash[:12]} where "
                f"{(expected_prev or 'genesis')[:12]} was expected"
            )
        recomputed = event_hash(
            prev_hash=link.prev_hash,
            intent_id=intent_id,
            sequence_no=link.sequence_no,
            name=link.name,
            action_id=link.action_id,
            payload=link.payload,
            occurred_at=link.occurred_at,
        )
        if recomputed != link.hash:
            findings.append(
                f"sequence {link.sequence_no} ({link.name}) has been altered: its "
                f"stored hash {link.hash[:12]} does not match its material "
                f"{recomputed[:12]}"
            )
        expected_prev = link.hash

    head = links[-1].hash if links else GENESIS
    return ChainVerdict(
        intact=not findings,
        complete=not findings and unhashed == 0 and bool(links),
        length=len(links),
        hashed=hashed,
        unhashed=unhashed,
        head_hash=head,
        findings=tuple(findings),
    )


def receipt_digest(
    *,
    intent_id: str,
    head_hash: str,
    chain_length: int,
    what_happened: str,
    verification: str,
    provenance: str,
    artifacts: Sequence[str],
    learned: str,
    next_steps: str,
    issued_at: str,
) -> str:
    """SHA-256 over the receipt and the chain head it certifies."""
    material = canonical(
        {
            "v": CHAIN_VERSION,
            "intent_id": intent_id,
            "head_hash": head_hash,
            "chain_length": chain_length,
            "what_happened": what_happened,
            "verification": verification,
            "provenance": provenance,
            "artifacts": list(artifacts),
            "learned": learned,
            "next_steps": next_steps,
            "issued_at": issued_at,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def sign(digest: str, key: str) -> str:
    """HMAC-SHA256 of a digest under the estate key. Hex, 64 characters."""
    if not key:
        raise ValueError("a receipt cannot be signed with an empty key")
    return hmac.new(key.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(digest: str, signature: str, key: str) -> bool:
    """Constant time comparison. An empty signature never verifies."""
    if not signature or not key:
        return False
    return hmac.compare_digest(sign(digest, key), signature)


def key_id(key: str) -> str:
    """Names the signing key without revealing it. Sixteen hex characters."""
    if not key:
        return ""
    material = b"devon-receipt-signing-key:" + key.encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


RECEIPT_KEY_LABEL = "devon:receipt-signing:v1"


def derive_receipt_key(secret_key: str) -> str:
    """A receipt signing key distinct from the estate secret, when no dedicated
    key is configured. HMAC-SHA256 of a fixed label under the secret, hex."""
    if not secret_key:
        raise ValueError("a receipt key cannot be derived from an empty secret")
    return hmac.new(
        secret_key.encode("utf-8"), RECEIPT_KEY_LABEL.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def find_signing_key(digest: str, signature: str, keys: Sequence[str]) -> Optional[str]:
    """The first key in the ring that verifies this signature, or None.

    The ring is the current key first, then previous keys, so a receipt signed
    before a rotation still verifies and the caller can say which key did it.
    """
    for key in keys:
        if key and verify_signature(digest, signature, key):
            return key
    return None
