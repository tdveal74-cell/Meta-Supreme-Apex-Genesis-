"""
The DEVON ecosystem, compiled from Tee's architecture diagram.

Source: the DEVON ECOSYSTEM diagram supplied by Tee on 2026-08-26, titled
"DEVON ECOSYSTEM. One Organism. One Intent. One Receipt." The diagram is the
doctrine; this module is the diagram made executable, the same move every other
module in this package makes. It carries no Drive id yet. When it is filed the
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

TWO RULINGS, RECORDED HERE SO THE PICTURE IS NEVER MISREAD

The diagram draws Meta Supreme, the Council of Reason, in an External
Intelligence box at the edge. Tee ruled on 2026-08-26 that the Council stays
under DEVON, exactly as built. The diagram's own authority line agrees, so the
box placement is geography and the hierarchy is law.

The diagram also draws the Complementary Operating Layer beside DEVON. That
layer already exists in `services/devon/operating_layer.py` and this module
imports its Surface registry rather than declaring a second one. Two registries
of the same thing is the fork this package exists to prevent.

WHAT THIS MODULE IS AND IS NOT

Data and gates only. Nothing here opens a socket, writes a ledger row, calls an
executor, or touches Pinecone. It answers "what is the shape of the organism",
"is this event sequence legal", "who outranks whom", "where does this action
route", "may this index be deleted", and "is this receipt complete". The caller
performs every effect, which is the standing split for everything in
`services/devon` and is enforced by `test_devon_integrity.py`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Sequence, Set, Tuple

from services.devon.operating_layer import Surface

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
# Authority. Locked means no code path reorders it and no caller supplies
# their own ordering.
# ---------------------------------------------------------------------------

class Authority(IntEnum):
    """Rank in the locked hierarchy. A lower value outranks a higher one."""

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

HIERARCHY_LINE = "TEE > TEE SOUL > DEVON > COUNCIL > AUTOMATION > TOOLS"

HIERARCHY_RULE = (
    "Hierarchy locked. Tee is sovereign. The Tee Soul is Tee's standing word and "
    "binds everything below it. DEVON decides within that word. The Council "
    "advises DEVON and stays under him, ruled by Tee on 2026-08-26. Automation "
    "carries out what was decided and approved. Tools do only what they are told."
)

COUNCIL_RULING = (
    "The Council of Reason remains under DEVON as built: nine seats, convened by "
    "DEVON, advisory only. The External Intelligence box in the diagram is "
    "placement on the page, not a promotion. Ruled by Tee on 2026-08-26."
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
        "escalate upward, never sideways and never by repetition."
    )


# ---------------------------------------------------------------------------
# The Tee Soul. Read only, absolute precedence, eight facets.
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
    "it, outside the system, and every copy inside the system is a mirror. It "
    "takes absolute precedence: a plan that contradicts it is wrong even when "
    "the plan is newer, cheaper, or unanimous."
)


# ---------------------------------------------------------------------------
# The five layers of the DEVON mind.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MindLayer:
    """One layer of the mind, with what it holds and how it may change."""

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

MIND_LAYERS_BY_NUMBER: Dict[int, MindLayer] = {layer.number: layer for layer in MIND_LAYERS}


def check_layer_write(layer_number: int, approved_by_tee: bool = False) -> Tuple[bool, str]:
    """Gate a proposed write to a mind layer. Fails closed on an unknown layer."""
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
            return True, "Soul commit permitted: validated learning carrying a human ruling."
        return False, (
            "The Devon Soul is trusted identity. Nothing joins it without "
            "validation and Tee's approval. Raise the commit for a ruling."
        )
    return False, f"No layer numbered {layer_number}. The mind has five."


# ---------------------------------------------------------------------------
# Context and memory sources. What Attention may draw from.
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
# Input channels and the Universal Intent.
# ---------------------------------------------------------------------------

INPUT_CHANNELS: Tuple[str, ...] = (
    "chat_voice",
    "forms",
    "email",
    "documents",
    "web_apis",
    "other_systems",
)

CHANNEL_ALIASES: Dict[str, str] = {
    "chat": "chat_voice",
    "voice": "chat_voice",
    "chat/voice": "chat_voice",
    "chat_voice": "chat_voice",
    "form": "forms",
    "forms": "forms",
    "email": "email",
    "document": "documents",
    "documents": "documents",
    "web": "web_apis",
    "api": "web_apis",
    "apis": "web_apis",
    "web/apis": "web_apis",
    "web_apis": "web_apis",
    "other": "other_systems",
    "other systems": "other_systems",
    "other_systems": "other_systems",
}


def normalize_channel(channel: str) -> str:
    """Resolve a channel spelling to one of the six, or refuse it by name.

    A new channel is a ruling, not a default. Guessing one silently would put
    an intent on the record with a provenance nobody can trust.
    """
    key = channel.strip().lower()
    resolved = CHANNEL_ALIASES.get(key)
    if resolved is None:
        raise ValueError(
            f"'{channel}' is not a recorded input channel. The channels are: "
            + ", ".join(INPUT_CHANNELS)
            + ". Adding one is Tee's ruling."
        )
    return resolved


@dataclass(frozen=True)
class UniversalIntent:
    """One intent, one id. Everything downstream traces back to it."""

    intent_id: str
    channel: str
    stated: str

    def to_dict(self) -> Dict[str, str]:
        return {"intent_id": self.intent_id, "channel": self.channel, "stated": self.stated}


def open_intent(channel: str, stated: str) -> UniversalIntent:
    """Mint the one Universal Intent for an input.

    The id is a UUID minted here rather than supplied by the caller, so no
    channel can collide two inputs onto one id or replay an old one.
    """
    normalized = normalize_channel(channel)
    if not stated.strip():
        raise ValueError("An intent with no stated content cannot be acted on or receipted.")
    return UniversalIntent(intent_id=str(uuid.uuid4()), channel=normalized, stated=stated.strip())


# ---------------------------------------------------------------------------
# The Live State Ledger. The present tense of DEVON.
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
    "The ledger is the present tense of DEVON. If it is not in the ledger it did "
    "not happen, and a claim that disagrees with the ledger is wrong."
)

LEDGER_APPROVAL_RULE = (
    "The ledger's approvals table observes the approval authority. It never "
    "grants. The authority stays in services/devon/approval.py and its shared "
    "store, and a ledger row only records which request was raised and how it "
    "was ruled."
)


class IntentState(str, Enum):
    """Where an intent stands in the ledger. The present tense of one intent."""

    RECEIVED = "received"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RECEIPTED = "receipted"


# An intent's state is derived from its events rather than set by a caller, so
# the two can never disagree. The ledger stores the derived value for cheap
# reads and recomputes it on every append.
def derive_state(seen: Sequence[str]) -> IntentState:
    """Compute an intent's state from the events on its record."""
    already = set(seen)
    if not already:
        return IntentState.RECEIVED
    if "VERIFICATION_PASSED" in already or "ACTION_COMPLETED" in already:
        state = IntentState.COMPLETED
    elif "ACTION_FAILED" in already:
        state = IntentState.FAILED
    elif "ACTION_STARTED" in already:
        state = IntentState.EXECUTING
    elif "APPROVAL_REQUESTED" in already and "APPROVAL_GRANTED" not in already:
        state = IntentState.AWAITING_APPROVAL
    elif "PLAN_CREATED" in already:
        state = IntentState.PLANNED
    else:
        state = IntentState.RECEIVED
    # A failure after a completion still leaves the intent failed overall: the
    # ledger reports the worse truth, never the more flattering one.
    if "ACTION_FAILED" in already and state is IntentState.COMPLETED:
        state = IntentState.FAILED
    return state


