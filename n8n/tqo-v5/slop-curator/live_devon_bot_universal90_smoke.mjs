/**
 * No-spend offline smoke against two fingerprint-pinned LIVE export copies.
 * QUALITY90_DEVON_RECORD and QUALITY90_DEVON_REPURPOSE must name private files.
 * Never signs a receipt, mutates the n8n database or publishes.
 */
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { buildDevonBot90Candidates } from "./live_devon_bot_universal90_candidate.mjs";

const recordFile=process.env.QUALITY90_DEVON_RECORD;
const repurposeFile=process.env.QUALITY90_DEVON_REPURPOSE;
if(!recordFile||!repurposeFile)throw Error("independently captured input files required");
const sources=[readFileSync(recordFile,"utf8"),readFileSync(repurposeFile,"utf8")];
const [rec,rep]=Object.values(buildDevonBot90Candidates(...sources));
let assertions=0;
const validate=(a,b,msg)=>{assert.deepEqual(a,b,msg);assertions++};
for(const [i,d] of [rec,rep].entries()){
  const old=JSON.parse(sources[i]),source=Array.isArray(old)?old[0]:old;
  const draft=Array.isArray(d.draft)?d.draft[0]:d.draft;
  validate(draft.nodes.length,source.nodes.length,"node count");
  validate(draft.active,false,"no activation");
  validate(Object.hasOwn(draft,"id"),false,"cannot address live workflow");
  validate(draft.connections,source.connections,"graph preserved");
  validate(draft.settings,source.settings,"settings preserved");
  validate(draft.nodes.map(n=>n.credentials),source.nodes.map(n=>n.credentials),"credential refs preserved");
  const modified=draft.nodes.filter((n,k)=>n.parameters?.jsCode!==source.nodes[k].parameters?.jsCode);
  validate(modified.length,1,"exactly one node body changed");
  new Function("$","$json","$input",d.code);
}
const invoke=(code,b,prior=[])=>{
  const dollar=name=>{
    if(name==="QC Record In")return{first:()=>({json:{body:b}})};
    if(name==="Get Prior Scripts")return{all:()=>prior.map(json=>({json}))};
    throw Error("unexpected synthetic node "+name);
  };
  return new Function("$","$json","$input",code)(dollar,undefined,undefined)[0].json;
};
for(const brand of ["The Quiet Operator","The Shadow We Share","NCO Forge","Ascension Caudex"]){
  for(const score of [89,90,100]){
    const out=invoke(rec.code,{
      frameId:"frame-900001",brand,stage:"qc",recordedBy:"synthetic-checker",
      script:"Synthetic final output. No real sources.",qcScore:score,qcVerdict:"SHIP",
    });
    validate(out.ok,true,"valid intake even when quality hold");
    validate(out.record.score,score,"score unchanged");
    validate(out.record.passed,false,"cannot pass without independent receipt");
    if(score===89) assert.match(out.record.report,/Score or verdict does not clear the 90 floor/);
    else assert.match(out.record.report,/HOLD: trusted independent final-script receipt not yet connected/);
    assertions++;
  }
}
// A caller cannot forge all three stage passed fields to bypass the repurposer.
const repDollar=name=>{
  if(name==="Validate Handoff")return{first:()=>({json:{frameId:"frame-900001",qcNotes:""}})};
  throw Error("unexpected repurposer node "+name);
};
const rows=["script","qc","human"].map(stage=>({json:{
  stage,passed:true,verdict:"PASS",score:100,recorded_at:"2026-10-19T23:00:00Z",
  script_fingerprint:"synthetic-matching-fingerprint",
}}));
const out=new Function("$","$json","$input",rep.code)(repDollar,undefined,{all:()=>rows})[0].json;
validate(out.ok,false,"manual passed rows cannot unlock repurposing");
assert.match(out.error,/Universal independent final-script receipt not yet connected/);
assertions++;
console.log(JSON.stringify({
  state:"PASS",assertions,sourceExportHashes:[rec.report.capturedSha256,rep.report.capturedSha256],
  changedNodes:[rec.report.node,rep.report.node],
  rule:"89 fails numerical bar; 90-100 HOLD pending independent reviewer; forged passed rows still HOLD",
  productionChanged:false,
}));
