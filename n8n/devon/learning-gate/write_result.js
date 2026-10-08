const ctx = $('Build Record').first().json;
const httpResp = $input.first().json;
const record = ctx.record;
const namespace = "experience";

const statusCode = httpResp.statusCode;
const body = httpResp.body !== undefined ? httpResp.body : httpResp;
const ok = typeof statusCode === "number" ? (statusCode >= 200 && statusCode < 300) : true;

// Strip the record so the response mirrors the previous node's shape
const { record: _omit, ...rest } = ctx;

return [{
  json: {
    ...rest,
    subconscious_write: ok
      ? {
          ok: true,
          dry_run: false,
          record_id: record._id,
          namespace,
          note: "live upsert succeeded",
          pinecone_response: body
        }
      : {
          ok: false,
          dry_run: false,
          record_id: record._id,
          namespace,
          error: `Pinecone upsert failed (status ${statusCode})`,
          note: "live upsert failed",
          pinecone_response: body
        }
  }
}];