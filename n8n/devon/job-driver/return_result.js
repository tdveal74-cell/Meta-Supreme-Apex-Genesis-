// What the caller receives. The approval_queue decision TOKEN never leaves this
// workflow and is never read; the card request ids do travel, because the poll's
// digest and the ledger both name them.
const f = $('Finish').first().json || {};
return [{ json: { intent_id: f.intent_id, entry_state: f.entry_state, exit_state: f.exit_state, outcome: f.outcome, steps: f.steps, approval_card: f.approval_card, verify_card: f.verify_card, bad_pass: f.bad_pass === true, repeat_refusal: f.repeat_refusal === true, last_pass_at: f.last_pass_at || '', log: f.log, envelope: f.envelope } }];
