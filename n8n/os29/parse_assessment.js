// If the model fails or returns something unparseable, the change is still real.
// It is filed as unreviewed with the failure attached, because swallowing it
// would turn a detected policy change into silence - the one outcome this
// module exists to prevent.
const d = $('Build Assessment Prompt').first().json;
const out = $json;
let a = null, parseError = null;
try {
  // Truncation is not a parse problem, so name it rather than letting JSON.parse
  // report a mangled brace. Either way this lands in ASSESSMENT FAILED, which is
  // the fail-closed direction a policy sensor has to fail in.
  if (out.stop_reason === 'max_tokens' || (out.choices && out.choices[0] && out.choices[0].finish_reason === 'length')) {
    throw new Error('the response was truncated at the output ceiling');
  }
  // Cerebras returns the OpenAI chat shape, Anthropic returns content blocks.
  // Read both so this node survives a swap back without another edit.
  let raw = (out.choices && out.choices[0] && out.choices[0].message)
    ? String(out.choices[0].message.content == null ? '' : out.choices[0].message.content)
    : (out.content || []).filter(function (c) { return c.type === 'text'; }).map(function (c) { return c.text; }).join('');
  raw = String(raw).trim();
  if (!raw) throw new Error('the model returned an empty body');
  const s = raw.indexOf('{'), e = raw.lastIndexOf('}');
  a = JSON.parse(s === -1 ? raw : raw.slice(s, e + 1));
} catch (err) {
  parseError = String(err.message || err);
}
// gpt-oss-120b emits typographic hyphens in prose: probe execution 217 returned
// "non<U+2011>compliance" with a NON-BREAKING HYPHEN. U+2010, U+2011 and U+2212
// are the same character as an ASCII hyphen typographically, so folding them is
// lossless. Em and en dashes are deliberately NOT folded here. A dash between
// digits can be a range, and rewriting one invents a number that was never
// written. The system prompt asks the model not to emit those; if one lands it
// lands visible in a line a human reads, rather than silently rewritten.
const ascii = function (s) { return String(s == null ? '' : s).replace(/[\u2010\u2011\u2212]/g, '-'); };
const material = a ? a.material === true : null;
const stamp = new Date().toISOString();
let assessment;
if (a) {
  assessment = [
    stamp + ' - ' + (material ? 'MATERIAL' : 'not material') + ' (confidence: ' + (a.confidence || '?') + ')',
    '',
    a.headline || '(no headline)',
    '',
    'affects: ' + (Array.isArray(a.affects) && a.affects.length ? a.affects.join(', ') : 'none'),
    'OS 28 gate: ' + (a.gate || 'none'),
    'action: ' + (a.action || 'none'),
    '',
    'source: ' + d.source,
    d.url
  ].join('\n');
} else {
  assessment = [
    stamp + ' - CHANGE DETECTED, ASSESSMENT FAILED',
    '',
    'The page text moved but the assessment could not be read, so this needs a human look.',
    parseError ? ('parse error: ' + parseError) : 'no response from the model',
    '',
    'source: ' + d.source,
    d.url
  ].join('\n');
}
return [{ json: Object.assign({}, d, { material: material, assessment: ascii(assessment), headline: ascii(a ? (a.headline || '') : 'assessment failed'), affects: ascii(a && Array.isArray(a.affects) ? a.affects.join(', ') : ''), gate: ascii(a ? (a.gate || 'none') : 'unknown'), action: ascii(a ? (a.action || 'none') : 'read the page yourself') }) }];
