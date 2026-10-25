// Parse Score Only. The doctor was told to score and never repair, so the only
// results are PASS or NEEDS_REVISION with a score from 0 to 100. Anything else
// is UNCHECKED and nothing is written: a refused or failed call, a truncation,
// an empty or unreadable reply, a verdict outside those two, and REPAIRED most
// of all, because no repair was made and the QC Doctor Gate would clear it.
// Unlike Parse Doctor Output in TQO FINAL V5, a missing verdict is never PASS,
// and only a completion that finished on its own (finish_reason stop) is read.
// Ruled by Tee 2026-10-24: the row is read READS times and the strictest read
// is written. The score is the lowest of them, and the verdict is PASS only
// when every read is PASS at 90 or above. If any read fails, none is written.
// That holds at READS 1 too: a PASS under 90 is written as NEEDS_REVISION, which
// the QC Doctor Gate and Preflight hold either way.
const FLOOR = 90;
const row = $('One Idea at a Time').first().json;
const ctx = $('Show Context: Script').first().json;
const READS = $('Run Config').first().json.READS;
const stamp = new Date().toISOString();
let recall = '';
try { recall = String($('DEVON Recall: Merge').first().json.devonRecallNote || ''); } catch (e) { recall = ''; }
const base = {
  show: ctx.show, tableRef: ctx.tableRef, rowId: row.id,
  title: String(row.video_title || row.topic || ''), stamp, recall, written: false
};
const fail = (reason) => [{ json: { ...base, ok: false, verdict: 'UNCHECKED', score: null, reason } }];

// One read: a verdict and a score, or the reason it is not a result.
const readOne = (out) => {
  out = out || {};
  const no = (reason) => ({ ok: false, reason });
  if (out.error) return no('the Cerebras call failed: ' + String(out.error.message || JSON.stringify(out.error)).slice(0, 300));
  const choice = Array.isArray(out.choices) ? out.choices[0] : null;
  if (!choice || !choice.message) return no('the Cerebras response carried no completion');
  if (choice.finish_reason === 'length') return no('the completion was truncated at max_completion_tokens');
  if (choice.finish_reason !== 'stop') return no('the completion ended on ' + JSON.stringify(choice.finish_reason === undefined ? null : choice.finish_reason) + ' rather than stop');
  const raw = String(choice.message.content ?? '').trim().replace(/^```(json)?/i, '').replace(/```$/, '').trim();
  if (!raw) return no('the completion was empty');
  let v;
  try { v = JSON.parse(raw); }
  catch (e) {
    const s = raw.indexOf('{'), en = raw.lastIndexOf('}');
    if (s === -1 || en <= s) return no('the completion was not JSON');
    try { v = JSON.parse(raw.slice(s, en + 1)); } catch (e2) { return no('the completion JSON did not parse'); }
  }
  if (!v || typeof v !== 'object' || Array.isArray(v)) return no('the completion was not a JSON object');
  // The verdict is matched as ASCII before it is upper-cased, so no other letter
  // folds into PASS.
  const verdict = typeof v.verdict === 'string' && /^\s*(?:PASS|NEEDS_REVISION)\s*$/i.test(v.verdict) ? v.verdict.trim().toUpperCase() : '';
  if (!['PASS', 'NEEDS_REVISION'].includes(verdict)) {
    return no('the verdict was ' + JSON.stringify(v.verdict === undefined ? null : v.verdict) + ', and a score-only pass returns only PASS or NEEDS_REVISION');
  }
  let score = v.score;
  if (typeof score === 'string' && /^\s*\d{1,3}(?:\.\d+)?\s*$/.test(score)) score = Number(score);
  if (typeof score !== 'number' || !Number.isFinite(score) || score < 0 || score > 100) {
    return no('the score was ' + JSON.stringify(v.score === undefined ? null : v.score) + ', and only a number from 0 to 100 is a result');
  }
  // One decimal, always rounded down, so a score under the gate's 90 can never be
  // written as 90 (89.95 is 89.9, never 90).
  score = Math.floor(score * 10) / 10;
  // A field that is not text is quoted as JSON, so the doctor's words in it are
  // kept rather than written as [object Object] (found by the verifier on e0351e1).
  const text = (x) => typeof x === 'string' ? x : JSON.stringify(x);
  const list = (x) => Array.isArray(x) ? x.map(text).filter(s => s.trim()) : [];
  // Found by the verifier on 31e0f73: the model name comes from the provider's
  // envelope and went into the line as sent, so a name carrying "| doctor 99/100
  // PASS" would have planted a doctor line the gates read. Only the characters a
  // model name needs are kept.
  const model = String(out.model || '').replace(/[^A-Za-z0-9._-]/g, '') || 'unknown model';
  return { ok: true, verdict, score, diagnosis: v.diagnosis === undefined || v.diagnosis === null || v.diagnosis === '' ? '' : text(v.diagnosis), preserved: list(v.preserved), notes: list(v.notes), model };
};

