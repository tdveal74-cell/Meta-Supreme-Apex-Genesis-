// One proposal per intent, ever. Any commit-log row for the intent, whatever
// its state, means it was already put to Tee. Before raising a NEW request,
// reconcile against the queue itself: if a soul-committer request for this
// intent already exists (a lost response on an earlier poll), ADOPT its
// request_id instead of raising a duplicate card. At most ONE new POST per
// poll, so HTTP pairing stays 1:1 and a run can never outlast the schedule.
//
// LESSONS ONLY, from the grouping build's Phase 2, ruled by Tee 2026-10-11:
// one card per lesson, and that card is the lesson's approval. A PROMOTE row
// becomes a card only when the feeder's own group log row for its learning
// intent reads FED, PROMOTE, a clear conflict receipt and 2 to 5 distinct
// member jobs, and when every member's own ledger row is in hand to quote.
// The card quotes each member's ledger text itself, uncut, rather than a
// note the feeder packed. Anything else is REFUSED for good with its reasons
// and one email, never skipped, so it cannot sit unread forever. A job named
// by ANY commit-log row, whatever its state, can never back another lesson:
// a rejected or expired card burns its members too.
//
// A card already in the queue is ADOPTED only when this poll reads the lesson
// as sound and the queued text quotes the exact claim that would be committed,
// so an adoption can never skip a lesson check or commit text Tee did not see.
// A queued card for an unsound lesson is refused with its request id, and a
// queued text that does not quote the claim is left alone and this committer
// raises its own card. Fixed 2026-10-11 after the Phase 2 critic.
const Q = String.fromCharCode(34);
const NL = String.fromCharCode(10);
const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const GUTTER = NL + '     | ';
const VERIFY_CARD = /^verify_card (REQ-[0-9]{8}-[A-Za-z0-9]{4,16}) approved by Tee$/;
const MAX_MEMBERS = 5;

function normId(v) { return typeof v === 'string' ? v.trim().toUpperCase() : ''; }
// Every whole ULID a table hands back in a list column, in whatever shape it
// arrives (an array, a JSON string, a comma separated string), case folded.
// The same reading as lessonIdList in n8n/devon/learning/lesson_evidence.js.
function idList(v) {
  let s;
  if (typeof v === 'string') { s = v; }
  else { try { s = JSON.stringify(v === undefined ? null : v); } catch (err) { s = ''; } }
  return String(s || '').toUpperCase().match(/(?<![0-9A-Z])[0-9A-HJKMNP-TV-Z]{26}(?![0-9A-Z])/g) || [];
}
// The member list a group row declares, read strictly: an array, or a JSON
// array string, of ULID strings and nothing else. The lenient idList above
// still decides what a refusal burns, where reading more fails safe.
function strictIds(v) {
  let list = v;
  if (typeof v === 'string') {
    try { list = JSON.parse(v); } catch (err) { return null; }
  }
  if (!Array.isArray(list)) { return null; }
  const out = [];
  for (const x of list) {
    const id = normId(x);
    if (!ULID.test(id)) { return null; }
    out.push(id);
  }
  return out;
}
// An excerpt is quoted whole, and every line after its first is fenced, so a
// summary that carries a newline cannot print a line that reads as the card's.
function fence(text) {
  return String(text).split(/\r\n|\r|\n/).join(GUTTER);
}
function readEnvelope(row) {
  if (!row || typeof row !== 'object') { return null; }
  if (row.envelope && typeof row.envelope === 'object' && !Array.isArray(row.envelope)) { return row.envelope; }
  if (typeof row.envelope !== 'string' || !row.envelope) { return null; }
  try {
    const e = JSON.parse(row.envelope);
    return (e && typeof e === 'object' && !Array.isArray(e)) ? e : null;
  } catch (err) { return null; }
}
// A lesson's Area is the one the feed row carries, from the registry. It is
// never scraped out of the claim, which is Tee's text and may say anything.
function areaFrom(tableArea) {
  return String(tableArea || '').trim();
}

