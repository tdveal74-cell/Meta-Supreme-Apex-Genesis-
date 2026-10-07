// Parse Expanded After Doctor. Same contract as Parse Expanded Script 2. The
// lengthened text is used only if it is longer, keeps the first two sentences
// and the last sentence verbatim, and carries no number the doctored text did
// not. Otherwise the doctored text goes on unchanged with the reason, and the
// gate fails it on the floor as before. A failed pass never costs the draft.
const prev = $('Script: Short After Doctor?').first().json;
const { expandBody, needsExpansion3, shortAfterDoctorWords, ...base } = prev;
const before = Number(shortAfterDoctorWords) || 0;
const stamp = new Date().toISOString();
const keep = (reason) => [{ json: { ...base, lastFeedback: String(base.lastFeedback || '') + '\n\nLENGTH AFTER DOCTOR at ' + stamp + ': kept at ' + before + ' words, ' + reason } }];

const out = $json || {};
if (out.choices?.[0]?.finish_reason === 'length') return keep('the expansion was truncated at the token ceiling');
let text = out.choices?.[0]?.message ? String(out.choices[0].message.content ?? '') : '';
if (!text.trim()) return keep('no text returned');
text = text.replace(/```json/gi, '```');
const s0 = text.indexOf('{'), e0 = text.lastIndexOf('}');
if (s0 === -1 || e0 === -1) return keep('not a JSON object');
let parsed;
try { parsed = JSON.parse(text.slice(s0, e0 + 1)); } catch (e) { return keep('JSON did not parse: ' + e.message); }

const old = String(base.script || '');
const script = String(parsed.script || '');
const words = script.split(/\s+/).filter(Boolean).length;
if (words <= before) return keep('came back at ' + words + ' words, no longer');
const sent = (t) => (t.trim().match(/[^.!?]+[.!?]+|[^.!?]+$/g) || []).map(x => x.trim());
const a = sent(old), b = sent(script);
if (a.slice(0, 2).join(' ') !== b.slice(0, 2).join(' ')) return keep('the hook changed');
if (a.length && a[a.length - 1] !== b[b.length - 1]) return keep('the last sentence changed');
const nums = (t) => new Set((t.match(/\d[\d,]*(?:\.\d+)?/g) || []).map(x => x.replace(/,/g, '')));
const had = nums(old);
const added = [...nums(script)].filter(n => !had.has(n));
if (added.length) return keep('it added figure(s) the doctored text did not carry: ' + added.slice(0, 8).join(', '));

return [{ json: {
  ...base,
  script,
  expansion: String(base.expansion || '') + ', then a pass after the doctor to ' + words + ' words',
  expandedWords: words,
  lastFeedback: String(base.lastFeedback || '') + '\n\nLENGTH AFTER DOCTOR at ' + stamp + ': ' + before + ' to ' + words + ' words, hook and close kept, no figure added.'
} }];
