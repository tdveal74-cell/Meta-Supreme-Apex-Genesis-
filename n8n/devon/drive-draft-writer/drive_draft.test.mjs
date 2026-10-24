/**
 * Can the Drive Draft Writer record a blank document as a written draft?
 *
 *   node n8n/devon/drive-draft-writer/drive_draft.test.mjs
 *
 * Each node body is plain JS that reads n8n's `$('Node')` and `$input` and ends
 * in a `return`, so it runs here inside a Function with both stubbed. No n8n,
 * no network, no Drive.
 *
 * THE BASE CASE IS REAL. Job 01M5JVGEDWVYFKWQ28T3N71QW2, the NCO S1E1 outline,
 * read from the state ledger on 2026-10-24. Its first pass at
 * 2026-10-22T23:00:46Z created Doc 1gxKvA6Lhpgx5RW1wrw4RpHyn4vPsfkVLBxkDXSITt54
 * and then took "Forbidden" on the Docs API call that inserts the text. Its
 * second pass at 2026-10-23T00:00:43Z found that Doc by its idempotency
 * properties and adopted it. Exporting that Doc as text/plain returns the three
 * bytes EF BB BF, a byte order mark and nothing else, which is what
 * SHELL_EXPORT below is.
 *
 * The old adoption rule is reimplemented in one line, from the live Existing?
 * node, purely so the test can show it adopting the shell where the new rule
 * refuses. A fix nobody measured against the behaviour it replaces is a claim.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const load = (f) => new Function("$", "$input", readFileSync(new URL(`./${f}`, import.meta.url), "utf8"));
const buildUpload = load("build_upload.js");
const checkContent = load("check_existing_content.js");
const docResult = load("doc_result.js");

const BOM = String.fromCharCode(0xfeff);
const SHELL_EXPORT = BOM;
const INTENT = "01M5JVGEDWVYFKWQ28T3N71QW2";
const SHELL_ID = "1gxKvA6Lhpgx5RW1wrw4RpHyn4vPsfkVLBxkDXSITt54";
const IDEM = "face-b51ea7cbf8bc4cd9bd7ffcb7afebf673-4njmrr";
const NAME = "DRAFT_2026-10-22_devon_draft-a-one-page-outline-for-nco-forge-s1e1-nobody-teaches";
const FOLDER = "1GhyNDBaBLrcJux9gEVtVpSTnbDK1eJzO";

/** What Check Existing handed on for the real second pass. */
const CHECK_EXISTING = {
  refused: false, intent_id: INTENT, idem: IDEM, doc_name: NAME, folder_id: FOLDER, folder_name: "Areas/NCO",
  existing_file_id: SHELL_ID, existing_name: NAME,
  existing_link: `https://docs.google.com/document/d/${SHELL_ID}/edit`,
  existing_created: "2026-10-22T23:00:44.878Z", existing_matched_by: "idempotency_properties",
};

const words = (n) => Array.from({ length: n }, (_, i) => `word${i}`).join(" ");
const DRAFT = "DEVON DRAFT. Job " + INTENT + ".\n\nNOBODY TEACHES YOU WHAT HAPPENS AFTER YOU GET PROMOTED\n\n" + words(300) +
  "\n\nOPEN QUESTIONS FOR TEE\n- Is the cold open the ceremony, or the first morning? Café été ’quotes’ survive.\n";
const PARSE_DRAFT = { ...CHECK_EXISTING, existing_file_id: "", refused: false, draft_text: DRAFT, draft_words: 330, draft_by: "cerebras gpt-oss-120b" };

const stub = (nodes, input) => ({
  $: (name) => ({ first: () => ({ json: nodes[name] && nodes[name][0] }), all: () => (nodes[name] || []).map((json) => ({ json })) }),
  $input: { first: () => ({ json: input }), all: () => [{ json: input }] },
});
const run = (fn, nodes, input) => { const s = stub(nodes, input); return fn(s.$, s.$input)[0].json; };

/** The live Existing? condition, verbatim, that sent the shell to Advance Envelope. */
const oldAdopts = (c) => c.refused === false && typeof c.existing_file_id === "string" && c.existing_file_id.length > 0;

let passed = 0;
const t = (name, f) => { f(); passed += 1; console.log("ok  " + name); };

// ---- the reuse path ------------------------------------------------------

t("the old rule adopts the real blank shell, which is the defect", () => {
  assert.equal(oldAdopts(CHECK_EXISTING), true);
});

t("the new rule refuses the real blank shell, with 0 words named", () => {
  const out = run(checkContent, { "Check Existing": [CHECK_EXISTING] }, { data: SHELL_EXPORT });
  assert.equal(out.refused, true);
  assert.match(out.reason, /holds 0 words, under the 120 word floor/);
  assert.match(out.reason, new RegExp(SHELL_ID));
  assert.match(out.reason, /nothing was deleted/);
});

t("a found draft at the floor is adopted and carries its measured words", () => {
  const out = run(checkContent, { "Check Existing": [CHECK_EXISTING] }, { data: BOM + words(120) });
  assert.equal(out.refused, false);
  assert.equal(out.draft_words, 120);
  assert.equal(out.existing_file_id, SHELL_ID);
});

