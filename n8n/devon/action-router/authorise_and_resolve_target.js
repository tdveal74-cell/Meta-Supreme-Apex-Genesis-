// DEVON Action Router, Build 05, n8n lane.
// Contract: SYS_DATA_job-envelope-schema_v1_2026-08-23.json, Drive 1mH0T1B5MK-qFT1W71ZoezPcrfgg7GPoj
// The Zapier lane is NOT built. It needs a Zap with a webhook trigger and a code step,
// which is Tee's hands in the Zapier UI. Build 05 is half shipped and says so.
//
// REPAIRED 2026-09-05. Every gate refusal used to be a thrown error, which n8n turned
// into an empty 200 body and an ERROR execution. The caller (the Job Driver) read
// "http 200 null" and could not tell a refusal from a crash. A refusal is now a
// designed answer: this node emits { refused: true, reason } as data, the Accepted?
// node routes accepted envelopes on and everything else to Return Refusal, and the
// caller parks the job with the reason. Genuine faults still throw; the shared
// Error Alarm (XDQXwgFkUhYxoEjG) is this workflow's error workflow as of the same
// day, so a fault emails Tee.

const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;

// ALLOWLIST. A router that dispatches to any name it is handed is an arbitrary
// execution hole wearing a routing table. Adding an entry is a deliberate act.
// Key is the action name an envelope may request; value is what actually runs.
//
// RULED 2026-08-24, approval_mode contested. editforge.render was added to this table
// earlier the same day and is now REMOVED. Reason, found by reading both organs side by
// side rather than by running them: this router dispatches the envelope in AUTHORIZED,
// and Build 07 accepts EXECUTING only, so every dispatch would have been refused.
// spine.echo works because Build 01 accepts AUTHORIZED and advances it to EXECUTING.
//
// The fix is not to widen Build 07. Build 07 is a SECOND-STAGE organ: it acts on a job
// that is already executing, and it is called directly by whoever holds the EXECUTING
// envelope, not through this router. This router owns the AUTHORIZED handoff only.
//
// A wired but unusable allowlist entry is the same class of defect as a green flag over
// a refused ledger. It reads as a capability that does not exist. Do not re-add it
// without first changing which state Build 07 accepts, which would cost Ruling B.
//
// RULED 2026-09-05 by Tee ("do it", then "create it"): drive.draft is the first real
// executor. Build 16 accepts AUTHORIZED, writes one Google Doc draft in the folder the
// vault permits for the Area, and advances the envelope to EXECUTING with the artifact.
// Quarantined off this list the same evening by the fourth critic cycle (the approval
// card did not name the executor; the executor's grant check had a hole) and restored
// once the Drive Draft Writer (version 7ff4d7d4) and the Job Driver carried the fixes,
// proven by pinned runs 5916 to 5926. The card now names the executor and the driver
// dispatches only the action bound to the grant.
const TARGETS = {
  'spine.echo': {
    url: 'https://thequietoperator.app.n8n.cloud/webhook/devon-spine-n8n',
    workflow_id: 'Oi7o1sTEqhxhOaJL',
    max_blast_radius: 'read',
    description: 'Spine conformance executor. Advances one legal state and returns.'
  },
  'drive.draft': {
    url: 'https://thequietoperator.app.n8n.cloud/webhook/devon-drive-draft',
    workflow_id: 'J7Ly7riwXEd95D9a',
    max_blast_radius: 'reversible_write',
    description: 'Drive Draft Writer, Build 16. Writes one Google Doc draft and advances AUTHORIZED to EXECUTING.'
  }
};

// Ordered weakest to strongest, so a target ceiling can be compared numerically.
const BR = ['none', 'read', 'reversible_write', 'irreversible_write', 'destructive'];

function pick(j) {
  if (j && j.body && typeof j.body === 'object') { return j.body.envelope || j.body; }
  return j;
}

// A refusal is data, not a crash. It carries enough for the caller to park the job
// and for a human to read why without opening this execution. Return Refusal echoes
// this item as the response body, so this is the one definition of the shape.
function refusal(e, requested, reason) {
  return { json: {
    refused: true,
    outcome: 'refused',
    reason: reason,
    intent_id: (e && typeof e === 'object' && e.intent_id) ? String(e.intent_id) : null,
    state: (e && typeof e === 'object' && e.state) ? String(e.state) : null,
    action: requested || null,
    known_actions: Object.keys(TARGETS)
  } };
}

