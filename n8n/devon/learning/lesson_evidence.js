// LESSON EVIDENCE RULES, the one copy of the grouping rule block.
// Spec: docs/devon/SYS_SPEC_learning-lane-grouping_v1_2026-10-07.md, "The
// independence rule". Ruled by Tee 2026-10-08: build Phase 0 and Phase 1.
//
// This file defines functions and runs nothing. From Phase 3 it is pasted,
// unchanged, at the top of two live Code nodes: the feeder's Form Lesson
// Groups, which PICKS members, and the gate's Evidence Verifier, which only
// CHECKS the members it was sent and refuses the whole group if one fails.
// Both read the same rules, so a gate refusal of a group the feeder formed
// means the two live copies have drifted. Every name starts with "lesson" so
// pasting it beside other node code cannot collide.
//
// Everything is read from the LIVE ledger row (columns plus the envelope
// JSON), never from what a caller posted. Every unknown fails closed: a
// missing field never makes a job count, and an unreadable act never makes
// two jobs look independent.

const LESSON_ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const LESSON_MAX_MEMBERS = 5;
// A group refused before the conflict search never was a proposal, so its
// members stay free for another lesson. Any other recorded outcome, and any
// group still in flight, holds its members for good. HOLD_SUBCONSCIOUS is
// absent on purpose: the gate answers it before the search (key unknown, too
// few verified) and after it (learning-gate/learning_gate.js), and the decision string alone
// cannot tell which, so a HOLD holds.
const LESSON_PREFLIGHT_REFUSALS = ['REJECT_MALFORMED', 'REJECT_SECRET', 'REJECT_UNREGISTERED', 'REJECT_UNVERIFIED_SOURCE'];
// The verify card string Build 14 writes when Tee approves a verification.
const LESSON_VERIFY_EVIDENCE = /^verify_card REQ-[0-9]{8}-[A-Za-z0-9]{4,16} approved by Tee$/;

function lessonNormId(id) {
  return typeof id === 'string' ? id.trim().toUpperCase() : '';
}

function lessonEnvelope(row) {
  if (!row || typeof row !== 'object') { return null; }
  if (row.envelope && typeof row.envelope === 'object') { return row.envelope; }
  if (typeof row.envelope !== 'string' || !row.envelope) { return null; }
  try {
    const e = JSON.parse(row.envelope);
    return (e && typeof e === 'object' && !Array.isArray(e)) ? e : null;
  } catch (err) { return null; }
}

function lessonIsTrue(v) {
  return v === true || v === 'true';
}

// Compatibility folded, invisible characters removed, whitespace collapsed,
// case folded. Each step can only make two texts collide, never split one.
function lessonText(v) {
  return String(v === null || v === undefined ? '' : v).normalize('NFKC')
    .replace(/[\u00ad\u200b-\u200d\u2060\ufeff]/g, '').trim().replace(/\s+/g, ' ').toLowerCase();
}

function lessonIsEmpty(v) {
  return v === null || v === undefined || (typeof v === 'string' && lessonText(v) === '') || (Array.isArray(v) && v.length === 0);
}

// Numbers and booleans read as text, so 1 and "1" are one value, and a key
// holding nothing reads as a key that is absent. Both only add collisions.
function lessonCanon(v) {
  if (v === null || v === undefined) { return 'null'; }
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') { return JSON.stringify(lessonText(v)); }
  if (Array.isArray(v)) { return '[' + v.map(lessonCanon).join(',') + ']'; }
  if (typeof v === 'object') {
    return '{' + Object.keys(v).filter(function (k) { return !lessonIsEmpty(v[k]); }).sort()
      .map(function (k) { return JSON.stringify(k) + ':' + lessonCanon(v[k]); }).join(',') + '}';
  }
  return JSON.stringify(String(v));
}

// Every id a table hands back as a list, in whatever shape it arrives: an
// array, a JSON string, a comma or space separated string. Read as every
// whole ULID it holds, case folded. The registry writes evidence_ids as a
// JSON string (lesson_registry.py Lesson.row), so reading only arrays would
// refuse every declared member under E4.
function lessonIdList(v) {
  let s;
  if (typeof v === 'string') { s = v; }
  else { try { s = JSON.stringify(v === undefined ? null : v); } catch (err) { s = ''; } }
  return String(s || '').toUpperCase().match(/(?<![0-9A-Z])[0-9A-HJKMNP-TV-Z]{26}(?![0-9A-Z])/g) || [];
}

