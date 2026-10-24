// Recall Required. The doctor treats any first person claim that is not in
// TEE'S RECORD as invented, so a score taken without the DEVON recall is not a
// score of the script as Tee wrote it. When the recall does not answer, the
// run stops here, before the provider is paid, and says why. Rows written
// earlier in the run stay written, and running again picks up the rest. The
// test is the one DEVON Recall: Merge applies: HTTP 200 with a records array,
// which may be empty.
const res = $('DEVON Recall: Ask').first().json || {};
const code = Number(res.statusCode);
let body = res.body;
if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { body = null; } }
if (!(code === 200 && body && Array.isArray(body.records))) {
  const row = $('One Idea at a Time').first().json;
  const merged = $input.first() ? $input.first().json : {};
  throw new Error('The DEVON recall did not answer for ' + String(row.__key || row.id) + ', so it was not scored and the run stopped before calling the provider. '
    + String(merged.devonRecallNote || 'No recall note.') + ' Rows written earlier in this run stay written; run it again once the recall answers.');
}
return $input.all();
