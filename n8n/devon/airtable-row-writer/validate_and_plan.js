// DEVON Airtable Row Writer, Build 17. Validation and planning half.
// The third executor on the Action Router allowlist (action airtable.row, ceiling
// reversible_write). Accepts one AUTHORIZED envelope with a granted, unexpired
// approval and a structural payload (intent.payload.airtable: a table name and a
// fields object), checks the table and every field against the allowlist below,
// and hands the plan on. Refusals are data (refused: true, reason), never thrown;
// a genuine fault still throws and the shared Error Alarm fires.
// Contract: SYS_DATA_job-envelope-schema_v1_2026-08-23.
// TABLES mirrors AIRTABLE_ROW_TABLES in services/devon/vault.py and BASE mirrors
// AIRTABLE.live_base there. Two copies on purpose, n8n cannot import the vault:
// change both or neither; test_devon_integrity pins them together.
//
// Why a structural payload and not a keyword. The Drive Draft Writer is chosen
// from words in the summary because a draft is what prose asks for. A row is
// data: which table, which fields, which values. Guessing those from a sentence
// is the speculation the first law forbids, so the job has to carry them, and the
// approval card names the table and the fields Tee is consenting to.
//
// Why an allowlist of tables and fields. The base holds some forty tables and
// several are the estate's own records (Credentials, Strategic Decisions, the
// three content tables). A writer that takes any table name is a write anywhere
// hole with an approval card in front of it. Adding a table or a field is a
// deliberate act, done here and in the vault in the same change.
//
// What this executor never does. It never sends typecast, so an option name that
// does not exist on a select field is refused by Airtable (HTTP 422) and that
// refusal comes back as data. It never sets DEVON key or DEVON job from the job;
// it stamps them itself, and a job that tries to set them is refused. It never
// defaults a field the job did not name: the card says exactly what is written.

const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const BR = ['none', 'read', 'reversible_write', 'irreversible_write', 'destructive'];
const CEILING = 'reversible_write';
const BASE = 'app28z7XnKzjfTXwc';
const TABLES = {
  'Inbox Captures': {
    id: 'tbl4ziFRbl5mnUcKc',
    key_field: 'DEVON key',
    job_field: 'DEVON job',
    rules: {
      'Title': { kind: 'text', max: 200, required: true },
      'Captured': { kind: 'date' },
      'Kind': { kind: 'select' },
      'Source': { kind: 'select' },
      'Area': { kind: 'multi', max_items: 9 },
      'Body': { kind: 'text', max: 20000 },
      'Notes': { kind: 'text', max: 5000 }
    }
  }
};
const DATE = /^\d{4}-\d{2}-\d{2}$/;

function pick(j) {
  if (j && j.body && typeof j.body === 'object') { return j.body.envelope || j.body; }
  return j;
}
function refusal(e, reason) {
  return { json: { refused: true, outcome: 'refused', reason: reason, action: 'airtable.row',
    intent_id: (e && typeof e === 'object' && e.intent_id) ? String(e.intent_id) : null,
    state: (e && typeof e === 'object' && e.state) ? String(e.state) : null } };
}
function s(v) { return String(v === undefined || v === null ? '' : v).replace(/\s+/g, ' ').trim(); }
function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
// Returns the cleaned value, or { bad: reason } when the value fails its rule. A
// text value keeps its line breaks (Body and Notes are multiline fields) and loses
// only the whitespace at either end; nothing inside it is rewritten.
function clean(name, rule, value) {
  if (rule.kind === 'text') {
    if (typeof value !== 'string') { return { bad: name + ' must be a string' }; }
    const t = value.replace(/\r\n?/g, '\n').trim();
    if (!t) { return { bad: name + ' is empty' }; }
    if (t.length > rule.max) { return { bad: name + ' is ' + t.length + ' characters, over the ' + rule.max + ' limit' }; }
    return t;
  }
  if (rule.kind === 'date') {
    // A date that parses is not a date that exists: V8 reads 2026-02-30 as March 2
    // and Airtable refuses it, so the value must come back out of the parser as it
    // went in.
    if (typeof value !== 'string' || !DATE.test(value)) { return { bad: name + ' must be a date written YYYY-MM-DD' }; }
    const ms = Date.parse(value + 'T00:00:00Z');
    if (Number.isNaN(ms) || new Date(ms).toISOString().slice(0, 10) !== value) { return { bad: name + ' is not a calendar date that exists' }; }
    return value;
  }
  if (rule.kind === 'select') {
    if (typeof value !== 'string' || !value.trim() || value.trim().length > 80) { return { bad: name + ' must be one option name, a string of 1 to 80 characters' }; }
    return value.trim();
  }
  if (rule.kind === 'multi') {
    if (!Array.isArray(value) || value.length === 0 || value.length > rule.max_items) { return { bad: name + ' must be a list of 1 to ' + rule.max_items + ' option names' }; }
    const out = [];
    for (const x of value) {
      if (typeof x !== 'string' || !x.trim() || x.trim().length > 80) { return { bad: name + ' must contain only option names, strings of 1 to 80 characters' }; }
      out.push(x.trim());
    }
    return out;
  }
  return { bad: name + ' has no rule in this executor' };
}

