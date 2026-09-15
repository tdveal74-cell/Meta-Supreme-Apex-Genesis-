// DEVON Zapier Executor, Build 19. Validation and planning half.
// The fourth executor on the Action Router allowlist (action zapier.mcp, ceiling
// reversible_write). Accepts one AUTHORIZED envelope with a granted, unexpired
// approval and a structural payload (intent.payload.zapier: a tool name and an
// arguments object), checks the tool against the allowlist below and the
// arguments against their shape rules, and hands the plan on. Refusals are data
// (refused: true, reason), never thrown; a genuine fault still throws and the
// shared Error Alarm fires.
// Contract: SYS_DATA_job-envelope-schema_v1_2026-08-23.
// TOOLS mirrors ZAPIER_MCP_TOOLS in services/devon/vault.py. Two copies on
// purpose, n8n cannot import the vault: change both or neither;
// test_devon_integrity pins them together.
//
// What Zapier is here. Ruled by Tee 2026-09-15: DEVON reaches Zapier through the
// Zapier MCP server (mcp.zapier.com, Streamable HTTP, JSON-RPC 2.0), a server Tee
// configures in Zapier by attaching actions to it. The credential is an n8n
// header auth credential by id; nothing in this workflow holds the token. Every
// call is one tools/call on one tool with the arguments the job declares, inside
// a session this executor opens with initialize and never reuses across jobs.
//
// Why an allowlist of tools with a blast radius each. The server exposes whatever
// Tee attached, and a Zapier action can send an email or post to LinkedIn, which
// nobody can take back. A tool reaches this map only by a deliberate change here
// and in the vault, with the radius it really has, and the executor ceiling is
// reversible_write: a tool whose radius is wider cannot be added without raising
// the ceiling, which is a ruling for Tee, not an edit.
//
// What this executor never does. It never sends an argument the job did not
// declare, never calls a tool that is not on the map, never discovers tools at
// run time, never retries a write whose outcome it could not read, and never
// writes the arguments into its call log, only a fingerprint of them.

const ULID = /^[0-9A-HJKMNP-TV-Z]{26}$/;
const BR = ['none', 'read', 'reversible_write', 'irreversible_write', 'destructive'];
const CEILING = 'reversible_write';
const MCP_URL = 'https://mcp.zapier.com/api/v1/connect';
const PROTOCOL = '2025-06-18';
const TOOLS = {
  'get_configuration_url': {
    blast_radius: 'read',
    description: 'Returns the URL where the Zapier MCP server is configured. Read only; the proof tool for the lane.'
  }
};
const KEY = /^[a-zA-Z][a-zA-Z0-9_]{0,60}$/;
const MAX_KEYS = 24;
const MAX_STRING = 20000;
const MAX_LIST = 50;
const MAX_ITEM = 2000;
const MAX_TOTAL = 60000;