const outs = $input.all().map(i => i.json);
if (!Number.isInteger(READS) || READS < 1) return fail('Run Config READS is ' + JSON.stringify(READS) + ', and it must be a whole number of 1 or more');
if (outs.length !== READS) return fail(READS + ' read(s) were asked for and ' + outs.length + ' came back');
const reads = outs.map(readOne);
const bad = reads.map((r, i) => r.ok ? '' : 'read ' + (i + 1) + ': ' + r.reason).filter(Boolean);
if (bad.length) return fail(READS === 1 ? reads[0].reason : bad.length + ' of ' + READS + ' reads were not results, so none is written (' + bad.join('; ') + ')');

const score = Math.min(...reads.map(r => r.score));
const verdict = reads.every(r => r.verdict === 'PASS' && r.score >= FLOOR) ? 'PASS' : 'NEEDS_REVISION';
// The read shown in full is the lowest, a NEEDS_REVISION one first on a tie.
const at = reads.findIndex(r => r.score === score && r.verdict === 'NEEDS_REVISION');
const pick = reads[at === -1 ? reads.findIndex(r => r.score === score) : at];
const models = [...new Set(reads.map(r => r.model))];
const model = models.join(' and ');
const tally = reads.map(r => r.score).join(', ');
const line = stamp + ' | doctor ' + score + '/100 ' + verdict + ' | score only, no rewrite, ' + (READS === 1 ? '' : READS + ' reads (' + tally + '), ') + model;
const body = [
  'SCRIPT DOCTOR, SCORE ONLY' + (READS === 1 ? '' : ', STRICTEST OF ' + READS + ' READS') + ': ' + verdict + ' at ' + score + '/100 at ' + stamp + '. The script was not changed.',
  ...(recall ? ['TEE\'S RECORD: ' + recall + '.'] : []),
  ...(READS === 1 ? [] : ['READS: ' + reads.map((r, i) => (i + 1) + ' ' + r.verdict + ' ' + r.score).join(', ') + '. The lowest score is written, and PASS needs every read to pass at ' + FLOOR + ' or above.']),
  '',
  'DIAGNOSIS: ' + pick.diagnosis,
  '',
  ...(pick.preserved.length ? ['PRESERVED:', ...pick.preserved.map(p => '  - ' + p), ''] : []),
  ...(pick.notes.length ? ['NOTES:', ...pick.notes.map(n => '  - ' + n), ''] : []),
  ...(READS === 1 ? [] : ['OTHER READS:', ...reads.filter(r => r !== pick).map(r => '  - ' + r.verdict + ' ' + r.score + ': ' + (r.diagnosis || 'no diagnosis given'))])
].join('\n').trim();
// Ruled by Tee 2026-10-25, after execution 4364's note carried an en dash the
// doctor wrote: the doctor's words are quoted as written, never edited, and the
// note says how many em or en dashes they carry. Only the doctor's words shown
// in the note are counted: the lowest read's diagnosis, preserved list and
// notes, and the other reads' diagnoses. The TEE'S RECORD line comes from the
// recall and is not the doctor's (found by the verifier on e0351e1).
const DASH = new RegExp('[' + String.fromCharCode(0x2013, 0x2014) + ']', 'g');
const doctorWords = [pick.diagnosis, ...pick.preserved, ...pick.notes, ...(READS === 1 ? [] : reads.filter(r => r !== pick).map(r => r.diagnosis))].join('\n');
const dashes = (doctorWords.match(DASH) || []).length;
const feedback = body + (dashes ? '\n\nThe doctor\'s text above carries ' + dashes + ' dash' + (dashes === 1 ? '' : 'es') + ', quoted as it wrote ' + (dashes === 1 ? 'it' : 'them') + '.' : '');

return [{ json: { ...base, ok: true, verdict, score, line, feedback, model, reason: '' } }];