// The structural act a job performed: its action and the structural objects
// the intake whitelists (form_job.js): airtable {table, fields}, zapier
// {tool, arguments}, editforge {kind, prompt, provider, options}. Values are
// read through lessonText, so invisible characters, spacing, case and number
// versus string cannot split one act. The free text fields are left out on
// purpose: summary, note, brief and lesson_key, so a reworded summary, note
// or brief cannot split one act into two. A changed word or punctuation mark
// inside a structural field, a Title or a Body, still reads as another act,
// and those can be model output (face/parse_reply.js). An action with none of
// those objects (spine.echo, drive.draft today) fingerprints as the action
// alone, so two of them always count once. That fails closed.
function lessonActFingerprint(env) {
  const intent = (env && env.intent && typeof env.intent === 'object') ? env.intent : {};
  const p = (intent.payload && typeof intent.payload === 'object') ? intent.payload : {};
  const act = { action: lessonText(p.action) };
  if (p.airtable && typeof p.airtable === 'object') {
    act.airtable = { table: p.airtable.table, fields: p.airtable.fields };
  }
  if (p.zapier && typeof p.zapier === 'object') {
    act.zapier = { tool: p.zapier.tool, arguments: p.zapier.arguments };
  }
  if (p.editforge && typeof p.editforge === 'object') {
    act.editforge = { kind: p.editforge.kind, prompt: p.editforge.prompt, provider: p.editforge.provider, options: p.editforge.options };
  }
  return lessonCanon(act);
}

// One artifact read three ways: its uri, its Airtable record id, its Drive
// file id. A Drive uri is built one way (drive-draft-writer/advance_envelope.js)
// and the file id is the belt. KNOWN LIMIT: a Zapier artifact carries only
// the first URL its tool answered, which can be empty, so two Zapier jobs that
// touched one external object can count twice here. URLs are not normalised
// to close that, because some tools name the object in the query string.
function lessonArtifactKeys(env) {
  const keys = [];
  const arts = (env && Array.isArray(env.artifacts)) ? env.artifacts : [];
  for (const a of arts) {
    if (!a || typeof a !== 'object') { continue; }
    if (typeof a.uri === 'string' && a.uri.trim()) { keys.push('uri:' + a.uri.trim().toLowerCase()); }
    if (typeof a.record_id === 'string' && a.record_id.trim()) { keys.push('record:' + a.record_id.trim()); }
    if (typeof a.drive_file_id === 'string' && a.drive_file_id.trim()) { keys.push('drive:' + a.drive_file_id.trim()); }
  }
  return keys;
}

function lessonVerifiedDay(env, row) {
  const v = (env && env.verification && typeof env.verification === 'object') ? env.verification : {};
  const t = Date.parse(String(v.verified_at || ''));
  return Number.isNaN(t) ? '' : new Date(t).toISOString().slice(0, 10);
}

function lessonExecutionPair(env, row) {
  const ex = (env && env.execution && typeof env.execution === 'object') ? env.execution : {};
  const wf = String((row && row.workflow_id) || ex.workflow_id || '').trim();
  const id = String((row && row.execution_id) || ex.execution_id || '').trim();
  return (wf && id) ? wf + '#' + id : '';
}

// The parent chain from one job upward, through the ledger rows in hand.
// Bounded and cycle safe. The chain is CLOSED only when it ends on a row
// with no parent. A parent whose row is not in hand, a cycle, or the hop
// bound leaves it OPEN, and an open chain cannot prove two jobs unrelated:
// at the gate the rows in hand are the members' own, so a walk there stops
// after one hop and a grandparent or a cousin would read as independent.
// Today no writer sets parent_intent_id (intake-former/apply_tags.js writes
// null), so nothing is refused for it; Phase 3 may fetch ancestors instead.
function lessonAncestors(id, rowsById) {
  const seen = [];
  let cur = rowsById[id];
  for (let hops = 0; hops < 20 && cur; hops++) {
    const env = lessonEnvelope(cur);
    const parent = lessonNormId(cur.parent_intent_id) || lessonNormId(env && env.parent_intent_id);
    if (!parent) { return { chain: seen, closed: true }; }
    if (seen.indexOf(parent) !== -1 || parent === id) { return { chain: seen, closed: false }; }
    seen.push(parent);
    cur = rowsById[parent];
  }
  return { chain: seen, closed: false };
}

