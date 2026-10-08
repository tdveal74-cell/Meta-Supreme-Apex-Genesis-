const input = $input.first().json;
const candidate = input.candidate;
const receipt = input.receipt;

const result = {
  candidate_id: candidate?.candidate_id,
  claim: candidate?.claim,
  decision: null,
  reason: null,
  receipt_complete: receipt?.complete === true,
  conflict_status: receipt?.conflict_status || null,
  independent_sources: candidate?.independent_evidence_count || (candidate?.source_intent_ids || []).length
};

// Gate rules (mirror of devon_build12_learning_gate.py)
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
} else if (result.independent_sources < 2) {
  result.decision = "HOLD_SUBCONSCIOUS";
  result.reason = "fewer than two independent source_intent_ids";
} else if (receipt.conflict_status === "clear") {
  result.decision = "PROMOTE";
  result.reason = "clear receipt + sufficient independent evidence";
} else {
  result.decision = "REQUIRES_HUMAN";
  result.reason = "unrecognised conflict_status";
}

return [{ json: { ...input, gate: result } }];