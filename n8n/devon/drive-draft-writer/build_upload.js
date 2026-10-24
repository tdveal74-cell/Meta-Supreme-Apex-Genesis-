// Builds the one request that creates the draft. Found 2026-10-24 on job
// 01M5JVGEDWVYFKWQ28T3N71QW2, the NCO S1E1 outline Tee opened and found blank.
//
// The Drive node's createFromText with convertToGoogleDocument makes TWO calls
// (n8n v2/actions/file/createFromText.operation.ts lines 112 to 143): a Drive
// files.create that makes an empty Google Doc already carrying the
// appProperties, then a Docs API batchUpdate that inserts the text. On
// 2026-10-22T23:00Z the second call answered "Forbidden", the first had already
// left the empty Doc in Areas/NCO under this job's key, and the retry an hour
// later found it by that key and adopted it as the draft.
//
// A Drive multipart upload does it in ONE call: the metadata part names the
// Google Doc mime type and the text part is imported into it, so Drive either
// creates the Doc with its text or creates nothing. It also needs only the
// Drive API, which the credential already reaches.
//
// The boundary must not appear in the text, or the text part would be cut
// short. It starts from the intent id and grows a counter until it is absent,
// so it never refuses and never depends on chance.
const p = $input.first().json || {};
const text = String(p.draft_text || '');
let boundary = 'devon_draft_' + String(p.intent_id || 'job');
let n = 0;
while (text.indexOf(boundary) !== -1) { n += 1; boundary = 'devon_draft_' + String(p.intent_id || 'job') + '_' + n; }
const metadata = {
  name: String(p.doc_name),
  parents: [String(p.folder_id)],
  mimeType: 'application/vnd.google-apps.document',
  appProperties: { devon_idempotency_key: String(p.idem), devon_intent_id: String(p.intent_id), devon_action: 'drive.draft' }
};
const CRLF = '\r\n';
const body = '--' + boundary + CRLF +
  'Content-Type: application/json; charset=UTF-8' + CRLF + CRLF +
  JSON.stringify(metadata) + CRLF +
  '--' + boundary + CRLF +
  'Content-Type: text/plain; charset=UTF-8' + CRLF + CRLF +
  text + CRLF +
  '--' + boundary + '--';
return [{ json: Object.assign({}, p, { upload_boundary: boundary, upload_body: body }) }];