// E1 to E6 for one posted or candidate id. Returns every reason it fails,
// so a refusal names all of them rather than the first.
//   ctx.lessonKey       the lesson being formed or checked
//   ctx.entry           its registry row: {lesson_key, status, evidence_ids}
//   ctx.rowsById        normalised intent id to live ledger row
//   ctx.groups          group log rows: {learning_intent_id, source_intent_ids, gate_decision, state}
//   ctx.selfGroupId     the learning_intent_id under check, excluded from E6
//   ctx.committedIds    ids already named by a Soul Committer row
function lessonCheckMember(rawId, ctx) {
  const id = lessonNormId(rawId);
  const reasons = [];
  if (!LESSON_ULID.test(id)) {
    reasons.push('E1 not a ULID');
    return { id: id, ok: false, reasons: reasons };
  }
  const row = (ctx.rowsById || {})[id];
  const env = lessonEnvelope(row);
  if (!row) {
    reasons.push('E2 no ledger row');
  } else {
    if (String(row.state || '') !== 'COMPLETED') { reasons.push('E2 state is ' + String(row.state || 'empty') + ', not COMPLETED'); }
    if (!lessonIsTrue(row.terminal)) { reasons.push('E2 not terminal'); }
    if (String(row.receipt_outcome || '') !== 'completed') { reasons.push('E2 receipt outcome is ' + String(row.receipt_outcome || 'empty') + ', not completed'); }
    if (!env) { reasons.push('E2 envelope unreadable'); }
    else if (lessonNormId(env.intent_id) !== id) { reasons.push('E2 envelope intent_id does not match the row'); }
  }
  if (row) {
    const v = (env && env.verification && typeof env.verification === 'object') ? env.verification : {};
    const evidence = Array.isArray(v.evidence) ? v.evidence : [];
    if (String(row.verification_state || '') !== 'passed') { reasons.push('E3 verification is ' + String(row.verification_state || 'empty') + ', not passed'); }
    if (String(row.verification_method || '') !== 'human_watch') { reasons.push('E3 not verified by a human watch'); }
    if (!lessonIsTrue(row.human_watched)) { reasons.push('E3 human_watched is not true'); }
    if (!evidence.some(function (e) { return typeof e === 'string' && LESSON_VERIFY_EVIDENCE.test(e.trim()); })) { reasons.push('E3 no verify card approved by Tee in the evidence'); }
    if (!lessonVerifiedDay(env, row)) { reasons.push('E3 no readable verified_at'); }
  }
  const entry = ctx.entry || null;
  const declared = entry ? lessonIdList(entry.evidence_ids) : [];
  const payload = (env && env.intent && env.intent.payload && typeof env.intent.payload === 'object') ? env.intent.payload : {};
  const keyed = typeof payload.lesson_key === 'string' && payload.lesson_key.trim() === String(ctx.lessonKey || '');
  if (!keyed && declared.indexOf(id) === -1) { reasons.push('E4 not declared for lesson ' + String(ctx.lessonKey || 'unknown')); }
  if (!entry || String(entry.status || '') !== 'active') { reasons.push('E5 lesson ' + String(ctx.lessonKey || 'unknown') + ' is not active'); }
  if (payload.auto_verify === true || payload.auto_verify === 'true') { reasons.push('E5 filed with auto_verify'); }
  const self = lessonNormId(ctx.selfGroupId);
  if (!Array.isArray(ctx.groups)) { reasons.push('E6 the group log was not read'); }
  for (const g of (Array.isArray(ctx.groups) ? ctx.groups : [])) {
    if (!g || (self && lessonNormId(g.learning_intent_id) === self)) { continue; }
    if (lessonIdList(g.source_intent_ids).indexOf(id) === -1) { continue; }
    if (LESSON_PREFLIGHT_REFUSALS.indexOf(String(g.gate_decision || '')) !== -1) { continue; }
    reasons.push('E6 already backs group ' + String(g.learning_intent_id || 'unknown'));
  }
  if (ctx.committedIds === undefined || ctx.committedIds === null) { reasons.push('E6 the soul commit list was not read'); }
  else if (lessonIdList(ctx.committedIds).indexOf(id) !== -1) { reasons.push('E6 already named by a soul commit'); }
  return { id: id, ok: reasons.length === 0, reasons: reasons };
}

