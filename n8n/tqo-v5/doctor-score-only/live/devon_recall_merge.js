// DEVON Recall: Merge (added 15 Sep 2026). Ruled by Tee on an inline card:
// the writer is grounded by retrieval from his own record plus capture of his
// edits. This node folds two things onto the idea row before Build Script
// Prompt reads it: the devon-soul recall for this topic, and the newest
// exemplars of how Tee rewrote earlier machine drafts. Both are optional. A
// recall that fails (probe execution 86 on 15 Sep 2026 returned 401 because
// the stored credential does not match the service) is named in
// devonRecallNote and the script is still written; nothing here blocks.
const row = $('One Idea at a Time').first().json;
let recallText = '';
let recallNote = '';
try {
  const res = $('DEVON Recall: Ask').first().json || {};
  const code = Number(res.statusCode);
  let body = res.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = null; } }
  if (code === 200 && body && Array.isArray(body.records)) {
    const recs = body.records.filter(r => r && String(r.text || '').trim()).slice(0, 7);
    recallText = recs.map(r => '- [' + String(r.source || 'soul') + ', score ' + (Number(r.score) || 0).toFixed(2) + '] ' + String(r.text).replace(/\s+/g, ' ').trim().slice(0, 600)).join('\n');
    recallNote = 'DEVON recall: ' + recs.length + ' record(s), ' + (body.tee_count ?? '?') + ' from Tee and ' + (body.devon_count ?? '?') + ' from DEVON' + (Array.isArray(body.errors) && body.errors.length ? '; partial: ' + body.errors.join('; ') : '');
  } else {
    const detail = body && body.detail ? String(body.detail) : (res.error ? String(res.error.message || res.error) : '');
    recallNote = 'DEVON recall unavailable (HTTP ' + (code || 'none') + (detail ? ', ' + detail.slice(0, 120) : '') + '); the script was written without it';
  }
} catch (e) {
  recallNote = 'DEVON recall did not run: ' + e.message;
}
const exemplars = $input.all().map(i => i.json || {}).filter(j => String(j.tee_script || '').trim());
const squeeze = (s, n) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
const exemplarText = exemplars.map((j, i) => [
  'Exemplar ' + (i + 1) + ' (' + String(j.topic || 'untitled') + ', captured ' + String(j.captured_at || '').slice(0, 10) + ', ' + (j.machine_words || '?') + ' machine words to ' + (j.tee_words || '?') + ' after Tee):',
  'MACHINE DRAFT OPENED: ' + squeeze(j.machine_script, 400),
  'TEE REWROTE IT AS: ' + squeeze(j.tee_script, 900)
].join('\n')).join('\n\n');
return [{ json: { ...row, devonRecall: recallText, devonRecallNote: recallNote, devonExemplars: exemplarText, devonExemplarCount: exemplars.length } }];
