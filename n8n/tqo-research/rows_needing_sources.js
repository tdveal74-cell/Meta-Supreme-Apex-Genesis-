// A row needs research when the package is locked, the row is still an Idea and
// it carries no usable source. The writer skips exactly these rows (Package:
// Plan Batch in TQO FINAL V5), so this is the only way one of them moves.
const MAX_ROWS = 2;
const s = (v) => (v === null || v === undefined) ? '' : String(v).trim();
function sourcesOk(raw) {
  let list = null;
  try { list = JSON.parse(s(raw)); } catch (e) { return false; }
  return Array.isArray(list) && list.some(x => x && s(x.url) && s(x.quote));
}
const rows = $input.all().map(i => i.json)
  .filter(j => s(j.status) === 'Idea' && s(j.package_locked) && !sourcesOk(j.sources))
  .sort((a, b) => Number(a.id) - Number(b.id))
  .slice(0, MAX_ROWS);
return rows.map(j => ({ json: {
  id: j.id,
  topic: s(j.topic) || s(j.video_title),
  angle: s(j.angle),
  idea: s(j.idea),
  primary_subject: s(j.primary_subject),
  notes: s(j.notes),
  searchQuery: (s(j.primary_subject) || s(j.topic)) + ' 2026 report data -site:linkedin.com -site:instagram.com -site:facebook.com -site:tiktok.com -site:x.com -site:youtube.com'
} }));
