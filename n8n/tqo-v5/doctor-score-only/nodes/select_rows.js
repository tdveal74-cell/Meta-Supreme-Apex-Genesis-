// Select Rows. Picks the Scripted rows that carry a script and no doctor line,
// TQO first and then NCO, each in row order. A row that already carries a
// doctor line is never scored again, so a run that stops halfway is finished
// by running it again. The doctor line is read with the same pattern as the QC
// Doctor Gate and Preflight: Can This Clear? in TQO FINAL V5.
// Until a score-only line exists on a Scripted row in either table, a run takes
// FIRST_RUN_LIMIT rows. Once one does, it takes ROW_LIMIT. Only Scripted rows
// are read, so if every scored row has moved on, the next run is one row again.
const cfg = $('Run Config').first().json;
const whole = (n) => Number.isInteger(n) && n > 0;
if (!whole(cfg.FIRST_RUN_LIMIT) || !whole(cfg.ROW_LIMIT)) {
  throw new Error('Run Config FIRST_RUN_LIMIT and ROW_LIMIT must be whole numbers above 0, and they read ' + JSON.stringify(cfg.FIRST_RUN_LIMIT) + ' and ' + JSON.stringify(cfg.ROW_LIMIT) + '.');
}
if (typeof cfg.WRITE !== 'boolean') {
  throw new Error('Run Config WRITE must be true or false, and it reads ' + JSON.stringify(cfg.WRITE === undefined ? null : cfg.WRITE) + '.');
}
const only = Array.isArray(cfg.ONLY_ROWS) ? cfg.ONLY_ROWS.map(String) : [];
const DOCTOR = /\|\s*doctor\s+(\d+(?:\.\d+)?)\/100\s+([^|\n]*?)\s*(?=\||\n|$)/;
const SCORE_ONLY = /\|\s*doctor\s+\d+(?:\.\d+)?\/100\s+(?:PASS|NEEDS_REVISION)\s*\|\s*score only, no rewrite\b/;
const SHOWS = [
  { show: 'TQO', tableRef: '2GtmrFcTNqVMbddh', node: 'Get TQO Scripted Rows' },
  { show: 'NCO', tableRef: 'DSH1tn4TZjzAEKxp', node: 'Get NCO Scripted Rows' }
];
const eligible = [];
const counts = [];
let proven = false;
for (const s of SHOWS) {
  const rows = $(s.node).all().map(i => i.json).filter(j => j && j.id !== undefined && j.id !== null)
    .sort((a, b) => Number(a.id) - Number(b.id));
  let scored = 0, empty = 0, other = 0;
  for (const r of rows) {
    const history = String(r.score_history || '');
    if (SCORE_ONLY.test(history)) proven = true;
    if (String(r.status) !== 'Scripted') { other++; continue; }
    if (!String(r.script || '').trim()) { empty++; continue; }
    if (DOCTOR.test(history)) { scored++; continue; }
    eligible.push({ ...r, nco: s.show === 'NCO', __show: s.show, __tableRef: s.tableRef, __key: s.show + ':' + r.id });
  }
  counts.push(s.show + ' ' + rows.length + ' Scripted read, ' + scored + ' already carry a doctor line, ' + empty + ' have no script' + (other ? ', ' + other + ' not Scripted' : ''));
}
const unknown = only.filter(k => !eligible.some(r => r.__key === k));
if (unknown.length) throw new Error('ONLY_ROWS names ' + unknown.join(', ') + ', which is not a Scripted row with a script and no doctor line. ' + counts.join('; ') + '.');
const limit = proven ? cfg.ROW_LIMIT : cfg.FIRST_RUN_LIMIT;
const pool = only.length ? eligible.filter(r => only.includes(r.__key)) : eligible;
const picked = pool.slice(0, limit);
const note = 'select: ' + counts.join('; ') + '; ' + eligible.length + ' eligible; '
  + (proven ? 'a score-only line exists, so the limit is ROW_LIMIT ' : 'no score-only line yet, so the limit is FIRST_RUN_LIMIT ') + limit
  + '; ' + picked.length + ' scored this run (' + picked.map(r => r.__key).join(', ') + ')';
if (!picked.length) throw new Error('No row to score. ' + note + '.');
return picked.map(r => ({ json: { ...r, __selectNote: note } }));
