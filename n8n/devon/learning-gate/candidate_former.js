// PREFLIGHT. Reads the POST and decides, before any conflict search is spent,
// whether there is anything to search at all. Phase 1 of the grouping build,
// docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md, ruled by Tee
// 2026-10-08.
//
// Two shapes reach this door:
//   kind "job"     one completed job, as the Ledger Feeder posts it. kind is
//                  absent on every feeder POST today and defaults to job. A
//                  single job never promotes, so it is answered HOLD without
//                  a search. The bar is two independent sources.
//   kind "lesson"  a group the feeder formed for a lesson Tee declared. Off
//                  until Phase 3 creates the tables the gate must read first,
//                  so every lesson POST is refused as unregistered today.
//
// Every refusal is DATA, never a throw: the webhook answers 200 with
// gate.decision set, hostile input cannot trip the error handler, and nothing
// is searched or written. Throws stay for infrastructure faults downstream.
// Nothing the caller sends as evidence, outcomes, counts or a receipt is
// read; the gate only ever counts what it verified itself.
const LESSON_PATH_ENABLED = false;
const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const MAX_MEMBERS = 5;
// The registry's shapes, in the same order. services/devon/lesson_registry.py
// carries the source list and test_devon_lesson_registry.py pins this copy to it.
const SECRET_SHAPES = [
  ["a Pinecone key", String.raw`pcsk_[A-Za-z0-9_-]{20,}`],
  ["a console token", String.raw`dst_[0-9a-f]{32,}`],
  ["a capture token", String.raw`dcp_[A-Za-z0-9_]{16,}`],
  ["an Anthropic key", String.raw`\bsk-ant-[A-Za-z0-9_-]{20,}`],
  ["an OpenAI style key", String.raw`\bsk-[A-Za-z0-9_-]{20,}`],
  ["a Cerebras key", String.raw`\bcsk-[A-Za-z0-9]{20,}`],
  ["an AWS access key id", String.raw`\bAKIA[0-9A-Z]{16}\b`],
  ["a private key block", String.raw`-----BEGIN [A-Z ]*PRIVATE KEY-----`],
  ["a Slack token", String.raw`\bxox[abprs]-[A-Za-z0-9-]{10,}`],
  ["a GitHub token", String.raw`\bgh[pousr]_[A-Za-z0-9]{30,}`],
  ["a Google API key", String.raw`\bAIza[0-9A-Za-z_-]{30,}`],
  ["an Airtable token", String.raw`\bpat[A-Za-z0-9]{14}\.[0-9a-f]{40,}`],
  ["a JSON web token", String.raw`\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.`],
  ["a bearer credential", String.raw`\b[Bb][Ee][Aa][Rr][Ee][Rr]\s+[A-Za-z0-9._~+/=-]{16,}`],
  ["an x-devon-key value", String.raw`[Xx]-[Dd][Ee][Vv][Oo][Nn]-[Kk][Ee][Yy]\s*[:=]\s*\S{8,}`],
];

// The reference gate's key name rule, kept: a field NAMED like a credential
// that carries any value is refused, whatever the value looks like.
const SECRET_KEY_NAMES = /^(password|passwd|api[_ -]?key|secret|client[_ -]?secret|private[_ -]?key|authorization|session[_ -]?cookie|x-devon-key|token)$/i;

const item = $input.first().json || {};
const body = (item.body && typeof item.body === "object" && !Array.isArray(item.body)) ? item.body : null;

function answer(decision, reason, extra) {
  return [{ json: { candidate: null, preflight: Object.assign({ decision: decision, reason: reason, search_needed: false }, extra || {}) } }];
}
function norm(id) { return typeof id === "string" ? id.trim().toUpperCase() : ""; }
function stringsIn(v, out, depth) {
  if (depth > 8 || out.length > 2000) { return out; }
  if (typeof v === "string") { out.push(v); }
  else if (Array.isArray(v)) { for (const x of v) { stringsIn(x, out, depth + 1); } }
  else if (v && typeof v === "object") { for (const k of Object.keys(v)) { out.push(k); stringsIn(v[k], out, depth + 1); } }
  return out;
}

