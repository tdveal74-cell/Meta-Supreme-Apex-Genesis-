// RULED 2026-08-23. The bus-returned envelope is authoritative after every report.
// The dispatch receipt must carry the envelope as the ledger now holds it, including
// the trace entry the bus appended for ACTION_COMPLETED or ACTION_FAILED.
//
// RULED 2026-08-24, approval_mode delegated. The receipt now carries ledger persistence for
// BOTH reports. Entry fields are re-read from Reconcile Entry Envelope rather than relayed
// through Report Dispatch, so that node stays a pure recorder and cannot drop them.
// null means the bus never answered. false means the ledger refused. Never collapse them.
//
// 2026-09-05: the receipt also carries refused, reason and marked, so the caller can tell
// an executor refusal from a crash and knows whether the reason already reached the ledger.
// marked is the whole contract between this organ and the Job Driver: true means this
// router's exit report persisted the reason into the ledger row, so the driver stops;
// false or absent means nothing durable carries it, so the driver posts its own mark.
// Exactly one of the two writes it, and neither writes it twice for the same pass.

function busResult(raw, intentId) {
  const empty = { envelope: null, persisted: null, outcome: null, said: null, retryable: null };
  try {
    const txt = (typeof raw === 'string') ? raw
      : (raw && typeof raw.data === 'string') ? raw.data : '';
    if (!txt) { return empty; }
    const parsed = JSON.parse(txt);
    const arr = Array.isArray(parsed) ? parsed : [parsed];
    const r = arr[0];
    if (!r) { return empty; }
    const env = r.envelope ? r.envelope : null;
    return {
      envelope: (env && env.intent_id === intentId) ? env : null,
      persisted: (typeof r.persisted === 'boolean') ? r.persisted : null,
      outcome: r.outcome ? String(r.outcome) : null,
      said: r.ledger_said ? String(r.ledger_said) : null,
      retryable: (typeof r.retryable === 'boolean') ? r.retryable : null
    };
  } catch (err) { return empty; }
}

const d = $('Report Dispatch').first().json;
const entry = $('Reconcile Entry Envelope').first().json;
const b = busResult($input.first().json, d.intent_id);

// ledger_clean is the one-glance answer to "is this actually in the ledger".
// True only when BOTH reports persisted. Anything else, including unknown, is false.
const ledgerClean = (entry.entry_ledger_persisted === true && b.persisted === true);

return [{ json: Object.assign({}, d, {
  envelope: b.envelope || d.envelope,
  exit_bus_reconciled: b.envelope !== null,
  entry_ledger_persisted: entry.entry_ledger_persisted,
  entry_ledger_outcome: entry.entry_ledger_outcome,
  exit_ledger_persisted: b.persisted,
  exit_ledger_outcome: b.outcome,
  exit_ledger_said: b.said,
  exit_ledger_retryable: b.retryable,
  ledger_clean: ledgerClean,
  refused: d.refused === true,
  reason: d.refused === true ? d.refusal_reason : null,
  marked: d.refused === true && b.persisted === true
}) }];
