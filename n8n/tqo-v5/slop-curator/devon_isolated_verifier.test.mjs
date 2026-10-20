import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync,mkdirSync,writeFileSync,chmodSync,rmSync,symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runIsolatedVerifier } from "./devon_isolated_verifier.mjs";

function stage() {
  const root=mkdtempSync(join(tmpdir(),"q90-stage-"));
  chmodSync(root,0o700);
  for(const path of ["trust","reviews","reviews/job001"]) {
    mkdirSync(join(root,path),{mode:0o700});
  }
  const save=(relative,obj)=>writeFileSync(join(root,relative),
    typeof obj==="string" ? obj : JSON.stringify(obj),{mode:0o600});
  save("trust/registry.json",{schemaVersion:"quality90-trust-v1",registryRevision:"test-only",keys:{}});
  save("reviews/job001/packet.json",{policyVersion:"ecosystem-quality-90-v1",brand:"TQO"});
  save("reviews/job001/attestation.json",{});
  save("reviews/job001/final.txt","Synthetic final draft. No publication.");
  return {root,save,reviewId:"job001"};
}
test("missing independent verifier signature remains HOLD, never release",()=>{
  const v=stage();
  try {
    const result=runIsolatedVerifier(v);
    assert.equal(result.state,"HOLD");
    assert.equal(result.releaseAuthorized,false);
    assert.equal(result.spendAuthorized,false);
    assert.equal(result.publicationAuthorized,false);
    assert.ok(!JSON.stringify(result).includes("Synthetic final draft"));
  } finally {rmSync(v.root,{force:true,recursive:true});}
});
test("unknown, malformed, traversal and embedded path strings never resolve files",()=>{
  const v=stage();
  try{
    for (const reviewId of ["../trust","../","job/001","","job001/../../trust"]) {
      const result=runIsolatedVerifier({...v,reviewId});
      assert.equal(result.state,"HOLD");
    }
    assert.equal(runIsolatedVerifier({root:"",reviewId:"job001"}).state,"HOLD");
  } finally {rmSync(v.root,{force:true,recursive:true});}
});
test("group-readable trust registry and swapped symlink files fail closed",()=>{
  const v=stage();
  try{
    chmodSync(join(v.root,"trust/registry.json"),0o644);
    assert.equal(runIsolatedVerifier(v).state,"HOLD");
    chmodSync(join(v.root,"trust/registry.json"),0o600);
    rmSync(join(v.root,"reviews/job001/final.txt"));
    symlinkSync(join(v.root,"trust/registry.json"),join(v.root,"reviews/job001/final.txt"));
    assert.equal(runIsolatedVerifier(v).state,"HOLD");
  } finally {rmSync(v.root,{force:true,recursive:true});}
});
test("changed final content or missing source receipt never clears",()=>{
  const v=stage();
  try{
    v.save("reviews/job001/final.txt","Post-editor revision changed the bytes.");
    assert.equal(runIsolatedVerifier(v).state,"HOLD");
    v.save("reviews/job001/attestation.json",{"signature":"pretend"});
    assert.equal(runIsolatedVerifier(v).state,"HOLD");
  } finally {rmSync(v.root,{force:true,recursive:true});}
});