const out = [];
for (const it of $input.all()) {
  const b = (it.json && it.json.body) ? it.json.body : it.json;
  const e = pick(it.json);
  const requested = (b && b.action) ? String(b.action)
    : ((e && e.intent && e.intent.payload && e.intent.payload.action) ? String(e.intent.payload.action) : null);

  // A bodyless or envelope-less POST reads as an object either way, so the test is
  // whether anything envelope-shaped is present at all.
  if (!e || typeof e !== 'object' || (!e.schema_version && !e.intent_id)) {
    out.push(refusal(null, requested, 'REFUSED: no envelope in the request body.')); continue;
  }
  if (e.schema_version !== '1.0.0') {
    out.push(refusal(e, requested, 'REFUSED: schema_version ' + String(e.schema_version) + ' is not implemented by this router.')); continue;
  }
  if (!ULID.test(String(e.intent_id || ''))) {
    out.push(refusal(e, requested, 'REFUSED: intent_id ' + String(e.intent_id) + ' is not a ULID.')); continue;
  }

  // The approval gate, enforced rather than trusted. AUTHORIZED is the only state
  // from which work may start, and the schema already forbids AUTHORIZED without a
  // grant. Checking both means a forged state alone is not enough to run anything.
  if (e.state !== 'AUTHORIZED') {
    out.push(refusal(e, requested, 'REFUSED: actions dispatch from AUTHORIZED only. This envelope is ' +
      String(e.state) + '. Executing an unauthorised job is the whole thing the approval queue exists to stop.')); continue;
  }
  const appr = (e.approval && e.approval.state) ? e.approval.state : '';
  if (appr !== 'granted' && appr !== 'not_required') {
    out.push(refusal(e, requested, 'REFUSED: state says AUTHORIZED but approval.state is ' + String(appr) +
      '. State and grant disagree, so nothing runs.')); continue;
  }
  // Authorisation decays. A grant with no readable expiry cannot be trusted either way.
  if (appr === 'granted') {
    const expRaw = e.approval.expires_at;
    if (!expRaw) {
      out.push(refusal(e, requested, 'REFUSED: approval.state is granted but approval.expires_at is absent. A grant without a decay time is not a grant.')); continue;
    }
    const expMs = Date.parse(String(expRaw));
    if (Number.isNaN(expMs)) {
      out.push(refusal(e, requested, 'REFUSED: approval.expires_at ' + String(expRaw) + ' is not a readable time, so the grant cannot be trusted.')); continue;
    }
    if (expMs < Date.now()) {
      out.push(refusal(e, requested, 'REFUSED: the approval expired at ' + String(expRaw) + '. An expired grant is not a grant.')); continue;
    }
  }

  if (!requested) {
    out.push(refusal(e, requested, 'REFUSED: no action named. POST { envelope, action } or set intent.payload.action.')); continue;
  }
  const target = TARGETS[requested];
  if (!target) {
    out.push(refusal(e, requested, 'REFUSED: action ' + requested + ' is not on the allowlist. Known actions: ' +
      Object.keys(TARGETS).join(', ') + '. Adding one is a deliberate act, not a runtime decision.')); continue;
  }

  // A target that can write needs a decided grant. not_required is what a job carries
  // when no card was raised, and no card means no human consented to a write.
  if (BR.indexOf(target.max_blast_radius) >= BR.indexOf('reversible_write') && appr !== 'granted') {
    out.push(refusal(e, requested, 'REFUSED: action ' + requested + ' can write (ceiling ' + target.max_blast_radius +
      ') and approval.state is ' + String(appr) + '. A write needs a card and a decision, not an absence of one.')); continue;
  }

  // A target carries a ceiling. A read-only executor must never be handed a
  // destructive job just because the job was authorised for something else.
  const jobBr = (e.intent && e.intent.blast_radius) ? e.intent.blast_radius : 'none';
  if (BR.indexOf(jobBr) === -1) {
    out.push(refusal(e, requested, 'REFUSED: blast radius ' + String(jobBr) + ' is not in the vocabulary (' + BR.join(', ') + '). An unknown radius is not a small one.')); continue;
  }
  if (BR.indexOf(jobBr) > BR.indexOf(target.max_blast_radius)) {
    const ceilings = Object.keys(TARGETS).map(function (k) { return k + ' ' + TARGETS[k].max_blast_radius; }).join(', ');
    out.push(refusal(e, requested, 'REFUSED: job blast radius ' + jobBr + ' exceeds the ceiling ' +
      target.max_blast_radius + ' for action ' + requested + '. An executor exceeding its scope must fail, not widen. ' +
      'Ceilings of the known actions: ' + ceilings + '.')); continue;
  }

  // Writes are only safe to retry when the job carries an idempotency key.
  if (BR.indexOf(jobBr) >= BR.indexOf('reversible_write') && !e.idempotency_key) {
    out.push(refusal(e, requested, 'REFUSED: ' + jobBr + ' requires an idempotency_key before any executor may write.')); continue;
  }

  out.push({ json: { refused: false, envelope: e, action: requested, target_url: target.url,
    target_workflow: target.workflow_id, intent_id: e.intent_id, blast_radius: jobBr } });
}
return out;
