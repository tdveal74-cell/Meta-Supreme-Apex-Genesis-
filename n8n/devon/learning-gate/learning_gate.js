const input = $input.first().json;
const candidate = input.candidate;
const receipt = input.receipt;

// From Phase 1 of the grouping build, ruled by Tee 2026-10-08, PROMOTE needs a
// lesson whose members the gate verified ITSELF against the live ledger. The
// count is verified_count, which only the Evidence Verifier (Phase 3) sets,
// and never the length of the id list a caller sent. A single job never
// promotes. Until Phase 3 nothing reaches this node, and if anything did, it
// could not carry a verified count, so it would HOLD.
// The count only stands when the member list the verifier returned agrees
// with it; a count with no matching list counts as none.
const verifiedIds = candidate && Array.isArray(candidate.verified_ids) ? candidate.verified_ids : [];
const verified = candidate && typeof candidate.verified_count === "number" && candidate.verified_count === verifiedIds.length ? candidate.verified_count : 0;
const floor = candidate && typeof candidate.min_sources === "number" && candidate.min_sources >= 2 ? candidate.min_sources : 2;

const result = {
  candidate_id: candidate?.candidate_id,
  claim: candidate?.claim,
  decision: null,
  reason: null,
  receipt_complete: receipt?.complete === true,
  conflict_status: receipt?.conflict_status || null,
  independent_sources: verified
};

// Gate rules (mirror of devon_build12_learning_gate.py, narrowed by the grouping spec)
if (!candidate || !candidate.claim || candidate.claim.length < 12) {
  result.decision = "REJECT_WEAK_EVIDENCE";
  result.reason = "claim missing or too vague";
} else if (!receipt || receipt.complete !== true) {
  result.decision = "REQUIRES_HUMAN";
  result.reason = "conflict receipt incomplete or missing";
} else if (receipt.conflict_status === "conflict") {
  result.decision = "REJECT_CONFLICT";
  result.reason = "higher-layer conflict detected";
} else if (receipt.conflict_status === "requires_human") {
  result.decision = "REQUIRES_HUMAN";
  result.reason = "conflict search deferred to human";
} else if (candidate.kind !== "lesson") {
  result.decision = "HOLD_SUBCONSCIOUS";
  result.reason = "a single job never promotes";
} else if (verified < floor) {
  result.decision = "HOLD_SUBCONSCIOUS";
  result.reason = "fewer verified independent sources than the lesson requires";
} else if (receipt.conflict_status === "clear") {
  result.decision = "PROMOTE";
  result.reason = "clear receipt + verified independent evidence";
} else {
  result.decision = "REQUIRES_HUMAN";
  result.reason = "unrecognised conflict_status";
}

return [{ json: { ...input, gate: result } }];