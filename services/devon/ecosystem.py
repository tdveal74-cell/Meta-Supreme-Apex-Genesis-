"""
The DEVON ecosystem, compiled from Tee's architecture diagram.

Source: the DEVON ECOSYSTEM diagram supplied by Tee on 2026-08-26, titled
"DEVON ECOSYSTEM. One Organism. One Intent. One Receipt." The diagram is the
doctrine; this module is the diagram made executable, the same move every other
module in this package makes. It has no Drive id yet. When it is filed the
conforming name is SYS_SPEC_devon-ecosystem_v1_2026-08-26 and the id belongs in
SOURCE below.

THE THREE WORDS

    One organism.  Every box in the diagram is one system, not a federation.
    One intent.    Every input, from any channel, becomes exactly one
                   Universal Intent with a UUID, and everything that happens
                   after traces back to that id.
    One receipt.   Every intent ends in exactly one Universal Receipt. A
                   second receipt for the same intent is refused, and an
                   intent with no receipt is visibly unfinished rather than
                   quietly forgotten.

ONE RULING, RECORDED HERE SO THE PICTURE IS NEVER MISREAD

The diagram draws Meta Supreme, the Council of Reason, in an External
Intelligence box at the edge. Tee ruled on 2026-08-26 that the Council stays
under DEVON, exactly as built: the nine seats deliberate when DEVON brings them
a question, and their advice ranks below DEVON's decision and far below Tee's.
The diagram's own authority line agrees, TEE above TEE SOUL above DEVON above
COUNCIL above AUTOMATION above TOOLS, so the box placement is geography and the
hierarchy is law. This module encodes the law.

WHAT THIS MODULE IS AND IS NOT

Data and gates only. Nothing here opens a socket, writes a ledger row, calls
an executor, or touches Pinecone. It answers "what is the shape of the
organism", "is this event sequence legal", "who outranks whom", "where does
this action route", and "is this receipt complete". The caller executes, which
is the standing split for everything in services/devon and is enforced by
test_devon_integrity.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Sequence, Tuple

SOURCE = {
    "drive_id": None,
    "title": "DEVON ECOSYSTEM. One Organism. One Intent. One Receipt.",
    "supplied_by": "Tee",
    "supplied": "2026-08-26",
    "file_as": "SYS_SPEC_devon-ecosystem_v1_2026-08-26",
    "note": (
        "Compiled from the diagram attachment, not from a Drive document. "
        "When the diagram is filed to the vault, record its Drive id here."
    ),
}

MOTTO = "One organism. One intent. One receipt."


# ---------------------------------------------------------------------------
# Authority. The hierarchy is locked: TEE > TEE SOUL > DEVON > COUNCIL >
# AUTOMATION > TOOLS. Locked means no code path reorders it and no caller
# supplies their own.
# ---------------------------------------------------------------------------

class Authority(IntEnum):
    """Rank in the locked hierarchy. Lower value outranks higher."""

    TEE = 1
    TEE_SOUL = 2
    DEVON = 3
    COUNCIL = 4
    AUTOMATION = 5
    TOOLS = 6


HIERARCHY: Tuple[Authority, ...] = (
    Authority.TEE,
    Authority.TEE_SOUL,
    Authority.DEVON,
    Authority.COUNCIL,
    Authority.AUTOMATION,
    Authority.TOOLS,
)

HIERARCHY_RULE = (
    "Hierarchy locked. Tee is sovereign. The Tee Soul is Tee's standing word and "
    "binds everything below it. DEVON decides within that word. The Council "
    "advises DEVON and stays under him, ruled by Tee 2026-08-26. Automation "
    "carries out what was decided and approved. Tools do only what they are told."
)

COUNCIL_RULING = (
    "The Council of Reason remains under DEVON as built: nine seats, convened by "
    "DEVON, advisory only. The External Intelligence box in the diagram is "
    "placement on the page, not a promotion. Ruled by Tee 2026-08-26."
)


def outranks(higher: Authority, lower: Authority) -> bool:
    """True when the first authority binds the second. Nothing outranks itself."""
    return higher < lower


def may_override(actor: Authority, decision_owner: Authority) -> Tuple[bool, str]:
    """Whether an actor may override a decision owned at another level.

    Every refusal names its reason, because a refusal nobody hears is an
    approval.
    """
    if actor is decision_owner:
        return False, "An authority does not override itself. Revise the decision instead."
    if outranks(actor, decision_owner):
        return True, f"{actor.name} outranks {decision_owner.name} in the locked hierarchy."
    return False, (
        f"{actor.name} ranks below {decision_owner.name}. The hierarchy is locked: "
        "escalate upward, never sideways or by repetition."
    )


# ---------------------------------------------------------------------------
# The Tee Soul. Read only, absolute precedence. Eight facets, exactly as the
# diagram lists them.
# ---------------------------------------------------------------------------

TEE_SOUL_FACETS: Tuple[str, ...] = (
    "Values",
    "Rulings",
    "Voice",
    "Boundaries",
    "Principles",
    "Quality Laws",
    "Ownership Laws",
    "Non-Negotiables",
)

TEE_SOUL_RULE = (
    "The Tee Soul is read only everywhere it appears: the mind's first layer, "
    "the tee-soul-layer index, and the deployed soul service. Only Tee amends "
    "it, outside the system, and every copy inside the system is a mirror. "
    "It takes absolute precedence: a plan that contradicts it is wrong even "
    "when the plan is newer, cheaper, or unanimous."
)


# ---------------------------------------------------------------------------
# The five layers of the DEVON mind.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MindLayer:
    """One layer of the mind, with who may write it and how it changes."""

    number: int
    name: str
    holds: str
    mutability: str


MIND_LAYERS: Tuple[MindLayer, ...] = (
    MindLayer(
        1,
        "Tee Soul",
        "Who Tee is. The eight facets, binding everything below.",
        "Read only. Amended by Tee alone, outside the system.",
    ),
    MindLayer(
        2,
        "Devon Attention",
        "What DEVON notices now. Selects what enters consciousness.",
        "Volatile. Rebuilt per intent from the context sources, never persisted.",
    ),
    MindLayer(
        3,
        "Devon Conscious",
        "What DEVON is thinking now. Reasons, plans, decides, solves.",
        "Volatile. Its durable trace is the ledger and the receipt, not the layer.",
    ),
    MindLayer(
        4,
        "Devon Subconscious",
        "What DEVON has experienced. Experiences, associations, patterns, "
        "failures, recoveries, dormant memories.",
        "Appended by the learning lane after the gate. Never edited in place.",
    ),
    MindLayer(
        5,
        "Devon Soul",
        "Who DEVON has become. Validated, durable, trusted learning.",
        "Written only by the approval gated Soul Committer. Every commit has a ruling.",
    ),
)


def check_layer_write(layer_number: int, approved_by_tee: bool = False) -> Tuple[bool, str]:
    """Gate a proposed write to a mind layer. Fails closed on unknown layers."""
    if layer_number == 1:
        return False, TEE_SOUL_RULE
    if layer_number in (2, 3):
        return False, (
            "Attention and Conscious are working memory. They are rebuilt, not "
            "written. Durable facts go to the ledger, the subconscious, or the soul."
        )
    if layer_number == 4:
        return True, "Subconscious writes append through the learning gate, never edit in place."
    if layer_number == 5:
        if approved_by_tee:
            return True, "Soul commit permitted: validated learning with a human ruling."
        return False, (
            "The Devon Soul is trusted identity. Nothing joins it without "
            "validation and Tee's approval. Raise the commit for a ruling."
        )
    return False, f"No layer numbered {layer_number}. The mind has five."


# ---------------------------------------------------------------------------
# Context and memory sources. What Attention is allowed to draw from.
# ---------------------------------------------------------------------------

CONTEXT_SOURCES: Dict[str, str] = {
    "Canon": "Project truth and law.",
    "Live State": "Current operational state, read from the ledger.",
    "Thread History": "Decisions and conversations already on the record.",
    "Devon Soul": "Durable lessons, layer five.",
    "Subconscious": "Relevant memories, layer four.",
    "World Knowledge": "Reference material.",
    "Tools & Permissions": "What DEVON can do, and what he is allowed to do.",
}


# ---------------------------------------------------------------------------
# Input channels and the Universal Intent. Every input becomes one intent.
# ---------------------------------------------------------------------------

INPUT_CHANNELS: Tuple[str, ...] = (
    "chat/voice",
    "forms",
    "email",
    "documents",
    "web/apis",
    "other systems",
)


@dataclass(frozen=True)
class UniversalIntent:
    """One intent, one id. Everything downstream traces back to it."""

    intent_id: str
    channel: str
    stated: str


def open_intent(channel: str, stated: str) -> UniversalIntent:
    """Mint the one Universal Intent for an input. Refuses unknown channels.

    The id is a UUID minted here, not supplied by the caller, so no channel can
    collide two inputs onto one id or replay an old one.
    """
    normalized = channel.strip().lower()
    if normalized not in INPUT_CHANNELS:
        raise ValueError(
            f"'{channel}' is not a recorded input channel. The channels are: "
            + ", ".join(INPUT_CHANNELS)
            + ". A new channel is a ruling, not a default."
        )
    if not stated.strip():
        raise ValueError("An intent with no stated content cannot be acted on or receipted.")
    return UniversalIntent(intent_id=str(uuid.uuid4()), channel=normalized, stated=stated.strip())


# ---------------------------------------------------------------------------
# The Live State Ledger. The present tense of DEVON. Postgres owns it.
# ---------------------------------------------------------------------------

LEDGER_TABLES: Tuple[str, ...] = (
    "intents",
    "actions",
    "events",
    "approvals",
    "artifacts",
    "executors",
    "systems",
    "errors",
    "verifications",
    "learning_candidates",
)

LEDGER_RULE = (
    "The ledger is the present tense of DEVON. If it is not in the ledger it "
    "did not happen, and a claim that disagrees with the ledger is wrong."
)


# ---------------------------------------------------------------------------
# The Event Bus. Thirteen universal events, and the order they may legally
# occur in for a single intent.
# ---------------------------------------------------------------------------

EVENTS: Tuple[str, ...] = (
    "INTENT_RECEIVED",
    "CONTEXT_LOADED",
    "SOUL_READ",
    "SUBCONSCIOUS_RECALLED",
    "PLAN_CREATED",
    "APPROVAL_REQUESTED",
    "APPROVAL_GRANTED",
    "ACTION_STARTED",
    "ACTION_COMPLETED",
    "ACTION_FAILED",
    "VERIFICATION_PASSED",
    "ARTIFACT_CREATED",
    "LEARNING_CAPTURED",
)

# What each event requires to have already happened on the same intent.
# Absence from this map means only the universal requirement applies: the
# sequence opens with INTENT_RECEIVED.
_REQUIRES: Dict[str, Tuple[str, ...]] = {
    "CONTEXT_LOADED": ("INTENT_RECEIVED",),
    "SOUL_READ": ("INTENT_RECEIVED",),
    "SUBCONSCIOUS_RECALLED": ("INTENT_RECEIVED",),
    "PLAN_CREATED": ("CONTEXT_LOADED",),
    "APPROVAL_REQUESTED": ("PLAN_CREATED",),
    "APPROVAL_GRANTED": ("APPROVAL_REQUESTED",),
    "ACTION_STARTED": ("PLAN_CREATED",),
    "ACTION_COMPLETED": ("ACTION_STARTED",),
    "ACTION_FAILED": ("ACTION_STARTED",),
    "VERIFICATION_PASSED": ("ACTION_COMPLETED",),
    "ARTIFACT_CREATED": ("ACTION_STARTED",),
    "LEARNING_CAPTURED": ("INTENT_RECEIVED",),
}


def check_event_sequence(sequence: Sequence[str], effect: bool = False) -> List[str]:
    """Return every law the sequence breaks. Empty means legal.

    `effect` marks an intent whose action changes the world outside the
    system. For those, ACTION_STARTED without APPROVAL_GRANTED is the one
    violation this whole architecture exists to make impossible, so it is
    checked by name rather than left to the dependency map.
    """
    violations: List[str] = []
    if not sequence:
        return ["An empty sequence is not a run. Every run opens with INTENT_RECEIVED."]
    if sequence[0] != "INTENT_RECEIVED":
        violations.append(
            f"Opens with {sequence[0]}. Every run opens with INTENT_RECEIVED: "
            "nothing happens to an intent that was never received."
        )
    seen: set = set()
    for name in sequence:
        if name not in EVENTS:
            violations.append(f"'{name}' is not one of the thirteen universal events.")
            seen.add(name)
            continue
        for required in _REQUIRES.get(name, ()):
            if required not in seen:
                violations.append(f"{name} before {required}. {required} must come first.")
        if effect and name == "ACTION_STARTED" and "APPROVAL_GRANTED" not in seen:
            violations.append(
                "ACTION_STARTED on an effect intent with no APPROVAL_GRANTED on "
                "the record. Automation never commits effects unattended."
            )
        seen.add(name)
    return violations


# ---------------------------------------------------------------------------
# The Universal Receipt. One per intent, closing the loop.
# ---------------------------------------------------------------------------

@dataclass
class UniversalReceipt:
    """What the intent came to. The organism's unit of accountability."""

    intent_id: str
    what_happened: str
    verification: str
    provenance: str
    artifacts: List[str] = field(default_factory=list)
    learned: Optional[str] = None
    next_steps: Optional[str] = None


