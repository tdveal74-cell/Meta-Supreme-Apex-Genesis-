/**
 * Universal 90 live continuity candidate, guarded by exact readback SHA pins.
 * Allows SCRIPT/QC scoring to continue at 90, but blocks all V5 publication
 * and DEVON repurposing until the independent signed-review lane exists.
 * Does not write a workflow, publish, use credentials, or spend.
 */
import { buildLiveUniversal90Candidate } from "./live_v5_universal90_candidate.mjs";
import { buildDevonBot90Candidates } from "./live_devon_bot_universal90_candidate.mjs";

export function once(code,oldText,newText,label) {
  if (typeof code!=="string" || code.split(oldText).length!==2)
    throw Error("HOLD: "+label+" candidate drift");
  return code.replace(oldText,newText);
}
const decode=raw=>{const v=JSON.parse(raw);return Array.isArray(v)?v[0]:v;};
const encode=work=>[work];
const nameNode=(work,name)=>{
  const found=work.nodes.filter(n=>n.name===name);
  if(found.length!==1)throw Error("HOLD: "+name+" missing/duplicate");
  return found[0];
};
function replaceCode(work,name,oldText,newText,label) {
  const node=nameNode(work,name);
  node.parameters.jsCode=once(node.parameters.jsCode,oldText,newText,label);
}
function restore(original, draft, allowed) {
  const source=decode(original);
  const candidate=decode(draft);
  const copy=structuredClone(source);
  for(const name of allowed){
    nameNode(copy,name).parameters.jsCode=nameNode(candidate,name).parameters.jsCode;
  }
  for(const n of copy.nodes){
    const o=nameNode(source,n.name);
    if(!allowed.includes(n.name) &&
       JSON.stringify(n)!==JSON.stringify(o))throw Error("HOLD: unexpected node changed");
  }
  if(copy.id!==source.id||copy.active!==source.active||
     JSON.stringify(copy.connections)!==JSON.stringify(source.connections)||
     JSON.stringify(copy.settings)!==JSON.stringify(source.settings)||
     JSON.stringify(copy.nodes.map(n=>n.credentials))!==JSON.stringify(source.nodes.map(n=>n.credentials))){
    throw Error("HOLD: original graph identity or credentials altered");
  }
  return encode(copy);
}

export function buildContinuityCandidates(v5Export,recordExport,repurposeExport) {
  // Both transformations throw on any deviation from independently captured
  // exact live export SHA and target node SHA.
  const v5=buildLiveUniversal90Candidate(v5Export);
  const bots=buildDevonBot90Candidates(recordExport,repurposeExport);
  const scriptLine="\nfailures.push('Universal 90 independent final-script receipt not yet integrated');";
  const resultGate="\nif (result.state === 'READY_FOR_HUMAN_REVIEW') return [{ json: { doctorGate: 'HOLD', doctorGateReason: 'Universal 90 independent final-script receipt not yet integrated', qc_score: score, qc_verdict: verdict, rowId: f.id } }];";
  const activeV5=restore(v5Export,v5.candidate,
    ["Script Gate: Quality","Parse QC + Set Verdict","QC Doctor Gate","OS 28: Publish Gate"]);
  replaceCode(activeV5[0],"Script Gate: Quality",scriptLine,"",
    "leave Script Doctor scoring live at >=90");
  replaceCode(activeV5[0],"QC Doctor Gate",resultGate,"",
    "keep QC in human review while publisher stays locked");
  // The OS28 publishing node retains the independently verified receipt HOLD,
  // even for a score of 100 and manual WAIVED.
  const activeRecord=restore(recordExport,bots.record.draft,["Run Gate"]);
  replaceCode(activeRecord[0],"Run Gate",
    "\n  failures.push('Universal independent final-script verifier not yet connected');","",
    "allow scored script QC records");
  replaceCode(activeRecord[0],"Run Gate",
    "  const passed = false; // Until trusted final-script verification exists, never authorize a recorded QC pass.",
    "  const passed = meetsScore; // Numeric QC record only; repurpose still signed-receipt HOLD.",
    "allow scored QC records");
  const activeRepurpose=restore(repurposeExport,bots.repurpose.draft,["QC Gate"]);
  // This gate deliberately remains blocked even for forged user-supplied
  // passed=true records. No repurpose or paid media operation is authorized.
  return {
    v5:activeV5,
    devonQc:activeRecord,
    devonRepurpose:activeRepurpose,
    status:"READY_FOR_SEPARATE_LIVE_DEPLOYMENT",
    pending:"Independent evidence signer / signed final artifact needed to unlock publishing",
  };
}