# ---------------------------------------------------------------------------
# The Event Bus. Thirteen universal events and the order they may occur in.
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

EVENT_SET: Set[str] = set(EVENTS)

# Events that may occur at most once for one intent. The rest are per action
# and may legitimately repeat.
SINGLE_OCCURRENCE_EVENTS: Tuple[str, ...] = (
    "INTENT_RECEIVED",
    "CONTEXT_LOADED",
    "PLAN_CREATED",
)

# What each event requires to have already happened on the same intent.
# Absence from this map means only the universal rule applies: a sequence
# opens with INTENT_RECEIVED.
EVENT_PREREQUISITES: Dict[str, Tuple[str, ...]] = {
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

EFFECT_GATE_RULE = (
    "ACTION_STARTED on an effect intent requires APPROVAL_GRANTED on the same "
    "intent first. Automation never commits effects unattended."
)


def check_event(
    name: str,
    seen: Sequence[str],
    effect: bool = False,
    emergency_stopped: bool = False,
) -> List[str]:
    """Return every law this one event would break given what came before.

    An empty list means the event may be appended. This is the single gate the
    ledger writer calls, so the laws cannot drift between the checker and the
    writer.
    """
    violations: List[str] = []
    already = list(seen)
    already_set = set(already)

    if name not in EVENT_SET:
        return [f"'{name}' is not one of the thirteen universal events."]

    if not already:
        if name != "INTENT_RECEIVED":
            violations.append(
                f"{name} is the first event on this intent. Every intent opens with "
                "INTENT_RECEIVED: nothing happens to an intent that was never received."
            )
    elif name == "INTENT_RECEIVED":
        violations.append(
            "INTENT_RECEIVED already stands on this intent. One intent is received once."
        )

    if name in SINGLE_OCCURRENCE_EVENTS and name in already_set and already:
        if name != "INTENT_RECEIVED":
            violations.append(f"{name} already stands on this intent and may not repeat.")

    for required in EVENT_PREREQUISITES.get(name, ()):
        if required not in already_set:
            violations.append(f"{name} before {required}. {required} must come first.")

    if name == "ACTION_STARTED":
        if effect and "APPROVAL_GRANTED" not in already_set:
            violations.append(EFFECT_GATE_RULE)
        if emergency_stopped:
            violations.append(EMERGENCY_STOP_RULE)

    return violations


def check_event_sequence(sequence: Sequence[str], effect: bool = False) -> List[str]:
    """Return every law a whole sequence breaks. Empty means legal."""
    if not sequence:
        return ["An empty sequence is not a run. Every intent opens with INTENT_RECEIVED."]
    violations: List[str] = []
    seen: List[str] = []
    for name in sequence:
        violations.extend(check_event(name, seen, effect=effect))
        seen.append(name)
    return violations


def next_legal_events(seen: Sequence[str], effect: bool = False) -> Tuple[str, ...]:
    """Which events could legally come next. Useful to a caller planning a run."""
    return tuple(name for name in EVENTS if not check_event(name, seen, effect=effect))


TERMINAL_EVENTS: Tuple[str, ...] = ("ACTION_COMPLETED", "ACTION_FAILED", "VERIFICATION_PASSED")


def intent_is_receiptable(seen: Sequence[str], effect: bool = False) -> Tuple[bool, str]:
    """Whether an intent has reached a state a receipt can honestly close.

    A receipt written before anything happened certifies nothing, and an
    effect intent that never cleared its gate has no completion to report.
    """
    already = set(seen)
    if "INTENT_RECEIVED" not in already:
        return False, "No INTENT_RECEIVED on the record. There is nothing to receipt."
    if effect and "ACTION_STARTED" in already and "APPROVAL_GRANTED" not in already:
        return False, EFFECT_GATE_RULE
    if not already & set(TERMINAL_EVENTS):
        return False, (
            "Nothing reached a terminal event. A receipt reports what happened, so "
            "an action must have completed, failed, or verified first."
        )
    return True, "The intent reached a terminal event and can be closed with its one receipt."


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

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent_id": self.intent_id,
            "what_happened": self.what_happened,
            "verification": self.verification,
            "provenance": self.provenance,
            "artifacts": list(self.artifacts),
            "learned": self.learned,
            "next_steps": self.next_steps,
        }


