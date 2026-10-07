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
// Nothing of the doctored text may repeat more often than it did, so a
// lengthening cannot pad itself by doubling a sentence (fourth critic).
const tally = (xs) => xs.reduce((m, x) => m.set(x, (m.get(x) || 0) + 1), new Map());
const ta = tally(a), tb = tally(b);
for (const [x, n] of tb) if (ta.has(x) && n > ta.get(x)) return keep('a sentence of the doctored text appears more often: "' + x.slice(0, 80) + '"');
if (/[\u2012-\u2015]/.test(script)) return keep('it added a dash');
// Figures are counted, not just seen, so a number the doctored text carried
// once cannot be reused in a new sentence. Small number words count only in a
// ratio ("nine out of ten", "two in five"); every other number word counts
// wherever it stands.
const FIG = /\d[\d,]*(?:\.\d+)?|[\u00bc-\u00be\u2150-\u215e]|\b(?:one|two|three|four|five|six|seven|eight|nine|ten)(?=\s+(?:out of|in|of every|per)\s)|\b(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundreds?|thousands?|millions?|billions?|trillions?|percent|cent|pct|dozens?|half|halves|thirds?|quarters?|fourths?|fifths?|sixths?|sevenths?|eighths?|ninths?|tenths?|majority|twice|thrice|double|doubled|triple|tripled|quadrupled|halved)\b/gi;
const figs = (t) => tally((t.match(FIG) || []).map(x => x.toLowerCase().replace(/,/g, '')));
const fa = figs(old), fb = figs(script);
const more = [...fb].filter(([x, n]) => n > (fa.get(x) || 0)).map(([x]) => x);
if (more.length) return keep('it added figure(s) or number word(s) the doctored text did not carry, or carried fewer times: ' + more.slice(0, 8).join(', '));
// A new capitalised word is a name, wherever it stands. At the start of a
// sentence it is a name when the doctored text never uses the word at all,
// so "Amazon cut its managers" is refused and "This means" is not.
const tokens = (x) => x.split(/\s+/).map(w => w.replace(/^[^\w]+|[^\w']+$/g, '')).filter(Boolean);
const oldLower = new Set(tokens(old).map(w => w.toLowerCase()));
const hadNames = new Set(a.flatMap(x => tokens(x).slice(1)).filter(w => /^[A-Z]/.test(w)));
const SELF = /^(?:I|I'm|I've|I'll|I'd)$/;
const newNames = [];
for (const x of b) {
  if (ta.has(x)) continue;
  tokens(x).forEach((w, i) => {
    if (!/^[A-Z]/.test(w) || SELF.test(w)) return;
    const fresh = i === 0 ? !oldLower.has(w.toLowerCase()) : !hadNames.has(w);
    if (fresh && !newNames.includes(w)) newNames.push(w);
  });
}
if (newNames.length) return keep('it added name(s) the doctored text did not carry: ' + newNames.slice(0, 8).join(', '));

return [{ json: {
  ...base,
  script,
  expansion: String(base.expansion || '') + ', then a pass after the doctor to ' + words + ' words',
  expandedWords: words,
  lastFeedback: String(base.lastFeedback || '') + '\n\nLENGTH AFTER DOCTOR at ' + stamp + ': ' + before + ' to ' + words + ' words, every doctored sentence kept in order, no number, number word, name or dash added.'
} }];