t("a found file one word under the floor is refused", () => {
  const out = run(checkContent, { "Check Existing": [CHECK_EXISTING] }, { data: words(119) });
  assert.equal(out.refused, true);
  assert.match(out.reason, /holds 119 words/);
});

t("an export that errors is refused, not adopted", () => {
  const out = run(checkContent, { "Check Existing": [CHECK_EXISTING] }, { error: { message: "Forbidden - perhaps check your credentials?" } });
  assert.equal(out.refused, true);
  assert.match(out.reason, /could not read its text back \(Forbidden/);
});

t("an export with no text field is refused, not adopted", () => {
  const out = run(checkContent, { "Check Existing": [CHECK_EXISTING] }, {});
  assert.equal(out.refused, true);
  assert.match(out.reason, /came back as nothing/);
});

// ---- the one call create ---------------------------------------------------

/** Splits a multipart/related body the way a server reads it, RFC 2046. */
function parts(body, boundary) {
  const sep = "--" + boundary;
  assert.ok(body.endsWith(sep + "--"), "closing delimiter");
  const chunks = body.slice(0, -(sep.length + 2)).split(sep + "\r\n").slice(1).map((c) => c.replace(/\r\n$/, ""));
  return chunks.map((c) => { const at = c.indexOf("\r\n\r\n"); return { head: c.slice(0, at), body: c.slice(at + 4) }; });
}

t("the upload is one body: metadata naming a Google Doc, then the exact text", () => {
  const out = run(buildUpload, {}, PARSE_DRAFT);
  const [meta, text] = parts(out.upload_body, out.upload_boundary);
  assert.match(meta.head, /application\/json; charset=UTF-8/);
  const m = JSON.parse(meta.body);
  assert.equal(m.mimeType, "application/vnd.google-apps.document");
  assert.deepEqual(m.parents, [FOLDER]);
  assert.equal(m.name, NAME);
  assert.deepEqual(m.appProperties, { devon_idempotency_key: IDEM, devon_intent_id: INTENT, devon_action: "drive.draft" });
  assert.match(text.head, /text\/plain; charset=UTF-8/);
  assert.equal(text.body, DRAFT, "the text part is the draft byte for byte, accents, quotes and line breaks included");
});

t("a draft containing the boundary gets a longer boundary, never a cut text", () => {
  const sneaky = { ...PARSE_DRAFT, draft_text: DRAFT + "\n--devon_draft_" + INTENT + "\n" };
  const out = run(buildUpload, {}, sneaky);
  assert.notEqual(out.upload_boundary, "devon_draft_" + INTENT);
  assert.equal(sneaky.draft_text.indexOf(out.upload_boundary), -1);
  const [, text] = parts(out.upload_body, out.upload_boundary);
  assert.equal(text.body, sneaky.draft_text);
});

// ---- the result after create --------------------------------------------

const CREATED = { id: "1NEWDOCidXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", name: NAME, mimeType: "application/vnd.google-apps.document", createdTime: "2026-10-24T01:00:00.000Z" };
const nodes = (create, confirm) => ({ "Parse Draft": [PARSE_DRAFT], "Create Doc": [create], "Confirm Properties": confirm });

t("a created Doc that reads back full is recorded with the words Drive holds", () => {
  const out = run(docResult, nodes(CREATED, [{ id: CREATED.id }]), { data: BOM + DRAFT });
  assert.equal(out.refused, false);
  assert.equal(out.id, CREATED.id);
  assert.equal(out.properties_verified, true);
  assert.equal(out.draft_words, DRAFT.split(/\s+/).filter(Boolean).length);
});

t("a created Doc that reads back empty is refused, the 2026-10-22 shape", () => {
  const out = run(docResult, nodes(CREATED, [{ id: CREATED.id }]), { data: SHELL_EXPORT });
  assert.equal(out.refused, true);
  assert.match(out.reason, /reads back with 0 words/);
});

t("a create Forbidden is refused and says no document was left", () => {
  const out = run(docResult, nodes({ error: { message: "Forbidden - perhaps check your credentials?" } }, []), { error: { message: "no id" } });
  assert.equal(out.refused, true);
  assert.match(out.reason, /one call, so a refused create leaves no document/);
});

t("a create that made a plain text file, not a Doc, is refused", () => {
  const out = run(docResult, nodes({ ...CREATED, mimeType: "text/plain" }, [{ id: CREATED.id }]), { data: DRAFT });
  assert.equal(out.refused, true);
  assert.match(out.reason, /as text\/plain rather than a Google Doc/);
});

t("a read back that errors is refused, not recorded as written", () => {
  const out = run(docResult, nodes(CREATED, [{ id: CREATED.id }]), { error: { message: "Forbidden" } });
  assert.equal(out.refused, true);
  assert.match(out.reason, /could not read its text back \(Forbidden\)/);
});

t("properties_verified stays false when the search did not find the new file", () => {
  const out = run(docResult, nodes(CREATED, [{ id: "someOtherFile" }]), { data: DRAFT });
  assert.equal(out.refused, false);
  assert.equal(out.properties_verified, false);
});

console.log(`\n${passed} passed`);