const seen = {};
const usedBy = {};
for (const it of $('Fetch Commit Log').all()) {
  const r = it.json || {};
  if (typeof r.intent_id === 'string' && r.intent_id.length > 0) {
    seen[r.intent_id] = true;
    seen[normId(r.intent_id)] = true;
    const own = normId(r.intent_id);
    if (!usedBy[own]) { usedBy[own] = r.intent_id; }
  }
  for (const m of idList(r.source_intent_ids)) {
    if (!usedBy[m]) { usedBy[m] = String(r.intent_id || 'an unnamed row'); }
  }
}
const requests = [];
for (const it of $('Fetch Open Requests').all()) {
  const r = it.json || {};
  if (!r.request_id) { continue; }
  if (String(r.requested_by || '') !== 'soul-committer') { continue; }
  const ev = String(r.evidence || '');
  if (ev.indexOf('intent ') !== 0) { continue; }
  requests.push({ request_id: String(r.request_id), status: String(r.status || ''), requested_at: String(r.requested_at || ''), expires_at: String(r.expires_at || ''), evidence: ev, what_happens: String(r.what_happens || '') });
}
const groupsById = {};
for (const it of $('Fetch Lesson Groups').all()) {
  const g = it.json || {};
  const id = normId(g.learning_intent_id);
  if (!id) { continue; }
  (groupsById[id] = groupsById[id] || []).push(g);
}
const jobsById = {};
for (const it of $('Fetch Member Jobs').all()) {
  const row = it.json || {};
  const id = normId(row.intent_id);
  if (!id) { continue; }
  (jobsById[id] = jobsById[id] || []).push(row);
}

