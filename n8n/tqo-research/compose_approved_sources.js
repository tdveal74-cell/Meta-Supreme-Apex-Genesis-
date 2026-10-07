// Only checked sources the doctor approved reach the row, and each one keeps the
// exact text that passed the quote check. A doctor reply that cannot be read
// approves nothing.
const prev = $('Build Doctor Prompt').first().json;
const checked = prev.checked || [];
let parsed = null;
const content = (((($input.first().json || {}).choices || [])[0] || {}).message || {}).content || '';
try { parsed = JSON.parse(content); } catch (e) { parsed = null; }
const verdicts = (parsed && Array.isArray(parsed.verdicts)) ? parsed.verdicts : [];
const now = new Date().toISOString();
const approved = [];
const rejected = [];
checked.forEach((s, i) => {
  const v = verdicts.find(x => Number(x.index) === i);
  if (v && String(v.verdict).toLowerCase() === 'approve') approved.push({ ...s, approved_by: 'script doctor', doctor_reason: String(v.reason || '').slice(0, 300), checked_at: now });
  else rejected.push({ url: s.url, reason: v ? String(v.reason || 'rejected').slice(0, 200) : 'no verdict' });
});
const note = '[' + now.slice(0, 10) + '] ' + (approved.length
  ? approved.length + ' source(s) approved on ' + now.slice(0, 10) + '; ' + rejected.length + ' rejected by the doctor; ' + (prev.dropped || []).length + ' dropped by the quote check.'
  : 'No source written: ' + checked.length + ' passed the quote check and the doctor approved none' + (parsed === null ? ' (reply was not JSON)' : '') + (rejected.length ? ': ' + rejected.map(r => r.reason).join('; ') : '') + '.');
return [{ json: { id: prev.id, show: prev.show, tableRef: prev.tableRef, sources: approved.length ? JSON.stringify(approved) : '', research_note: note.slice(0, 2000), approved: approved.length } }];
