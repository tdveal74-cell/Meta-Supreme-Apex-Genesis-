// Parses the Cerebras answer into the draft text. Too little text refuses; a
// refusal here costs nothing because nothing has been written yet.
const c = $('Check Existing').first().json;
const res = $input.first().json || {};
const code = res.statusCode;
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: c.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
if (code !== 200) { return refuse('REFUSED: the language lane answered HTTP ' + String(code || 'no response') + '; nothing was written. The next pass retries.'); }
const body = res.body || {};
const choice = (body.choices && body.choices[0]) || {};
let txt = String((choice.message && choice.message.content) || '').trim();
txt = txt.replace(/```[a-z]*\n?/g, '').replace(/\s*[\u2014\u2013]\s*/g, ', ');
const words = txt.split(/\s+/).filter(Boolean).length;
if (words < 120) { return refuse('REFUSED: the language lane returned ' + words + ' words, under the 120 word floor for a draft; nothing was written. The next pass retries.'); }
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const header = 'DEVON DRAFT. Job ' + c.intent_id + ', written ' + now + ' UTC by DEVON through drive.draft. A working draft for Tee to edit. Nothing in it has been published, sent, rendered or verified.\n\n';
return [{ json: Object.assign({}, c, { draft_text: header + txt, draft_words: words, draft_by: 'cerebras ' + String(body.model || 'gpt-oss-120b') }) }];