// I1 to I7 for one pair. Both ids must already have a ledger row.
function lessonCheckPair(rawA, rawB, ctx) {
  const a = lessonNormId(rawA);
  const b = lessonNormId(rawB);
  const rows = ctx.rowsById || {};
  const ra = rows[a];
  const rb = rows[b];
  const ea = lessonEnvelope(ra);
  const eb = lessonEnvelope(rb);
  const reasons = [];
  if (a === b) { reasons.push('I1 the same job'); }
  if (!ra || !rb) {
    reasons.push('I0 a ledger row is missing, so independence cannot be read');
    return { a: a, b: b, ok: false, reasons: reasons };
  }
  const ka = String(ra.idempotency_key || (ea && ea.idempotency_key) || '').trim();
  const kb = String(rb.idempotency_key || (eb && eb.idempotency_key) || '').trim();
  if (!ka || !kb) { reasons.push('I2 an idempotency key is missing'); }
  else if (ka === kb) { reasons.push('I2 the same idempotency key, one job retried'); }
  const upA = lessonAncestors(a, rows);
  const upB = lessonAncestors(b, rows);
  if (upA.chain.indexOf(b) !== -1 || upB.chain.indexOf(a) !== -1) { reasons.push('I3 one is the other\'s ancestor'); }
  else if (upA.chain.some(function (x) { return upB.chain.indexOf(x) !== -1; })) { reasons.push('I3 they share a parent'); }
  else if (!upA.closed || !upB.closed) { reasons.push('I3 a parent chain leaves the rows in hand, so lineage cannot be read'); }
  const artA = lessonArtifactKeys(ea);
  const artB = lessonArtifactKeys(eb);
  const shared = artA.filter(function (x) { return artB.indexOf(x) !== -1; });
  if (shared.length) { reasons.push('I4 they share an artifact'); }
  if (lessonActFingerprint(ea) === lessonActFingerprint(eb)) { reasons.push('I5 the same structural act'); }
  if (ctx.distinctDays !== false) {
    const da = lessonVerifiedDay(ea, ra);
    const db = lessonVerifiedDay(eb, rb);
    if (!da || !db) { reasons.push('I6 a verified date is missing'); }
    else if (da === db) { reasons.push('I6 verified on the same UTC day ' + da); }
  }
  const xa = lessonExecutionPair(ea, ra);
  const xb = lessonExecutionPair(eb, rb);
  if (!xa || !xb) { reasons.push('I7 a workflow and execution id pair is missing'); }
  else if (xa === xb) { reasons.push('I7 the same workflow execution'); }
  return { a: a, b: b, ok: reasons.length === 0, reasons: reasons };
}

// THE GATE: checks exactly the ids it was sent. It never picks, never trims
// a group to its good members, and never trusts a count from the caller. One
// failing member or pair refuses the whole group.
function lessonVerifyGroup(rawIds, ctx) {
  const ids = (Array.isArray(rawIds) ? rawIds : []).map(lessonNormId);
  const members = ids.map(function (id) { return lessonCheckMember(id, ctx); });
  const pairs = [];
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      pairs.push(lessonCheckPair(ids[i], ids[j], ctx));
    }
  }
  const ok = ids.length >= 2 && ids.length <= LESSON_MAX_MEMBERS &&
    members.every(function (m) { return m.ok; }) && pairs.every(function (p) { return p.ok; });
  return { ok: ok, verified_count: ok ? ids.length : 0, members: members, pairs: pairs };
}

// THE FEEDER: picks members for one lesson from its declared candidates,
// oldest verified first, skipping any that fail a member rule or a pair rule
// against a member already chosen. Returns the chosen ids and a reason for
// every id left out, so a quiet day reports a count and not silence.
function lessonPickMembers(rawCandidateIds, ctx) {
  const seen = [];
  const checked = [];
  const excluded = [];
  for (const raw of (Array.isArray(rawCandidateIds) ? rawCandidateIds : [])) {
    const id = lessonNormId(raw);
    if (seen.indexOf(id) !== -1) { excluded.push({ id: id, reasons: ['a repeat of an id already considered'] }); continue; }
    seen.push(id);
    const m = lessonCheckMember(id, ctx);
    if (!m.ok) { excluded.push({ id: id, reasons: m.reasons }); continue; }
    const env = lessonEnvelope((ctx.rowsById || {})[id]);
    // E3 already refused a member with no readable verified_at, so every
    // time here parses; compared as instants, not as strings.
    checked.push({ id: id, at: Date.parse(String((env && env.verification && env.verification.verified_at) || '')) });
  }
  checked.sort(function (x, y) { return x.at !== y.at ? x.at - y.at : (x.id < y.id ? -1 : 1); });
  const chosen = [];
  for (const c of checked) {
    if (chosen.length >= LESSON_MAX_MEMBERS) { excluded.push({ id: c.id, reasons: ['group already holds ' + LESSON_MAX_MEMBERS + ' members'] }); continue; }
    const clash = [];
    for (const k of chosen) {
      const p = lessonCheckPair(k, c.id, ctx);
      if (!p.ok) { clash.push('against ' + k + ': ' + p.reasons.join('; ')); }
    }
    if (clash.length) { excluded.push({ id: c.id, reasons: clash }); continue; }
    chosen.push(c.id);
  }
  return { members: chosen, excluded: excluded };
}