def check_receipt(receipt: UniversalReceipt, already_receipted: Sequence[str] = ()) -> List[str]:
    """Return everything that stops this receipt standing. Empty means it stands.

    `already_receipted` is the set of intent ids that hold a receipt. One
    receipt per intent is the third word of the motto, so a second one is
    refused rather than merged, versioned, or quietly overwritten.
    """
    failures: List[str] = []
    if not receipt.intent_id.strip():
        failures.append("No intent id. A receipt that traces to nothing certifies nothing.")
    if receipt.intent_id in already_receipted:
        failures.append(
            f"Intent {receipt.intent_id} already holds its one receipt. "
            "Amendments are new intents, not second receipts."
        )
    if not receipt.what_happened.strip():
        failures.append("No account of what happened. That is the receipt's whole job.")
    if not receipt.verification.strip():
        failures.append(
            "No verification. A success response is a claim, not a receipt. "
            "Read the state back and say what was read."
        )
    if not receipt.provenance.strip():
        failures.append("No provenance. Say what produced this, so a later reader can check.")
    return failures


# ---------------------------------------------------------------------------
# Long term memory indexes, and the deletion protection on each.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemoryIndex:
    """One Pinecone index, with its layer and its protection."""

    name: str
    layer: str
    protection: str
    write_rule: str


