// Already-fed intent ids. Fetch Feed Log runs with alwaysOutputData, so an
// empty log arrives as one synthetic item without intent_id; skip those.
const fed = {};
for (const it of $input.all()) {
  const r = it.json || {};
  if (typeof r.intent_id === 'string' && r.intent_id.length > 0) { fed[r.intent_id] = true; }
}

const out = [];
for (const it of $('Fetch Completed Jobs').all()) {
  const j = it.json || {};
  if (!j.intent_id || fed[j.intent_id]) { continue; }
  const summary = String(j.intent_summary || '').trim() || 'unnamed job';
  const area = String(j.area || '').trim();
  const executor = String(j.executor || '').trim();
  const outcome = String(j.receipt_outcome || '').trim();
  const verified = String(j.verification_state || '').toUpperCase() === 'VERIFIED';
  let claim = 'Completed job experience: ' + summary;
  if (area) { claim += '. Area: ' + area; }
  if (executor) { claim += '. Executor: ' + executor; }
  if (outcome) { claim += '. Outcome: ' + outcome; }
  claim += '.';
  out.push({ json: {
    intent_id: j.intent_id,
    claim: claim,
    payload: {
      claim: claim,
      source_intent_ids: [j.intent_id],
      proposed_scope: area || 'experience',
      confidence: verified ? 0.8 : 0.6,
      source: 'ledger-feeder',
      ledger: {
        intent_id: j.intent_id,
        event_id: j.event_id || '',
        state: j.state || '',
        completed_at: j.updated_at || '',
        human_watched: j.human_watched === true
      }
    }
  } });
}
return out;