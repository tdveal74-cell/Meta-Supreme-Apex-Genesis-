// DEVON Organism Spine v1, n8n adapter. Validation half.
// Contract: SYS_DATA_job-envelope-schema_v1_2026-08-23.json, Drive 1mH0T1B5MK-qFT1W71ZoezPcrfgg7GPoj
// SPLIT OUT of Advance Envelope 2026-08-23. The entry report to the event bus has to
// sit between refusing and advancing: report before validation and a refused job still
// leaves an INTENT_RECEIVED in the ledger, which is a lie; report after advancing and
// the ledger never sees the job arrive, which is the exact defect execution 3178 found.

const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;

// The authoritative table lives in the conformance harness. This node carries only
// the transitions it is allowed to make, so it cannot silently drift into claiming
// authority over the rest of the machine.
const ALLOWED = {
  RECEIVED: ['UNDERSTANDING', 'BLOCKED', 'FAILED'],
  AUTHORIZED: ['EXECUTING'],
  EXECUTING: ['VERIFYING', 'FAILED', 'RETRYING']
};

function pickEnvelope(j) {
  if (j && j.body && typeof j.body === 'object') { return j.body.envelope || j.body; }
  return j;
}

const out = [];
for (const it of $input.all()) {
  const env = pickEnvelope(it.json);

  if (!env || typeof env !== 'object') {
    throw new Error('REFUSED: no envelope in the request body.');
  }
  if (env.schema_version !== '1.0.0') {
    throw new Error('REFUSED: schema_version ' + String(env.schema_version) + ' is not implemented by this adapter. Expected 1.0.0.');
  }
  if (!ULID.test(String(env.intent_id || ''))) {
    throw new Error('REFUSED: intent_id ' + String(env.intent_id) + ' is not a ULID. 26 chars, Crockford base32, no I L O U.');
  }

  const from = env.state;
  const legal = ALLOWED[from];
  if (!legal) {
    throw new Error('REFUSED: this adapter does not accept envelopes in state ' + String(from) + '.');
  }

  // 2026-09-05. An execution the executor marked failed is not advanced to VERIFYING
  // by this echo; FAILED or RETRYING is the caller's call, and this adapter only walks
  // the happy transition.
  if (from === 'EXECUTING' && env.execution && typeof env.execution === 'object' && env.execution.state === 'failed') {
    throw new Error('REFUSED: execution.state is failed for ' + String(env.intent_id) + '; EXECUTING to VERIFYING is not an advance this adapter makes for a failed execution.');
  }

  // The one advance this lane makes. Deterministic, not a guess.
  const to = from === 'RECEIVED' ? 'UNDERSTANDING'
           : from === 'AUTHORIZED' ? 'EXECUTING'
           : 'VERIFYING';
  if (legal.indexOf(to) === -1) {
    throw new Error('REFUSED: ' + from + ' to ' + to + ' is not a legal transition.');
  }

  out.push({ json: { envelope: env, intent_id: env.intent_id, from_state: from, to_state: to } });
}
return out;
