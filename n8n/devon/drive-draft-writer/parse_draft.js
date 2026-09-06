// Parses the Cerebras answer into the draft text. Too little text refuses; a
// refusal here costs nothing because nothing has been written yet.
//
// The normalise chain exists because the model writes for a markdown reader even
// when the system prompt asks for plain text. The first live draft (job
// 01M1SN5X4ETKEPPCC4JT61TE5V, written 2026-09-06T01:58:58Z) reached Tee's Drive
// carrying a literal backslash on every list line and non breaking hyphens
// inside compound words: 25 bullet markers, 9 ordered markers, 10 hyphens, and
// zero em or en dashes, so the one rule the model already honoured was Tee's.
//
// REWRITTEN 2026-09-06 after a gauntlet cycle reproduced four ways the first
// version destroyed legitimate text. Every rule below is now the narrowest one
// that fixes an OBSERVED defect. The first version widened on speculation and
// each widening cost something real:
//
//   The dash class used \s on both sides, and \s matches a newline, so a dash
//   opening a line swallowed the line break. A block of dialogue collapsed into
//   one run-on line and so did a dash bulleted checklist. Drafts land in a
//   show's 01_SCRIPTS folder, which is exactly where a line opening dash lives.
//   The class also gained U+2012, the figure dash, which exists for numerals,
//   so 555<figure dash>0100 became "555, 0100"; and U+2015, the horizontal bar,
//   which is the character used to open a line of dialogue. Neither appeared in
//   the reported defect. Both are gone, the class is back to the em and en dash
//   Tee's rule actually names, and no rule may now cross a newline.
//
//   The escape strip ran over the whole document against a wide punctuation
//   class, so a regex written in prose lost its meaning (\. became .), LaTeX
//   delimiters were stripped to bare brackets, and a Windows path lost its
//   separator whenever the next segment opened with punctuation. The observed
//   defect was list markers alone, so that is all it strips now, anchored to
//   the start of a line where a markdown list marker is the only thing a
//   backslash can be escaping.
//
//   The code fence rule ate the lowercase run after an inline triple backtick,
//   deleting a word outright, and left an uppercase language tag behind as
//   stray prose. It now removes a fence only when the fence is its own line.
//
// Not folded, on purpose. U+2212 is the minus sign: it renders like a dash but
// it is arithmetic, and "the delta is <minus>5" must survive. Tee's rule names
// the em dash and the en dash, and this is neither.
//
// The character classes are built with fromCharCode. Those code points are
// invisible or near enough on screen, so a literal class cannot be reviewed in
// a diff, and a backslash u escape does not survive the round trip through the
// n8n API. Building them keeps this file and the live node byte identical and
// pure ASCII.
const EM_EN = String.fromCharCode(0x2014, 0x2013);
const SOFT_HYPHEN = new RegExp(String.fromCharCode(0x00ad), 'g');
const HYPHENS = new RegExp('[' + String.fromCharCode(0x2010, 0x2011) + ']', 'g');
// A fence on a line of its own, language tag or not. Never mid line.
const FENCE = /^[ \t]*```[A-Za-z0-9+#.-]*[ \t]*\r?\n?/gm;
// The two markdown list markers the model actually escaped, at a line start.
const ESC_BULLET = /^([ \t]*)\\([-*+])(?=[ \t])/gm;
const ESC_ORDERED = /^([ \t]*\d+)\\(\.)(?=[ \t])/gm;
// Four dash rules, none of which may cross a newline: [ \t] never matches one.
// A line opening dash is a bullet, so it becomes one and the line survives.
const DASH_LINE = new RegExp('^[ \\t]*[' + EM_EN + '][ \\t]*', 'gm');
// Digits on both sides are a range whether or not the dash is spaced, so it
// keeps a hyphen. A comma turns "pages 10 to 20" into two page numbers, which
// is the same class of damage as the figure dash removed above.
const DASH_NUM_RANGE = new RegExp('(\\d)[ \\t]*[' + EM_EN + '][ \\t]*(?=\\d)', 'g');
// Spaced between words is the parenthetical use, and a comma carries it.
const DASH_SPACED = new RegExp('([A-Za-z0-9,;:)\\]}"\'])[ \\t]+[' + EM_EN + '][ \\t]+(?=[A-Za-z0-9("\'\\[{])', 'g');
// Tight between alphanumerics is a range or a compound: 1914<dash>1918, so a
// hyphen keeps the meaning where a comma would split it into two numbers.
const DASH_TIGHT = new RegExp('([A-Za-z0-9])[' + EM_EN + '](?=[A-Za-z0-9])', 'g');
// Anything still standing is a stray. Drop it rather than let it reach Drive.
const DASH_REST = new RegExp('[ \\t]*[' + EM_EN + '][ \\t]*', 'g');
const SPACE_BEFORE_PUNCT = /[ \t]+([.,;:!?])/g;
const TRAILING_SPACE = /[ \t]+$/gm;

const c = $('Check Existing').first().json;
const res = $input.first().json || {};
const code = res.statusCode;
function refuse(reason) { return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft', intent_id: c.intent_id, state: 'AUTHORIZED', reason: reason } }]; }
if (code !== 200) { return refuse('REFUSED: the language lane answered HTTP ' + String(code || 'no response') + '; nothing was written. The next pass retries.'); }
const body = res.body || {};
const choice = (body.choices && body.choices[0]) || {};
const raw = String((choice.message && choice.message.content) || '').trim();

// The floor is measured on what the lane returned, before any substitution.
// The first version measured after, and the substitutions move the count in
// both directions: a spaced dash becomes a comma and loses a token, a tight one
// gains one, a fence ate a word. A 119 word answer was accepted while the
// refusal reported 122, and a 122 word answer was refused as 119. The number in
// the refusal sentence is now the number the lane actually produced.
const rawWords = raw.split(/\s+/).filter(Boolean).length;
if (rawWords < 120) { return refuse('REFUSED: the language lane returned ' + rawWords + ' words, under the 120 word floor for a draft; nothing was written. The next pass retries.'); }

const txt = raw
  .replace(FENCE, '')
  .replace(ESC_BULLET, '$1$2')
  .replace(ESC_ORDERED, '$1$2')
  .replace(SOFT_HYPHEN, '')
  .replace(HYPHENS, '-')
  .replace(DASH_LINE, '- ')
  .replace(DASH_NUM_RANGE, '$1-')
  .replace(DASH_SPACED, '$1, ')
  .replace(DASH_TIGHT, '$1-')
  .replace(DASH_REST, ' ')
  .replace(SPACE_BEFORE_PUNCT, '$1')
  .replace(TRAILING_SPACE, '');

// The document's own length, which is what the artifact reports. It is not
// rawWords: the gate above answers "did the lane write enough", this answers
// "how long is the thing in Tee's Drive". Both are true and they differ.
const words = txt.split(/\s+/).filter(Boolean).length;
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const header = 'DEVON DRAFT. Job ' + c.intent_id + ', written ' + now + ' UTC by DEVON through drive.draft. A working draft for Tee to edit. Nothing in it has been published, sent, rendered or verified.\n\n';
return [{ json: Object.assign({}, c, { draft_text: header + txt, draft_words: words, draft_lane_words: rawWords, draft_by: 'cerebras ' + String(body.model || 'gpt-oss-120b') }) }];