def check_receipt(
    receipt: UniversalReceipt,
    already_receipted: Sequence[str] = (),
) -> List[str]:
    """Return everything that stops this receipt standing. Empty means it stands.

    `already_receipted` is the set of intent ids that already hold a receipt.
    One receipt per intent is the third word of the motto, so a second one is
    refused rather than merged, versioned, or quietly overwritten.
    """
    failures: List[str] = []
    if not receipt.intent_id.strip():
        failures.append("No intent id. A receipt that traces to nothing certifies nothing.")
    if receipt.intent_id in set(already_receipted):
        failures.append(
            f"Intent {receipt.intent_id} already holds its one receipt. "
            "An amendment is a new intent, never a second receipt."
        )
    if not receipt.what_happened.strip():
        failures.append("No account of what happened. That is the receipt's whole job.")
    if not receipt.verification.strip():
        failures.append(
            "No verification. A success response is a claim, not a receipt. Read the "
            "state back and say what was read."
        )
    if not receipt.provenance.strip():
        failures.append("No provenance. Say what produced this, so a later reader can check.")
    return failures


# ---------------------------------------------------------------------------
# Long term memory indexes and the deletion protection on each.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemoryIndex:
    """One Pinecone index, with its layer and its protection."""

    name: str
    layer: str
    protection: str
    write_rule: str


PROTECTION_MAX = "PROTECTED (MAX)"
PROTECTION_STANDARD = "PROTECTED"
PROTECTION_POLICY = "PROTECTED (POLICY)"

