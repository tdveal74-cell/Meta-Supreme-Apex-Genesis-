// DEVON Job Driver, Build 14. One slot of the state machine. Reads the envelope
// as it stands and chooses the ONE organ call that legally advances it, or stops.
// This node writes nothing. Every state change travels through an organ or the
// Event Bus, and the Build 02 ledger's guard table stays the authority on legality.
const HOST = 'https://thequietoperator.app.n8n.cloud/webhook/';
const GRANT_HOURS = 24;
const ABSENT_GRACE_H = 96;
const MAX_STEPS = 8;
const it = $input.first().json || {};
const env = it.envelope;
const mem = Object.assign({}, it.memory || {});
const log = Array.isArray(it.log) ? it.log.slice() : [];
const nowMs = Date.now();
const now = new Date(nowMs).toISOString().replace(/\.\d{3}Z$/, 'Z');
function plan(o) {
  return [{ json: Object.assign({}, it, { memory: mem, log: log, call: false, kind: '', url: '', body: null, event_type: '', after: '', card_kind: '', stop_reason: '', reason: it.reason || '' }, o) }];
}
if (it.stop === true || !env || typeof env !== 'object') { return plan({ stop: true }); }
if ((typeof it.steps === 'number' ? it.steps : 0) >= MAX_STEPS) { return plan({ stop: true, reason: 'step budget of ' + MAX_STEPS + ' calls reached this pass; the next pass continues' }); }
const state = String(env.state || '');
const intent = env.intent || {};
const p = (intent.payload && typeof intent.payload === 'object') ? intent.payload : {};
const summary = String(intent.summary || '').slice(0, 300);
const arts = Array.isArray(env.artifacts) ? env.artifacts : [];
// Executor selection, Build 16, narrowed by the fourth critic cycle. A draft-like
// reversible write with no EditForge payload and no word that names another
// surface goes to drive.draft; everything else goes to the spine echo, whose read
// ceiling makes the router refuse any job it cannot honestly carry. The choice is
// made ONCE, when the approval card is raised, written into intent.payload.action
// and named on the card, so the grant Tee gives is bound to the executor he read.
const DRAFT_WORDS = /\b(draft|outline|script|memo|brief|synopsis|treatment|checklist|essay|one[ -]?pager|one page)\b/i;
const NOT_DRAFT = /\b(airtable|notion|sheet|row|calendar|email|mail|send|publish|upload|deploy|delete|render|tweet|post to)\b/i;
const AREA_FOLDER_LABEL = { TQO: 'the TQO scripts folder (TQO/01_SCRIPTS)', Podcast: 'the TSWS scripts folder (TSWS/01_SCRIPTS)' };
// Executor selection, Build 17. A structural Airtable payload (intent.payload.airtable
// carrying a table name and a fields object) binds airtable.row. The executor holds
// the table and field allowlist, so a payload naming a table it does not permit
// parks the job with that reason rather than writing anywhere. Structure is tested
// before the keyword rule on purpose: a summary is prose and prose is guessed at, a
// payload is a declared intent. Both need a reversible write and no EditForge payload.
function airtablePayload() {
  const a = p.airtable;
  if (!a || typeof a !== 'object' || Array.isArray(a)) { return null; }
  if (typeof a.table !== 'string' || !a.table.trim()) { return null; }
  if (!a.fields || typeof a.fields !== 'object' || Array.isArray(a.fields)) { return null; }
  return a;
}
function selectAction() {
  const ef = (p.editforge && typeof p.editforge === 'object') ? p.editforge : null;
  const br = String(intent.blast_radius || 'none');
  if (!ef && br === 'reversible_write' && airtablePayload()) { return 'airtable.row'; }
  if (!ef && br === 'reversible_write' && DRAFT_WORDS.test(summary) && !NOT_DRAFT.test(summary)) { return 'drive.draft'; }
  return 'spine.echo';
}
// A fingerprint of the Airtable payload (FNV-1a, 32 bits, over its canonical JSON
// with keys sorted). Not a secret and not a signature: eight hex characters on
// the card and in approval.card_executor so the ledger can say which values Tee
// approved, and so dispatch can tell a payload rewritten after the card from the
// one the card described. The card also quotes how the Body begins, because a
// list of field names is not consent to a value nobody saw (critic, 2026-09-06).
function canon(v) {
  if (Array.isArray(v)) { return '[' + v.map(canon).join(',') + ']'; }
  if (v && typeof v === 'object') { return '{' + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ':' + canon(v[k]); }).join(',') + '}'; }
  return JSON.stringify(v === undefined ? null : v);
}
function fingerprint(v) {
  const str = canon(v);
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
  return ('0000000' + h.toString(16)).slice(-8);
}
function executorLine(action) {
  if (action === 'airtable.row') {
    const a = airtablePayload() || { table: '', fields: {} };
    const names = Object.keys(a.fields).join(', ');
    const title = String(a.fields.Title || '').replace(/\s+/g, ' ').trim().slice(0, 120);
    const body = (typeof a.fields.Body === 'string') ? a.fields.Body.replace(/\s+/g, ' ').trim() : '';
    const excerpt = body.length > 160 ? body.slice(0, 160) + ' [' + body.length + ' characters in all]' : body;
    return 'Airtable Row Writer (airtable.row): one row will be written into the ' + String(a.table).trim() + ' table of the DEVON base (payload fingerprint ' + fingerprint(a) + ')' + (title ? ', titled ' + title : '') + ', carrying the fields ' + (names || 'none') + ' as the job declares them plus DEVON key and DEVON job' + (excerpt ? '. Body begins: ' + excerpt : '') + '. Reversible by deleting the row. Nothing is published or sent';
  }
  if (action === 'drive.draft') {
    const area = String(env.area || '');
    const where = AREA_FOLDER_LABEL[area] || (area ? 'the ' + area + ' Area folder' : 'the capture inbox');
    return 'Drive Draft Writer (drive.draft): one Google Doc will be written into ' + where + ' in your Drive, named DRAFT_date_devon_slug, reversible by trashing it. Nothing is published or sent';
  }
  if (p.editforge && typeof p.editforge === 'object') {
    return 'spine.echo, a certification echo: nothing physical runs. This job carries an EditForge payload, and the Action Router has no EditForge executor, so the job will park at AUTHORIZED with that reason rather than render anything';
  }
  return 'spine.echo, a certification echo: nothing physical runs';
}
// A refusal reason that embeds a time or an execution id differs every pass, which
// would defeat both the ledger dedupe below and the digest's once per reason rule.
// Comparison runs on the shape of the reason, not its instance.
function normalize(v) {
  return String(v || '')
    .replace(/\d{4}-\d{2}-\d{2}T[0-9:.]+Z?/g, '<time>')
    .replace(/\b\d{3,}\b/g, '<n>')
    .replace(/\s+/g, ' ')
    .trim();
}
if (state === 'COMPLETED' || state === 'CANCELLED') { return plan({ stop: true, reason: 'terminal' }); }
if (state === 'RECEIVED') { return plan({ call: true, kind: 'spine', url: HOST + 'devon-spine-n8n', body: env }); }
if (state === 'UNDERSTANDING') { return plan({ call: true, kind: 'runtime', url: HOST + 'devon-runtime', body: { envelope: env } }); }
if (state === 'PLANNING') { return plan({ call: true, kind: 'route', url: HOST + 'devon-route', body: { envelope: env } }); }
if (state === 'AUTHORIZED') {
  const ga = env.approval || {};
  const gExp = Date.parse(String(ga.expires_at || ''));
  if (ga.state === 'granted' && !Number.isNaN(gExp) && nowMs > gExp) {
    return cancel(ga, 'expired', 'The grant on card ' + String(ga.queue_row_id || 'unknown') + ' decayed at ' + ga.expires_at + ' with the job still at AUTHORIZED. Each driver pass since the approval, and what the executor answered, is in devon_driver_log. A fresh card is needed to run it again.', ga.queue_row_id, ga.decided_at || now);
  }
  // A refusal from the router this pass leaves its mark in the ledger before the
  // pass ends (Tee's ruling, 2026-09-05): same state, state_reason set, one trace
  // entry, and only when the row does not already carry that reason.
  if (mem.park && mem.park.intent_id === env.intent_id) {
    const park = mem.park;
    delete mem.park;
    const marked = ('Parked at ' + state + ': ' + String(park.reason)).slice(0, 500);
    if (normalize(env.state_reason) === normalize(marked)) {
      log.push('ledger already carries this reason; no new mark');
      return plan({ stop: true, reason: 'organ_refused' });
    }
    const e = copy(env);
    e.state_reason = marked;
    const note = 'Action ' + String(park.action) + ' refused by the router: ' + String(park.reason);
    return busPlan('ACTION_FAILED', e, note, 'stop', 'organ_refused');
  }
  // The grant is bound to the action the card named. A job with no bound action
  // runs the echo only: its card, if it had one, said nothing physical runs.
  // The choice is re-derived here and must still agree with the bound field. They
  // can only differ if something rewrote the envelope between the card and now,
  // which is exactly the case where the human read one act and another would run.
  const bound = (typeof p.action === 'string' && p.action) ? p.action : '';
  const derived = selectAction();
  if (bound && bound !== derived) {
    const e = copy(env);
    e.state_reason = ('Parked at ' + state + ': the bound action ' + bound + ' no longer matches the executor this job selects (' + derived + '). The card Tee approved named one act; nothing runs until a human looks.').slice(0, 500);
    return busPlan('ACTION_FAILED', e, e.state_reason, 'stop', 'bound_action_mismatch');
  }
  const action = bound || 'spine.echo';
  // The values are bound too, not only the action name. The card carried the
  // payload fingerprint; a payload that no longer produces it was changed after
  // Tee read the card, and the grant does not cover what it now says.
  if (action === 'airtable.row') {
    const carded = String((env.approval && env.approval.card_executor) || '').match(/payload fingerprint ([0-9a-f]{8})/);
    const nowFp = fingerprint(airtablePayload());
    if (carded && carded[1] !== nowFp) {
      const e = copy(env);
      e.state_reason = ('Parked at ' + state + ': the Airtable payload no longer matches the one the approval card described (fingerprint ' + carded[1] + ' on the card, ' + nowFp + ' now). Tee approved one row; nothing runs until a human looks.').slice(0, 500);
      return busPlan('ACTION_FAILED', e, e.state_reason, 'stop', 'bound_payload_mismatch');
    }
  }
  return plan({ call: true, kind: 'action', url: HOST + 'devon-action', body: { envelope: env, action: action } });
}

