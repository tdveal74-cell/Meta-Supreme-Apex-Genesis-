// Sources Gate, ruled by Tee 2026-10-07: the gate refuses any figure that is not
// in the row's approved sources. Measured, never judged. Every numeral in the
// script must appear in a source quote or claim, except counts of ten or under
// and a year the episode idea names. A sentence that says according to someone
// must name an approved origin or publisher, and no unnamed person may be cited
// as a source, as in an interview with a senior HR director. TQO only. A
// failure lands as Error with the reason in qc_findings, the same as every
// other gate failure.
const ctx = $('Show Context: Script').first().json;
const d = $input.first().json;
if (ctx.show === 'NCO') return [{ json: d }];
const row = $('One Idea at a Time').first().json;
let list = [];
try { const l = JSON.parse(String(row.sources || '')); if (Array.isArray(l)) list = l.filter(x => x && x.url && x.quote); } catch (e) { list = []; }
const NUM = /\$?\d[\d,]*(?:\.\d+)?%?/g;
const key = (t) => t.replace(/[$,%]/g, '').replace(/\.$/, '');
const nums = (t) => (String(t || '').match(NUM) || []).map(key);
const sourced = new Set(nums(list.map(s => [s.quote, s.quote_text, s.claim].join(' ')).join(' ')));
const brief = new Set(nums([row.topic, row.angle, row.idea, row.video_title].join(' ')));
const script = String(d.script || '');
const unsourced = [];
for (const raw of (script.match(NUM) || [])) {
  const k = key(raw);
  const n = Number(k);
  if (sourced.has(k)) continue;
  if (!/[$%]/.test(raw) && Number.isInteger(n) && n <= 10) continue;
  if (/^(19|20)\d\d$/.test(k) && brief.has(k)) continue;
  const shown = raw.replace(/[,.]+$/, '');
  if (!unsourced.includes(shown)) unsourced.push(shown);
}
const names = list.map(s => (String(s.origin || '') + ' ' + String(s.publisher || '')).toLowerCase()).join(' | ');
const strangers = [];
const ATTR = /\b[Aa]ccording to (?:the |a |an )?([A-Z][\w&.'-]*)/g;
let m;
while ((m = ATTR.exec(script))) { const w = m[1].replace(/['.]s?$/, '').toLowerCase(); if (!names.includes(w) && !strangers.includes(m[1])) strangers.push(m[1]); }
const UNNAMED = /\b(?:interview|conversation|call|chat|discussion|meeting) with (?:a|an|one|several|some|two|three) (?:[\w-]+ ){0,4}(?:director|manager|executive|leader|officer|founder|employee|worker|analyst|engineer|consultant|recruiter|professional)s?\b/i;
const unnamed = script.split(/(?<=[.!?])\s+/).filter(t => UNNAMED.test(t)).map(t => '"' + t.trim().slice(0, 140) + '"');
const extra = [];
if (unnamed.length) extra.push('evidence, an unnamed person cited as a source: ' + unnamed.join(' '));
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