MEMORY_INDEXES: Dict[str, MemoryIndex] = {
    "tee-soul-layer": MemoryIndex(
        name="tee-soul-layer",
        layer="Tee Soul",
        protection=PROTECTION_MAX,
        write_rule="Read only. A mirror of Tee's word, refreshed only from Tee.",
    ),
    "devon-soul": MemoryIndex(
        name="devon-soul",
        layer="Devon Soul",
        protection=PROTECTION_STANDARD,
        write_rule="Validated durable lessons, committed only through the approval gate.",
    ),
    "devon-subconscious": MemoryIndex(
        name="devon-subconscious",
        layer="Devon Subconscious",
        protection=PROTECTION_POLICY,
        write_rule="Experiences and associations, appended by the learning lane.",
    ),
}

# Passed to the vendor on index creation. The vendor enforces it server side,
# which is the point: a policy that lives only in this repository cannot stop a
# console click or a stray script that never imports this module.
VENDOR_DELETION_PROTECTION = "enabled"


def deletion_protection_for(name: str) -> str:
    """The vendor side setting for an index. Every recorded index is protected."""
    if name in MEMORY_INDEXES:
        return VENDOR_DELETION_PROTECTION
    return VENDOR_DELETION_PROTECTION


def may_delete_index(name: str) -> Tuple[bool, str]:
    """Whether an index may be deleted. The answer is no, and the reason is named."""
    index = MEMORY_INDEXES.get(name)
    if index is None:
        return False, (
            f"No recorded index named '{name}'. Deleting the unrecorded is still deleting, "
            "and an unrecorded index is a map problem to fix before it is a delete to run."
        )
    return False, (
        f"{index.name} is {index.protection}. Memory indexes are never deleted by "
        "automation. Deletion is Tee's ruling, made outside the system, with the "
        "vendor protection lifted deliberately first."
    )


def may_delete_record(index_name: str, approved_by_tee: bool = False) -> Tuple[bool, str]:
    """A single record is a different question from the whole index.

    Records are reversible by design, which is what makes a proposal safe to
    accept. The soul still requires a ruling, because forgetting a validated
    lesson changes who DEVON is.
    """
    index = MEMORY_INDEXES.get(index_name)
    if index is None:
        return False, f"No recorded index named '{index_name}'."
    if index.protection == PROTECTION_MAX:
        return False, TEE_SOUL_RULE
    if index.name == "devon-soul" and not approved_by_tee:
        return False, (
            "A devon-soul record is validated identity. Removing one needs the same "
            "ruling that put it there."
        )
    return True, f"A single {index.name} record may be removed, and the removal is receipted."


# ---------------------------------------------------------------------------
# The action execution layer. DEVON decides where; the executors execute.
# ---------------------------------------------------------------------------

class Executor(str, Enum):
    """Who carries out an approved action. DEVON decides which."""

    N8N = "n8n"
    ZAPIER = "zapier"


N8N_DUTIES: Tuple[str, ...] = (
    "internal infrastructure",
    "devon workflows",
    "databases",
    "apis",
    "complex logic",
    "soul ops",
    "subconscious ops",
    "editforge orchestration",
    "github workflows",
    "approval infrastructure",
)

ZAPIER_DUTIES: Tuple[str, ...] = (
    "external saas",
    "commercial integrations",
    "crm",
    "email marketing",
    "forms",
    "marketing",
    "sales systems",
    "simple third party actions",
)

UNROUTED = "UNROUTED"

UNROUTED_RULE = (
    "An unrecognised duty is parked where a human will see it. A guessed executor "
    "runs the wrong thing somewhere real, and unlike a wrong tag it cannot be "
    "corrected after the fact."
)


def route_action(duty: str) -> Tuple[str, str]:
    """Name the executor for a duty, or park it.

    This mirrors the vault's capture routing: recognised goes where it belongs,
    unrecognised goes to a place a person looks, and nothing is guessed.
    """
    wanted = duty.strip().lower()
    if wanted in N8N_DUTIES:
        return "n8n", f"'{wanted}' is a recorded internal executor duty."
    if wanted in ZAPIER_DUTIES:
        return "zapier", f"'{wanted}' is a recorded external executor duty."
    return UNROUTED, f"'{duty}' is not a recorded duty for any executor. " + UNROUTED_RULE


EXECUTORS: Dict[str, Dict[str, object]] = {
    "n8n": {
        "role": "internal executor",
        "duties": N8N_DUTIES,
        "boundary": "Runs inside the estate. Still passes the approval gate for effects.",
    },
    "zapier": {
        "role": "external executor",
        "duties": ZAPIER_DUTIES,
        "boundary": "Reaches commercial services. Never holds DEVON canon or secrets.",
    },
}


# ---------------------------------------------------------------------------
# Emergency stop. The one control that outranks a running plan.
# ---------------------------------------------------------------------------

