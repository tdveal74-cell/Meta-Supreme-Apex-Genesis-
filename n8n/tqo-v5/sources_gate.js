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
const NUM = /\$?\d[\d,]*(?:\.\d+)?(?:%|\s?percent\b)?/gi;
const bare = (t) => t.replace(/\s?percent$/i, '').replace(/[$,%]/g, '').replace(/\.$/, '');
const unit = (t) => (/^\$/.test(t) ? '$' : '') + bare(t) + (/(%|percent)$/i.test(t) ? '%' : '');
const sourcedBare = new Set((sourceText.match(NUM) || []).map(bare));
const sourcedUnit = new Set((sourceText.match(NUM) || []).map(unit));
const brief = new Set(([row.topic, row.angle, row.idea, row.video_title].join(' ').match(NUM) || []).map(bare));
const script = String(d.script || '');
const unsourced = [];
const flag = (shown) => { if (!unsourced.includes(shown)) unsourced.push(shown); };
for (const raw of (script.match(NUM) || [])) {
  const k = bare(raw);
  const n = Number(k);
  const withUnit = /[$%]|percent/i.test(raw);
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
for (const m of (script.match(SPELLED) || [])) {
  if (!sourceFlat.includes(flat(m))) flag(m.trim());
}
const names = list.map(s => (String(s.origin || '') + ' ' + String(s.publisher || '')).toLowerCase()).join(' | ');
const strangers = [];
const stranger = (name) => { const w = name.replace(/['.]s?$/, '').toLowerCase(); if (!names.includes(w) && !strangers.includes(name)) strangers.push(name); };
const ATTR = /\b[Aa]ccording to (?:the |a |an )?(?:[a-z]+ ){0,2}([A-Z][\w&.'-]*)/g;
let m;
while ((m = ATTR.exec(script))) stranger(m[1]);
const COMMON = /^(?:It|This|That|These|Those|He|She|They|We|You|I|The|A|An|One|Each|Every|Most|Some|Our|Your|Their|His|Her|Its|What|Which|Who|Nobody|Everyone|Research|Data|AI|More|Less|Fewer|Many|Few|All|Both|Here|There|Today|Now|But|And|So|If|When|Then|Even|Still|Also|Leaders|Managers|Companies|Teams|Workers|Employers)$/;
const SAID = /\b([A-Z][\w&.'-]+)(?: [A-Z][\w&.'-]+){0,3} (?:found|finds|reported|estimated|estimates|predicted|predicts|projected|surveyed)\b/g;
while ((m = SAID.exec(script))) { if (!COMMON.test(m[1])) stranger(m[1]); }
const UNNAMED = /\b(?:interview|conversation|call|chat|discussion|meeting) with (?:a|an|one|several|some|two|three) (?:[\w-]+ ){0,4}(?:director|manager|executive|leader|officer|founder|employee|worker|analyst|engineer|consultant|recruiter|professional)s?\b/i;
const UNNAMED_ORG = /\b(?:[Aa]n?|[Oo]ne|[Ss]everal|[Ss]ome|[Mm]any) (?:[a-z][\w-]* ){0,3}(?:firm|company|companies|bank|retailer|startup|employer|organization|organisation|study|studies|survey|report|analysis|case)s?\b(?= (?:reported|found|showed|shows|says|said|indicated|indicates|estimated|revealed|noted|cut|saw|told))/;
const unnamed = script.split(/(?<=[.!?])\s+/).filter(t => UNNAMED.test(t) || UNNAMED_ORG.test(t)).map(t => '"' + t.trim().slice(0, 140) + '"');
const extra = [];
if (unnamed.length) extra.push('evidence, an unnamed person or organisation cited as a source: ' + unnamed.join(' '));
if (unsourced.length) extra.push('sources, ' + unsourced.length + ' figure(s) not in the approved sources: ' + unsourced.slice(0, 12).join(', '));
if (strangers.length) extra.push('sources, attributed to ' + strangers.join(', ') + ', which is not an approved source');
const line = '  sources: ' + list.length + ' approved | ' + (script.match(NUM) || []).length + ' numeral(s) | ' + unsourced.length + ' unsourced | ' + strangers.length + ' unapproved attribution(s)';
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
