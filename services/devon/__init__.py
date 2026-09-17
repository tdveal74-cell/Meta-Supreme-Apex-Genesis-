"""
DEVON: Tee's second brain, running inside Meta Supreme Apex Genesis.

DEVON began as a knowledge system spread across Google Drive, Notion, Airtable,
n8n and GitHub, governed by a set of doctrine documents in the vault's
`_Devon Core` folder. Those documents kept being violated by threads that had
read them, which is the failure this package exists to end: prose does not
enforce, a function that refuses does.

The assistant surface was rebuilt from the Jarvis voice assistant at
github.com/Vannu07/jarvis (commit 21b9d63), hardened against the Flagship Bar.

LAYERS

  Doctrine, compiled from the vault:
    areas        the nine Areas, and the rule that a supplied Area is never trusted
    naming       AREA_TYPE_slug_vN_DATE, parsed, validated, built
    precedence   which draft is current, and when nothing wins
    filing       the eight filing laws as checks
    receipts     the DEVON RECEIPT, both formats, parsed and validated
    vault        the Drive, Notion, Airtable and n8n map, inert data only
    flagship     the ship gate and its scoring

  Imported doctrine, compiled from an outside source rather than the vault:
    rule_ledger  rules that know whether they bend, and an assembly that
                 refuses to go out having dropped one that may not
    wager        a prediction recorded before the measurement, and the miss
                 carried into the next prediction

  Assistant:
    persona      who DEVON is and the rules he works under
    commands     one router for the command language and the device intents
    approval     the gate every high impact action passes through
    assistant    DEVON himself

NOTHING IN THIS PACKAGE PERFORMS A NETWORK CALL OR AN EFFECT. It parses, plans,
validates and gates. The caller executes. That split is what keeps importing
DEVON free of consequences and is load bearing for the security score.
"""

from __future__ import annotations

from services.devon.approval import (
    ApprovalQueue,
    ApprovalRequest,
    ApprovalState,
    Decision,
    DecisionResult,
)
from services.devon.areas import (
    AREAS,
    Area,
    AreaError,
    canonical_codes,
    canonical_labels,
    classify,
    get_area,
    is_valid_area,
    normalize_code,
    normalize_label,
    require_area,
    resolve_area,
)
from services.devon.assistant import Devon, DevonResponse, FilingPlan
from services.devon.commands import (
    ALL_INTENTS,
    Intent,
    Kind,
    ParsedCommand,
    approval_gated_intents,
    effect_intents,
    parse,
)
from services.devon.ecosystem import (
    CONTEXT_SOURCES,
    EVENTS,
    EXECUTORS,
    HIERARCHY,
    INPUT_CHANNELS,
    LEDGER_TABLES,
    MEMORY_INDEXES,
    MIND_LAYERS,
    OUTPUTS,
    PORTFOLIO,
    SECURITY_GUARANTEES,
    TEE_SOUL_FACETS,
    Authority,
    Executor,
    IntentState,
    MemoryIndex,
    MindLayer,
    UniversalIntent,
    UniversalReceipt,
    check_event,
    check_event_sequence,
    check_layer_write,
    check_receipt,
    derive_state,
    intent_is_receiptable,
    may_delete_index,
    may_delete_record,
    may_override,
    may_release_emergency_stop,
    next_legal_events,
    normalize_channel,
    open_intent,
    outranks,
    route_action,
    route_thinking,
)
from services.devon.filing import (
    LAWS,
    ChangeKind,
    FilingLaw,
    ReadBack,
    WriteCheck,
    WriteRequest,
    check_write,
    law3_validate_readback,
)
from services.devon.flagship import (
    CLAUSES,
    DIMENSIONS,
    Assessment,
    CriticMode,
    Finding,
    Verdict,
    blank_scores,
)
from services.devon.naming import (
    AREA_CODES,
    TYPE_CODES,
    NamingError,
    ParsedName,
    build_filename,
    parse_filename,
    slugify,
    validate_filename,
)
from services.devon.operating_layer import (
    AUDIT_VERSION,
    HANDOFF_VERSION,
    POLICY_VERSION,
    RETURN_VERSION,
    ArtifactReference,
    ArtifactReturnPlan,
    AuditFinding,
    AuditPlan,
    AuditVerdict,
    ContractIssue,
    HandoffEnvelope,
    Need,
    Risk,
    RoutingDecision,
    SourceReference,
    Surface,
    TaskProfile,
    build_audit_plan,
    capability_status,
    evaluate_audit,
    plan_artifact_return,
    route,
    validate_handoff,
)
from services.devon.persona import HARD_RULES, check_punctuation, system_prompt
from services.devon.precedence import Candidate, Outcome, Ruling, resolve
from services.devon.receipts import (
    Receipt,
    ReceiptError,
    ReceiptFormat,
    parse_receipt,
    render_standing,
    render_v1,
    validate,
)
from services.devon.rule_ledger import (
    UNCONDITIONAL_DOMAINS,
    Assembly,
    AssemblyCheck,
    AssemblyRefused,
    Bend,
    Rule,
    RuleClass,
    RuleError,
    RuleLedger,
    check_assembly,
    require_assembly,
)
from services.devon.wager import (
    Adjustment,
    Calibration,
    Measurement,
    Wager,
    WagerBook,
    WagerError,
    open_wager,
)