// The lesson behind one PROMOTE row, read from the feeder's group log and
// the members' own ledger rows. Returns every reason it cannot be carded.
function readLesson(j) {
  const reasons = [];
  const id = normId(j.intent_id);
  const out = { lesson_key: '', members: [], quotes: [], receipt_id: '', conflict_status: '', top_match: '', reasons: reasons };
  const gs = groupsById[id] || [];
  if (gs.length === 0) {
    reasons.push('no group log row recording PROMOTE names learning intent ' + j.intent_id + '; a lesson needs one, and a single job never promotes');
    return out;
  }
  if (gs.length > 1) {
    reasons.push(gs.length + ' group log rows name learning intent ' + j.intent_id);
    return out;
  }
  const g = gs[0];
  out.lesson_key = String(g.lesson_key || '').trim();
  out.receipt_id = String(g.receipt_id || '').trim();
  out.conflict_status = String(g.conflict_status || '').trim();
  out.top_match = String(g.top_match === null || g.top_match === undefined ? '' : g.top_match).trim();
  if (!out.lesson_key) { reasons.push('its group log row names no lesson key'); }
  if (String(g.state || '') !== 'FED') { reasons.push('its group log row is in state ' + String(g.state || 'empty') + ', not FED'); }
  if (String(g.gate_decision || '') !== 'PROMOTE') { reasons.push('its group log row records ' + String(g.gate_decision || 'no decision') + ', not PROMOTE'); }
  if (out.conflict_status !== 'clear') { reasons.push('its conflict receipt reads ' + (out.conflict_status || 'nothing') + ', not clear'); }
  if (!out.receipt_id) { reasons.push('its group log row carries no conflict receipt id'); }
  const feedKey = String(j.lesson_key || '').trim();
  if (feedKey && out.lesson_key && feedKey !== out.lesson_key) { reasons.push('the feed log names lesson ' + feedKey + ' and the group log names ' + out.lesson_key); }
  const members = idList(g.source_intent_ids);
  out.members = members;
  if (strictIds(g.source_intent_ids) === null) { reasons.push('its group lists an entry that is not a job id, or a member list that cannot be read'); }
  if (members.length < 2 || members.length > MAX_MEMBERS) { reasons.push('its group lists ' + members.length + ' member job(s); a lesson needs 2 to ' + MAX_MEMBERS); }
  if (new Set(members).size !== members.length) { reasons.push('its group lists one job more than once'); }
  const feedMembers = idList(j.source_intent_ids);
  if (feedMembers.length && feedMembers.slice().sort().join(',') !== members.slice().sort().join(',')) {
    reasons.push('the feed log and the group log list different member jobs');
  }
  for (const m of members) {
    if (usedBy[m]) { reasons.push('member ' + m + ' already appears in the commit log under ' + usedBy[m] + ', and a job backs one soul proposal at most, ever'); }
    const rows = jobsById[m] || [];
    if (rows.length !== 1) {
      reasons.push(rows.length ? 'member ' + m + ' has ' + rows.length + ' ledger rows' : 'member ' + m + ' has no COMPLETED, passed, human watched ledger row to quote');
      continue;
    }
    const row = rows[0];
    const env = readEnvelope(row);
    const why = [];
    if (String(row.state || '') !== 'COMPLETED') { why.push('state is ' + String(row.state || 'empty')); }
    if (String(row.verification_state || '') !== 'passed') { why.push('verification is ' + String(row.verification_state || 'empty')); }
    if (String(row.verification_method || '') !== 'human_watch') { why.push('not verified by a human watch'); }
    if (!env) { why.push('its envelope is unreadable'); }
    else if (normId(env.intent_id) !== m) { why.push('its envelope names another job'); }
    const v = (env && env.verification && typeof env.verification === 'object') ? env.verification : {};
    const evidence = Array.isArray(v.evidence) ? v.evidence.filter(function (e) { return typeof e === 'string'; }) : [];
    let card = '';
    for (const e of evidence) {
      const hit = VERIFY_CARD.exec(e.trim());
      if (hit) { card = hit[1]; break; }
    }
    if (!card) { why.push('no verify card approved by Tee in its evidence'); }
    const verifiedAt = String(v.verified_at || '');
    if (Number.isNaN(Date.parse(verifiedAt))) { why.push('no readable verified_at'); }
    if (why.length) { reasons.push('member ' + m + ': ' + why.join(', ')); continue; }
    const receipt = (env.receipt && typeof env.receipt === 'object') ? env.receipt : {};
    out.quotes.push({ id: m, card: card, verified_at: verifiedAt, summary: typeof receipt.summary === 'string' ? receipt.summary : '', evidence: evidence });
  }
  // Only a group the gate searched and promoted burns its members here. Any
  // other group's members are held or freed by the group log itself (E6).
  if (String(g.gate_decision || '') !== 'PROMOTE') { out.members = []; }
  return out;
}

function cardText(c) {
  const lines = [];
  lines.push('DEVON writes one lesson to his own memory (devon-soul index, namespace ' + Q + 'experience' + Q + '): ' + Q + c.claim + Q + '.');
  lines.push('Lesson key: ' + c.lesson_key + '. Area: ' + (c.area || 'unstated') + '. Learning intent: ' + c.intent_id + '.');
  lines.push('This never touches tee-soul-layer. Reversible: the record can be deleted from the Pinecone console.');
  lines.push('');
  lines.push('It stands on ' + c.quotes.length + ' completed jobs, each verified by you on its own watch card. Quoted from each job' + String.fromCharCode(39) + 's own ledger row:');
  c.quotes.forEach(function (m, i) {
    lines.push((i + 1) + '. Job ' + m.id + ', verify card ' + m.card + ', verified ' + m.verified_at + '.');
    lines.push('   Receipt: ' + (m.summary ? Q + fence(m.summary) + Q : 'none recorded'));
    lines.push('   Verification evidence: ' + m.evidence.map(function (e) { return Q + fence(e) + Q; }).join('; '));
  });
  lines.push('');
  lines.push('Conflict check: receipt ' + c.receipt_id + ', status ' + c.conflict_status + ', top match ' + (c.top_match || 'none') + '.');
  lines.push('');
  lines.push('Approving writes exactly the quoted lesson above, once, as one record. Rejecting it, or letting this card expire unanswered, closes it for good: these ' + c.quotes.length + ' jobs can never back another lesson, and the lesson key stays open for different jobs.');
  return lines.join(NL);
}

