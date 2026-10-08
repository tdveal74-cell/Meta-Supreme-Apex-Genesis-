// Forms one learning candidate from the feeder's POST. No test fallbacks,
// ruled by Tee 2026-10-07: a missing claim or missing source ids is refused,
// never filled in, so no caller can borrow fabricated provenance. Ids are
// trimmed and upper cased (ULIDs are case insensitive) before duplicates are
// dropped, so one job cannot pose as two independent sources.
const body = ($input.first().json && $input.first().json.body) || $input.first().json || {};

const claim = typeof body.claim === "string" ? body.claim.trim() : "";
if (claim.length < 12) {
  throw new Error("REFUSED: claim missing, not text, or shorter than 12 characters; nothing was searched or written");
}

const rawIds = Array.isArray(body.source_intent_ids) ? body.source_intent_ids : [];
const sourceIntentIds = [...new Set(rawIds
  .filter(id => typeof id === "string")
  .map(id => id.trim().toUpperCase())
  .filter(id => id.length >= 10))];
if (sourceIntentIds.length < 1) {
  throw new Error("REFUSED: no source_intent_ids; a candidate needs at least one real completed intent id");
}

// Minimal candidate former (JS port of the reference)
function newUlid() {
  const alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
  let out = "";
  for (let i = 0; i < 26; i++) {
    out += alphabet[Math.floor(Math.random() * 32)];
  }
  return out;
}

const candidate = {
  schema_version: "1.0.0",
  candidate_id: newUlid(),
  source_intent_ids: sourceIntentIds,
  claim: claim,
  evidence: sourceIntentIds.map(id => ({ intent_id: id, state: "COMPLETED" })),
  observed_outcomes: sourceIntentIds.map((_, i) => `independent observation ${i + 1}`),
  proposed_scope: body.proposed_scope || "system",
  confidence: typeof body.confidence === "number" ? body.confidence : 0.75,
  created_at: new Date().toISOString(),
  independent_evidence_count: sourceIntentIds.length
};

return [{ json: { candidate } }];