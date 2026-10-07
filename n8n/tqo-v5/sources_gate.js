// Sources Gate, ruled by Tee 2026-10-07: the gate refuses any figure that is not
// in the row's approved sources. Measured, never judged. Every numeral in the
// script must appear in a source quote or claim, except counts of ten or under
// and a year the episode idea names, and a figure written in words must appear
// in the sources in the same words. A sentence that says according to someone
// must name an approved origin or publisher, and so must a name followed by
// found, reported, estimated or predicts. No unnamed person or organisation may
// be cited as a source, as in an interview with a senior HR director or a
// consulting firm that reported. Both shows, NCO from the same day's second
// ruling. A failure lands as Error with the reason in qc_findings, like every
// other gate failure.
const d = $input.first().json;
const row = $('One Idea at a Time').first().json;
let list = [];
try { const l = JSON.parse(String(row.sources || '')); if (Array.isArray(l)) list = l.filter(x => x && x.url && x.quote); } catch (e) { list = []; }
// Numbers are read from each source's clean quote_text and its claim, never
// the raw quote: a raw quote can carry a markdown link, and a URL like
// .../2024-03-15/...-30-of-... put 30, 03, 15 and 2024 into the sourced set,
// which let "30 minutes" through in execution 2351 (found by the critic).
const unlink = (t) => String(t || '').replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
const sourceText = list.map(s => unlink(s.quote_text || s.quote) + ' ' + String(s.claim || '')).join(' ');
// A figure is the numeral with its unit: a dollar sign, a percent in any
// spelling, or a magnitude. "41 million" is not "41", so a sourced 41 percent
// cannot lend itself to an invented 41 million (third critic, 2026-10-07).
const NUM = /\$?\d[\d,]*(?:\.\d+)?(?:\s?%|\s?(?:percent|per cent)\b|\s?(?:thousand|million|billion|trillion)\b|[KMB]\b)?/gi;
const MAG = /(?:\s?(?:thousand|million|billion|trillion)|[KMB])$/i;
const magOf = (t) => { const m = MAG.exec(t); return m ? m[0].trim()[0].toUpperCase() : ''; };
const bare = (t) => t.replace(MAG, '').replace(/\s?(?:%|percent|per cent)$/i, '').replace(/[$,%]/g, '').replace(/\.$/, '');
const unit = (t) => (/^\$/.test(t) ? '$' : '') + bare(t) + (/(?:%|percent|per cent)$/i.test(t) ? '%' : '') + magOf(t);
const sourcedBare = new Set((sourceText.match(NUM) || []).map(bare));
const sourcedUnit = new Set((sourceText.match(NUM) || []).map(unit));
const brief = new Set(([row.topic, row.angle, row.idea, row.video_title].join(' ').match(NUM) || []).map(bare));
const script = String(d.script || '');
const unsourced = [];
const flag = (shown) => { if (!unsourced.includes(shown)) unsourced.push(shown); };
// Military identifiers are names, not figures, ruled by Tee 2026-10-07 for NCO
// Forge prose, and blanked before the numeral scan only. Each pattern is
// narrow on purpose, because the first version blanked "VA 70" out of "VA 70%"
// and "1500" out of "1500 hours to finish" (third critic, 2026-10-07):
//   a form number written with its hyphen or the word Form: DD-214, DA Form 2166-9;
//   a 24 hour time after at, until, till, before, after or from, with its
//   leading zero (at 0600) or with hours (after 1800 hours); by takes only the
//   leading zero form, so "by 2030 hours" stays a year;
//   a unit ordinal followed by a unit noun: the 101st Airborne, 82nd Division.
// Nothing touching a percent, a decimal, a thousands comma or a magnitude is
// ever blanked. A bare ordinal or an MOS code (11B reads as eleven billion)
// fails closed to Error for Tee to clear.
const NOT_A_FIGURE = '(?![.,]\\d)(?!\\s*(?:%|percent|per cent|thousand|million|billion))';
const UNIT_NOUN = '(?:Airborne|Infantry|Division|Brigade|Battalion|Regiment|Cavalry|Armored|Marine|Marines|Fighter|Wing|Squadron|Fleet|Corps|Army|Ranger|Rangers|Signal|Engineer|Engineers|Aviation|Mountain|Expeditionary|Artillery|Sustainment|Special|MEU|BCT|SFG|ID)';
const MILITARY = [
  new RegExp('\\b(?:DD|DA|SF|VA|AF|NAVPERS|NAVMC|OPNAV)(?:-|\\s+Form\\s+)\\d+(?:-\\d+)*\\b' + NOT_A_FIGURE, 'g'),
  new RegExp('(?<=\\b(?:[Aa]t|[Bb]y|[Uu]ntil|[Tt]ill|[Bb]efore|[Aa]fter|[Ff]rom)\\s)0\\d[0-5]\\d\\b' + NOT_A_FIGURE, 'g'),
  new RegExp('(?<=\\b(?:[Aa]t|[Uu]ntil|[Tt]ill|[Bb]efore|[Aa]fter|[Ff]rom)\\s)(?:1\\d|2[0-3])[0-5]\\d(?=\\s(?:hours|hrs)\\b)', 'g'),
  new RegExp('\\b\\d{1,3}(?:st|nd|rd|th)\\b(?=\\s(?:[A-Z][a-z]+\\s)?' + UNIT_NOUN + '\\b)', 'g')
];
const blankMilitary = (t) => MILITARY.reduce((a, re) => a.replace(re, (m) => ' '.repeat(m.length)), t);
const numText = blankMilitary(script);
for (const raw of (numText.match(NUM) || [])) {
  const k = bare(raw);
  const n = Number(k);
  const withUnit = /[$%]|percent|per cent/i.test(raw) || MAG.test(raw);
  if (withUnit ? sourcedUnit.has(unit(raw)) : sourcedBare.has(k)) continue;
  if (!withUnit && Number.isInteger(n) && n <= 10) continue;
  if (/^(19|20)\d\d$/.test(k) && brief.has(k)) continue;
  flag(raw.replace(/[,.]+$/, ''));
}
// Figures written as words. A spelled out percentage, a magnitude, a fraction
// or an "N in M" must appear in the sources in the same words.
const flat = (t) => String(t || '').toLowerCase().replace(/[-‐‑]/g, ' ').replace(/\s+/g, ' ');
const sourceFlat = flat(sourceText);
const W = '(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|a hundred)';
const SPELLED = new RegExp('\\b(?:' + W + '[ -]?){1,3}(?:percent|hundred|thousand|million|billion)\\b|\\b(?:one|two|three|four)[ -](?:thirds?|quarters?|fifths?|tenths?)\\b|\\b' + W + ' in ' + W + '\\b', 'gi');
// A count of eleven or more written in words is a figure too: "Twelve
// companies cut managers" passed every version before this one.
const TEENS = '(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)';
const SPELLED_COUNT = new RegExp('\\b' + TEENS + '(?:[ -](?:one|two|three|four|five|six|seven|eight|nine))?\\b', 'gi');
for (const m of (script.match(SPELLED_COUNT) || [])) {
  if (!sourceFlat.includes(flat(m))) flag(m.trim());
}
for (const m of (script.match(SPELLED) || [])) {
  if (!sourceFlat.includes(flat(m))) flag(m.trim());
}
const names = list.map(s => (String(s.origin || '') + ' ' + String(s.publisher || '')).toLowerCase()).join(' | ');
const strangers = [];
const stranger = (name) => { const w = name.replace(/['.]s?$/, '').toLowerCase(); if (!names.includes(w) && !strangers.includes(name)) strangers.push(name); };
// Read one sentence at a time, so an approved name ending one sentence cannot
// carry an unapproved name in the next one past the check (found by the second
// critic, 2026-10-07: "according to Gallup. Microsoft found that").
const sentences = script.split(/(?<=[.!?])\s+/);
const ATTR = /\b[Aa]ccording to (?:the |a |an )?(?:[a-z]+ ){0,2}([A-Z][\w&.'-]*)/g;
let m;
for (const t of sentences) { ATTR.lastIndex = 0; while ((m = ATTR.exec(t))) stranger(m[1]); }
const COMMON = /^(?:It|This|That|These|Those|He|She|They|We|You|I|The|A|An|One|Each|Every|Most|Some|Our|Your|Their|His|Her|Its|What|Which|Who|Nobody|Everyone|Research|Data|AI|More|Less|Fewer|Many|Few|All|Both|Here|There|Today|Now|But|And|So|If|When|Then|Even|Still|Also|Leaders|Managers|Companies|Teams|Workers|Employers)$/;
const SAID = /\b([A-Z][\w&.'-]+)(?: [A-Z][\w&'-]+){0,3} (?:found|finds|reported|estimated|estimates|predicted|predicts|projected|surveyed)\b/g;
for (const t of sentences) { SAID.lastIndex = 0; while ((m = SAID.exec(t))) { if (!COMMON.test(m[1])) stranger(m[1]); } }
// A group with no name standing in for a source, as in "managers who applied
// this report that", which row 46 carried past both gates. A sentence that
// names an approved origin is left to the checks above.
const GROUP = /\b(?:managers|leaders|companies|employers|teams|workers|professionals|people|users|clients|veterans|soldiers|recruiters|executives|organizations|organisations|readers|viewers)\b[^.!?]{0,90}?\b(?:report|reported|say|said|find|found|tell|told|agree|agreed)\s+that\b/i;
// A source counts as named only as a whole word in its own capitals: the verb
// "ramp" is not the publisher Ramp (third critic, 2026-10-07).
const esc = (x) => String(x).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const approved = (t) => list.some(s => [s.origin, s.publisher].some(n => n && new RegExp('(?<![\\w])' + esc(n) + '(?![\\w])').test(t)));
const UNNAMED = /\b(?:interview|conversation|call|chat|discussion|meeting) with (?:a|an|one|several|some|two|three) (?:[\w-]+ ){0,4}(?:director|manager|executive|leader|officer|founder|employee|worker|analyst|engineer|consultant|recruiter|professional)s?\b/i;
const UNNAMED_ORG = /\b(?:[Aa]n?|[Oo]ne|[Ss]everal|[Ss]ome|[Mm]any) (?:[a-z][\w-]* ){0,3}(?:firm|company|companies|bank|retailer|startup|employer|organization|organisation|study|studies|survey|report|analysis|case)s?\b(?= (?:reported|found|showed|shows|says|said|indicated|indicates|estimated|revealed|noted|cut|saw|told))/;
// A projection stated as fact. A sentence about the future that carries a
// figure must name an approved origin, because a figure the sources hold as a
// count of the past can be restated as a forecast nobody made (ruled by Tee
// 2026-10-07, the gap the second critic graded open).
const FUTURE = /\b(?:will|won't|shall|going to|could|may|might|likely to|expected to|projected to|forecast to|set to|on track to|next (?:year|month|quarter|decade)|within (?:a|the next) (?:year|decade)|by (?:19|20)\d\d|by the end of)\b|\w'll\b/i;
const FRACTION = /\b(?:half of|(?:a|one)[ -]third of|one[ -]third|(?:a|one)[ -]quarter of|three[ -]quarters of|two[ -]thirds of|one in (?:two|three|four|five|six|seven|eight|nine|ten|\d+))\b/i;
const hasFigure = (t) => FRACTION.test(t) || (t.match(SPELLED_COUNT) || []).length > 0 || (blankMilitary(t).replace(/\b(?:19|20)\d\d\b/g, '').match(NUM) || []).some(r => /[$%]|percent|per cent/i.test(r) || MAG.test(r) || Number(bare(r)) > 10);
const projections = sentences.filter(t => FUTURE.test(t) && hasFigure(t) && !approved(t)).map(t => '"' + t.trim().slice(0, 140) + '"');
const unnamed = sentences.filter(t => UNNAMED.test(t) || UNNAMED_ORG.test(t) || (GROUP.test(t) && !approved(t))).map(t => '"' + t.trim().slice(0, 140) + '"');
const extra = [];
if (unnamed.length) extra.push('evidence, an unnamed person or organisation cited as a source: ' + unnamed.join(' '));
if (projections.length) extra.push('sources, a projection with a figure and no approved source named: ' + projections.join(' '));
if (unsourced.length) extra.push('sources, ' + unsourced.length + ' figure(s) not in the approved sources: ' + unsourced.slice(0, 12).join(', '));
if (strangers.length) extra.push('sources, attributed to ' + strangers.join(', ') + ', which is not an approved source');
const line = '  sources: ' + list.length + ' approved | ' + (numText.match(NUM) || []).length + ' numeral(s) | ' + unsourced.length + ' unsourced | ' + strangers.length + ' unapproved attribution(s)';
if (!extra.length) {
  const report = String(d.gateReport || '').replace('\n  writer:', '\n' + line + '\n  writer:');
  return [{ json: { ...d, gateReport: report, lastFeedback: String(d.lastFeedback || '').replace(String(d.gateReport || ''), report) } }];
}
const failures = (d.gateFailures || []).concat(extra);
const stamp = new Date().toISOString();
const report = String(d.gateReport || '').replace(/^SCRIPT GATE PASS/, 'SCRIPT GATE FAIL').replace('\n  writer:', '\n' + line + '\n  writer:').replace('\n\nCleared for Promote.', '') + '\n\nSOURCES GATE FAILED BECAUSE:\n' + extra.map(f => '  - ' + f).join('\n') + '\n\nSet status to Scripted to accept it as is, or to Idea to write it again.';
return [{ json: { ...d,
  status: 'Error',
  gateFailures: failures,
  gateReport: report,
  gateReason: 'SCRIPT GATE FAILED ' + stamp + '. ' + failures.join('; ') + '. Set status to Scripted to accept it as is, or to Idea to write it again.',
  lastFeedback: String(d.lastFeedback || '').replace(String(d.gateReport || ''), report)
} }];
