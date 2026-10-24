// Confirm Write. Reads the row back after Save Score Line and checks both
// columns hold exactly what Compose Write sent. The run report counts a row as
// written only from this read, never from the update call returning success.
const c = $('Compose Write').first().json;
const back = $input.all().map(i => i.json).filter(j => j && String(j.id) === String(c.rowId));
const held = back.length === 1
  && String(back[0].score_history ?? '') === c.scoreHistory
  && String(back[0].last_feedback ?? '') === c.lastFeedback;
return [{ json: {
  show: c.show, rowId: c.rowId, title: c.title, ok: c.ok, verdict: c.verdict, score: c.score, line: c.line,
  written: held,
  reason: held ? '' : 'the write did not read back as sent (' + back.length + ' row(s) read back)'
} }];
