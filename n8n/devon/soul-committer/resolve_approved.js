// Reads ONLY status and timing fields from approval rows; the token column is
// never referenced, and this workflow persists no execution data, so tokens
// never land in stored executions either. Do not turn execution saving on.
//
// ONE commit per poll (oldest first): pairing stays 1:1 and a backlog commits
// at 4 records per hour, which is plenty for individually approved lessons.
// The record id embeds the FULL request id, case intact, so two approvals can
// never fold to one record and retries upsert the SAME record.
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
  approved.push({ p: p, d: d, claim: claim });
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
  ndjson: JSON.stringify({ _id: recordId, text: chosen.claim, kind: 'lesson', area: String(p.area || ''), observed_on: dateStr, source_note: 'Build 12 learning gate PROMOTE; source intent ' + p.intent_id + '; approval ' + p.request_id, author: 'devon', approved: true })
} }];