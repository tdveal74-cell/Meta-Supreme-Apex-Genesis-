// One proposal per intent, ever. Any commit-log row for the intent, whatever
// its state, means it was already put to Tee. Before raising a NEW request,
// reconcile against the queue itself: if a soul-committer request for this
// intent already exists (a lost response on an earlier poll), ADOPT its
// request_id instead of raising a duplicate card. At most ONE new POST per
// poll, so HTTP pairing stays 1:1 and a run can never outlast the schedule.
const seen = {};
for (const it of $('Fetch Commit Log').all()) {
  const r = it.json || {};
  if (typeof r.intent_id === 'string' && r.intent_id.length > 0) { seen[r.intent_id] = true; }
}
const requests = [];
for (const it of $input.all()) {
  const r = it.json || {};
  if (!r.request_id) { continue; }
  if (String(r.requested_by || '') !== 'soul-committer') { continue; }
  const ev = String(r.evidence || '');
  if (ev.indexOf('intent ') !== 0) { continue; }
  requests.push({ request_id: String(r.request_id), status: String(r.status || ''), requested_at: String(r.requested_at || ''), expires_at: String(r.expires_at || ''), evidence: ev });
}
function areaFrom(claim, tableArea) {
  const direct = String(tableArea || '').trim();
  if (direct) { return direct; }
  const k = claim.lastIndexOf('. Area: ');
  if (k === -1) { return ''; }
  let seg = claim.slice(k + 8);
  const stops = ['. Executor: ', '. Outcome: '];
  for (const stop of stops) {
    const s = seg.indexOf(stop);
    if (s !== -1) { seg = seg.slice(0, s); }
  }
  seg = seg.trim();
  if (seg.charAt(seg.length - 1) === '.') { seg = seg.slice(0, -1); }
  return seg.trim();
}
const nowIso = new Date().toISOString();
const adoptions = [];
const candidates = [];
const batch = {};
for (const it of $('Fetch Promoted Jobs').all()) {
  const j = it.json || {};
  if (!j.intent_id || seen[j.intent_id] || batch[j.intent_id]) { continue; }
  const claim = String(j.claim || '').trim();
  if (!claim) { continue; }
  batch[j.intent_id] = true;
  const area = areaFrom(claim, j.area);
  const marker = 'intent ' + j.intent_id + ';';
  let match = null;
  for (const q of requests) {
    if (q.evidence.indexOf(marker) !== 0) { continue; }
    if (!match) { match = q; continue; }
    if (q.status === 'approved' && match.status !== 'approved') { match = q; continue; }
    if (q.status === match.status && q.requested_at > match.requested_at) { match = q; }
  }
  if (match) {
    adoptions.push({ json: { mode: 'adopt', intent_id: j.intent_id, claim: claim, area: area, request_id: match.request_id, expires_at: match.expires_at, adopted_status: match.status, proposed_at: nowIso } });
  } else {
    candidates.push({ intent_id: j.intent_id, claim: claim, area: area });
  }
}
if (adoptions.length > 0) { return adoptions; }
if (candidates.length === 0) { return []; }
const c = candidates[0];
const Q = String.fromCharCode(34);
const what = 'DEVON writes one lesson to his own memory (devon-soul index, namespace ' + Q + 'experience' + Q + '): ' + Q + c.claim + Q + '. Area: ' + (c.area || 'unstated') + '. This never touches tee-soul-layer. Reversible: the record can be deleted from the Pinecone console. Source: Build 12 learning gate PROMOTE for job ' + c.intent_id + ', which requires a complete clear conflict receipt and at least two independent sources.';
return [{ json: {
  mode: 'post',
  intent_id: c.intent_id,
  claim: c.claim,
  area: c.area,
  deferred: candidates.length - 1,
  approval_body: {
    title: 'Soul commit: ' + c.claim.slice(0, 90),
    what_happens: what,
    action_type: 'identity_voice_rights',
    project: 'DEVON Build 12',
    requested_by: 'soul-committer',
    blast_radius: 'one record in devon-soul, namespace experience',
    reversible: 'yes, the record can be deleted from the Pinecone console',
    evidence: 'intent ' + c.intent_id + '; gate decision PROMOTE recorded in devon_build12_feed_log'
  }
} }];