__all__ = [
    "CONTEXT_SOURCES",
    "EVENTS",
    "EXECUTORS",
    "HIERARCHY",
    "INPUT_CHANNELS",
    "LEDGER_TABLES",
    "MEMORY_INDEXES",
    "MIND_LAYERS",
    "OUTPUTS",
    "PORTFOLIO",
    "SECURITY_GUARANTEES",
    "TEE_SOUL_FACETS",
    "UNCONDITIONAL_DOMAINS",
    "Authority",
    "Executor",
    "IntentState",
    "MemoryIndex",
    "MindLayer",
    "UniversalIntent",
    "UniversalReceipt",
    "check_event",
    "check_event_sequence",
    "check_layer_write",
    "check_receipt",
    "derive_state",
    "intent_is_receiptable",
    "may_delete_index",
    "may_delete_record",
    "may_override",
    "may_release_emergency_stop",
    "next_legal_events",
    "normalize_channel",
    "open_intent",
    "outranks",
    "route_action",
    "route_thinking",
    "AREAS",
    "AREA_CODES",
    "AUDIT_VERSION",
    "ALL_INTENTS",
    "CLAUSES",
    "DIMENSIONS",
    "HARD_RULES",
    "HANDOFF_VERSION",
    "HandoffEnvelope",
    "LAWS",
    "POLICY_VERSION",
    "RETURN_VERSION",
    "TYPE_CODES",
    "Adjustment",
    "Area",
    "AreaError",
    "ApprovalQueue",
    "ApprovalRequest",
    "ApprovalState",
    "Assembly",
    "AssemblyCheck",
    "AssemblyRefused",
    "Assessment",
    "ArtifactReference",
    "ArtifactReturnPlan",
    "AuditFinding",
    "AuditPlan",
    "AuditVerdict",
    "Bend",
    "Calibration",
    "Candidate",
    "ChangeKind",
    "ContractIssue",
    "CriticMode",
    "Decision",
    "DecisionResult",
    "Devon",
    "DevonResponse",
    "FilingLaw",
    "FilingPlan",
    "Finding",
    "Intent",
    "Kind",
    "NamingError",
    "Need",
    "Outcome",
    "ParsedCommand",
    "ParsedName",
    "ReadBack",
    "Measurement",
    "Receipt",
    "ReceiptError",
    "ReceiptFormat",
    "Risk",
    "Rule",
    "RuleClass",
    "RuleError",
    "RuleLedger",
    "RoutingDecision",
    "Ruling",
    "SourceReference",
    "Surface",
    "TaskProfile",
    "Verdict",
    "Wager",
    "WagerBook",
    "WagerError",
    "WriteCheck",
    "WriteRequest",
    "approval_gated_intents",
    "blank_scores",
    "build_audit_plan",
    "build_filename",
    "canonical_codes",
    "canonical_labels",
    "capability_status",
    "check_assembly",
    "check_punctuation",
    "check_write",
    "classify",
    "effect_intents",
    "evaluate_audit",
    "get_area",
    "is_valid_area",
    "law3_validate_readback",
    "normalize_code",
    "normalize_label",
    "open_wager",
    "parse",
    "parse_filename",
    "parse_receipt",
    "plan_artifact_return",
    "render_standing",
    "require_assembly",
    "render_v1",
    "require_area",
    "resolve",
    "resolve_area",
    "route",
    "slugify",
    "system_prompt",
    "validate",
    "validate_filename",
    "validate_handoff",
]

__version__ = "1.0.0"