function pick(j) {
  if (j && j.body && typeof j.body === 'object') { return j.body.envelope || j.body; }
  return j;
}
function refusal(e, reason) {
  return { json: { refused: true, outcome: 'refused', reason: reason, action: 'zapier.mcp',
    intent_id: (e && typeof e === 'object' && e.intent_id) ? String(e.intent_id) : null,
    state: (e && typeof e === 'object' && e.state) ? String(e.state) : null } };
}
function s(v) { return String(v === undefined || v === null ? '' : v).replace(/\s+/g, ' ').trim(); }
function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
function scalar(v) { return typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean' || v === null; }
// A canonical JSON (keys sorted) and an FNV-1a fingerprint over it, the same two
// functions the Job Driver uses, so the eight hex characters on the approval card
// and the eight this executor records are the same computation.
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
// Returns { ok: true, value } or { ok: false, bad: reason }. A string keeps its
// content and loses nothing; over a bound it is refused, never cut (a silent
// truncation is a value the card never showed). One level of nesting is allowed
// so a tool's dynamic_properties object can ride through, and no deeper.
function bad(reason) { return { ok: false, bad: reason }; }
function cleanValue(path, v, depth) {
  if (scalar(v)) {
    if (typeof v === 'string' && v.length > MAX_STRING) { return bad(path + ' is ' + v.length + ' characters, over the ' + MAX_STRING + ' limit'); }
    if (typeof v === 'number' && !Number.isFinite(v)) { return bad(path + ' is not a finite number'); }
    return { ok: true, value: v };
  }
  if (Array.isArray(v)) {
    if (v.length > MAX_LIST) { return bad(path + ' lists ' + v.length + ' items, over the ' + MAX_LIST + ' limit'); }
    const list = [];
    for (let i = 0; i < v.length; i++) {
      const x = v[i];
      if (!scalar(x)) { return bad(path + '[' + i + '] must be a string, a number, a boolean or null'); }
      if (typeof x === 'string' && x.length > MAX_ITEM) { return bad(path + '[' + i + '] is ' + x.length + ' characters, over the ' + MAX_ITEM + ' limit'); }
      if (typeof x === 'number' && !Number.isFinite(x)) { return bad(path + '[' + i + '] is not a finite number'); }
      list.push(x);
    }
    return { ok: true, value: list };
  }
  if (isObj(v)) {
    if (depth >= 2) { return bad(path + ' nests an object inside an object; one level is the limit'); }
    const keys = Object.keys(v);
    if (keys.length > MAX_KEYS) { return bad(path + ' has ' + keys.length + ' keys, over the ' + MAX_KEYS + ' limit'); }
    const obj = {};
    for (const k of keys) {
      if (!KEY.test(k)) { return bad(path + ' has a key that is not a plain name: ' + s(k).slice(0, 40)); }
      const c = cleanValue(path + '.' + k, v[k], depth + 1);
      if (!c.ok) { return c; }
      obj[k] = c.value;
    }
    return { ok: true, value: obj };
  }
  return bad(path + ' must be a string, a number, a boolean, null, a list of those or a flat object of those');
}

const out = [];
for (const it of $input.all()) {
  const e = pick(it.json);
  if (!e || typeof e !== 'object' || (!e.schema_version && !e.intent_id)) {
    out.push(refusal(null, 'REFUSED: no envelope in the request body.')); continue;
  }
  if (e.schema_version !== '1.0.0') { out.push(refusal(e, 'REFUSED: schema_version ' + String(e.schema_version) + ' is not implemented by this executor.')); continue; }
  if (!ULID.test(String(e.intent_id || ''))) { out.push(refusal(e, 'REFUSED: intent_id ' + String(e.intent_id) + ' is not a ULID.')); continue; }
  if (e.state !== 'AUTHORIZED') { out.push(refusal(e, 'REFUSED: this executor runs from AUTHORIZED only. This envelope is ' + String(e.state) + '.')); continue; }
  const intent = isObj(e.intent) ? e.intent : {};
  const br = String(intent.blast_radius || 'none');
  if (BR.indexOf(br) === -1 || BR.indexOf(br) > BR.indexOf(CEILING)) {
    out.push(refusal(e, 'REFUSED: blast radius ' + br + ' exceeds the ceiling ' + CEILING + ' of this executor. A Zapier call through this lane is a reversible write at most; anything wider needs a ruling, not a dispatch.')); continue;
  }
  // A call leaves the estate whatever the label says, so every envelope needs a
  // decided, unexpired grant. Two gates, one truth: the router checks the same.
  const appr = isObj(e.approval) ? e.approval : {};
  if (appr.state !== 'granted') { out.push(refusal(e, 'REFUSED: a Zapier call leaves the estate and needs approval.state granted; it is ' + String(appr.state || 'absent') + '. A card and a decision are required.')); continue; }
  const expMs = Date.parse(String(appr.expires_at || ''));
  if (Number.isNaN(expMs)) { out.push(refusal(e, 'REFUSED: approval.expires_at ' + String(appr.expires_at) + ' is not a readable time, so the grant cannot be trusted.')); continue; }
  if (expMs < Date.now()) { out.push(refusal(e, 'REFUSED: the approval expired at ' + String(appr.expires_at) + '. An expired grant is not a grant.')); continue; }
  // Single flight, best effort, the same rule as the Airtable Row Writer: the entry
  // report marks the ledger row execution.state running under this workflow's id
  // and a second pass inside ten minutes steps back. The mark lives in the ledger
  // row only and a router failure exit rewrites it away, so what actually stops a
  // second call is the call log this executor owns (devon_zapier_call_log), read
  // by idempotency key and intent id before every call.
  const ex = isObj(e.execution) ? e.execution : {};
  if (ex.state === 'running' && ex.workflow_id === $workflow.id) {
    const lockAge = Date.now() - Date.parse(String(e.updated_at || ''));
    if (Number.isNaN(lockAge) || lockAge < 10 * 60 * 1000) {
      out.push(refusal(e, 'REFUSED: another pass began this call at ' + String(e.updated_at) + ' (execution ' + String(ex.execution_id || 'unknown') + '); this pass steps back. The lock ages out ten minutes after a readable updated_at, and an unreadable one counts as held.')); continue;
    }
  }
  const idem = String(e.idempotency_key === undefined || e.idempotency_key === null ? '' : e.idempotency_key);
  if (idem.length < 8 || idem.length > 128 || /[\s'"\\{}]/.test(idem)) { out.push(refusal(e, 'REFUSED: idempotency_key must be 8 to 128 characters with no whitespace, quotes, braces or backslashes before this executor calls anything; it is stamped on the call log row verbatim and filtered on before every call.')); continue; }
  const p = isObj(intent.payload) ? intent.payload : {};
  if (isObj(p.editforge)) { out.push(refusal(e, 'REFUSED: this job carries an EditForge payload; renders go through the Build 07 handoff, not the Zapier executor.')); continue; }

  // The structural payload. Nothing below is guessed from the summary.
  const z = p.zapier;
  if (!isObj(z)) { out.push(refusal(e, 'REFUSED: no intent.payload.zapier object. This executor calls only what the job declares: { zapier: { tool, arguments } }.')); continue; }
  const tool = s(z.tool);
  const t = TOOLS[tool];
  if (!t) { out.push(refusal(e, 'REFUSED: tool ' + (tool || '(unnamed)') + ' is not on this executor\'s allowlist. Callable tools: ' + Object.keys(TOOLS).join(', ') + '. Adding one is a deliberate act in the executor and the vault, with the blast radius it really has, not a runtime decision.')); continue; }
  if (BR.indexOf(t.blast_radius) > BR.indexOf(br)) { out.push(refusal(e, 'REFUSED: tool ' + tool + ' is a ' + t.blast_radius + ' and this job declares ' + br + '. A job cannot run a tool wider than what its card described.')); continue; }
  const argsIn = (z.arguments === undefined || z.arguments === null) ? {} : z.arguments;
  if (!isObj(argsIn)) { out.push(refusal(e, 'REFUSED: intent.payload.zapier.arguments must be an object of argument name to value.')); continue; }
  const cleaned = cleanValue('arguments', argsIn, 0);
  if (!cleaned.ok) { out.push(refusal(e, 'REFUSED: ' + cleaned.bad + '. Nothing was called.')); continue; }
  const args = cleaned.value;
  const keys = Object.keys(args);
  const total = JSON.stringify(args).length;
  if (total > MAX_TOTAL) { out.push(refusal(e, 'REFUSED: arguments serialise to ' + total + ' characters, over the ' + MAX_TOTAL + ' limit. Nothing was called.')); continue; }
  const fp = fingerprint({ tool: tool, arguments: args });

  // The entry report carries the lock: execution running under this workflow.
  const locked = JSON.parse(JSON.stringify(e));
  locked.execution = Object.assign({}, ex, { state: 'running', executor: 'n8n', workflow_id: $workflow.id, execution_id: String($execution.id), started_at: ex.started_at || new Date().toISOString().replace(/\.\d{3}Z$/, 'Z') });
  out.push({ json: {
    refused: false, action: 'zapier.mcp', envelope: locked, intent_id: e.intent_id, from_state: 'AUTHORIZED', to_state: 'EXECUTING',
    idem: idem, area: s(e.area), blast_radius: br, summary: s(intent.summary),
    tool: tool, tool_blast_radius: t.blast_radius, tool_description: t.description,
    arguments: args, argument_keys: keys, argument_count: keys.length, fingerprint: fp,
    // A read whose outcome could not be read may be tried again; a write may not.
    retry_after_unknown: t.blast_radius === 'read',
    mcp_url: MCP_URL, protocol: PROTOCOL,
    init_body: { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: PROTOCOL, capabilities: {}, clientInfo: { name: 'devon-zapier-executor', version: '19' } } },
    call_body: { jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: tool, arguments: args } }
  } });
}
return out;