MEMORY_INDEXES: Dict[str, MemoryIndex] = {
    "tee-soul-layer": MemoryIndex(
        name="tee-soul-layer",
        layer="Tee Soul",
        protection="PROTECTED (MAX)",
        write_rule="Read only. A mirror of Tee's word, refreshed only from Tee.",
    ),
    "devon-soul": MemoryIndex(
        name="devon-soul",
        layer="Devon Soul",
        protection="PROTECTED",
        write_rule="Validated durable lessons, committed only through the approval gate.",
    ),
    "devon-subconscious": MemoryIndex(
        name="devon-subconscious",
        layer="Devon Subconscious",
        protection="PROTECTED (POLICY)",
        write_rule="Experiences and associations, appended by the learning lane.",
    ),
}


def may_delete_index(name: str) -> Tuple[bool, str]:
    """Whether an index may be deleted. The answer is no, and the reason is named."""
    index = MEMORY_INDEXES.get(name)
    if index is None:
        return False, f"No recorded index named '{name}'. Deleting the unrecorded is still deleting."
    return False, (
        f"{index.name} is {index.protection}. Memory indexes are never deleted by "
        "automation. Deletion is Tee's ruling, made outside the system, with the "
        "protection lifted deliberately first."
    )


# ---------------------------------------------------------------------------
# The action execution layer. DEVON decides where; the executors execute.
# ---------------------------------------------------------------------------

