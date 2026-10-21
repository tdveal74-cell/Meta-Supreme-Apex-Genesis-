'use strict';
// Public-key-only verifier. This code cannot invoke Claude or sign a result.
const crypto = require('crypto');
function verifyAIReview(envelope, expected, publicKeyPem, now=Date.now()) {
  const base={aiReviewPassed:false,state:'HOLD',reviewKind:'AI_REVIEW',threshold:90,
    humanApprovalRequired:true,publicationAuthorized:false,spendAuthorized:false};
  const hold=reason=>({...base,reason});
  const nonempty=x=>typeof x==='string'&&x.trim().length>0;
  const hash64=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
  try {
    if (!expected||!nonempty(expected.artifact)||!nonempty(expected.brand)||!nonempty(expected.scope)||!Number.isFinite(now))return hold('Final script or expected review scope missing');
    const hash=crypto.createHash('sha256').update(expected.artifact,'utf8').digest('hex');
    if (expected.artifactSha256!==hash)return hold('Final artifact identity changed');
    if (!envelope||typeof envelope.payload!=='string'||Buffer.byteLength(envelope.payload)>16000||typeof envelope.signature!=='string'||!/^[A-Za-z0-9+/]{86}==$/.test(envelope.signature))return hold('No signed AI review for this final artifact');
    const key=crypto.createPublicKey(publicKeyPem);
    if(key.asymmetricKeyType!=='ed25519'||!crypto.verify(null,Buffer.from(envelope.payload,'utf8'),key,Buffer.from(envelope.signature,'base64')))return hold('AI review signature invalid');
    const p=JSON.parse(envelope.payload);
    if(p.schemaVersion!=='devon-ai-review-summary-v1'||p.reviewKind!=='AI_REVIEW'||p.issuer!=='DEVON-AI-review-orchestrator'||p.policyVersion!=='ecosystem-quality90-ai-v2')return hold('Wrong AI receipt schema, issuer or policy');
    if(p.artifactSha256!==hash||p.brand!==expected.brand||p.scope!==expected.scope||p.rubricVersion!==expected.brand.toLowerCase()+'-'+expected.scope+'-ai-v2')return hold('AI review not bound to this brand, final text and scope');
    if(!hash64(p.packetId)||!hash64(p.rulesSha256)||!hash64(p.reportSha256)||!nonempty(p.reviewId)||!/^[A-Za-z0-9_-]{1,100}$/.test(p.reviewId))return hold('AI review identity incomplete');
    const start=Date.parse(p.issuedAt),end=Date.parse(p.expiresAt);
    if(!Number.isFinite(start)||!Number.isFinite(end)||start>now+120000||now>=end||end<=start||end-start>86400000)return hold('AI review expired or future dated');
    const obs=p.observation;
    if(p.reviewer!=='claude'||!['openai','google','human'].includes(p.producerProvider)||!obs||obs.provider!=='anthropic'||obs.provider===p.producerProvider||obs.source!=='observed_cli_run'||!nonempty(obs.sessionId)||!nonempty(obs.model)||!obs.model.startsWith('claude-')||obs.authMethod!=='claude.ai')return hold('Observed separate Claude review not established');
    if(p.state!=='READY_FOR_TEE_REVIEW'||!Number.isInteger(p.score)||p.score<90||p.score>100)return hold('AI review score or verdict did not clear');
    if(p.humanApprovalRequired!==true||p.humanApproval!==null||p.publicationAuthorized!==false||p.spendAuthorized!==false)return hold('AI review improperly claims human approval or spend authority');
    return {...base,aiReviewPassed:true,state:'READY_FOR_TEE_REVIEW',reason:'Verified AI review; separate human publication approval is still required',score:p.score,
      brand:p.brand,scope:p.scope,artifactSha256:hash,packetId:p.packetId,reviewId:p.reviewId,model:obs.model,issuedAt:p.issuedAt,expiresAt:p.expiresAt,rubricVersion:p.rubricVersion};
  }catch{return hold('AI receipt unavailable, malformed or unverifiable');}
}
module.exports={verifyAIReview};
