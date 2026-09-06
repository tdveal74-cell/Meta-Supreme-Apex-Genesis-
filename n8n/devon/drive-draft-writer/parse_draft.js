// Parses the Cerebras answer into the draft text. Too little text refuses; a
// refusal here costs nothing because nothing has been written yet.
//
// The normalise chain exists because the model writes for a markdown reader even
// when the system prompt asks for plain text. The first live draft (job
// 01M1SN5X4ETKEPPCC4JT61TE5V, written 2026-09-06T01:58:58Z) reached Tee's Drive
// carrying a literal backslash on every list line, "\\- Brief reminder" and
// "1\\. Receipts show", and non breaking hyphens inside compound words. Both are
// cosmetic, both are visible the moment the document opens, and neither is
// something a human should clean by hand on every draft. Order matters: code
// fences, then markdown escapes, then hyphen variants to a plain hyphen, then
// true dashes to a comma, which is Tee's hard rule and was the only one of the
// four the model already honoured. A backslash before anything outside that
// punctuation class, a Windows path for instance, survives untouched.
//
// The two character classes are built with fromCharCode rather than written out.
// U+2010 and U+2011 are indistinguishable from a hyphen on screen and U+2012 and
// U+2015 from a dash, so a literal class is unreviewable in a diff, and a backslash
// u escape does not survive the round trip through the n8n API intact. Building
// them keeps this file and the live node byte identical and pure ASCII.
const HYPHENS = new RegExp('[' + String.fromCharCode(0x2010, 0x2011) + ']', 'g');
const DASHES = new RegExp('\\s*[' + String.fromCharCode(0x2012, 0x2013, 0x2014, 0x2015) + ']\\s*', 'g');
const c = $('Check Existing').first().json;
const res = $input.first().json || {};
const code = res.statusCode;
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: c.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
if (code !== 200) { return refuse('REFUSED: the language lane answered HTTP ' + String(code || 'no response') + '; nothing was written. The next pass retries.'); }
const body = res.body || {};
const choice = (body.choices && body.choices[0]) || {};
let txt = String((choice.message && choice.message.content) || '').trim();
txt = txt
  .replace(/```[a-z]*\n?/g, '')
  .replace(/\\([-.*_#+>~`!|{}()\[\]])/g, '$1')
  .replace(HYPHENS, '-')
  .replace(DASHES, ', ');
const words = txt.split(/\s+/).filter(Boolean).length;
if (words < 120) { return refuse('REFUSED: the language lane returned ' + words + ' words, under the 120 word floor for a draft; nothing was written. The next pass retries.'); }
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const header = 'DEVON DRAFT. Job ' + c.intent_id + ', written ' + now + ' UTC by DEVON through drive.draft. A working draft for Tee to edit. Nothing in it has been published, sent, rendered or verified.\n\n';
return [{ json: Object.assign({}, c, { draft_text: header + txt, draft_words: words, draft_by: 'cerebras ' + String(body.model || 'gpt-oss-120b') }) }];
