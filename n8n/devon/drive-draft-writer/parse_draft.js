// Parses the Cerebras answer into the draft text. Nothing has been written when
// this node runs, so a refusal here costs nothing and a wrong guess costs a
// corrupted document in Tee's Drive that nobody reads before it lands.
//
// RULED BY TEE 2026-09-06, after two gauntlet cycles quarantined two different
// versions of this file in one night: STOP SCRUBBING, START REFUSING.
//
// Both quarantined versions tried to rewrite an em or en dash into what the
// author probably meant. Both were wrong, in ways only an executed test found:
//
//   v1 used \s on both sides of the dash class, and \s matches a newline, so a
//   dash opening a line ate the line break and a block of dialogue collapsed
//   into one run on line.
//
//   v2 narrowed that, then added a rule saying digits either side of a dash
//   mean a range. "The offer was 120 <em dash> 30% above my last one" became
//   "120-30%", inventing a number in career strategy content. Its fallback rule
//   deleted the dash and substituted nothing, so "Revenue grew 40% <em dash>
//   the biggest jump yet" ran the clause on, and a trailing dash, which is how
//   an interruption is written in a two character podcast, vanished silently.
//
// The pattern is the finding. A rule that decides what a dash MEANT is a guess,
// and a guess that lands unread in a script folder is worse than no draft. So
// this version keeps only the transformations that CANNOT change meaning, and
// refuses the draft outright when a dash is present. The lane retries, and the
// system prompt (validate_and_plan.js, the same repository) is what has to earn
// the pass.
//
// Refusing is affordable here because the model already honours this rule. The
// first live draft (job 01M1SN5X4ETKEPPCC4JT61TE5V, 2026-09-06T01:58:58Z)
// carried 25 escaped bullet markers, 9 escaped ordered markers and 10 non
// breaking hyphens, and ZERO em or en dashes. The prompt's dash instruction
// works; its "no markdown symbols" instruction is the one being ignored, and
// markdown symbols are exactly what the safe rules below remove.
//
// WHAT IS SAFE TO CHANGE, and why each one cannot alter meaning:
//   U+00A0 to a space         an invisible space becomes a visible one
//   U+00AD removed            a soft hyphen is invisible and advisory
//   U+2010 U+2011 to '-'      these ARE hyphens; only the code point changes
//   a fence line removed      the marker is markup, the code inside is kept
//   a leading '\' before a
//     list marker removed     the backslash is markdown escaping, not text
//   trailing space trimmed    whitespace at end of line carries nothing
//
// WHAT IS NOT TOUCHED, on purpose:
//   U+2212, the minus sign, is arithmetic. "the delta is <minus>5" survives.
//   U+2015 and U+2012 are neither an em nor an en dash. v2 folded them on
//   speculation and broke dialogue and phone numbers. Tee's rule names two
//   characters; this file acts on exactly those two.
//   Indentation inside a code sample. v2 had a "space before punctuation" rule
//   with no observed defect behind it, and it flattened every indented line.
//
// ORDER IS LOAD BEARING. Character normalisation runs BEFORE the escape strip,
// because HYPHENS turns "\<U+2010> First point" into "\- First point", which is
// the shape the escape strip is looking for. v2 ran them the other way round
// and the backslash reached Drive.
//
// The character classes are built with fromCharCode. Those code points are
// invisible in a diff, and a backslash u escape does not survive the round trip
// through the n8n API, so building them keeps this file and the live node byte
// identical and pure ASCII.
const NBSP = new RegExp(String.fromCharCode(0x00a0), 'g');
const SOFT_HYPHEN = new RegExp(String.fromCharCode(0x00ad), 'g');
const HYPHENS = new RegExp('[' + String.fromCharCode(0x2010, 0x2011) + ']', 'g');
// The two characters Tee's rule names, and nothing else.
const BANNED = new RegExp('[' + String.fromCharCode(0x2014, 0x2013) + ']', 'g');
// A fence on a line of its own. {3,} is greedy so a run of six backticks is
// consumed whole; v2 took three and left three behind, so a second pass would
// have produced a different document from the first.
const FENCE = /^[ \t]*`{3,}[A-Za-z0-9+#.-]*[ \t]*(?:\r?\n|$)/gm;
// The two markdown list markers the model actually escaped, at a line start,
// where a backslash can only be escaping a list marker.
const ESC_BULLET = /^([ \t]*)\\([-*+])(?=[ \t])/gm;
const ESC_ORDERED = /^([ \t]*\d+)\\(\.)(?=[ \t])/gm;

const FLOOR = 120;

const c = $('Check Existing').first().json;
const res = $input.first().json || {};
function refuse(reason) {
  return [{ json: { refused: true, outcome: 'refused', action: 'drive.draft',
    intent_id: c.intent_id, state: 'AUTHORIZED', reason: reason } }];
}

const code = res.statusCode;
if (code !== 200) {
  return refuse('REFUSED: the language lane answered HTTP ' + String(code || 'no response') + '; nothing was written. The next pass retries.');
}
const body = res.body || {};
const choice = (body.choices && body.choices[0]) || {};
// Type guard. v2 called String() on whatever came back, so a content array
// stringified to "[object Object]" and the refusal reported 2 words for a full
// answer. A shape this node cannot read is a fault in the lane, not a short
// draft, and it says so.
const content = choice.message && choice.message.content;
if (typeof content !== 'string') {
  return refuse('REFUSED: the language lane returned message.content as ' + (content === undefined ? 'nothing' : Array.isArray(content) ? 'an array' : typeof content) + ' rather than a string, so this pass cannot read the draft; nothing was written. The next pass retries.');
}
const raw = content.trim();

// Measured on what the lane returned, before any substitution, so the number in
// the refusal sentence is the number the lane actually produced.
const rawWords = raw.split(/\s+/).filter(Boolean).length;
if (rawWords < FLOOR) {
  return refuse('REFUSED: the language lane returned ' + rawWords + ' words, under the ' + FLOOR + ' word floor for a draft; nothing was written. The next pass retries.');
}

// Counted before the strip so the artifact records what the model actually did,
// which is the only signal that says whether the prompt is being honoured.
function count(s, re) { const m = s.match(re); return m ? m.length : 0; }
const fired = {
  nbsp: count(raw, NBSP),
  soft_hyphen: count(raw, SOFT_HYPHEN),
  unicode_hyphens: count(raw, HYPHENS),
  fences: count(raw, FENCE),
  escaped_bullets: count(raw, ESC_BULLET),
  escaped_ordered: count(raw, ESC_ORDERED)
};

const normalised = raw
  .replace(NBSP, ' ')
  .replace(SOFT_HYPHEN, '')
  .replace(HYPHENS, '-')
  .replace(ESC_BULLET, '$1$2')
  .replace(ESC_ORDERED, '$1$2')
  .replace(FENCE, '');

// trimEnd, not a regex, and the distinction is the whole point. v2 used
// /[ \t]+$/gm, which is quadratic on a run of spaces: 10k took 272ms, 80k took
// 14.9s, four times the cost per doubling, on input the model controls, so a
// repetition loop in a degenerate answer blocked the n8n worker for a minute
// instead of refusing. A greedy run followed by an anchor backtracks once per
// start position. Rewriting it as /[ \t\r]+$/ per line does NOT fix that, it
// just moves it, which is what the first attempt at this fix did. trimEnd is a
// native scan backwards from the end: linear, and it cannot backtrack at all.
const txt = normalised.split('\n').map(function (line) { return line.trimEnd(); }).join('\n').trim();

// THE RULING. Not a rewrite, a refusal. The reason names the count and shows one
// site with the character replaced by a label, so the retry has something to act
// on and this sentence does not itself carry the character Tee's rule forbids.
const banned = txt.match(BANNED);
if (banned) {
  const at = txt.search(BANNED);
  const from = Math.max(0, at - 45);
  const window = txt.slice(from, at + 45).replace(BANNED, ' [EM OR EN DASH] ').replace(/\s+/g, ' ').trim();
  return refuse('REFUSED: the draft contains ' + banned.length + ' em or en dash' + (banned.length === 1 ? '' : 'es') + ', which the house rule forbids and this executor will not rewrite. Rewriting one is a guess at what the sentence meant, and two earlier versions of this node corrupted numbers and deleted dialogue doing exactly that. Nothing was written. First site: "' + window + '". The next pass retries; the system prompt in Validate and Plan is what has to stop producing them.');
}

// Rechecked after normalisation. v2 measured only before, so an answer of 130
// lines of nothing but code fences scored 130 raw words, cleared the floor, and
// wrote a document whose body was the empty string.
const bodyWords = txt.split(/\s+/).filter(Boolean).length;
if (bodyWords < FLOOR) {
  return refuse('REFUSED: the lane returned ' + rawWords + ' words but only ' + bodyWords + ' survived removing markdown markup, under the ' + FLOOR + ' word floor; the answer was mostly markup. Nothing was written. The next pass retries.');
}

const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
const header = 'DEVON DRAFT. Job ' + c.intent_id + ', written ' + now + ' UTC by DEVON through drive.draft. A working draft for Tee to edit. Nothing in it has been published, sent, rendered or verified.\n\n';
const draftText = header + txt;

// draft_words is the length of the DOCUMENT, header included, because that is
// what lands in Drive and what the artifact claims. v2 counted the body only
// and understated every draft by the 28 words of the header it did not count.
return [{ json: Object.assign({}, c, {
  refused: false,
  outcome: 'written',
  draft_text: draftText,
  draft_words: draftText.split(/\s+/).filter(Boolean).length,
  draft_body_words: bodyWords,
  draft_lane_words: rawWords,
  draft_normalised: fired,
  draft_by: 'cerebras ' + String(body.model || 'gpt-oss-120b')
}) }];
