/**
 * Offline-only, fail-closed universal-90 patch for TWO live DEVON workflows:
 *   DEVON - Bot QC Record
 *   DEVON - Bot Handoff to Repurpose
 * These are NEVER modified here. Inputs must match precise read-only captures.
 */
import { createHash } from "node:crypto";
const sha = raw => createHash("sha256").update(raw,"utf8").digest("hex");

export const DEVON_BOT_CAPTURE = Object.freeze({
  record: {
    id:"MmFNWeewHEuG5x8T", updatedAt:"2026-10-19T04:02:41.195Z",
    nodeCount:8, nodeName:"Run Gate",
    exportSha256:"c44fc2796b15e521015e108a94f94e5f757e396f163278fddb14e518fa6ff22f",
    codeSha256:"2f38bb3fdb1b96ece79ff521fdbd448c78650ef0d53231513bb0617269a53259",
  },
  repurpose: {
    id:"wXl6p7hKN74lKH0e", updatedAt:"2026-10-19T04:02:44.219Z",
    nodeCount:11, nodeName:"QC Gate",
    exportSha256:"7fbf2c739ca2b4e3861f4c49a5c13563fed94071029f89e0f851a0d6f667bac5",
    codeSha256:"4bb150ddaafb3610d4e82ba620254265b106e058ea0cd4c8b9fbc9bf96435779",
  },
});

function once(text,a,b,label) {
  if (text.split(a).length !== 2) throw Error("HOLD: " + label + " live source drift");
  return text.replace(a,b);
}
function load(raw,expected) {
  if (typeof raw !== "string" || sha(raw) !== expected.exportSha256) {
    throw Error("HOLD: live DEVON bot export fingerprint mismatch");
  }
  const value=JSON.parse(raw), work=Array.isArray(value)?value[0]:value;
  if (work?.id!==expected.id || work.updatedAt!==expected.updatedAt
      || work.active!==true || work.nodes?.length!==expected.nodeCount) {
    throw Error("HOLD: live DEVON bot workflow identity drift");
  }
  const found=work.nodes.filter(n=>n.name===expected.nodeName);
  if (found.length!==1 || sha(found[0].parameters?.jsCode||"")!==expected.codeSha256) {
    throw Error("HOLD: live DEVON bot node code drift");
  }
  return {value,work,code:found[0].parameters.jsCode};
}
function stage(source,expected,code) {
  const draft=structuredClone(source);
  const w=Array.isArray(draft)?draft[0]:draft;
  const n=w.nodes.find(n=>n.name===expected.nodeName);
  n.parameters.jsCode=code;
  w.active=false;
  w.name="DRAFT universal 90 - independent verifier NOT CONNECTED";
  delete w.id;
  return {
    draft, code,
    report:{capturedId:expected.id,capturedSha256:expected.exportSha256,
      node:expected.nodeName,nodeSha256:sha(code),
      changedNodeCount:1,state:"INACTIVE_NOT_DEPLOYED"},
  };
}
export function buildDevonBot90Candidates(recordExport,repurposeExport) {
  const rec=load(recordExport,DEVON_BOT_CAPTURE.record);
  let c=once(rec.code,
    "let WORD_FLOOR = 1200, WORD_CEILING = 2400, DOCTOR_FLOOR = 99, RHYTHM_FLOOR = 50, SIMILARITY_FLOOR = 50, BROLL_FLOOR = 6, SHIP_AT = 99;",
    "let WORD_FLOOR = 1200, WORD_CEILING = 2400, DOCTOR_FLOOR = 90, RHYTHM_FLOOR = 50, SIMILARITY_FLOOR = 50, BROLL_FLOOR = 6, SHIP_AT = 90; // universal quality acceptance",
    "recorder default 99");
  c=once(c,
    "if (brand === 'The Quiet Operator') { DOCTOR_FLOOR = 90; SHIP_AT = 90; }   // Tee 2026-10-18 23:50 ET: TQO QC bar and doctor floor 90. Other brands stay 99 until he rules",
    "// All four registered brands have 90/100 quality floors, Tee 2026-10-19.",
    "recorder brand-specific 99 override");
  c=once(c,
    "  const failures = [];",
    "  const failures = [];\n  failures.push('Universal independent final-script verifier not yet connected');",
    "recorder script receipt");
  c=once(c,
    "  const passed = v === 'SHIP' && s >= SHIP_AT;",
    "  const meetsScore = v === 'SHIP' && s >= SHIP_AT;\n  const passed = false; // Until trusted final-script verification exists, never authorize a recorded QC pass.",
    "recorder QC receipt");
  c=once(c,
    "  return row(passed, v, s, 'QC ' + v + ' ' + s + '/100 (ships at ' + SHIP_AT + ')' + (v === 'SHIP' && s < SHIP_AT ? '. A SHIP under ' + SHIP_AT + ' does not clear.' : '') + '\\n' + String(b.findings || ''), script);",
    "  return row(passed, v, s, 'QC ' + v + ' ' + s + '/100 (ships at ' + SHIP_AT + ')' + (meetsScore ? '. HOLD: trusted independent final-script receipt not yet connected.' : '. Score or verdict does not clear the 90 floor.') + '\\n' + String(b.findings || ''), script);",
    "recorder QC report");

  const rep=load(repurposeExport,DEVON_BOT_CAPTURE.repurpose);
  let d=once(rep.code,
    "QC (SHIP at the brand's bar: TQO 90, others 99) judged on the",
    "QC (SHIP at universal 90) judged on the",
    "repurpose threshold comment");
  d=once(d,
    "at or over the brand bar (TQO 90, others 99)",
    "at or over the universal 90 quality bar",
    "repurpose threshold message");
  d=once(d,"const blocks = [];",
    "const blocks = [];\nblocks.push('Universal independent final-script receipt not yet connected');",
    "repurpose evidence bypass");
  return {
    record:stage(rec.value,DEVON_BOT_CAPTURE.record,c),
    repurpose:stage(rep.value,DEVON_BOT_CAPTURE.repurpose,d),
  };
}
