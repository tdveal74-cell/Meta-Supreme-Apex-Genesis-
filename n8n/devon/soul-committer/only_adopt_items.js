// Adopted requests are log-only: the card already exists in the queue (raised
// on an earlier poll whose response was lost), so no new POST and no new email.
// Whatever its status, adopting honors what Tee decided or will decide on the
// EXISTING card; the resolve lane takes it from here.
const out = [];
for (const it of $input.all()) {
  const j = it.json || {};
  if (j.mode !== 'adopt') { continue; }
  let note = 'adopted existing approval request (reconciled after a lost response); awaiting decision, expires ' + (j.expires_at || 'unknown');
  if (j.adopted_status && j.adopted_status !== 'pending') { note = note + '; queue status at adoption: ' + j.adopted_status; }
  out.push({ json: { intent_id: j.intent_id, state: 'PROPOSED', request_id: j.request_id, record_id: '', claim: j.claim, area: j.area, proposed_at: j.proposed_at, resolved_at: '', note: note, lesson_key: String(j.lesson_key || ''), source_intent_ids: String(j.source_intent_ids || '[]') } });
}
return out;