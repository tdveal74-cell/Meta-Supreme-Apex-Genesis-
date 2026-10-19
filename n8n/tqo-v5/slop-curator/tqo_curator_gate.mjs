import { createHash } from "node:crypto";
// Staging-only, deterministic reviewer for The Quiet Operator.
// This is not an n8n deployment or a substitute for Sources Gate, QC or human approval.
export const TQO_SLOP_POLICY = Object.freeze({ version: "tqo-slop-v1", minScore: 90 });

const BLOCKED_WORDS = /\b(?:actually|leverage|probably|maybe|really)\b/gi;
const BLOCKED_PHRASE = /\bfree audit linked below\b/i;
const SHA256 = /^[a-f0-9]{64}$/i;

function validScore(score) {
  return typeof score === "number" && Number.isFinite(score) && score >= 0 && score <= 100;
}

export function lintTqoText(text) {
  const s = String(text || "");
  const hardFailures = [];
  if (/[\u2013\u2014]/.test(s)) hardFailures.push("em/en dash in narrated text");
  if (s.includes(";")) hardFailures.push("semicolon in narrated text");
  for (const m of s.matchAll(BLOCKED_WORDS)) hardFailures.push("banned word: " + m[0].toLowerCase());
  if (BLOCKED_PHRASE.test(s)) hardFailures.push("retired CTA: free audit linked below");
  // These are context-sensitive: report them, never mechanically rewrite them.
  const reviewFlags = [];
  if (/\b(?:it's|it is) not\b[^.!?]{0,140}\b(?:it's|it is)\b/i.test(s)) {
    reviewFlags.push("possible repeated negative-to-positive reveal; inspect in context");
  }
  return { hardFailures: [...new Set(hardFailures)], reviewFlags };
}

/**
 * Assessment and doctor receipts must be bound by the trusted orchestration
 * layer to the SHA-256 of the exact final draft. Do not ask the model to
 * calculate or invent a hash. A passing result only proceeds to existing gates.
 */
export function assessTqoDraft(input) {
  const failures = [];
  if (!input || input.brand !== "TQO") {
    return { state: "HOLD", threshold: TQO_SLOP_POLICY.minScore, failures: ["missing or incorrect TQO brand"], humanApprovalRequired: true };
  }
  const script = String(input.script || "");
  if (!script.trim()) failures.push("final script missing");
  const suppliedHash = String(input.draftSha256 || "");
  if (!SHA256.test(suppliedHash)) {
    failures.push("trusted final-draft SHA-256 missing or invalid");
  } else {
    // Recompute against the exact final text, including whitespace. A valid-looking
    // hash supplied by a model or a stale upstream node is not trusted on its own.
    const computedHash = createHash("sha256").update(script, "utf8").digest("hex");
    if (computedHash !== suppliedHash.toLowerCase()) {
      failures.push("trusted final-draft SHA-256 does not match script text");
    }
  }
  const lint = lintTqoText(script);
  failures.push(...lint.hardFailures);

  const editorial = input.editorial || {};
  if (editorial.schemaVersion !== TQO_SLOP_POLICY.version) failures.push("Slop Curator report schema missing or unrecognized");
  if (editorial.draftSha256 !== input.draftSha256) failures.push("Slop Curator report is not bound to the final script");
  if (!validScore(editorial.score) || editorial.score < TQO_SLOP_POLICY.minScore) {
    failures.push("Slop Curator score missing, invalid or below 90");
  }
  if (editorial.verdict !== "PASS") failures.push("Slop Curator verdict does not pass");
  if (editorial.voicePreserved !== true || editorial.factualFidelity !== true ||
      editorial.constraintsPassed !== true) failures.push("voice, factual fidelity or hard constraints not verified");
  if (!Array.isArray(editorial.hardFailures) || editorial.hardFailures.length) {
    failures.push("Slop Curator hard-failure report missing or nonempty");
  }

  const doctor = input.scriptDoctor || {};
  if (doctor.draftSha256 !== input.draftSha256) failures.push("Script Doctor report is missing or stale");
  if (!validScore(doctor.score) || doctor.score < TQO_SLOP_POLICY.minScore) {
    failures.push("Script Doctor score missing, invalid or below 90");
  }
  if (!["PASS", "REPAIRED"].includes(doctor.verdict)) failures.push("Script Doctor verdict does not pass");

  // This is an independent deterministic receipt, not a claim made by the curator model.
  const evidence = input.evidenceReceipt || {};
  if (evidence.draftSha256 !== input.draftSha256 || evidence.verified !== true) {
    failures.push("independent source/provenance receipt missing or stale");
  }

  return {
    state: failures.length ? "HOLD" : "READY_FOR_EXISTING_GATES",
    threshold: TQO_SLOP_POLICY.minScore,
    failures: [...new Set(failures)],
    reviewFlags: lint.reviewFlags,
    // Never return SHIP, APPROVED, PUBLISHED or RELEASE_ELIGIBLE.
    humanApprovalRequired: true
  };
}