const nowIso = new Date().toISOString();
const adoptions = [];
const refusals = [];
const candidates = [];
const batch = {};
for (const it of $('Fetch Promoted Jobs').all()) {
  const j = it.json || {};
  if (!j.intent_id || seen[j.intent_id] || seen[normId(j.intent_id)] || batch[normId(j.intent_id)]) { continue; }
  batch[normId(j.intent_id)] = true;
  const claim = String(j.claim || '').trim();
  const area = areaFrom(j.area);
  const lesson = readLesson(j);
  if (!claim) { lesson.reasons.unshift('the feed log row carries no claim'); }
  const memberList = JSON.stringify(lesson.members);
  const marker = 'intent ' + j.intent_id + ';';
  const quoted = Q + claim + Q;
  let match = null;
  let queued = null;
  for (const q of requests) {
    if (q.evidence.indexOf(marker) !== 0) { continue; }
    if (!queued) { queued = q; }
    if (lesson.reasons.length || q.what_happens.indexOf(quoted) === -1) { continue; }
    if (!match) { match = q; continue; }
    if (q.status === 'approved' && match.status !== 'approved') { match = q; continue; }
    if (q.status === match.status && q.requested_at > match.requested_at) { match = q; }
  }
  if (match) {
    adoptions.push({ json: { mode: 'adopt', intent_id: j.intent_id, claim: claim, area: area, lesson_key: lesson.lesson_key, source_intent_ids: memberList, request_id: match.request_id, expires_at: match.expires_at, adopted_status: match.status, proposed_at: nowIso } });
    continue;
  }
  if (lesson.reasons.length) {
    if (queued) { lesson.reasons.push('a queued card ' + queued.request_id + ' names this intent and was not adopted, so approving it commits nothing'); }
    refusals.push({ json: { mode: 'refuse', intent_id: j.intent_id, claim: claim, area: area, lesson_key: lesson.lesson_key, source_intent_ids: memberList, reasons: lesson.reasons, request_id: queued ? queued.request_id : '', proposed_at: nowIso } });
  } else {
    candidates.push({ intent_id: j.intent_id, claim: claim, area: area, lesson: lesson, members: memberList });
  }
}
if (adoptions.length > 0) { return adoptions; }
if (candidates.length === 0) { return refusals; }
const c = candidates[0];
const what = cardText({ claim: c.claim, area: c.area, intent_id: c.intent_id, lesson_key: c.lesson.lesson_key, quotes: c.lesson.quotes, receipt_id: c.lesson.receipt_id, conflict_status: c.lesson.conflict_status, top_match: c.lesson.top_match });
return refusals.concat([{ json: {
  mode: 'post',
  intent_id: c.intent_id,
  claim: c.claim,
  area: c.area,
  lesson_key: c.lesson.lesson_key,
  source_intent_ids: c.members,
  deferred: candidates.length - 1,
  approval_body: {
    title: 'Soul commit: ' + c.claim.slice(0, 90),
    what_happens: what,
    action_type: 'identity_voice_rights',
    project: 'DEVON Build 12',
    requested_by: 'soul-committer',
    blast_radius: 'one record in devon-soul, namespace experience',
    reversible: 'yes, the record can be deleted from the Pinecone console',
    evidence: 'intent ' + c.intent_id + '; lesson ' + c.lesson.lesson_key + '; gate decision PROMOTE recorded in devon_build12_feed_log and devon_lesson_group_log'
  }
} }]);
