// Portable, OFFLINE universal-90 review boundary for ecosystem brands.
// This does not call ChatGPT, sign a review, authorize spending, or publish.
// Any trusted signer must independently verify the review before signing.
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

export const ECOSYSTEM_QUALITY_POLICY = Object.freeze({
  version: "ecosystem-quality-90-v1", minScore: 90,
  knownBrands: ["TQO", "NCO_FORGE", "TSWS", "ACX", "EDITFORGE", "WHATBROKE", "DEVON", "META_SUPREME_X"],
});
const hash = s => createHash("sha256").update(s, "utf8").digest("hex");
const validHash = s => typeof s === "string" && /^[a-f0-9]{64}$/i.test(s);
const meaningful = s => typeof s === "string" && s.trim().length > 0;
const aliases = Object.freeze({
  "NCO": "NCO_FORGE", "NCO FORGE": "NCO_FORGE",
  "THE QUIET OPERATOR": "TQO", "THE SHADOW WE SHARE": "TSWS",
  "EDITFORGE DIGITAL": "EDITFORGE", "META SUPREME X": "META_SUPREME_X",
});
const normalize = value => {
  const label = String(value || "").trim().toUpperCase();
  return aliases[label] || label;
};
const canonBrands = new Set(["TSWS", "ACX"]);

function identity(packet) {
  const { policyVersion, brand, finalArtifactSha256, rubricRef, brandRulesRef,
    evidenceRefs, requiredCanon } = packet;
  return hash(JSON.stringify({ policyVersion, brand, finalArtifactSha256,
    rubricRef, brandRulesRef, evidenceRefs, requiredCanon }));
}

/** Create a durable, revision-bound review handoff, not an approval. */
export function prepareEcosystemReview(input) {
  const brand = normalize(input?.brand);
  if (!ECOSYSTEM_QUALITY_POLICY.knownBrands.includes(brand)) {
    throw new Error("unregistered brand requires an explicit reviewed quality profile");
  }
  if (!meaningful(input?.finalArtifact) || !meaningful(input?.rubricRef)
      || !meaningful(input?.brandRulesRef)
      || !Array.isArray(input?.evidenceRefs)
      || !input.evidenceRefs.length || input.evidenceRefs.some(x => !meaningful(x))) {
    throw new Error("exact final artifact, versioned rubric/brand rules and evidence references required");
  }
  if (canonBrands.has(brand) && !meaningful(input?.canonRef)) {
    throw new Error("locked story canon reference required");
  }
  const packet = {
    policyVersion: ECOSYSTEM_QUALITY_POLICY.version, brand,
    status: "AWAITING_INDEPENDENT_REVIEW",
    finalArtifact: input.finalArtifact,
    finalArtifactSha256: hash(input.finalArtifact),
    rubricRef: input.rubricRef, brandRulesRef: input.brandRulesRef,
    evidenceRefs: [...input.evidenceRefs],
    requiredCanon: canonBrands.has(brand) ? input.canonRef : null,
  };
  packet.packetId = identity(packet);
  return packet;
}

export function verifyEcosystemReview({ packet, signedReturn, signingSecret }) {
  const hold = reason => ({
    state: "HOLD", reason, threshold: 90, humanApprovalRequired: true,
  });
  const brand = normalize(packet?.brand);
  if (!packet || packet.policyVersion !== ECOSYSTEM_QUALITY_POLICY.version
      || !ECOSYSTEM_QUALITY_POLICY.knownBrands.includes(brand)
      || packet.brand !== brand || !meaningful(packet.finalArtifact)
      || !validHash(packet.finalArtifactSha256)
      || hash(packet.finalArtifact) !== packet.finalArtifactSha256
      || !validHash(packet.packetId) || packet.packetId !== identity(packet)
      || !meaningful(packet.rubricRef) || !meaningful(packet.brandRulesRef)
      || !Array.isArray(packet.evidenceRefs) || !packet.evidenceRefs.length
      || packet.evidenceRefs.some(x => !meaningful(x))
      || (canonBrands.has(brand) && !meaningful(packet.requiredCanon))) {
    return hold("missing or modified final artifact, profile, evidence or packet hash");
  }
  if (!signedReturn || typeof signedReturn !== "object"
      || !signedReturn.payload || !validHash(signedReturn.signature)
      || typeof signingSecret !== "string" || signingSecret.length < 32) {
    return hold("independent verifier attestation missing");
  }
  const expected = createHmac("sha256", signingSecret)
    .update(JSON.stringify(signedReturn.payload), "utf8").digest("hex");
  if (!timingSafeEqual(Buffer.from(expected, "hex"),
    Buffer.from(signedReturn.signature, "hex"))) {
    return hold("independent verifier signature invalid");
  }
  const p = signedReturn.payload;
  if (p.packetId !== packet.packetId || p.brand !== brand
      || p.finalArtifactSha256 !== packet.finalArtifactSha256
      || p.policyVersion !== packet.policyVersion
      || p.rubricRef !== packet.rubricRef || p.brandRulesRef !== packet.brandRulesRef
      || p.verifierRole !== "independent-review-verifier"
      || !meaningful(p.verifierId) || !meaningful(p.verifiedAt)
      || !Number.isFinite(Date.parse(p.verifiedAt))) {
    return hold("attestation not independently bound to the reviewed version");
  }
  const review = p.qualityReview;
  if (!review || !Number.isFinite(review.score)
      || review.score < 90 || review.score > 100
      || review.verdict !== "PASS") {
    return hold("quality score missing, invalid, below 90 or not passed");
  }
  if (!Array.isArray(review.hardFailures) || review.hardFailures.length
      || review.criticalOrHigh !== 0
      || review.voiceVerified !== true || review.brandRulesVerified !== true
      || review.factualFidelityVerified !== true) {
    return hold("hard failure, critical finding or brand-specific review remains");
  }
  if (p.evidenceReceipt?.verified !== true
      || p.evidenceReceipt.finalArtifactSha256 !== packet.finalArtifactSha256) {
    return hold("independent evidence receipt missing or stale");
  }
  if (canonBrands.has(brand)
      && (p.canonReceipt?.verified !== true
      || p.canonReceipt.canonRef !== packet.requiredCanon
      || p.canonReceipt.finalArtifactSha256 !== packet.finalArtifactSha256)) {
    return hold("locked canon verification missing or stale");
  }
  return {
    state: "READY_FOR_EXISTING_GATES", brand, score: review.score,
    threshold: 90, packetId: packet.packetId,
    verifierId: p.verifierId, humanApprovalRequired: true,
  };
}
