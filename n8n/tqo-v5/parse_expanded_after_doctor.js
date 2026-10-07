// Parse Expanded After Doctor. Same contract as Parse Expanded Script 2. The
// lengthened text runs after the doctor and the dash repair, so nothing reads
// it again but the gates. It is used only if it is longer, keeps every
// sentence of the doctored text verbatim and in order with the hook first and
// the close last, carries no dash, and adds no number, no number word and no
// capitalised name the doctored text did not carry (third critic, 2026-10-07:
// the first version checked digits only). Otherwise the doctored text goes on
// unchanged with the reason, and the gate fails it on the floor as before. A
// parse failure never costs the draft; a provider refusal throws, like the
// other expansion nodes, so the watchdog sees it.
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
const sent = (t) => (t.trim().match(/[^.!?]+[.!?]+|[^.!?]+$/g) || []).map(x => x.trim()).filter(Boolean);
const a = sent(old), b = sent(script);
if (a.slice(0, 2).join(' ') !== b.slice(0, 2).join(' ')) return keep('the hook changed');
if (a.length && a[a.length - 1] !== b[b.length - 1]) return keep('the last sentence changed');
if (b.filter(x => x === a[a.length - 1]).length > 1) return keep('the last sentence appears twice');
let at = 0;
for (const x of a) {
  const i = b.indexOf(x, at);
  if (i === -1) return keep('a sentence of the doctored text was changed or dropped: "' + x.slice(0, 80) + '"');
  at = i + 1;
}
if (/[—–]/.test(script)) return keep('it added an em or en dash');
const nums = (t) => new Set((t.match(/\d[\d,]*(?:\.\d+)?/g) || []).map(x => x.replace(/,/g, '')));
const had = nums(old);
const added = [...nums(script)].filter(n => !had.has(n));
if (added.length) return keep('it added figure(s) the doctored text did not carry: ' + added.slice(0, 8).join(', '));
const WORDS = /\b(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundreds?|thousands?|millions?|billions?|trillions?|percent|dozens?|half|third|thirds|quarter|quarters|majority)\b/gi;
const wordsIn = (t) => new Set((t.match(WORDS) || []).map(w => w.toLowerCase()));
const hadWords = wordsIn(old);
const newWords = [...wordsIn(script)].filter(w => !hadWords.has(w));
if (newWords.length) return keep('it added number word(s) the doctored text did not carry: ' + newWords.join(', '));
const names = (t) => new Set(sent(t).flatMap(x => x.split(/\s+/).slice(1)).map(w => w.replace(/^[^\w]+|[^\w]+$/g, '')).filter(w => /^[A-Z]/.test(w)));
const hadNames = names(old);
const newNames = [...names(script)].filter(w => !hadNames.has(w) && !/^(?:I|I'm|I've|I'll|I'd)$/.test(w));
if (newNames.length) return keep('it added name(s) the doctored text did not carry: ' + newNames.slice(0, 8).join(', '));

return [{ json: {
  ...base,
  script,
  expansion: String(base.expansion || '') + ', then a pass after the doctor to ' + words + ' words',
  expandedWords: words,
  lastFeedback: String(base.lastFeedback || '') + '\n\nLENGTH AFTER DOCTOR at ' + stamp + ': ' + before + ' to ' + words + ' words, every doctored sentence kept in order, no number, number word, name or dash added.'
} }];
