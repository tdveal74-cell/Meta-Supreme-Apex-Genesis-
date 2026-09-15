// Reads the tools/call answer. Three outcomes, each written to the call log row by
// the next node: succeeded (HTTP 200, a JSON-RPC result, isError not set), refused
// (the server answered with a JSON-RPC error or an isError result, so Zapier said
// no and nothing ran; a retry is safe), unknown (no readable answer at all, a
// timeout or a proxy page; the action may or may not have run, and only a read is
// tried again). The arguments are never written anywhere; the result text is kept
// to a head of 600 characters, enough for the verify card and the log.
const v = $('Validate and Plan').first().json;
const r = $input.first().json || {};
function rpc(raw) {
  let msg = null;
  try { msg = JSON.parse(raw); } catch (e) {
    const lines = String(raw).split('\n').filter(function (l) { return l.indexOf('data:') === 0; });
    for (const l of lines) { try { msg = JSON.parse(l.slice(5).trim()); } catch (e2) { } }
  }
  return msg;
}
const raw = typeof r.data === 'string' ? r.data : (typeof r.body === 'string' ? r.body : JSON.stringify(r.data || r.body || {}));
const msg = rpc(raw);
const code = (typeof r.statusCode === 'number') ? r.statusCode : null;
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const result = (msg && msg.result && typeof msg.result === 'object') ? msg.result : null;
const content = (result && Array.isArray(result.content)) ? result.content : [];
const text = content.map(function (c) { return (c && typeof c.text === 'string') ? c.text : ''; }).filter(function (t) { return t; }).join('\n');
const head = text.replace(/\s+/g, ' ').trim().slice(0, 600);
const urlMatch = text.match(/https?:\/\/[^\s"'<>]+/);
function done(state, error) {
  return [{ json: {
    refused: state !== 'succeeded', outcome: state === 'succeeded' ? 'succeeded' : 'refused', action: 'zapier.mcp', intent_id: v.intent_id, state: 'AUTHORIZED',
    call_state: state, call_status: code, finished_at: now, result_head: head, error: error,
    artifact_uri: (state === 'succeeded' && urlMatch) ? urlMatch[0] : '', content_count: content.length,
    reason: state === 'succeeded' ? '' : ('REFUSED: ' + error)
  } }];
}
if (msg === null) {
  return done('unknown', 'the Zapier MCP server gave no readable answer to tools/call (HTTP ' + String(code || 'no response') + '). Whether tool ' + v.tool + ' ran is unknown' + (v.retry_after_unknown ? '; it is a read, so the next pass tries again.' : '; it is a ' + v.tool_blast_radius + ', so it is not tried again until a human reads Zapier\'s history and closes the call log row.'));
}
if (msg.error) {
  return done('refused', 'the Zapier MCP server refused tools/call for ' + v.tool + ' (JSON-RPC error ' + String(msg.error.code || '') + ': ' + String(msg.error.message || '').replace(/\s+/g, ' ').slice(0, 300) + '). Nothing ran; the fix is in the job or in the Zapier configuration, and the next pass retries.');
}
if (code !== 200 || result === null) {
  return done('unknown', 'the Zapier MCP server answered HTTP ' + String(code || 'no response') + ' without a JSON-RPC result for ' + v.tool + '. Whether it ran is unknown' + (v.retry_after_unknown ? '; it is a read, so the next pass tries again.' : '; it is a ' + v.tool_blast_radius + ', so it is not tried again until a human reads Zapier\'s history and closes the call log row.'));
}
if (result.isError === true) {
  return done('refused', 'tool ' + v.tool + ' returned isError: ' + (head || 'no text') + '. Zapier reports the action did not complete; the next pass retries once the cause named there is fixed.');
}
return done('succeeded', '');
