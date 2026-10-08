// A success response is a claim, not a receipt. The issuer runs with
// fullResponse, so its status code is read back here. A failed or incomplete
// search is not a decision: it throws, the webhook answers 500, and the
// feeder logs FAILED, emails, and retries the job on its next poll instead
// of logging it as fed. Ruled by Tee 2026-10-07.
const candidate = $('Candidate Former').first().json.candidate;
const res = $input.first().json || {};
const statusCode = typeof res.statusCode === "number" ? res.statusCode : null;

let receipt = res.body !== undefined ? res.body : res;
if (typeof receipt === "string") {
  try { receipt = JSON.parse(receipt); } catch (e) {}
}

// n8n cuts a thrown Code node message at its LAST colon and keeps only the
// tail, and keeps only the first line, so a colon or a line break anywhere in
// the text would leave the error handler's email holding a fragment. Colons
// in quoted service text become "=" and line breaks become spaces.
function clip(v) {
  let s;
  try { s = typeof v === "string" ? v : JSON.stringify(v); } catch (e) { s = String(v); }
  return String(s).slice(0, 300).replace(/:/g, "=").replace(/[\r\n]+/g, " ");
}
// Names the job in every failure, so the feeder's FAILED line and the fault
// email can be matched without lining up timestamps.
const job = "job " + String((candidate.source_intent_ids || [])[0] || "unknown").replace(/:/g, "=");

if (statusCode === null || statusCode < 200 || statusCode >= 300) {
  throw new Error("Conflict-search issuer failed with HTTP " + statusCode + " for " + job + ", so there is no receipt and no gate decision. Body was " + clip(receipt));
}
if (!receipt || typeof receipt !== "object" || typeof receipt.complete !== "boolean" || typeof receipt.conflict_status !== "string") {
  throw new Error("Conflict-search issuer answered HTTP " + statusCode + " without a receipt for " + job + ", so there is no gate decision. Body was " + clip(receipt));
}
if (receipt.complete !== true) {
  throw new Error("Conflict-search did not complete for " + job + ", so there is no gate decision. Notes say " + clip(receipt.notes));
}

// Dry-run subconscious write simulation, overwritten by Skip Write or Write Result
const dryRunWrite = {
  ok: true,
  dry_run: true,
  record_id: candidate.candidate_id,
  namespace: "experience",
  note: "placeholder until the gate decides; Skip Write or Write Result replaces it",
  text: candidate.claim,
  source_intent_ids: candidate.source_intent_ids
};

return [{
  json: {
    candidate,
    receipt,
    subconscious_write: dryRunWrite,
    summary: {
      candidate_id: candidate.candidate_id,
      claim: candidate.claim,
      independent_sources: candidate.independent_evidence_count,
      receipt_complete: receipt.complete === true,
      conflict_status: receipt.conflict_status,
      write_attempted: false
    }
  }
}];