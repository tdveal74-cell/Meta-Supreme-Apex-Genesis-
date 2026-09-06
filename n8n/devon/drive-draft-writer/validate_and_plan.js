// DEVON Drive Draft Writer, Build 16. Validation and planning half.
// The first real executor on the Action Router allowlist (action drive.draft).
// Accepts one AUTHORIZED envelope with a granted, unexpired approval and a blast
// radius no wider than reversible_write, plans one Google Doc draft in the folder
// the vault permits for the job's Area, and hands the plan on. Refusals are data
// (refused: true, reason), never thrown; a genuine fault still throws and the
// shared Error Alarm fires. Contract: SYS_DATA_job-envelope-schema_v1_2026-08-23.
// The folder map mirrors DRAFT_FOLDERS in services/devon/vault.py. Two copies on
// purpose, n8n cannot import the vault: change both or neither.

const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const BR = ['none', 'read', 'reversible_write', 'irreversible_write', 'destructive'];
const CEILING = 'reversible_write';
const FOLDERS = {
  'TQO': { id: '1VtnHmKxus3YCJNDk3HbF3wf6Wyh1E-mB', name: 'TQO/01_SCRIPTS' },
  'Podcast': { id: '1gbx4JBnCVwpxS4eTOCy24SDkmH4LrztW', name: 'TSWS/01_SCRIPTS' },
  'NCO': { id: '1GhyNDBaBLrcJux9gEVtVpSTnbDK1eJzO', name: 'Areas/NCO' },
  'ACX': { id: '1a_baNvgH9CBb4biuBCbdNb_4P9fvkO1a', name: 'Areas/ACX' },
  'Systems': { id: '1La9LZ1zvpnU6-ep-EVStEy33M8cvyUGr', name: 'Areas/Systems' },
  'Learning': { id: '1_WWVxVMfhCxMdxXLv6NjSiKPCzZmbQFu', name: 'Areas/Learning' },
  'Family': { id: '1LU5mD4reyWwN-D3O_41FCvP1BuUvqlhd', name: 'Areas/Family' },
  'Money': { id: '1PbsQU2VSLSt-e7scjWY83X5k-y27c8OO', name: 'Areas/Money' },
  'Health': { id: '1BkZ0YfANbOS0fQf_2F-e-22LTSeV8xRg', name: 'Areas/Health' }
};
const INBOX = { id: '1ZusR2B7GWMf2MsCipgb5srZ8mS5z4F0B', name: '00_Capture Inbox' };

function pick(j) {
  if (j && j.body && typeof j.body === 'object') { return j.body.envelope || j.body; }
  return j;
}
function refusal(e, reason) {
  return { json: { refused: true, outcome: 'refused', reason: reason, action: 'drive.draft',
    intent_id: (e && typeof e === 'object' && e.intent_id) ? String(e.intent_id) : null,
    state: (e && typeof e === 'object' && e.state) ? String(e.state) : null } };
}
function s(v) { return String(v === undefined || v === null ? '' : v).replace(/\s+/g, ' ').trim(); }
function slug(v) { let x = s(v).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60); if (x.length === 60 && x.indexOf('-') !== -1) { x = x.replace(/-[^-]*$/, ''); } return x || 'draft'; }

