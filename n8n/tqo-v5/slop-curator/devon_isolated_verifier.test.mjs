import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync,mkdirSync,writeFileSync,chmodSync,rmSync,symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runIsolatedVerifier } from "./devon_isolated_verifier.mjs";
import { generateKeyPairSync, sign } from "node:crypto";
import { prepareEcosystemReview } from "./ecosystem_review_gate.mjs";

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

test("ephemeral independently signed 90 receipt reaches staging only, not publishing",()=>{
  const testRun=stage();
  try {
    const k=generateKeyPairSync("ed25519");
    const now=Date.now();
    const packet=prepareEcosystemReview({
      brand:"TQO",finalArtifact:"Synthetic final draft. No publication.",
      rubricRef:"test-rubric-v90",brandRulesRef:"test-brand-v1",
      evidenceRefs:["synthetic-source-snapshot-1"],
    });
    const publicKeyPem=k.publicKey.export({type:"spki",format:"pem"});
    testRun.save("trust/registry.json",{
      schemaVersion:"quality90-trust-v1",registryRevision:"ephemeral-test-only",
      keys:{qa:{issuerId:"independent-test-verifier",publicKeyPem,
        revoked:false,enabled:true,
        validFrom:new Date(now-60000).toISOString(),
        validUntil:new Date(now+60000).toISOString(),
        allowedBrands:["TQO"],allowedPolicyVersions:["ecosystem-quality-90-v1"],
      }},
    });
    const payload={
      schemaVersion:"ecosystem-review-ed25519-v1",
      keyId:"qa",issuerId:"independent-test-verifier",
      issuerRole:"independent-evidence-verifier",
      packetId:packet.packetId,policyVersion:packet.policyVersion,
      brand:packet.brand,finalArtifactSha256:packet.finalArtifactSha256,
      rubricRef:packet.rubricRef,brandRulesRef:packet.brandRulesRef,
      canonRef:packet.requiredCanon,evidenceRefs:packet.evidenceRefs,
      producerId:"synthetic-author",editorialReviewerId:"synthetic-editor",
      evidenceVerifierId:"independent-test-verifier",
      verifiedAt:new Date(now).toISOString(),
      quality:{score:90,verdict:"PASS",hardFailures:[],criticalOrHigh:0,
        factualFidelityVerified:true,voiceVerified:true,brandRulesVerified:true},
      evidenceVerified:true,lockedCanonVerified:true,
      reviewEvidenceRef:"synthetic-editorial-check",
    };
    const raw=JSON.stringify(payload);
    const attestation={keyId:"qa",payload:raw,
      signature:sign(null,Buffer.from(raw),k.privateKey).toString("base64")};
    testRun.save("reviews/job001/packet.json",packet);
    testRun.save("reviews/job001/attestation.json",attestation);
    const passed=runIsolatedVerifier({...testRun,now:new Date(now)});
    assert.equal(passed.state,"VERIFIED_STAGING_ONLY",JSON.stringify(passed));
    assert.equal(passed.verifiedScore,90);
    assert.equal(passed.releaseAuthorized,false);
    assert.equal(passed.publicationAuthorized,false);
    assert.equal(passed.spendAuthorized,false);

    payload.quality.score=89;
    const lower=JSON.stringify(payload);
    testRun.save("reviews/job001/attestation.json",{keyId:"qa",payload:lower,
      signature:sign(null,Buffer.from(lower),k.privateKey).toString("base64")});
    assert.equal(runIsolatedVerifier({...testRun,now:new Date(now)}).state,"HOLD");
  } finally {rmSync(testRun.root,{force:true,recursive:true});}
});
