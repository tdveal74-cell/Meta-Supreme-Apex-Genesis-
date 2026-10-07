// A row needs research when the package is locked, the row is still an Idea and
// it carries no usable source. The writer skips exactly these rows (Package:
// Plan Batch in TQO FINAL V5), so this is the only way one of them moves. Both
// shows: NCO was ruled to the same standard the same day, at most two rows each.
const MAX_ROWS = 2;
// A row that found nothing is left alone for RETRY_DAYS, read from the date its
// own research_note opens with, so two rows that cannot be sourced do not take
// both places every day and starve every newer locked row behind them.
const RETRY_DAYS = 7;
const today = Date.parse(new Date().toISOString().slice(0, 10));
function pausedNote(note) {
  const m = /^\[(\d{4}-\d{2}-\d{2})\] No source written/.exec(s(note));
  return !!m && (today - Date.parse(m[1])) / 86400000 < RETRY_DAYS;
}
const TABLES = [
  { show: 'TQO', tableRef: '2GtmrFcTNqVMbddh', node: 'Get TQO Idea Rows' },
  { show: 'NCO', tableRef: 'DSH1tn4TZjzAEKxp', node: 'Get NCO Idea Rows' }
];
const s = (v) => (v === null || v === undefined) ? '' : String(v).trim();
function sourcesOk(raw) {
  let list = null;
  try { list = JSON.parse(s(raw)); } catch (e) { return false; }
  return Array.isArray(list) && list.some(x => x && s(x.url) && s(x.quote));
}
const rows = [];
for (const t of TABLES) {
  rows.push(...$(t.node).all().map(i => i.json)
    .filter(j => j.id !== undefined && s(j.status) === 'Idea' && s(j.package_locked) && !sourcesOk(j.sources) && !pausedNote(j.research_note))
    .sort((a, b) => Number(a.id) - Number(b.id))
    .slice(0, MAX_ROWS)
    .map(j => ({ ...j, __show: t.show, __tableRef: t.tableRef })));
}
return rows.map(j => ({ json: {
  id: j.id,
  show: j.__show,
  tableRef: j.__tableRef,
  topic: s(j.topic) || s(j.video_title),
  angle: s(j.angle),
  idea: s(j.idea),
  primary_subject: s(j.primary_subject),
  notes: s(j.notes),
  searchQuery: (s(j.primary_subject) || s(j.topic)) + ' 2026 report data -site:linkedin.com -site:instagram.com -site:facebook.com -site:tiktok.com -site:x.com -site:youtube.com'
} }));