EXECUTORS: Dict[str, Dict[str, object]] = {
    "n8n": {
        "role": "internal executor",
        "duties": (
            "internal infrastructure",
            "devon workflows",
            "databases/apis",
            "complex logic",
            "soul/subconscious ops",
            "editforge orchestration",
            "github workflows",
            "approval infrastructure",
        ),
    },
    "zapier": {
        "role": "external executor",
        "duties": (
            "external saas",
            "commercial integrations",
            "crm/email",
            "forms/marketing",
            "sales systems",
            "simple 3rd party actions",
        ),
    },
}

UNROUTED_EXECUTOR = "UNROUTED. Park it and ask, do not guess an executor."


def route_action(duty: str) -> Tuple[str, str]:
    """Name the executor for a duty, or park it.

    Mirrors the vault's capture routing: an unrecognised duty is parked where a
    human will see it, because a guessed executor runs the wrong thing somewhere
    real.
    """
    wanted = duty.strip().lower()
    for name, executor in EXECUTORS.items():
        if wanted in executor["duties"]:
            return name, f"{wanted} is a recorded {executor['role']} duty."
    return UNROUTED_EXECUTOR, f"'{duty}' is not a recorded duty for any executor."


# ---------------------------------------------------------------------------
# External intelligence. Fast mechanical work goes down, judgement stays with
# the Council, and the Council stays under DEVON.
# ---------------------------------------------------------------------------

