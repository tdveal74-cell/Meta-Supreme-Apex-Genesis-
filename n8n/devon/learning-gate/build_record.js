const input = $input.first().json;
const candidate = input.candidate;

const record = {
  _id: candidate.candidate_id,
  text: candidate.claim,
  source_intent_ids: candidate.source_intent_ids,
  candidate_id: candidate.candidate_id,
  proposed_scope: candidate.proposed_scope,
  confidence: candidate.confidence,
  independent_evidence_count: candidate.independent_evidence_count,
  schema_version: candidate.schema_version || "1.0.0",
  created_at: new Date().toISOString()
};

// Carry the upstream context forward alongside the record for later formatting
return [{ json: { ...input, record } }];