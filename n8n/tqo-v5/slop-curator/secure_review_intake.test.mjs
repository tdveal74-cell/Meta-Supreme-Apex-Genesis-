import test from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign } from "node:crypto";
import { prepareEcosystemReview } from "./ecosystem_review_gate.mjs";
import { verifySecureReviewIntake } from "./secure_review_intake.mjs";

const pair=generateKeyPairSync("ed25519");
const packet=prepareEcosystemReview({
  brand:"TSWS", finalArtifact:"Synthetic artifact.",
  rubricRef:"rubric-v90",brandRulesRef:"rules-v1",canonRef:"canon-v2",
  evidenceRefs:["synthetic-source"],
});
const keys=()=>({schemaVersion:"quality90-trust-v1",registryRevision:"fixture",
  keys:{key1:{issuerId:"evidence-review-office",
    publicKeyPem:pair.publicKey.export({format:"pem",type:"spki"}),
    revoked:false,enabled:true,
    validFrom:"2026-10-18T00:00:00Z",validUntil:"2026-11-01T00:00:00Z",
    allowedBrands:["TSWS"],allowedPolicyVersions:["ecosystem-quality-90-v1"]}}});
const signed=score=>{
  const data={schemaVersion:"ecosystem-review-ed25519-v1",
    keyId:"key1",issuerId:"evidence-review-office",
    issuerRole:"independent-evidence-verifier",
    packetId:packet.packetId,policyVersion:packet.policyVersion,
    brand:packet.brand,finalArtifactSha256:packet.finalArtifactSha256,
    rubricRef:packet.rubricRef,brandRulesRef:packet.brandRulesRef,
    canonRef:packet.requiredCanon,evidenceRefs:packet.evidenceRefs,
    producerId:"author",editorialReviewerId:"editor",
    evidenceVerifierId:"evidence-review-office",
    verifiedAt:"2026-10-20T02:00:00Z",
    quality:{score,verdict:"PASS",hardFailures:[],criticalOrHigh:0,
      factualFidelityVerified:true,voiceVerified:true,brandRulesVerified:true},
    evidenceVerified:true,lockedCanonVerified:true,
    reviewEvidenceRef:"synthetic-editorial-report",
    canonEvidenceRef:"synthetic-canon-report"};
  const payload=JSON.stringify(data);
  return {keyId:"key1",payload,signature:sign(null,Buffer.from(payload),pair.privateKey).toString("base64")};
};
const check=(attestation,changes={})=>verifySecureReviewIntake({
  packet,attestation,currentFinalArtifact:packet.finalArtifact,
  trustRegistry:keys(),now:new Date("2026-10-20T04:18:00Z"),...changes});
test("89 fails, 90 meets numeric floor without release",()=>{
  assert.equal(check(signed(89)).state,"HOLD");
  const p=check(signed(90));
  assert.equal(p.state,"READY_FOR_EXISTING_GATES");
  assert.equal(p.releaseAuthorized,false);
});
test("tampered final text, revoked key and old receipt fail",()=>{
  assert.equal(check(signed(100),{currentFinalArtifact:"Changed."}).state,"HOLD");
  const revoked=keys();revoked.keys.key1.revoked=true;
  assert.equal(check(signed(100),{trustRegistry:revoked}).state,"HOLD");
  assert.equal(check(signed(100),{now:new Date("2026-10-30T04:18:00Z")}).state,"HOLD");
  assert.equal(check({...signed(90),signature:"0".repeat(88)}).state,"HOLD");
});