function copy(e) { return JSON.parse(JSON.stringify(e)); }
function busPlan(eventType, e, note, after, stopReason) {
  return plan({ call: true, kind: 'bus', url: HOST + 'devon-event', event_type: eventType, after: after || '', stop_reason: stopReason || '',
    body: { envelope: e, event_type: eventType, actor: 'devon', note: String(note).slice(0, 500) } });
}
function cardBody(kind) {
  const isVerify = kind === 'verify';
  const artLines = [];
  for (const a of arts) { artLines.push(String(a.kind) + ' ' + String(a.name || '') + (a.folder_name ? ' in ' + String(a.folder_name) : '') + (typeof a.words === 'number' ? ' (' + a.words + ' words)' : '') + ' ' + String(a.uri)); }
  const ef = (p.editforge && typeof p.editforge === 'object') ? p.editforge : null;
  const executor = executorLine(selectAction()) + (ef ? (' The job also carries an EditForge ' + String(ef.kind) + ' payload for provider ' + String(ef.provider || 'mock') + ', which the Build 07 handoff would run only after this job reaches EXECUTING.') : '');
  const brief = (p.brief && typeof p.brief === 'object') ? p.brief : null;
  const plan = brief && Array.isArray(brief.plan) ? brief.plan.map(function (s, i) { return String(i + 1) + ') ' + String(s); }).join(' ') : '';
  const doneWhen = brief && Array.isArray(brief.done_when) ? brief.done_when.join('; ') : '';
  const risks = brief && Array.isArray(brief.risks) && brief.risks.length ? brief.risks.join('; ') : '';
  const briefReason = brief && brief.reason ? String(brief.reason).replace(/[.\s]+$/, '') : '';
  const note = (typeof p.note === 'string' && p.note) ? (' NOTE FROM THE FILER, which steers what gets written: ' + String(p.note).replace(/\s+/g, ' ').trim().slice(0, 600) + '.') : '';
  const briefText = brief ? (' DEVON BRIEF. Plan: ' + (plan || 'none') + '. Done when: ' + (doneWhen || 'not stated') + '.' + (risks ? ' Risks: ' + risks + '.' : '') + ' DEVON recommends ' + String(brief.recommendation || 'hold') + (briefReason ? ': ' + briefReason : '') + '.') : ' No DEVON brief on this job.';
  const title = (isVerify ? 'VERIFY job: ' : 'Job needs approval: ') + summary.slice(0, 90);
  const what = isVerify
    ? ('DEVON marks job ' + env.intent_id + ' COMPLETED with verification passed and human_watched true. Job: ' + summary + '. Area ' + String(env.area) + '. Artifacts: ' + (artLines.length ? artLines.join(' | ') : 'none') + '. Approve ONLY after you have watched or listened to the output end to end. Reject sends the job to FAILED.' + (doneWhen ? ' The brief said done when: ' + doneWhen + '. The executor did not check these lines; judge the artifact itself.' : ''))
    : ('DEVON authorises job ' + env.intent_id + ' to execute exactly as planned, nothing more. Job: ' + summary + '. Area ' + String(env.area) + '. Level ' + String(intent.level) + ', blast radius ' + String(intent.blast_radius || 'none') + '. Executor: ' + executor + '.' + note + briefText + ' The grant decays ' + GRANT_HOURS + 'h after your decision. Reject cancels the job.');
  const paid = ef && String(ef.provider || 'mock') !== 'mock';
  return {
    title: title,
    what_happens: what,
    action_type: isVerify ? 'other' : (paid ? 'financial' : 'other'),
    project: 'DEVON Build 14',
    requested_by: 'job-driver',
    blast_radius: String(intent.blast_radius || 'none'),
    reversible: isVerify ? 'no, COMPLETED is terminal' : 'yes until it executes, the job can still be cancelled',
    evidence: 'intent ' + env.intent_id + '; card ' + kind + '; state ' + state + '; router: ' + String(env.state_reason || 'no reason recorded').slice(0, 220)
  };
}
function hoursSince(iso) { const t = Date.parse(String(iso || '')); return Number.isNaN(t) ? null : (nowMs - t) / 3600000; }
function cancel(a, approvalState, reason, id, decidedAt) {
  const e = copy(env);
  e.state = 'CANCELLED';
  e.state_reason = String(reason).slice(0, 500);
  e.approval = Object.assign({}, a, { state: approvalState, queue_row_id: id || a.queue_row_id || null, decided_at: decidedAt || a.decided_at || now, decided_by: approvalState === 'denied' ? 'tee' : (a.decided_by || null) });
  e.receipt = { issued_at: now, outcome: 'cancelled', summary: String(reason).slice(0, 2000), artifact_count: arts.length };
  return busPlan('ACTION_FAILED', e, reason, 'stop');
}