const out = [];
for (const it of $input.all()) {
  const e = pick(it.json);
  if (!e || typeof e !== 'object' || (!e.schema_version && !e.intent_id)) {
    out.push(refusal(null, 'REFUSED: no envelope in the request body.')); continue;
  }
  if (e.schema_version !== '1.0.0') { out.push(refusal(e, 'REFUSED: schema_version ' + String(e.schema_version) + ' is not implemented by this executor.')); continue; }
  if (!ULID.test(String(e.intent_id || ''))) { out.push(refusal(e, 'REFUSED: intent_id ' + String(e.intent_id) + ' is not a ULID.')); continue; }
  if (e.state !== 'AUTHORIZED') { out.push(refusal(e, 'REFUSED: this executor writes from AUTHORIZED only. This envelope is ' + String(e.state) + '.')); continue; }
  const intent = (e.intent && typeof e.intent === 'object') ? e.intent : {};
  const br = String(intent.blast_radius || 'none');
  if (BR.indexOf(br) === -1 || BR.indexOf(br) > BR.indexOf(CEILING)) {
    out.push(refusal(e, 'REFUSED: blast radius ' + br + ' exceeds the ceiling ' + CEILING + ' of this executor. A draft is a reversible write and nothing wider.')); continue;
  }
  // This executor always writes, whatever the label says, so every envelope needs a
  // decided, unexpired grant. Two gates, one truth: the router checks the same.
  const appr = (e.approval && typeof e.approval === 'object') ? e.approval : {};
  if (appr.state !== 'granted') { out.push(refusal(e, 'REFUSED: a draft is a write and needs approval.state granted; it is ' + String(appr.state || 'absent') + '. A card and a decision are required.')); continue; }
  const expMs = Date.parse(String(appr.expires_at || ''));
  if (Number.isNaN(expMs)) { out.push(refusal(e, 'REFUSED: approval.expires_at ' + String(appr.expires_at) + ' is not a readable time, so the grant cannot be trusted.')); continue; }
  if (expMs < Date.now()) { out.push(refusal(e, 'REFUSED: the approval expired at ' + String(appr.expires_at) + '. An expired grant is not a grant.')); continue; }
  // Single flight. The entry report below marks the ledger row execution.state running
  // under this workflow's id; a second pass that reads the row inside ten minutes is
  // refused rather than allowed to write a second draft under the same key.
  // An unreadable updated_at is treated as a lock still held, not as no lock. The
  // same rule the grant gets three lines above: a time that cannot be read cannot
  // be trusted, and failing open here writes a second document.
  const ex = (e.execution && typeof e.execution === 'object') ? e.execution : {};
  if (ex.state === 'running' && ex.workflow_id === $workflow.id) {
    const lockAge = Date.now() - Date.parse(String(e.updated_at || ''));
    if (Number.isNaN(lockAge) || lockAge < 10 * 60 * 1000) {
      out.push(refusal(e, 'REFUSED: another pass began writing this draft at ' + String(e.updated_at) + ' (execution ' + String(ex.execution_id || 'unknown') + '); this pass steps back. The lock ages out ten minutes after a readable updated_at, and an unreadable one counts as held.')); continue;
    }
  }
  const idem = s(e.idempotency_key);
  if (idem.length < 8 || idem.length > 128 || /['"\\]/.test(idem)) { out.push(refusal(e, 'REFUSED: idempotency_key must be 8 to 128 characters with no quotes or backslashes before this executor writes anything.')); continue; }
  const p = (intent.payload && typeof intent.payload === 'object') ? intent.payload : {};
  if (p.editforge && typeof p.editforge === 'object') { out.push(refusal(e, 'REFUSED: this job carries an EditForge payload; renders go through the Build 07 handoff, not the draft writer.')); continue; }
  const summary = s(intent.summary);
  if (summary.length < 8) { out.push(refusal(e, 'REFUSED: intent.summary is too short to draft from.')); continue; }

  const area = s(e.area);
  const folder = FOLDERS[area] || INBOX;
  // The day comes from the job, not from the clock. A retry after midnight has to
  // produce the same name, because that name is the second half of the idempotency
  // check below and a name that moves would write a second document.
  const created = Date.parse(String(e.created_at || ''));
  const day = new Date(Number.isNaN(created) ? Date.now() : created).toISOString().slice(0, 10);
  const docName = 'DRAFT_' + day + '_devon_' + slug(summary);

  const brief = (p.brief && typeof p.brief === 'object') ? p.brief : {};
  const plan = Array.isArray(brief.plan) ? brief.plan.map(function (x, i) { return String(i + 1) + '. ' + s(x); }).join('\n') : '';
  const doneWhen = Array.isArray(brief.done_when) ? brief.done_when.map(function (x) { return '- ' + s(x); }).join('\n') : '';
  const risks = Array.isArray(brief.risks) ? brief.risks.map(function (x) { return '- ' + s(x); }).join('\n') : '';
  const system = [
    'You are DEVON, the second brain of a content studio run by Tee, a retired US Army Sergeant First Class. Shows: The Quiet Operator (TQO, presenter led teaching on AI tools and AI era career strategy, calm, anti hype, proof driven; every episode opens with a learning objective in the first 30 seconds and carries a 3 to 5 step checklist), The Shadow We Share (TSWS, a scripted podcast with his wife, characters Auren and Vespera, relational metaphysics), NCO Forge (presenter led leadership content for NCOs and mid career professionals), Ascension Caudex (ACX, a micro drama).',
    'Write the working draft the job asks for. It is a draft for Tee to edit, not a finished piece. Plain text only: a one line title on the first line, short headings in capitals on their own lines, numbered steps and simple lists, blank lines between sections. No markdown symbols, no tables, no code fences, no emoji. Never use an em dash or an en dash; restructure the sentence instead. 300 to 900 words. Do not claim anything was published, sent, rendered, measured or verified. Where a fact is unknown, write the word unverified rather than inventing it. End with a short section titled OPEN QUESTIONS FOR TEE listing anything he must decide.'
  ].join('\n\n');
  const user = ['JOB: ' + summary, 'AREA: ' + (area || 'unstated'), 'LEVEL: ' + String(intent.level), 'BLAST RADIUS: ' + br,
    plan ? 'BRIEF PLAN:\n' + plan : 'BRIEF PLAN: none', doneWhen ? 'DONE WHEN:\n' + doneWhen : '', risks ? 'RISKS:\n' + risks : '',
    p.note ? 'NOTE FROM THE FILER: ' + s(p.note).slice(0, 1000) : '', 'Write the draft now.'].filter(Boolean).join('\n\n');

  // The entry report carries the lock: execution running under this workflow.
  const locked = JSON.parse(JSON.stringify(e));
  locked.execution = Object.assign({}, ex, { state: 'running', executor: 'n8n', workflow_id: $workflow.id, execution_id: String($execution.id), started_at: ex.started_at || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z') });
  out.push({ json: {
    refused: false, action: 'drive.draft', envelope: locked, intent_id: e.intent_id, from_state: 'AUTHORIZED', to_state: 'EXECUTING',
    idem: idem, area: area, blast_radius: br, folder_id: folder.id, folder_name: folder.name, doc_name: docName, summary: summary,
    // Two ways to find a draft this job already wrote. The app properties are the
    // exact answer when they persisted. They do not always: Drive's file list is
    // eventually consistent, and a pass that created the document but could not read
    // its own properties back (properties_verified false) would otherwise write a
    // second one on the next retry. The deterministic name is the fallback, and
    // Check Existing only accepts a name match when the properties do not name a
    // different job.
    query: "((appProperties has { key='devon_idempotency_key' and value='" + idem + "' } and appProperties has { key='devon_intent_id' and value='" + String(e.intent_id) + "' }) or name = '" + docName + "') and '" + folder.id + "' in parents and trashed = false",
    request: { model: 'gpt-oss-120b', max_completion_tokens: 2500, temperature: 0.4, reasoning_effort: 'medium',
      messages: [{ role: 'system', content: system }, { role: 'user', content: user }] }
  } });
}
return out;
