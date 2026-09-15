// The caller (the Action Router) receives the envelope as the ledger now holds
// it, including the ACTION_COMPLETED entry the bus appended. Ledger persistence is
// carried for both reports: null means the bus never answered, false means the
// ledger refused. Never collapse them. Response shape stays an array of one
// envelope, which is what the router's Report Dispatch parses.
function busResult(raw, intentId) {
  const empty = { envelope: null, persisted: null, outcome: null, said: null, retryable: null };
  try {
    const txt = (typeof raw === 'string') ? raw : (raw && typeof raw.data === 'string') ? raw.data : '';
    if (!txt) { return empty; }
    const parsed = JSON.parse(txt);
    const arr = Array.isArray(parsed) ? parsed : [parsed];
    const r = arr[0];
    if (!r) { return empty; }
    const e = r.envelope ? r.envelope : null;
    return {
      envelope: (e && e.intent_id === intentId) ? e : null,
      persisted: (typeof r.persisted === 'boolean') ? r.persisted : null,
      outcome: r.outcome ? String(r.outcome) : null,
      said: r.ledger_said ? String(r.ledger_said) : null,
      retryable: (typeof r.retryable === 'boolean') ? r.retryable : null
    };
  } catch (err) { return empty; }
}
const a = $('Advance Envelope').first().json;
const b = busResult($input.first().json, a.intent_id);
const ledgerClean = (a.entry_ledger_persisted === true && b.persisted === true);
return [{ json: Object.assign({}, a, {
  envelope: b.envelope || a.envelope,
  exit_bus_reconciled: b.envelope !== null,
  exit_ledger_persisted: b.persisted,
  exit_ledger_outcome: b.outcome,
  exit_ledger_said: b.said,
  exit_ledger_retryable: b.retryable,
  ledger_clean: ledgerClean
}) }];