if (state === 'WAITING_APPROVAL' || state === 'ESCALATED') {
  const a = env.approval || { state: 'not_required' };
  const card = mem.approval_card || null;
  const recordedId = String(a.queue_row_id || '');
  if (card && card.request_id && !recordedId) {
    const e = copy(env);
    e.approval = Object.assign({}, a, { state: 'pending', queue_row_id: card.request_id, requested_at: card.requested_at || now, expires_at: card.expires_at || null, scope: 'execute exactly as planned: ' + summary });
    // Bind the grant to the executor the card named.
    if (!e.intent || typeof e.intent !== 'object') { e.intent = {}; }
    if (!e.intent.payload || typeof e.intent.payload !== 'object') { e.intent.payload = {}; }
    const chosen = selectAction();
    e.intent.payload.action = chosen;
    // What the card said, kept where a later reader can find it. The driver never
    // copies an approval_queue row, so without this the ledger cannot answer the
    // one question that matters after the fact: what did Tee actually read.
    e.approval.card_executor = executorLine(chosen).slice(0, 500);
    return busPlan('APPROVAL_REQUESTED', e, 'Approval card ' + card.request_id + ' is in the DEVON Approval Queue (' + String(card.status || 'pending') + '). The job waits for Tee.', card.status === 'pending' ? 'stop' : '');
  }
  if (!card && !recordedId) {
    return plan({ call: true, kind: 'card', card_kind: 'approval', url: HOST + 'devon-approve-request', body: cardBody('approval') });
  }
  const id = recordedId || card.request_id;
  const status = card ? String(card.status || '') : 'unread';
  if (status === 'approved') {
    const e = copy(env);
    e.state = 'AUTHORIZED';
    e.state_reason = null;
    const decided = card.decided_at || now;
    const decidedMs = Date.parse(decided);
    const grantExpiry = new Date((Number.isNaN(decidedMs) ? nowMs : decidedMs) + GRANT_HOURS * 3600000).toISOString().replace(/\.\d{3}Z$/, 'Z');
    if (Date.parse(grantExpiry) < nowMs) {
      return cancel(Object.assign({}, a, { decided_by: 'tee' }), 'expired', 'Tee approved card ' + id + ' at ' + decided + ' but the grant decayed at ' + grantExpiry + ' before the driver acted (the poll did not run in time). Nothing executed; file the job again for a fresh card.', id, decided);
    }
    e.approval = Object.assign({}, a, { state: 'granted', queue_row_id: id, decided_at: decided, decided_by: 'tee', expires_at: grantExpiry, scope: a.scope || ('execute exactly as planned: ' + summary) });
    return busPlan('APPROVAL_GRANTED', e, 'Tee approved card ' + id + ' at ' + decided + '. Authorised for exactly what the card described; the grant decays at ' + grantExpiry + '.', '');
  }
  if (status === 'rejected' || status === 'refused' || status === 'denied') {
    return cancel(a, 'denied', 'Rejected by Tee on card ' + id + ' at ' + String(card.decided_at || 'unknown') + '. The job does not proceed.', id, card.decided_at);
  }
  if (status === 'expired') {
    return cancel(a, 'expired', 'Approval card ' + id + ' expired undecided. No decision is a rejection.', id, now);
  }
  if (status === 'pending') {
    const exp = Date.parse(String(card.expires_at || ''));
    if (!Number.isNaN(exp) && nowMs > exp) { return cancel(a, 'expired', 'Approval card ' + id + ' expired undecided at ' + card.expires_at + '. No decision is a rejection.', id, now); }
    return plan({ stop: true, reason: 'awaiting approval decision on card ' + id });
  }
  if (status === 'absent') {
    const h = hoursSince(a.requested_at || env.updated_at);
    if (h !== null && h > ABSENT_GRACE_H) { return cancel(a, 'expired', 'Approval card ' + id + ' is absent from the queue and the job has waited ' + Math.round(h) + 'h. Closed by absence, no recorded decision.', id, now); }
    return plan({ stop: true, reason: 'approval card ' + id + ' not found in the queue yet' });
  }
  return plan({ stop: true, reason: 'approval card ' + id + ' recorded, decision not read this pass' });
}