CEREBRAS_DUTIES: Tuple[str, ...] = (
    "classification",
    "summarization",
    "extraction",
    "bulk analysis",
    "routing assistance",
    "preprocessing",
)

COUNCIL_DUTIES: Tuple[str, ...] = (
    "deep deliberation",
    "complex reasoning",
    "risk analysis",
    "multi perspective",
    "sovereign advice",
)


def route_thinking(duty: str) -> Tuple[str, str]:
    """Send mechanical work to the fast lane and judgement to the Council."""
    wanted = duty.strip().lower()
    if wanted in CEREBRAS_DUTIES:
        return "cerebras", (
            f"{wanted} is mechanical and latency sensitive. It belongs on the "
            "cheapest model that can do it."
        )
    if wanted in COUNCIL_DUTIES:
        return "council", (
            f"{wanted} is judgement. It goes to the Council of Reason, which "
            "advises DEVON and stays under him."
        )
    return "DECLINED", (
        f"'{duty}' is not a recorded thinking duty. Declining is a correct answer; "
        "a confident wrong route is worse than no route."
    )


# ---------------------------------------------------------------------------
# Outputs, storage, observability. Named so the map is complete, inert so the
# map cannot act.
# ---------------------------------------------------------------------------

OUTPUTS: Tuple[str, ...] = (
    "EditForge",
    "Publishing",
    "Social",
    "Email/Newsletter",
    "Analytics",
)

STORAGE: Tuple[str, ...] = (
    "Google Drive",
    "Notion",
    "Pinecone",
    "Postgres",
    "S3/Cloud",
)

OBSERVABILITY: Tuple[str, ...] = (
    "health",
    "latency",
    "errors",
    "queues",
    "cost",
    "versions",
    "dependencies",
    "credentials",
    "system status",
    "alerts",
    "diagnostics",
)


# ---------------------------------------------------------------------------
# Security and authority. Nine guarantees, hierarchy locked.
# ---------------------------------------------------------------------------

SECURITY_GUARANTEES: Tuple[str, ...] = (
    "service identity",
    "least privilege",
    "secrets isolation",
    "signed requests",
    "approval scopes",
    "action expiry",
    "idempotency",
    "audit trails",
    "emergency stop",
)


def summary() -> Dict[str, object]:
    """The whole organism as one inert structure, for any surface that asks."""
    return {
        "source": SOURCE,
        "motto": MOTTO,
        "hierarchy": [a.name for a in HIERARCHY],
        "hierarchy_rule": HIERARCHY_RULE,
        "council_ruling": COUNCIL_RULING,
        "tee_soul": {"facets": list(TEE_SOUL_FACETS), "rule": TEE_SOUL_RULE},
        "mind_layers": [
            {
                "number": layer.number,
                "name": layer.name,
                "holds": layer.holds,
                "mutability": layer.mutability,
            }
            for layer in MIND_LAYERS
        ],
        "context_sources": dict(CONTEXT_SOURCES),
        "input_channels": list(INPUT_CHANNELS),
        "ledger": {"tables": list(LEDGER_TABLES), "rule": LEDGER_RULE},
        "events": list(EVENTS),
        "memory_indexes": {
            name: {
                "layer": index.layer,
                "protection": index.protection,
                "write_rule": index.write_rule,
            }
            for name, index in MEMORY_INDEXES.items()
        },
        "executors": {
            name: {"role": ex["role"], "duties": list(ex["duties"])}
            for name, ex in EXECUTORS.items()
        },
        "external_intelligence": {
            "cerebras": list(CEREBRAS_DUTIES),
            "council": list(COUNCIL_DUTIES),
        },
        "outputs": list(OUTPUTS),
        "storage": list(STORAGE),
        "observability": list(OBSERVABILITY),
        "security_guarantees": list(SECURITY_GUARANTEES),
    }
