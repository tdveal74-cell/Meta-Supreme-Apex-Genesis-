// A lesson the committer will not put to Tee is closed for good, never
// skipped: a skip would re-read the same row every hour and tell nobody.
// The row is written REFUSED with every reason, so `seen` keeps it from ever
// being carded, and with its member ids, so those jobs count as used by the
// feeder's E6 rule exactly as a rejected card's do. No card is raised and
// nothing reaches devon-soul. To put a refused lesson to Tee after a fix,
// delete its commit-log row by hand on his ruling; the next poll reads it
// fresh. Grouping build Phase 2, ruled by Tee 2026-10-11.
const out = [];
for (const it of $input.all()) {
  const j = it.json || {};
  if (j.mode !== 'refuse') { continue; }
  const reasons = Array.isArray(j.reasons) ? j.reasons : [];
  out.push({ json: { intent_id: j.intent_id, state: 'REFUSED', request_id: '', record_id: '', claim: j.claim || '', area: j.area || '', proposed_at: j.proposed_at, resolved_at: j.proposed_at, note: 'refused before a card, so no card was raised: ' + reasons.join('; '), lesson_key: String(j.lesson_key || ''), source_intent_ids: String(j.source_intent_ids || '[]') } });
}
return out;
