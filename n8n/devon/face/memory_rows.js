// Two rows per turn: what Tee said and what DEVON answered. The chat log carries
// no tokens and no secrets; it is the memory the next turn reads back.
let p = {};
try { p = $('Attach Receipt').first().json || {}; } catch (e) { p = $('Parse Reply').first().json || {}; }
const at = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
return [
  { json: { session_id: String(p.session_id || ''), role: 'user', content: String(p.chat_input || '').slice(0, 4000), at: at, action: '', intent_id: '', job: '' } },
  { json: { session_id: String(p.session_id || ''), role: 'assistant', content: String(p.reply || '').slice(0, 6000), at: at, action: String(p.action || 'none'), intent_id: String(p.intent_id || ''), job: p.job ? JSON.stringify(p.job).slice(0, 4000) : '' } }
];