if (state === 'EXECUTING') {
  if (p.editforge && typeof p.editforge === 'object') {
    if (mem.editforge_called === true) { return plan({ stop: true, reason: 'EditForge job observed once this pass, still running' }); }
    const ef = p.editforge;
    // A paid render is a spend. It runs only behind a granted, unexpired
    // approval, whatever the envelope claims about blast radius. Fail closed.
    if (String(ef.provider || 'mock') !== 'mock') {
      const ga = env.approval || {};
      const gExp = Date.parse(String(ga.expires_at || ''));
      if (ga.state !== 'granted' || Number.isNaN(gExp) || nowMs > gExp) {
        const e = copy(env);
        e.state = 'FAILED';
        e.state_reason = ('Paid render via provider ' + String(ef.provider) + ' refused: approval.state is ' + String(ga.state || 'absent') + (ga.expires_at ? ', expires_at ' + ga.expires_at : '') + '. A paid render needs a granted, unexpired approval card. Nothing was sent to EditForge.').slice(0, 500);
        e.execution = Object.assign({}, env.execution || { state: 'not_started' }, { state: 'failed', finished_at: now });
        return busPlan('ACTION_FAILED', e, e.state_reason, 'stop');
      }
    }
    const body = { envelope: env, kind: String(ef.kind || ''), prompt: String(ef.prompt || ''), provider: String(ef.provider || 'mock') };
    if (ef.label) { body.label = String(ef.label); }
    if (ef.options && typeof ef.options === 'object') { body.options = ef.options; }
    return plan({ call: true, kind: 'editforge', url: HOST + 'devon-editforge', body: body });
  }
  return plan({ call: true, kind: 'spine', url: HOST + 'devon-spine-n8n', body: env });
}

