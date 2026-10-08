const input = $input.first().json;
const gate = input.gate;

return [{
  json: {
    ...input,
    subconscious_write: {
      ok: true,
      dry_run: true,
      skipped: true,
      reason: `gate decision was ${gate?.decision || "missing"} – no write`,
      record_id: null
    }
  }
}];