const out = [];
for (const it of $input.all()) {
  const e = pick(it.json);
  if (!e || typeof e !== 'object' || (!e.schema_version && !e.intent_id)) {
    out.push(refusal(null, 'REFUSED: no envelope in the request body.')); continue;
  }
  if (e.schema_version !== '1.0.0') { out.push(refusal(e, 'REFUSED: schema_version ' + String(e.schema_version) + ' is not implemented by this executor.')); continue; }
  if (!ULID.test(String(e.intent_id || ''))) { out.push(refusal(e, 'REFUSED: intent_id ' + String(e.intent_id) + ' is not a ULID.')); continue; }
  if (e.state !== 'AUTHORIZED') { out.push(refusal(e, 'REFUSED: this executor writes from AUTHORIZED only. This envelope is ' + String(e.state) + '.')); continue; }
  const intent = isObj(e.intent) ? e.intent : {};
  const br = String(intent.blast_radius || 'none');
  if (BR.indexOf(br) === -1 || BR.indexOf(br) > BR.indexOf(CEILING)) {
    out.push(refusal(e, 'REFUSED: blast radius ' + br + ' exceeds the ceiling ' + CEILING + ' of this executor. A row is a reversible write and nothing wider.')); continue;
  }
  // This executor always writes, whatever the label says, so every envelope needs a
  // decided, unexpired grant. Two gates, one truth: the router checks the same.
  const appr = isObj(e.approval) ? e.approval : {};
  if (appr.state !== 'granted') { out.push(refusal(e, 'REFUSED: a row is a write and needs approval.state granted; it is ' + String(appr.state || 'absent') + '. A card and a decision are required.')); continue; }
  const expMs = Date.parse(String(appr.expires_at || ''));
  if (Number.isNaN(expMs)) { out.push(refusal(e, 'REFUSED: approval.expires_at ' + String(appr.expires_at) + ' is not a readable time, so the grant cannot be trusted.')); continue; }
  if (expMs < Date.now()) { out.push(refusal(e, 'REFUSED: the approval expired at ' + String(appr.expires_at) + '. An expired grant is not a grant.')); continue; }
  // Single flight, best effort, the same rule as the Drive Draft Writer. The entry
  // report marks the ledger row execution.state running under this workflow's id,
  // and a second pass that reads the row inside ten minutes steps back. An
  // unreadable updated_at is a lock still held: a time that cannot be read cannot
  // be trusted, and failing open here writes a second row. Stated plainly (critic,
  // 2026-09-06): this mark lives only in the ledger row, and the router's failure
  // exit rewrites that row from its pre dispatch envelope, so the mark does not
  // survive a failed pass. What actually stops a second row is the driver poll
  // skipping a job touched inside three minutes and the search by DEVON key and
  // DEVON job before every write. The residual window is two passes loading the
  // row before either entry report lands.
  const ex = isObj(e.execution) ? e.execution : {};
  if (ex.state === 'running' && ex.workflow_id === $workflow.id) {
    const lockAge = Date.now() - Date.parse(String(e.updated_at || ''));
    if (Number.isNaN(lockAge) || lockAge < 10 * 60 * 1000) {
      out.push(refusal(e, 'REFUSED: another pass began writing this row at ' + String(e.updated_at) + ' (execution ' + String(ex.execution_id || 'unknown') + '); this pass steps back. The lock ages out ten minutes after a readable updated_at, and an unreadable one counts as held.')); continue;
    }
  }
  // The key is stamped on the row exactly as the ledger holds it, so it is never
  // rewritten here: whitespace anywhere in it is refused rather than collapsed.
  const idem = String(e.idempotency_key === undefined || e.idempotency_key === null ? '' : e.idempotency_key);
  if (idem.length < 8 || idem.length > 128 || /[\s'"\\{}]/.test(idem)) { out.push(refusal(e, 'REFUSED: idempotency_key must be 8 to 128 characters with no whitespace, quotes, braces or backslashes before this executor writes anything; it is quoted into an Airtable formula and stamped on the row verbatim.')); continue; }
  const p = isObj(intent.payload) ? intent.payload : {};
  if (isObj(p.editforge)) { out.push(refusal(e, 'REFUSED: this job carries an EditForge payload; renders go through the Build 07 handoff, not the row writer.')); continue; }

  // The structural payload. Nothing below is guessed from the summary.
  const a = p.airtable;
  if (!isObj(a)) { out.push(refusal(e, 'REFUSED: no intent.payload.airtable object. This executor writes only what the job declares: { airtable: { table, fields } }.')); continue; }
  const tableName = s(a.table);
  const t = TABLES[tableName];
  if (!t) { out.push(refusal(e, 'REFUSED: table ' + (tableName || '(unnamed)') + ' is not on this executor\'s allowlist. Writable tables: ' + Object.keys(TABLES).join(', ') + '. Adding one is a deliberate act in the executor and the vault, not a runtime decision.')); continue; }
  if (!isObj(a.fields)) { out.push(refusal(e, 'REFUSED: intent.payload.airtable.fields must be an object of field name to value.')); continue; }
  const writable = Object.keys(t.rules);
  const fields = {};
  const names = [];
  let bad = '';
  for (const name of Object.keys(a.fields)) {
    if (name === t.key_field || name === t.job_field) { bad = name + ' is stamped by the executor and cannot be set by the job'; break; }
    const rule = t.rules[name];
    if (!rule) { bad = 'field ' + name + ' is not writable in ' + tableName + ' by this executor. Writable fields: ' + writable.join(', '); break; }
    const v = clean(name, rule, a.fields[name]);
    if (isObj(v) && v.bad) { bad = v.bad; break; }
    fields[name] = v;
    names.push(name);
  }
  if (bad) { out.push(refusal(e, 'REFUSED: ' + bad + '. Nothing was written.')); continue; }
  for (const name of writable) {
    if (t.rules[name].required && !(name in fields)) { bad = name + ' is required in ' + tableName + ' and the job did not set it'; break; }
  }
  if (bad) { out.push(refusal(e, 'REFUSED: ' + bad + '. Nothing was written.')); continue; }
  fields[t.key_field] = idem;
  fields[t.job_field] = String(e.intent_id);
  const title = String(fields.Title || '');

  // The entry report carries the lock: execution running under this workflow.
  const locked = JSON.parse(JSON.stringify(e));
  locked.execution = Object.assign({}, ex, { state: 'running', executor: 'n8n', workflow_id: $workflow.id, execution_id: String($execution.id), started_at: ex.started_at || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z') });
  out.push({ json: {
    refused: false, action: 'airtable.row', envelope: locked, intent_id: e.intent_id, from_state: 'AUTHORIZED', to_state: 'EXECUTING',
    idem: idem, area: s(e.area), blast_radius: br, summary: s(intent.summary),
    base_id: BASE, table: tableName, table_id: t.id, key_field: t.key_field, job_field: t.job_field,
    field_names: names, title: title, fields: fields,
    // Both DEVON fields, both quoted values already checked for quotes and braces.
    // A row carrying this key under another job's id is another job's row and is
    // ignored, never adopted; Check Existing re-reads both fields on every hit.
    formula: 'AND({' + t.key_field + "} = '" + idem + "', {" + t.job_field + "} = '" + String(e.intent_id) + "')",
    api_url: 'https://api.airtable.com/v0/' + BASE + '/' + t.id,
    record_url_base: 'https://airtable.com/' + BASE + '/' + t.id + '/',
    create_body: { fields: fields }
  } });
}
return out;
