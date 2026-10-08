const input = $input.first().json;
const candidate = input.candidate;
const receipt = input.receipt || {};

// From Phase 1 of the grouping build, ruled by Tee 2026-10-08. The record id
// is the learning intent id the feeder minted and stored BEFORE it posted, so
// a retry after a lost response rewrites the same record instead of adding a
// second one. The record says what it is (kind, status, lesson_key) and which
// receipt cleared it, and source_intent_ids holds only the members the gate
// verified. Only a lesson can reach this node.
const learningIntentId = String(candidate.learning_intent_id || "");
if (!/^[0-9A-HJKMNP-TV-Z]{26}$/.test(learningIntentId)) {
  throw new Error("Build Record reached without a learning intent id, so nothing is written and nothing was promoted");
}
const memberIds = Array.isArray(candidate.verified_ids) ? candidate.verified_ids.map(function (id) { return typeof id === "string" ? id.trim().toUpperCase() : ""; }) : [];
if (memberIds.length < 2 || memberIds.length !== candidate.verified_count || new Set(memberIds).size !== memberIds.length || !memberIds.every(function (id) { return /^[0-9A-HJKMNP-TV-Z]{26}$/.test(id); })) {
  throw new Error("Build Record reached without a verified list of distinct members for lesson group " + learningIntentId + ", so nothing is written and nothing was promoted");
}
const top = Array.isArray(receipt.matched_records) && receipt.matched_records.length ? receipt.matched_records[0] : null;

const record = {
  _id: learningIntentId,
  text: candidate.claim,
  kind: "lesson",
  status: "active",
  lesson_key: candidate.lesson_key,
  learning_intent_id: learningIntentId,
  area: candidate.area,
  proposed_scope: candidate.proposed_scope,
  source_intent_ids: memberIds,
  independent_evidence_count: candidate.verified_count,
  conflict_check_receipt_id: receipt.receipt_id || "",
  conflict_status: receipt.conflict_status || "",
  top_match_id: top ? String(top.id || "") : "",
  top_match_score: top && typeof top.score === "number" ? top.score : null,
  schema_version: "1.1.0",
  created_at: new Date().toISOString()
};

// Carry the upstream context forward alongside the record for later formatting
return [{ json: { ...input, record } }];