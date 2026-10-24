// Compose Write. Builds the two values Save Score Line writes from the row as it
// reads now, after the doctor call, and never from the copy read at the start
// of the run, so a line another lane appended in the meantime is kept. Score
// History and Last Feedback are appended to, the way Parse QC + Set Verdict
// appends. Nothing is written when the parse failed, when the row cannot be
// read back, when it left Scripted, or when a doctor line landed during the run.
const p = $('Parse Score Only').first().json;
const DOCTOR = /\|\s*doctor\s+(\d+(?:\.\d+)?)\/100\s+([^|\n]*?)\s*(?=\||\n|$)/;
const skip = (reason) => [{ json: { ...p, ok: false, verdict: 'UNCHECKED', write: false, reason } }];
if (!p.ok) return [{ json: { ...p, write: false } }];
const fresh = $input.all().map(i => i.json).filter(j => j && String(j.id) === String(p.rowId));
if (fresh.length !== 1) return skip('the row read back ' + fresh.length + ' time(s) before writing, and exactly 1 is required');
const r = fresh[0];
if (String(r.status) !== 'Scripted') return skip('the row moved to ' + JSON.stringify(r.status) + ' during the run');
if (DOCTOR.test(String(r.score_history || ''))) return skip('a doctor line landed on the row during the run');
const priorHistory = String(r.score_history || '');
const priorFeedback = String(r.last_feedback || '');
return [{ json: {
  ...p,
  write: true,
  scoreHistory: (priorHistory ? priorHistory + '\n' : '') + p.line,
  lastFeedback: (priorFeedback ? priorFeedback + '\n\n' : '') + p.feedback
} }];
