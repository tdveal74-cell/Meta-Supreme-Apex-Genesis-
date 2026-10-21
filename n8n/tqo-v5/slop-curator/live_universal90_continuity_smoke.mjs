/**
 * Offline real-export regression run; reads private exported live JSON only.
 * Never connects to n8n, uses API credentials or publishes.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildContinuityCandidates } from "./live_universal90_continuity_candidate.mjs";
const ids=["qEkGOUsNyVaRAmm6","MmFNWeewHEuG5x8T","wXl6p7hKN74lKH0e"];
const dir=process.env.QUALITY90_CAPTURE_DIR;
if(!dir)throw Error("read-only export directory required");
const raws=ids.map(id=>readFileSync(dir+"/"+id+".json","utf8"));
const out=buildContinuityCandidates(...raws);
const values=[out.v5,out.devonQc,out.devonRepurpose];
const names=[["Script Gate: Quality","Parse QC + Set Verdict","QC Doctor Gate","OS 28: Publish Gate"],["Run Gate"],["QC Gate"]];
let checks=0;
const test=(condition,label)=>{assert.ok(condition,label);checks++;};
for(let i=0;i<3;i++){
  const source=JSON.parse(raws[i])[0], w=values[i][0];
  test(w.id===source.id,"ID retained");
  test(w.active===source.active,"activation retained");
  test(w.nodes.length===source.nodes.length,"node count");
  test(JSON.stringify(w.connections)===JSON.stringify(source.connections),"connections");
  test(JSON.stringify(w.settings)===JSON.stringify(source.settings),"settings");
  test(JSON.stringify(w.nodes.map(n=>n.credentials))===JSON.stringify(source.nodes.map(n=>n.credentials)),"credentials");
  const changed=w.nodes.filter((n,index)=>n.parameters?.jsCode!==source.nodes[index].parameters?.jsCode).map(n=>n.name).sort();
  test(JSON.stringify(changed)===JSON.stringify(names[i].slice().sort()),"exact changed code bodies");
}
const code=(key,node)=>values[key][0].nodes.find(x=>x.name===node).parameters.jsCode;
const invoke=(source,nodes,json,input)=>new Function("$","$json","$input",source)(
  name=>{if(!(name in nodes))throw Error("node "+name+" not stubbed");return{
    first:()=>({json:nodes[name]}), all:()=>nodes[name].map(x=>({json:x})),
  }},json,input)[0].json;
const objective="Check what this model returned";
const script=objective+" "+"A measured workplace check starts with a source and a human. ".repeat(120)+"What would you share in the comments?";
function scriptGate(brand,doctorScore){
 const body={script,title:"The Quiet Test",description:"A calm documented source check",
   broll:"desk,screen,report,notebook,team,source",
   learningObjective:objective,checklist:["Compare sources","Test output","Record gaps"],
   doctorScore,doctorVerdict:"PASS",rhythmScore:75,similarityScore:75};
 return invoke(code(0,"Script Gate: Quality"),{
   "Show Context: Script":{show:brand},
   "Build Doctor Prompt":{original:{draftWords:1400,expansion:"not needed"}},
   "DEVON Recall: Merge":{devonRecallNote:"synthetic"},
 },body);
}
for(const brand of ["TQO","NCO"]){
 const low=scriptGate(brand,89);
 test(low.status==="Error"&&low.gateFailures.some(s=>s.includes("floor of 90")),brand+" 89 refused");
 for(const score of [90,100]){
   const next=scriptGate(brand,score);
   test(next.status==="Scripted",brand+" score "+score+" clears Script Doctor numeric only");
 }
}
function qcParser(score,blockers=[]){
 return invoke(code(0,"Parse QC + Set Verdict"),{
  "Show Context: Publish":{show:"TQO",channel:"The Quiet Operator"},
  "One Row at a Time":{fields:{id:7,Show:"TQO",Season:1,Episode:1}},
  "Build QC Prompt":{airtableId:7},
 },{choices:[{finish_reason:"stop",message:{content:JSON.stringify({scores:{hook:20},total:score,blockers,findings:[],batch_score:9})}}]});
}
test(qcParser(89).qcVerdict==="HOLD","QC 89");
test(qcParser(90).qcVerdict==="SHIP","QC 90");
test(qcParser(100,["unsourced claim"]).qcVerdict==="HOLD","hard blocker 100");
test(code(0,"OS 28: Publish Gate").includes("independent final-script receipt not yet integrated"),"publisher remains locked");
test(!code(0,"OS 28: Publish Gate").includes("gates.qc = verdict === 'SHIP' || verdict === 'WAIVED'"),"no WAIVED");
const botInvoke=(score)=>{
 const body={frameId:"frame-900001",brand:"NCO Forge",stage:"qc",recordedBy:"synthetic",
   script:"Synthetic check. No real source.",qcScore:score,qcVerdict:"SHIP"};
 return invoke(code(1,"Run Gate"),{"QC Record In":{body},"Get Prior Scripts":[]},undefined);
};
test(botInvoke(89).record.passed===false,"bot 89");
test(botInvoke(90).record.passed===true,"bot 90 numeric QC only");
const rows=["script","qc","human"].map(stage=>({stage,passed:true,verdict:"PASS",score:100,
  recorded_at:"2026-10-21T05:00:00Z",script_fingerprint:"forged-matching"}));
const rep=new Function("$","$json","$input",code(2,"QC Gate"))(
 name=>({first:()=>({json:{frameId:"frame-900001",qcNotes:""}})}),
 undefined,{all:()=>rows.map(json=>({json}))})[0].json;
test(rep.ok===false&&String(rep.error).includes("independent final-script receipt"),"repurpose remains locked");
console.log(JSON.stringify({result:"PASS",checks,sourceIds:ids,productionChanged:false,
  publisherLocked:true,repurposeLocked:true,scriptScoringContinues:true}));
