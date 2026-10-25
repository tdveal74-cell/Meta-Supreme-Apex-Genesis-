// Doctor Sources, ruled by Tee 2026-10-07 with the Sources Rule: the doctor sees
// the approved sources, so it keeps a sourced figure and cuts any other. Both
// shows, NCO from the same day's second ruling.
const row = $('One Idea at a Time').first().json;
const j = $input.first().json;
if (!j.claudeBody) return [{ json: j }];
let list = [];
try { const l = JSON.parse(String(row.sources || '')); if (Array.isArray(l)) list = l.filter(x => x && x.url && x.quote); } catch (e) { list = []; }
const block = list.length
  ? 'APPROVED SOURCES (the only figures and named sources that may stand):\n' + list.map((s, i) => '[S' + (i + 1) + '] ' + (s.origin || s.publisher) + ', reported by ' + s.publisher + ': "' + (s.quote_text || s.quote) + '"').join('\n')
  : 'APPROVED SOURCES: none. No figure, percentage, dollar amount or named study may stand.';
const rule = 'SOURCES: a figure, percentage, dollar amount or named study that is not in APPROVED SOURCES is invented. Cut it or make the point without it. Never change a sourced figure or the year it belongs to.';
const cb = j.claudeBody;
const msgs = (cb.messages || []).slice();
if (msgs.length) msgs[0] = { ...msgs[0], content: block + '\n\n' + String(msgs[0].content || '') };
return [{ json: { ...j, claudeBody: { ...cb, system: String(cb.system || '') + '\n' + rule, messages: msgs } } }];
