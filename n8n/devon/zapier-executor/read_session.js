// Reads the initialize answer. The Zapier MCP server issues an mcp-session-id
// header on a 200 and frames its JSON-RPC reply as server sent events; nothing is
// called without that id. initialize itself has no side effect, so a failure here
// is refused as data with the status and whatever the server said, and the next
// pass tries again. The session id is used for one tools/call and then dropped.
const v = $('Validate and Plan').first().json;
const r = $input.first().json || {};
const h = r.headers || {};
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
const sid = String(h['mcp-session-id'] || h['Mcp-Session-Id'] || '');
const serverName = (msg && msg.result && msg.result.serverInfo) ? String(msg.result.serverInfo.name || '') : '';
const err = (msg && msg.error) ? (String(msg.error.code || '') + ' ' + String(msg.error.message || '')).trim() : '';
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'zapier.mcp', intent_id: v.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
if (code !== 200) { return refuse('REFUSED: the Zapier MCP server did not accept initialize (HTTP ' + String(code || 'no response') + (err ? ', ' + err : '') + '). Nothing was called; the next pass retries. If this repeats, the Zapier MCP credential on n8n is the first thing to check.'); }
if (!sid) { return refuse('REFUSED: the Zapier MCP server answered initialize with HTTP 200 and no mcp-session-id header, so no call can be made inside a session. Nothing was called; the next pass retries.'); }
return [{ json: { refused: false, intent_id: v.intent_id, session_id: sid, init_status: code, server_name: serverName, protocol_version: (msg && msg.result) ? String(msg.result.protocolVersion || '') : '' } }];
