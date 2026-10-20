"""Strict, add-only interpretation of a draft ARF domain policy.

The policy cannot downgrade DEVON approval or edit existing authorities.
Validation rejects unknown keys, duplicate IDs and non-shadow activation.
Profile gates are proposals pending authoritative canon/signoff checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Mapping

ID = re.compile(r"^[a-z][a-z0-9_]{2,79}$")
KNOWN_DOMAINS = frozenset({
    "devon", "meta_supreme_x", "tsws", "tqo", "nco_forge", "editforge", "whatbroke"
})
FIXED_EFFECT_RISKS = frozenset({"write", "high_impact"})
FIXED_BLOCKED_RISKS = frozenset({"blocked"})
BASE_GATES = frozenset({
    "objective_defined", "finite_dod", "source_provenance", "requirement_evidence"
})

# Hard floors belong in audited source code. Domain policy JSON may add gates,
# but a configuration-only edit cannot silently remove protected requirements.
# To change these, an owner-approved code review and updated tests are required.
DOMAIN_FLOORS = {
    "devon": frozenset({"effect_free_devon_core", "runtime_policy_alignment",
                        "trusted_effect_receipts", "independent_readback"}),
    "meta_supreme_x": frozenset({"evidence_provenance", "council_role_coverage",
                                 "dissent_and_risk_record", "decision_traceability"}),
    "tsws": frozenset({"locked_canon_hash", "scene_continuity", "identity_continuity",
                        "protected_silence", "gold_thread_anahata", "decoded_media_qc",
                        "quality_threshold_99"}),
    "tqo": frozenset({"real_firsthand_evidence", "claim_provenance", "idiolect_compliance",
                       "script_doctor_threshold_90"}),
    "nco_forge": frozenset({"military_claim_sources", "civilian_translation_accuracy",
                             "branding_review", "lip_sync_audio_qc"}),
    "editforge": frozenset({"shot_manifest_provenance", "decoded_media_qc",
                             "version_and_hash_readback", "cost_and_retry_tracking",
                             "output_delivery_readback"}),
    "whatbroke": frozenset({"symptom_reproduction", "environment_version",
                             "root_cause_evidence", "fix_retest", "limitations_and_prevention"}),
}

REVIEW_FLOORS = {
    "devon": frozenset(),
    "meta_supreme_x": frozenset({"operator_decision_approval"}),
    "tsws": frozenset({"visual_producer_acceptance"}),
    "tqo": frozenset({"editorial_approval"}),
    "nco_forge": frozenset({"editorial_approval"}),
    "editforge": frozenset({"deliverable_acceptance"}),
    "whatbroke": frozenset(),
}

RELEASE_REQUIREMENT_FLOORS = {
    "devon": frozenset(), "meta_supreme_x": frozenset(), "tsws": frozenset(),
    "tqo": frozenset({"synthetic_media_disclosure", "active_version_readback"}),
    "nco_forge": frozenset({"synthetic_media_disclosure"}),
    "editforge": frozenset(), "whatbroke": frozenset(),
}

RELEASE_REVIEW_FLOORS = {
    "devon": frozenset(), "meta_supreme_x": frozenset(),
    "tsws": frozenset({"publication_approval"}),
    "tqo": frozenset({"publication_approval"}),
    "nco_forge": frozenset({"publication_approval"}),
    "editforge": frozenset(),
    "whatbroke": frozenset({"publication_approval"}),
}

RULE_FLOORS = {
    "devon": frozenset({"existing_approval_queue_only", "no_automatic_orphan_intent_replay", "no_new_executor"}),
    "meta_supreme_x": frozenset({"no_council_override_of_operator_authority", "no_unverified_consensus"}),
    "tsws": frozenset({"ep01_closeups_allowed_by_override", "do_not_change_sh135_approved_still", "new_gpu_spend_requires_approval"}),
    "tqo": frozenset({"tqo_script_doctor_90_of_100_as_of_2026_10_19", "no_invented_operator_tests"}),
    "nco_forge": frozenset({"do_not_invent_service_history", "no_unverified_benefits_or_policy_claims"}),
    "editforge": frozenset({"paid_render_requires_explicit_spend_approval", "ambiguous_render_must_not_auto_retry"}),
    "whatbroke": frozenset({"no_invented_error_logs", "scope_claims_to_tested_environment"}),
}


class PolicyError(ValueError):
    """The policy definition attempts an invalid or weaker contract."""


def _ids(value: object, context: str) -> FrozenSet[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not ID.fullmatch(x) for x in value):
        raise PolicyError(f"{context}: expected list of lowercase identifiers")
    if len(value) != len(set(value)):
        raise PolicyError(f"{context}: duplicate gate identifier")
    return frozenset(value)


@dataclass(frozen=True)
class DomainPolicy:
    name: str
    required_gates: FrozenSet[str]
    human_review_gates: FrozenSet[str]
    release_required_gates: FrozenSet[str]
    release_review_gates: FrozenSet[str]
    rules: FrozenSet[str]

    def gates_for(self, stage: str) -> FrozenSet[str]:
        return self.required_gates | (self.release_required_gates if stage == "release" else frozenset())

    def reviews_for(self, stage: str) -> FrozenSet[str]:
        return ((self.human_review_gates if stage in {"review", "release"} else frozenset())
                | (self.release_review_gates if stage == "release" else frozenset()))


@dataclass(frozen=True)
class ReliabilityPolicy:
    version: str
    digest: str
    profiles: Mapping[str, DomainPolicy]

    @classmethod
    def from_json(cls, path: str | Path) -> "ReliabilityPolicy":
        # JSON parser disallows duplicate keys, which otherwise silently overwrite
        # inherited settings. Run schema checks before any use of policy data.
        def strict_pairs(pairs):
            result = {}
            for key, val in pairs:
                if key in result:
                    raise PolicyError(f"duplicate JSON key: {key}")
                result[key] = val
            return result
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)
        except (OSError, json.JSONDecodeError) as exc:
            raise PolicyError(f"policy cannot be read: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "ReliabilityPolicy":
        if not isinstance(data, dict) or set(data) != {"policy_id", "version", "activation", "global", "profiles"}:
            raise PolicyError("policy keys are invalid")
        if data["policy_id"] != "arf-shared-reliability" or data["activation"] != "shadow_only":
            raise PolicyError("only known shadow-only policy can be loaded")
        if not isinstance(data["version"], str) or not data["version"].startswith("1.1."):
            raise PolicyError("unsupported policy version")
        base = data["global"]
        if not isinstance(base, dict) or set(base) != {"approval_required_for", "always_denied", "base_gates", "trust", "closure"}:
            raise PolicyError("unknown global policy settings")
        if _ids(base["approval_required_for"], "approval") != FIXED_EFFECT_RISKS:
            raise PolicyError("cannot weaken effect approval risks")
        if _ids(base["always_denied"], "blocked") != FIXED_BLOCKED_RISKS:
            raise PolicyError("blocked tools must remain forbidden")
        if _ids(base["base_gates"], "base gates") != BASE_GATES:
            raise PolicyError("base evidence gates cannot be changed")
        if base["trust"] != "evidence_attestations_from_authoritative_read_only_adapter_only":
            raise PolicyError("untrusted evidence mode forbidden")
        if base["closure"] != "no_automatic_closure_or_user_effects":
            raise PolicyError("automatic closure mode forbidden")
        profiles = data["profiles"]
        if not isinstance(profiles, dict) or set(profiles) != KNOWN_DOMAINS:
            raise PolicyError("all seven known domain overlays are required")
        checked = {}
        for name, raw in profiles.items():
            if not isinstance(raw, dict) or set(raw) != {"required_gates", "human_review_gates", "release_required_gates", "release_review_gates", "rules"}:
                raise PolicyError(f"{name}: unknown overlay keys")
            required = _ids(raw["required_gates"], name + " gates")
            reviews = _ids(raw["human_review_gates"], name + " reviews")
            release_required = _ids(raw["release_required_gates"], name + " release gates")
            release_reviews = _ids(raw["release_review_gates"], name + " release reviews")
            rules = _ids(raw["rules"], name + " rules")
            missing_floor = DOMAIN_FLOORS[name] - required
            if missing_floor:
                raise PolicyError(f"{name}: protected requirements removed: {','.join(sorted(missing_floor))}")
            if not REVIEW_FLOORS[name].issubset(reviews):
                raise PolicyError(f"{name}: protected human reviews removed")
            if not RULE_FLOORS[name].issubset(rules):
                raise PolicyError(f"{name}: protected policy rules removed")
            if not RELEASE_REQUIREMENT_FLOORS[name].issubset(release_required):
                raise PolicyError(f"{name}: protected release requirements removed")
            if not RELEASE_REVIEW_FLOORS[name].issubset(release_reviews):
                raise PolicyError(f"{name}: protected release reviews removed")
            checked[name] = DomainPolicy(name, required | BASE_GATES, reviews,
                                         release_required, release_reviews, rules)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return cls(version=data["version"],
                   digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                   profiles=checked)

    def domain(self, name: str) -> DomainPolicy:
        if name not in self.profiles:
            raise PolicyError("unknown domain; do not fall back to generic")
        return self.profiles[name]