function credentialKey(v, depth) {
  if (depth > 8 || !v || typeof v !== "object") { return ""; }
  if (Array.isArray(v)) {
    for (const x of v) { const k = credentialKey(x, depth + 1); if (k) { return k; } }
    return "";
  }
  for (const k of Object.keys(v)) {
    const val = v[k];
    const empty = val === null || val === undefined || val === "" || (Array.isArray(val) && !val.length) || (typeof val === "object" && !Array.isArray(val) && val !== null && !Object.keys(val).length);
    if (SECRET_KEY_NAMES.test(k) && !empty) { return k; }
    const inner = credentialKey(val, depth + 1);
    if (inner) { return inner; }
  }
  return "";
}

if (!body) {
  return answer("REJECT_MALFORMED", "the request body is not a JSON object");
}
const kind = body.kind === undefined ? "job" : body.kind;
if (kind !== "job" && kind !== "lesson") {
  return answer("REJECT_MALFORMED", "kind must be job or lesson");
}
const rawIds = body.source_intent_ids;
if (!Array.isArray(rawIds) || !rawIds.every(function (id) { return typeof id === "string"; })) {
  return answer("REJECT_MALFORMED", "source_intent_ids must be a list of id strings", { kind: kind });
}
const ids = rawIds.map(norm);
const notUlid = ids.filter(function (id) { return !ULID.test(id); });
if (notUlid.length) {
  return answer("REJECT_MALFORMED", notUlid.length + " source id(s) are not ULIDs", { kind: kind });
}
if (new Set(ids).size !== ids.length) {
  return answer("REJECT_MALFORMED", "a source id repeats once letter case is ignored", { kind: kind });
}
if (kind === "job" && ids.length !== 1) {
  return answer("REJECT_MALFORMED", "a job carries exactly one source id; " + ids.length + " were sent", { kind: kind });
}
if (kind === "lesson") {
  if (body.claim !== undefined) {
    return answer("REJECT_MALFORMED", "a lesson carries no claim; the gate reads the claim from the registry", { kind: kind });
  }
  if (!ULID.test(norm(body.learning_intent_id))) {
    return answer("REJECT_MALFORMED", "learning_intent_id is not a ULID", { kind: kind });
  }
  if (ids.length < 2 || ids.length > MAX_MEMBERS) {
    return answer("REJECT_MALFORMED", "a lesson carries 2 to " + MAX_MEMBERS + " source ids; " + ids.length + " were sent", { kind: kind });
  }
  if (typeof body.lesson_key !== "string" || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(body.lesson_key) || body.lesson_key.length > 60) {
    return answer("REJECT_MALFORMED", "lesson_key is not a lesson slug", { kind: kind });
  }
}

const namedKey = credentialKey(body, 0);
if (namedKey) {
  return answer("REJECT_SECRET", "the request carries a field named like a credential", { kind: kind });
}
const texts = stringsIn(body, [], 0);
for (const [label, source] of SECRET_SHAPES) {
  const re = new RegExp(source);
  if (texts.some(function (t) { return re.test(t); })) {
    // The matched text is never echoed back, only the shape it matched.
    return answer("REJECT_SECRET", "the request carries something shaped like " + label, { kind: kind });
  }
}

if (kind === "job") {
  const claim = typeof body.claim === "string" ? body.claim.trim() : "";
  if (claim.length < 12) {
    return answer("REJECT_WEAK_EVIDENCE", "claim missing, not text, or shorter than 12 characters", { kind: kind, source_intent_ids: ids });
  }
  return answer("HOLD_SUBCONSCIOUS", "a single job never promotes; a lesson needs two independent sources", { kind: kind, source_intent_ids: ids });
}

if (!LESSON_PATH_ENABLED) {
  return answer("REJECT_UNREGISTERED", "the lesson path is not enabled yet; it opens in Phase 3 with the registry and group log", { kind: kind, source_intent_ids: ids, learning_intent_id: norm(body.learning_intent_id), lesson_key: body.lesson_key });
}

// Phase 3 continues from here: the registration, registry and ledger reads
// and the Evidence Verifier decide search_needed. Until then this line is
// unreachable, and it refuses rather than searching if it is ever reached.
return answer("REJECT_UNREGISTERED", "the lesson path has no verifier yet", { kind: kind, source_intent_ids: ids });