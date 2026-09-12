// DEVON Job Driver, Build 14. Normalises what the caller passed.
// The Intake Former passes { envelope, origin: 'intake' }; the Driver Poll passes
// { envelope, origin: 'poll' } with the envelope parsed from the ledger row.
const it = $input.first().json || {};
let env = null;
if (it.envelope && typeof it.envelope === 'object') { env = it.envelope; }
else if (typeof it.envelope === 'string') { try { env = JSON.parse(it.envelope); } catch (e) { env = null; } }
else if (it.schema_version === '1.0.0') { env = it; }
const origin = String(it.origin || 'unknown');
const passAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
if (!env || !env.intent_id || env.schema_version !== '1.0.0') {
  return [{ json: { envelope: null, memory: {}, log: ['REFUSED: no v1 envelope in the call'], stop: true, reason: 'no_envelope', origin: origin, entry_state: '', pass_at: passAt } }];
}
return [{ json: { envelope: env, memory: {}, log: [], stop: false, reason: '', origin: origin, entry_state: String(env.state || ''), pass_at: passAt } }];
