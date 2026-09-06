// The only stage that touches approval_queue. It reads the card rows for THIS job
// by their evidence marker so a card whose POST response was lost is adopted
// rather than raised twice. Execution data saving is OFF on this workflow because
// the rows carry plaintext decision tokens; nothing here copies the token column.
const it = $input.first().json || {};
const env = it.envelope;
const base = Object.assign({}, it, { call: false, marker: '', card_kind: '' });
if (it.stop === true || !env) { return [{ json: base }]; }
const s = String(env.state || '');
if (s === 'WAITING_APPROVAL' || s === 'ESCALATED') {
  base.call = true; base.card_kind = 'approval'; base.marker = 'intent ' + env.intent_id + '; card approval';
} else if (s === 'VERIFYING') {
  base.call = true; base.card_kind = 'verify'; base.marker = 'intent ' + env.intent_id + '; card verify';
}
return [{ json: base }];
