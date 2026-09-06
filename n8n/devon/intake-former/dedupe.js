// Same idempotency_key, same job. A poster that retries (an iOS Shortcut after
// a timeout, Tee saying file it twice) gets the job that already exists, not a
// second one. Keys the intake mints itself never repeat, so only a supplied
// key dedupes; the ledger row is the authority.
const form = $('Form Job').first().json || {};
const out = Object.assign({}, form, { duplicate: false, existing: null });
if (form.refused || !form.draft) { return [{ json: out }]; }
const key = String(form.draft.idempotency_key || '');
const items = $input.all().map(i => i.json || {});
if (items.some(r => r && r.error && !r.intent_id)) {
  // The ledger could not be read, so the key cannot be checked. Filing anyway
  // would be the duplicate the check exists to prevent. Refuse, name it.
  out.refused = true;
  out.reason = 'The ledger could not be read to check idempotency_key ' + key + '. Nothing was filed; post again in a minute.';
  return [{ json: out }];
}
const rows = items.filter(r => r && r.intent_id && String(r.idempotency_key || '') === key);
if (rows.length) {
  const r = rows[0];
  out.duplicate = true;
  out.existing = { intent_id: String(r.intent_id), state: String(r.state || ''), terminal: r.terminal === true, updated_at: String(r.updated_at || '') };
}
return [{ json: out }];
