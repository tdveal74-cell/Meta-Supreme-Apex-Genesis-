// REFUSE BEFORE SEARCH. The answer for every POST the preflight settled
// without a conflict search: a refusal, or HOLD for a single job. It is the
// last node on its branch, so with the webhook's lastNode response this item
// IS the HTTP 200 body. The Ledger Feeder reads the decision as
// body.decision || body.gate_decision || body.gate.decision, so the decision
// lives at gate.decision and nowhere else, and no top level decision key can
// shadow it. Nothing was searched and nothing was written, and the answer
// says both. Phase 1 of the grouping build, ruled by Tee 2026-10-08.
const pre = ($input.first().json || {}).preflight || {};
const decision = String(pre.decision || "REJECT_MALFORMED");

return [{
  json: {
    receipt: null,
    gate: {
      decision: decision,
      reason: String(pre.reason || "the preflight returned no reason"),
      kind: pre.kind || null,
      source_intent_ids: Array.isArray(pre.source_intent_ids) ? pre.source_intent_ids : [],
      learning_intent_id: pre.learning_intent_id || null,
      lesson_key: pre.lesson_key || null,
      search_spent: false
    },
    subconscious_write: {
      ok: true,
      dry_run: true,
      skipped: true,
      reason: "decided before any search; nothing was written",
      record_id: null
    }
  }
}];