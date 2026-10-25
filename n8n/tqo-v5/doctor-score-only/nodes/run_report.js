// Run Report. One line per row scored. The run ends in error when any row was
// not written, so a partial run never reads as a clean one; the rows that were
// written stay written, and running again picks up only the rest. A PASS at 90
// or above is what the QC Doctor Gate and Preflight read as a clear doctor
// line. It clears that one check and nothing else on the row.
// In a measurement run (Run Config WRITE false) nothing is written on purpose:
// a row the doctor scored is listed as measured, and only a row that could not
// be scored ends the run in error.
const FLOOR = 90;
const results = $input.all().map(i => i.json);
if (!results.length || results.some(r => !r || r.rowId === undefined || typeof r.written !== 'boolean')) {
  throw new Error('Run Report could not read the loop results: ' + JSON.stringify(results).slice(0, 600));
}
const measure = $('Run Config').first().json.WRITE === false;
const written = results.filter(r => r.written);
const cleared = written.filter(r => r.verdict === 'PASS' && Number(r.score) >= FLOOR);
const measured = results.filter(r => !r.written && measure && r.ok === true);
const failed = results.filter(r => !r.written && !(measure && r.ok === true));
const lines = results.map(r => r.show + ' row ' + r.rowId + (r.title ? ' "' + r.title + '"' : '') + ': '
  + (r.written
    ? r.verdict + ' ' + r.score + '/100, ' + (r.verdict === 'PASS' && Number(r.score) >= FLOOR ? 'the doctor line clears at ' + FLOOR : 'the doctor line holds the row')
    : measured.includes(r)
      ? 'MEASURED, NOT WRITTEN: ' + r.verdict + ' ' + r.score + '/100. DIAGNOSIS: ' + ((String(r.feedback || '').match(/\nDIAGNOSIS: ([^\n]*)/) || [])[1] || 'none given')
      : 'NOT WRITTEN, ' + r.reason));
let note = '';
try { note = String($('Select Rows').first().json.__selectNote || ''); } catch (e) { note = ''; }
const summary = (measure ? 'MEASUREMENT RUN, Run Config WRITE is false: ' + measured.length + ' row(s) scored and nothing written.\n' : '')
  + 'Score-only doctor run: ' + results.length + ' row(s), ' + written.length + ' written, '
  + cleared.length + ' clear the doctor check at ' + FLOOR + ', ' + failed.length + ' not written.\n'
  + lines.join('\n') + (note ? '\n' + note : '');
if (failed.length) throw new Error(summary);
return [{ json: { summary, results } }];
