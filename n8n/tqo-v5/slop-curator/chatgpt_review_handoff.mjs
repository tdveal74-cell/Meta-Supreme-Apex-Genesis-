/**
 * No-provider ChatGPT review handoff for TQO.
 *
 * Packet construction is deterministic and never authorizes publication.
 * Signed returns may ONLY be issued by a separately authorized, trusted
 * verification service after it checks the actual ChatGPT review, Script
 * Doctor output and independent source evidence. Never put signing secrets
 * in the prompt, the packet, an n8n row or repository.
 */
import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { assessTqoDraft } from "./tqo_curator_gate.mjs";

const sha = text => createHash("sha256").update(text, "utf8").digest("hex");
const hex64 = value => typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const nonempty = value => typeof value === "string" && value.trim().length > 0;

function packetIdentity(packet) {
  return sha(JSON.stringify({
    schemaVersion: "tqo-chatgpt-review-v1",
    brand: packet.brand,
    scriptSha256: packet.scriptSha256,
    voiceCardRef: packet.voiceCardRef,
    doctorRubricRef: packet.doctorRubricRef,
    approvedSourceRefs: packet.approvedSourceRefs,
  }));
}

export function prepareChatgptReviewHandoff(input) {
  if (!input || input.brand !== "TQO" || !nonempty(input.script)) {
    throw new Error("TQO final script required");
  }
  if (!nonempty(input.voiceCardRef) || !nonempty(input.doctorRubricRef)) {
    throw new Error("versioned voice card and Script Doctor rubric references required");
  }
  if (!Array.isArray(input.approvedSourceRefs) || !input.approvedSourceRefs.length ||
      input.approvedSourceRefs.some(x => !nonempty(x))) {
    throw new Error("approved source references required");
  }
  const packet = {
    schemaVersion: "tqo-chatgpt-review-v1",
    brand: "TQO",
    status: "AWAITING_CHATGPT_REVIEW",
    script: input.script,
    scriptSha256: sha(input.script),
    voiceCardRef: input.voiceCardRef,
    doctorRubricRef: input.doctorRubricRef,
    approvedSourceRefs: [...input.approvedSourceRefs],
  };
  packet.packetId = packetIdentity(packet);
  return packet;
}

export function verifySignedChatgptReview({ packet, signedReturn, signingSecret }) {
  const hold = reason => ({ state: "HOLD", reason, humanApprovalRequired: true });
  if (!packet || packet.schemaVersion !== "tqo-chatgpt-review-v1" ||
      packet.brand !== "TQO" || !nonempty(packet.script) ||
      !hex64(packet.scriptSha256) || packet.scriptSha256 !== sha(packet.script) ||
      !hex64(packet.packetId) || packet.packetId !== packetIdentity(packet)) {
    return hold("missing, modified or stale review packet");
  }
  if (!signedReturn || !signedReturn.payload || !hex64(signedReturn.signature) ||
      typeof signingSecret !== "string" || signingSecret.length < 32) {
    return hold("trusted verification signature or secret missing");
  }
  const signature = createHmac("sha256", signingSecret)
    .update(JSON.stringify(signedReturn.payload), "utf8").digest("hex");
  if (!timingSafeEqual(Buffer.from(signature, "hex"), Buffer.from(signedReturn.signature, "hex"))) {
    return hold("trusted verifier signature invalid");
  }
  const p = signedReturn.payload;
  if (p.packetId !== packet.packetId || p.brand !== "TQO" ||
      p.draftSha256 !== packet.scriptSha256 ||
      p.verifierRole !== "independent-review-verifier" ||
      !nonempty(p.verifierId) ||
      !nonempty(p.verifiedAt) || !Number.isFinite(Date.parse(p.verifiedAt))) {
    return hold("verified return not tied to this final script and review packet");
  }
  // A valid HMAC establishes which trusted actor attested to these claims.
  // The signer MUST independently authenticate evidence/doctor/editorial
  // receipts. Signing these booleans directly from model JSON is forbidden.
  const result = assessTqoDraft({
    brand: "TQO",
    script: packet.script,
    draftSha256: packet.scriptSha256,
    editorial: p.editorial,
    scriptDoctor: p.scriptDoctor,
    evidenceReceipt: p.evidenceReceipt,
  });
  return {
    ...result,
    packetId: packet.packetId,
    reviewVerifier: p.verifierId,
    // Still not RELEASE_ELIGIBLE. Existing QC and authenticated human approval
    // continue to own that decision.
    humanApprovalRequired: true,
  };
}