EMERGENCY_STOP_RULE = (
    "Emergency stop is engaged. No action starts while it holds. Work already "
    "started is reported as it actually ended, never as cancelled, because the "
    "ledger records what happened rather than what was wanted."
)

EMERGENCY_STOP_AUTHORITY = Authority.TEE

EMERGENCY_STOP_NOTE = (
    "Engaging the stop is always permitted, from any level, because a stop that "
    "needs permission is not a stop. Releasing it is Tee's, because releasing is "
    "a decision to let effects run again."
)


def may_release_emergency_stop(actor: Authority) -> Tuple[bool, str]:
    """Only Tee releases the stop. Anyone may engage it."""
    if actor is Authority.TEE:
        return True, "Tee releases the stop."
    return False, (
        f"{actor.name} may engage the emergency stop but not release it. Releasing is "
        "a decision to let effects run again, and that is Tee's."
    )


# ---------------------------------------------------------------------------
# External intelligence. Mechanical work goes down, judgement stays with the
# Council, and the Council stays under DEVON.
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
            f"'{wanted}' is mechanical and latency sensitive. It belongs on the "
            "cheapest model that can do it."
        )
    if wanted in COUNCIL_DUTIES:
        return "council", (
            f"'{wanted}' is judgement. It goes to the Council of Reason, which advises "
            "DEVON and stays under him."
        )
    return "DECLINED", (
        f"'{duty}' is not a recorded thinking duty. Declining is a correct answer; a "
        "confident wrong route is worse than no route."
    )


# The complementary operating layer is declared once, in operating_layer.py.
# This is the same registry, named here so a reader of the map can see it.
OPERATING_SURFACES: Tuple[str, ...] = tuple(surface.value for surface in Surface)


# ---------------------------------------------------------------------------
# Outputs, portfolio, storage, observability.
# ---------------------------------------------------------------------------

OUTPUTS: Tuple[str, ...] = (
    "EditForge",
    "Publishing",
    "Social",
    "Email/Newsletter",
    "Analytics",
)

# The Area registry in areas.py owns these codes. They are listed here as the
# four portfolio properties the diagram draws, and a test asserts that every
# one still resolves through areas.py so this can never become a second
# registry that drifts.
PORTFOLIO: Tuple[Tuple[str, str], ...] = (
    ("TQO", "The Quiet Operator"),
    ("TSWS", "The Shadow We Share"),
    ("NCO", "NCO Forge"),
    ("ACX", "Ascension Caudex"),
)

PORTFOLIO_RULE = (
    "The four properties share infrastructure only where DEVON approves the shared "
    "service. Their canon, visual systems, audiences and strategy do not merge."
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
        "source": dict(SOURCE),
        "motto": MOTTO,
        "hierarchy": [authority.name for authority in HIERARCHY],
        "hierarchy_line": HIERARCHY_LINE,
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
        "ledger": {
            "tables": list(LEDGER_TABLES),
            "rule": LEDGER_RULE,
            "approval_rule": LEDGER_APPROVAL_RULE,
        },
        "events": list(EVENTS),
        "event_prerequisites": {k: list(v) for k, v in EVENT_PREREQUISITES.items()},
        "effect_gate_rule": EFFECT_GATE_RULE,
        "receipt": {
            "rule": "One receipt per intent.",
            "required": ["what_happened", "verification", "provenance"],
            "optional": ["artifacts", "learned", "next_steps"],
        },
        "memory_indexes": {
            name: {
                "layer": index.layer,
                "protection": index.protection,
                "write_rule": index.write_rule,
                "vendor_deletion_protection": VENDOR_DELETION_PROTECTION,
            }
            for name, index in MEMORY_INDEXES.items()
        },
        "executors": {
            name: {
                "role": executor["role"],
                "duties": list(executor["duties"]),
                "boundary": executor["boundary"],
            }
            for name, executor in EXECUTORS.items()
        },
        "emergency_stop": {
            "rule": EMERGENCY_STOP_RULE,
            "release_authority": EMERGENCY_STOP_AUTHORITY.name,
            "note": EMERGENCY_STOP_NOTE,
        },
        "external_intelligence": {
            "cerebras": list(CEREBRAS_DUTIES),
            "council": list(COUNCIL_DUTIES),
        },
        "operating_surfaces": list(OPERATING_SURFACES),
        "outputs": list(OUTPUTS),
        "portfolio": [{"code": code, "name": name} for code, name in PORTFOLIO],
        "portfolio_rule": PORTFOLIO_RULE,
        "storage": list(STORAGE),
        "observability": list(OBSERVABILITY),
        "security_guarantees": list(SECURITY_GUARANTEES),
    }
