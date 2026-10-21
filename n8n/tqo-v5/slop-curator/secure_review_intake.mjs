/**
 * Independent final-artifact review intake. This module verifies only.
 * Trust anchors MUST come from protected host configuration, never a draft,
 * an n8n row, an uploaded packet or an LLM. No signing and no publishing.
 */
import { createHash } from "node:crypto";
import { verifyPublicKeyReview } from "./public_key_review_verifier.mjs";

const sha = text => createHash("sha256").update(text, "utf8").digest("hex");
const validDate = value => typeof value === "string" && Number.isFinite(Date.parse(value));
const safeText = value => typeof value === "string" && value.trim().length > 0;
const MAX_AGE_MS = 72 * 60 * 60 * 1000;
const MAX_FUTURE_SKEW_MS = 5 * 60 * 1000;

export function verifySecureReviewIntake({
  packet, attestation, currentFinalArtifact, trustRegistry, now = new Date(),
}) {
  const hold = reason => ({
    state:"HOLD", reason, threshold:90,
    humanApprovalRequired:true, releaseAuthorized:false,
  });
  if (!safeText(currentFinalArtifact) ||
      currentFinalArtifact !== packet?.finalArtifact ||
      packet?.finalArtifactSha256 !== sha(currentFinalArtifact)) {
    return hold("final stored artifact differs from the reviewed bytes");
  }
  const currentTime = now instanceof Date ? now.getTime() : NaN;
  if (!Number.isFinite(currentTime)) return hold("trusted verification clock unavailable");
  // Trust registry is a host-controlled, reviewed configuration. A caller
  // supplied registry is not trustworthy; this boundary must be outside n8n.
  if (!trustRegistry || trustRegistry.schemaVersion !== "quality90-trust-v1" ||
      !safeText(trustRegistry.registryRevision) ||
      typeof trustRegistry.keys !== "object" || !trustRegistry.keys ||
      Array.isArray(trustRegistry.keys)) {
    return hold("protected trust registry missing");
  }
  const keyId = attestation?.keyId;
  if (typeof keyId !== "string" ||
      !Object.prototype.hasOwnProperty.call(trustRegistry.keys, keyId)) {
    return hold("unrecognized independent verifier");
  }
  const entry = trustRegistry.keys[keyId];
  if (!entry || !safeText(entry.issuerId) || !safeText(entry.publicKeyPem) ||
      entry.revoked === true || entry.enabled !== true ||
      !validDate(entry.validFrom) || !validDate(entry.validUntil) ||
      currentTime < Date.parse(entry.validFrom) ||
      currentTime >= Date.parse(entry.validUntil) ||
      !Array.isArray(entry.allowedBrands) ||
      !entry.allowedBrands.includes(packet.brand) ||
      !Array.isArray(entry.allowedPolicyVersions) ||
      !entry.allowedPolicyVersions.includes(packet.policyVersion)) {
    return hold("issuer disabled, expired, revoked, or not authorized for brand and policy");
  }
  const cryptographic = verifyPublicKeyReview({
    packet, attestation, trustedKeys:{
      [keyId]: { issuerId: entry.issuerId, publicKeyPem: entry.publicKeyPem },
    },
  });
  if (cryptographic.state !== "READY_FOR_EXISTING_GATES") {
    return hold("independent signed review receipt did not verify");
  }
  let payload;
  try { payload = JSON.parse(attestation.payload); }
  catch { return hold("malformed receipt"); }
  if (!validDate(payload.verifiedAt)) return hold("receipt timestamp invalid");
  const verifiedAt = Date.parse(payload.verifiedAt);
  if (verifiedAt < Date.parse(entry.validFrom) ||
      verifiedAt >= Date.parse(entry.validUntil) ||
      verifiedAt > currentTime + MAX_FUTURE_SKEW_MS ||
      currentTime - verifiedAt > MAX_AGE_MS) {
    return hold("review expired, future-dated, or outside verifier key validity");
  }
  if (!safeText(payload.reviewEvidenceRef) ||
      !safeText(payload.canonEvidenceRef) && ["TSWS","ACX"].includes(packet.brand)) {
    return hold("review and canon evidence references required");
  }
  // This only authenticates an independently-issued assertion; the issuer is
  // responsible for inspecting sources and canon BEFORE signing.
  return {
    state:"READY_FOR_EXISTING_GATES", threshold:90,
    score:cryptographic.score, brand:packet.brand,
    packetId:packet.packetId,
    verifierId:cryptographic.evidenceVerifierId,
    trustRegistryRevision:trustRegistry.registryRevision,
    humanApprovalRequired:true, releaseAuthorized:false,
  };
}
