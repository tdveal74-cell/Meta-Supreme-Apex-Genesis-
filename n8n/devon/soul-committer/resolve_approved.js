// Reads ONLY status and timing fields from approval rows; the token column is
// never referenced, and this workflow persists no execution data, so tokens
// never land in stored executions either. Do not turn execution saving on.
//
// ONE commit per poll (oldest first): pairing stays 1:1 and a backlog commits
// at one record per hour, which is plenty for individually approved lessons.
// The record id embeds the FULL request id, case intact, so two approvals can
// never fold to one record and retries upsert the SAME record.
//
// LESSONS ONLY, from the grouping build's Phase 2, ruled by Tee 2026-10-11.
// The record names its lesson key, its learning intent and the 2 to 5 jobs it
// stands on, read from the commit-log row the card was raised with, and says
// status active so recall shows it. A row without a lesson key and 2 to 5
// distinct member ids is NOT committed and nothing is written: it stays
// PROPOSED, the approval stands, and the Pulse names it as soul_overdue once
// it is open past 76 hours (EXPIRY_H 72 plus RESOLVE_GRACE_H 4 in
// compose_pulse.js); that finding does not say why, so read the row's
// lesson_key and source_intent_ids. That is the direction that fails closed if
// the commit log ever loses those columns; once they are back the next poll
// commits it.
function idList(v) {
  let s;
  if (typeof v === 'string') { s = v; }
  else { try { s = JSON.stringify(v === undefined ? null : v); } catch (err) { s = ''; } }
  return String(s || '').toUpperCase().match(/(?<![0-9A-Z])[0-9A-HJKMNP-TV-Z]{26}(?![0-9A-Z])/g) || [];
}
const decisions = {};
for (const it of $input.all()) {
  const r = it.json || {};
  if (r.request_id) { decisions[String(r.request_id)] = { status: String(r.status || ''), decided_at: String(r.decided_at || '') }; }
}
const nowIso = new Date().toISOString();
const approved = [];
for (const it of $('Fetch Pending Commits').all()) {
  const p = it.json || {};
  if (!p.request_id) { continue; }
  const claim = String(p.claim || '').trim();
  if (!claim) { continue; }
  const d = decisions[String(p.request_id)];
  if (!d || d.status !== 'approved') { continue; }
  const key = String(p.lesson_key || '').trim();
  const members = idList(p.source_intent_ids);
  if (!key || members.length < 2 || members.length > 5 || new Set(members).size !== members.length) { continue; }
  approved.push({ p: p, d: d, claim: claim, key: key, members: members });
}
if (approved.length === 0) { return []; }
approved.sort(function (a, b) { return String(a.p.proposed_at || '') < String(b.p.proposed_at || '') ? -1 : 1; });
const chosen = approved[0];
const p = chosen.p;
const dateStr = String(p.proposed_at || nowIso).slice(0, 10);
const recordId = 'devon-' + dateStr + '-' + String(p.request_id);
let attempt = 1;
const noteStr = String(p.note || '');
const ai = noteStr.indexOf('attempt ');
if (ai !== -1) {
  const n = parseInt(noteStr.slice(ai + 8), 10);
  if (!isNaN(n) && n > 0) { attempt = n + 1; }
}
return [{ json: {
  intent_id: p.intent_id,
  request_id: p.request_id,
  record_id: recordId,
  claim: chosen.claim,
  area: String(p.area || ''),
  decided_at: chosen.d.decided_at,
  attempt: attempt,
  deferred: approved.length - 1,
  lesson_key: chosen.key,
  source_intent_ids: chosen.members,
  // The same keys, in the same order, as SoulWriteCandidate.to_record in
  // services/intelligence/soul.py for a lesson; committer.test.mjs holds them equal.
  ndjson: JSON.stringify({ _id: recordId, text: chosen.claim, kind: 'lesson', area: String(p.area || ''), observed_on: dateStr, source_note: 'Build 12 lesson ' + chosen.key + ' PROMOTE; learning intent ' + p.intent_id + '; sources ' + chosen.members.join(', ') + '; approval ' + p.request_id, author: 'devon', approved: true, status: 'active', lesson_key: chosen.key, learning_intent_id: String(p.intent_id), source_intent_ids: chosen.members })
} }];