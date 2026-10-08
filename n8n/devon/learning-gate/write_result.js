const ctx = $('Build Record').first().json;
const httpResp = $input.first().json;
const record = ctx.record;
const namespace = "experience";

const statusCode = httpResp.statusCode;
const body = httpResp.body !== undefined ? httpResp.body : httpResp;

// From Phase 1 of the grouping build, ruled by Tee 2026-10-08. A failed
// subconscious write is NOT a PROMOTE. Before, it answered 200 PROMOTE with
// ok false buried in the body, the feeder logged PROMOTE, and the Soul
// Committer would have raised a card for a record that was never written. Now
// it throws, the webhook answers 500, and the feeder logs FAILED and retries
// under the same learning intent id, which rewrites the same record.
//
// n8n cuts a thrown Code node message at its LAST colon and keeps only the
// first line, so the message carries no colon or line break of its own.
function clip(v) {
  let s;
  try { s = typeof v === "string" ? v : JSON.stringify(v); } catch (e) { s = String(v); }
  return String(s).slice(0, 300).replace(/:/g, "=").replace(/[\r\n]+/g, " ");
}
if (typeof statusCode !== "number" || statusCode < 200 || statusCode >= 300) {
  throw new Error("Subconscious write failed with HTTP " + statusCode + " for lesson group " + String(record._id || "unknown").replace(/:/g, "=") + ", so nothing was promoted. Body was " + clip(body));
}

// Strip the record so the response mirrors the previous node's shape
const { record: _omit, ...rest } = ctx;

return [{
  json: {
    ...rest,
    subconscious_write: {
      ok: true,
      dry_run: false,
      record_id: record._id,
      namespace,
      note: "live upsert succeeded",
      pinecone_response: body
    }
  }
}];