if (state === 'VERIFYING') {
  const v = env.verification || { state: 'pending' };
  const ev = Array.isArray(v.evidence) ? v.evidence : [];
  let recordedId = '';
  for (const s of ev) { const t = String(s); if (t.indexOf('verify_card ') === 0) { recordedId = t.slice(12).trim(); } }
  const card = mem.verify_card || null;
  const ef = (p.editforge && typeof p.editforge === 'object') ? p.editforge : null;
  // Tee's ruling 3, held at this hop as well as at the Spine: an executor that
  // already succeeded keeps its own workflow id, execution id and finish time. A
  // verification Tee refuses is a verification failure, not an execution failure,
  // and the artifact it produced is real. The outcome goes to verification, which
  // exists for it.
  function keepExecution(outcome) {
    const prior = (env.execution && typeof env.execution === 'object') ? env.execution : { state: 'not_started' };
    if (prior.state === 'succeeded') { return prior; }
    return Object.assign({}, prior, { state: outcome, finished_at: now });
  }
  const autoOk = p.auto_verify === true && String(intent.blast_radius || 'none') === 'none' && arts.length === 0 && !ef;
  function complete(human, note, cardId) {
    const e = copy(env);
    e.state = 'COMPLETED';
    e.state_reason = null;
    e.verification = Object.assign({}, v, { state: 'passed', method: human ? 'human_watch' : 'auto_no_artifact', human_watched: human === true, verified_at: now, evidence: ev.concat([human ? ('verify_card ' + cardId + ' approved by Tee') : 'auto_verify: blast radius none, no artifacts, nothing to watch']) });
    e.execution = keepExecution('succeeded');
    e.learning = env.learning || { state: 'not_captured' };
    e.receipt = { issued_at: now, outcome: 'completed', summary: String(note).slice(0, 2000), artifact_count: arts.length };
    return busPlan('VERIFICATION_PASSED', e, note, 'stop');
  }
  function fail(reason) {
    const e = copy(env);
    e.state = 'FAILED';
    e.state_reason = String(reason).slice(0, 500);
    e.verification = Object.assign({}, v, { state: 'failed', method: 'human_watch', human_watched: false, verified_at: now });
    e.execution = keepExecution('failed');
    const toTrash = arts.map(function (a) { return String(a.uri || a.name || a.kind); });
    e.receipt = { issued_at: now, outcome: 'failed', summary: (String(reason) + (toTrash.length ? ' Artifacts to trash by hand: ' + toTrash.join(', ') : '')).slice(0, 2000), artifact_count: arts.length };
    return busPlan('ACTION_FAILED', e, reason, 'stop');
  }
  if (autoOk && !recordedId && !card) {
    return complete(false, 'Completed without a verification card: blast radius none, no artifacts, nothing a human could watch. Job: ' + summary, '');
  }
  if (card && card.request_id && !recordedId) {
    const e = copy(env);
    e.verification = Object.assign({}, v, { state: 'pending', method: 'human_watch', human_watched: false, evidence: ev.concat(['verify_card ' + card.request_id]) });
    return busPlan('APPROVAL_REQUESTED', e, 'Verification card ' + card.request_id + ' is in the DEVON Approval Queue (' + String(card.status || 'pending') + '). Tee watches, then rules.', card.status === 'pending' ? 'stop' : '');
  }
  if (!card && !recordedId) {
    return plan({ call: true, kind: 'card', card_kind: 'verify', url: HOST + 'devon-approve-request', body: cardBody('verify') });
  }
  const id = recordedId || card.request_id;
  const status = card ? String(card.status || '') : 'unread';
  if (status === 'approved') { return complete(true, 'Tee verified the output end to end and approved card ' + id + ' at ' + String(card.decided_at || now) + '. Job: ' + summary, id); }
  if (status === 'rejected' || status === 'refused' || status === 'denied') { return fail('Verification refused by Tee on card ' + id + ' at ' + String(card.decided_at || 'unknown') + '.'); }
  if (status === 'expired') { return fail('Verification card ' + id + ' expired undecided. No decision is a rejection.'); }
  if (status === 'pending') {
    const exp = Date.parse(String(card.expires_at || ''));
    if (!Number.isNaN(exp) && nowMs > exp) { return fail('Verification card ' + id + ' expired undecided at ' + card.expires_at + '. No decision is a rejection.'); }
    return plan({ stop: true, reason: 'awaiting verification decision on card ' + id });
  }
  if (status === 'absent') {
    const h = hoursSince(env.updated_at);
    if (h !== null && h > ABSENT_GRACE_H) { return fail('Verification card ' + id + ' is absent from the queue after ' + Math.round(h) + 'h. Closed by absence, no recorded decision.'); }
    return plan({ stop: true, reason: 'verification card ' + id + ' not found in the queue yet' });
  }
  return plan({ stop: true, reason: 'verification card ' + id + ' recorded, decision not read this pass' });
}
return plan({ stop: true, reason: 'state ' + state + ' is not driven automatically (FAILED, BLOCKED and RETRYING wait for a human or the Janitor)' });
