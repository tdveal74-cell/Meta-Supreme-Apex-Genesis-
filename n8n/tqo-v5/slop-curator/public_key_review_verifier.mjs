/**
 * Offline public-key ONLY verifier for independent 90/100 review receipts.
 * No signing, account access, n8n mutation, paid providers, or publication.
 * A production key registry and signer are NOT created here.
 */
import { createHash, createPublicKey, verify as ed25519Verify } from "node:crypto";
import { ECOSYSTEM_QUALITY_POLICY } from "./ecosystem_review_gate.mjs";

const digest = text => createHash("sha256").update(text, "utf8").digest("hex");
const nonempty = value => typeof value === "string" && value.trim().length > 0;
const hash64 = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const same = (a,b) => JSON.stringify(a) === JSON.stringify(b);
const supported = new Set(ECOSYSTEM_QUALITY_POLICY.knownBrands);
const lockedCanon = new Set(["TSWS","ACX"]);

export function verifyPublicKeyReview({ packet, attestation, trustedKeys }) {
  const hold = reason => ({
    state: "HOLD", reason, threshold: 90, humanApprovalRequired: true,
  });
  if (!packet || !supported.has(packet.brand)
      || packet.policyVersion !== ECOSYSTEM_QUALITY_POLICY.version
      || !nonempty(packet.finalArtifact)
      || !hash64(packet.finalArtifactSha256)
      || packet.finalArtifactSha256 !== digest(packet.finalArtifact)
      || !hash64(packet.packetId) || !nonempty(packet.rubricRef)
      || !nonempty(packet.brandRulesRef)
      || !Array.isArray(packet.evidenceRefs) || !packet.evidenceRefs.length
      || packet.evidenceRefs.some(x => !nonempty(x))
      || (lockedCanon.has(packet.brand) && !nonempty(packet.requiredCanon))) {
    return hold("unverifiable exact artifact or brand profile");
  }
  const identity = digest(JSON.stringify({
    policyVersion:packet.policyVersion, brand:packet.brand,
    finalArtifactSha256:packet.finalArtifactSha256, rubricRef:packet.rubricRef,
    brandRulesRef:packet.brandRulesRef, evidenceRefs:packet.evidenceRefs,
    requiredCanon:packet.requiredCanon,
  }));
  if (packet.packetId !== identity) return hold("review packet identity changed");

  const id=attestation?.keyId, encoded=attestation?.signature;
  const trusted = typeof id === "string" && trustedKeys && Object.hasOwn(trustedKeys,id)
    ? trustedKeys[id] : null;
  if (!trusted || !nonempty(trusted.issuerId) || !nonempty(trusted.publicKeyPem)
      || typeof attestation?.payload !== "string"
      || attestation.payload.length > 65536
      || typeof encoded !== "string" || !/^[A-Za-z0-9+/]{86}==$/.test(encoded)) {
    return hold("trusted external signer or detached receipt missing");
  }
  let payload;
  try {
    const key = createPublicKey(trusted.publicKeyPem);
    if (key.asymmetricKeyType !== "ed25519") return hold("wrong verifier key algorithm");
    if (!ed25519Verify(null, Buffer.from(attestation.payload,"utf8"),key,
      Buffer.from(encoded,"base64"))) return hold("detached signature invalid");
    payload = JSON.parse(attestation.payload);
  } catch {
    return hold("invalid signature, public key or receipt payload");
  }
  if (!payload || payload.schemaVersion !== "ecosystem-review-ed25519-v1"
      || payload.keyId !== id || payload.issuerId !== trusted.issuerId
      || payload.issuerRole !== "independent-evidence-verifier"
      || payload.packetId !== packet.packetId
      || payload.policyVersion !== packet.policyVersion
      || payload.brand !== packet.brand
      || payload.finalArtifactSha256 !== packet.finalArtifactSha256
      || payload.rubricRef !== packet.rubricRef
      || payload.brandRulesRef !== packet.brandRulesRef
      || payload.canonRef !== packet.requiredCanon
      || !same(payload.evidenceRefs, packet.evidenceRefs)
      || !nonempty(payload.verifiedAt)
      || !Number.isFinite(Date.parse(payload.verifiedAt))) {
    return hold("independent receipt is not bound to this exact final artifact");
  }
  if (!nonempty(payload.producerId) || !nonempty(payload.editorialReviewerId)
      || !nonempty(payload.evidenceVerifierId)
      || payload.producerId === payload.editorialReviewerId
      || payload.producerId === payload.evidenceVerifierId
      || payload.editorialReviewerId === payload.evidenceVerifierId
      || payload.evidenceVerifierId !== trusted.issuerId) {
    return hold("producer, reviewer and evidence-verifier independence unproved");
  }
  const score=payload.quality?.score;
  if (typeof score !== "number" || !Number.isFinite(score) || score < 90
      || score > 100 || payload.quality?.verdict !== "PASS") {
    return hold("quality score missing, invalid, or below 90");
  }
  if (!Array.isArray(payload.quality.hardFailures)
      || payload.quality.hardFailures.length
      || payload.quality.criticalOrHigh !== 0
      || payload.quality.factualFidelityVerified !== true
      || payload.quality.voiceVerified !== true
      || payload.quality.brandRulesVerified !== true
      || payload.evidenceVerified !== true) {
    return hold("hard requirements or independently checked evidence incomplete");
  }
  if (lockedCanon.has(packet.brand) && payload.lockedCanonVerified !== true) {
    return hold("locked canon has not been independently checked");
  }
  return {
    state:"READY_FOR_EXISTING_GATES", threshold:90, score,
    brand:packet.brand, packetId:packet.packetId,
    evidenceVerifierId:trusted.issuerId, humanApprovalRequired:true,
  };
}
