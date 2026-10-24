// Parse Score Only. The doctor was told to score and never repair, so the only
// results are PASS or NEEDS_REVISION with a score from 0 to 100. Anything else
// is UNCHECKED and nothing is written: a refused or failed call, a truncation,
// an empty or unreadable reply, a verdict outside those two, and REPAIRED most
// of all, because no repair was made and the QC Doctor Gate would clear it.
// Unlike Parse Doctor Output in TQO FINAL V5, a missing verdict is never PASS,
// and only a completion that finished on its own (finish_reason stop) is read.
const row = $('One Idea at a Time').first().json;
const ctx = $('Show Context: Script').first().json;
const stamp = new Date().toISOString();
let recall = '';
try { recall = String($('DEVON Recall: Merge').first().json.devonRecallNote || ''); } catch (e) { recall = ''; }
const base = {
  show: ctx.show, tableRef: ctx.tableRef, rowId: row.id,
  title: String(row.video_title || row.topic || ''), stamp, recall, written: false
};
const fail = (reason) => [{ json: { ...base, ok: false, verdict: 'UNCHECKED', score: null, reason } }];

const out = $json || {};
if (out.error) return fail('the Cerebras call failed: ' + String(out.error.message || JSON.stringify(out.error)).slice(0, 300));
const choice = Array.isArray(out.choices) ? out.choices[0] : null;
if (!choice || !choice.message) return fail('the Cerebras response carried no completion');
if (choice.finish_reason === 'length') return fail('the completion was truncated at max_completion_tokens');
if (choice.finish_reason !== 'stop') return fail('the completion ended on ' + JSON.stringify(choice.finish_reason === undefined ? null : choice.finish_reason) + ' rather than stop');
const raw = String(choice.message.content ?? '').trim().replace(/^```(json)?/i, '').replace(/```$/, '').trim();
if (!raw) return fail('the completion was empty');

let v;
try { v = JSON.parse(raw); }
catch (e) {
  const s = raw.indexOf('{'), en = raw.lastIndexOf('}');
  if (s === -1 || en <= s) return fail('the completion was not JSON');
  try { v = JSON.parse(raw.slice(s, en + 1)); } catch (e2) { return fail('the completion JSON did not parse'); }
}
if (!v || typeof v !== 'object' || Array.isArray(v)) return fail('the completion was not a JSON object');

// The verdict is matched as ASCII before it is upper-cased, so no other letter
// folds into PASS.
const verdict = typeof v.verdict === 'string' && /^\s*(?:PASS|NEEDS_REVISION)\s*$/i.test(v.verdict) ? v.verdict.trim().toUpperCase() : '';
if (!['PASS', 'NEEDS_REVISION'].includes(verdict)) {
  return fail('the verdict was ' + JSON.stringify(v.verdict === undefined ? null : v.verdict) + ', and a score-only pass returns only PASS or NEEDS_REVISION');
}
let score = v.score;
if (typeof score === 'string' && /^\s*\d{1,3}(?:\.\d+)?\s*$/.test(score)) score = Number(score);
if (typeof score !== 'number' || !Number.isFinite(score) || score < 0 || score > 100) {
  return fail('the score was ' + JSON.stringify(v.score === undefined ? null : v.score) + ', and only a number from 0 to 100 is a result');
}
// One decimal, always rounded down, so a score under the gate's 90 can never be
// written as 90 (89.95 is 89.9, never 90).
score = Math.floor(score * 10) / 10;

const model = String(out.model || 'unknown model');
const line = stamp + ' | doctor ' + score + '/100 ' + verdict + ' | score only, no rewrite, ' + model;
const list = (x) => Array.isArray(x) ? x.map(String).filter(s => s.trim()) : [];
const preserved = list(v.preserved);
const notes = list(v.notes);
const feedback = [
  'SCRIPT DOCTOR, SCORE ONLY: ' + verdict + ' at ' + score + '/100 at ' + stamp + '. The script was not changed.',
  ...(recall ? ['TEE\'S RECORD: ' + recall + '.'] : []),
  '',
  'DIAGNOSIS: ' + String(v.diagnosis || ''),
  '',
  ...(preserved.length ? ['PRESERVED:', ...preserved.map(p => '  - ' + p), ''] : []),
  ...(notes.length ? ['NOTES:', ...notes.map(n => '  - ' + n)] : [])
].join('\n').trim();

return [{ json: { ...base, ok: true, verdict, score, line, feedback, model, reason: '' } }];
