/**
 * DEVON universal-90 isolated staging verifier.
 *
 * Offline, no provider/network access, no signing, no deployment, no publishing.
 * A real review must be signed by a separately authorized evidence verifier.
 * Always outputs HOLD or VERIFIED_STAGING_ONLY, never release eligibility.
 *
 * The host operator (not n8n or the writer) owns DEVON_Q90_STAGE_ROOT.
 * Layout:
 *   root/trust/registry.json
 *   root/reviews/<id>/packet.json
 *   root/reviews/<id>/final.txt
 *   root/reviews/<id>/attestation.json
 *
 * Every directory must be owner-only (0700), regular file owner-only (0600)
 * and owned by the running process. Symlinks are refused.
 */
import { existsSync, lstatSync, readFileSync } from "node:fs";
import { join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { verifySecureReviewIntake } from "./secure_review_intake.mjs";

const REVIEW_ID = /^[a-zA-Z0-9_-]{1,64}$/;
const ROOT_MAX = 160;
const JSON_MAX = 256 * 1024;
const ARTIFACT_MAX = 512 * 1024;

const outcome = (state, reason, extra={}) => ({
  state, reason, policy:"ecosystem-quality-90-v1",
  threshold:90, humanApprovalRequired:true,
  releaseAuthorized:false, publicationAuthorized:false, spendAuthorized:false,
  ...extra,
});
function safeStat(path, type, maxBytes=JSON_MAX) {
  if (!existsSync(path)) throw Error("missing protected local input");
  const s = lstatSync(path);
  if (s.isSymbolicLink() ||
      (type === "dir" ? !s.isDirectory() : !s.isFile()) ||
      (s.mode & 0o077) !== 0 ||
      (typeof process.getuid === "function" && s.uid !== process.getuid()) ||
      (type === "file" && (!s.size || s.size > maxBytes))) {
    throw Error("local owner, permissions, or file type not trustworthy");
  }
}
function readProtected(path,maxBytes) {
  safeStat(path,"file",maxBytes);
  return readFileSync(path,"utf8");
}
function readJson(path) { return JSON.parse(readProtected(path,JSON_MAX)); }

export function runIsolatedVerifier({root,reviewId,now=new Date()}={}) {
  if (typeof root !== "string" || !root.trim() || root.length > ROOT_MAX ||
      typeof reviewId !== "string" || !REVIEW_ID.test(reviewId)) {
    return outcome("HOLD","invalid stage root or review identity");
  }
  try {
    const base=resolve(root);
    const trust=join(base,"trust");
    const reviews=join(base,"reviews");
    const folder=join(reviews,reviewId);
    if (!folder.startsWith(reviews+sep)) throw Error("review path escaped stage root");
    for (const dir of [base,trust,reviews,folder]) safeStat(dir,"dir");
    // Host-controlled trust and final-artifact files never come from caller JSON.
    const registry=readJson(join(trust,"registry.json"));
    const packet=readJson(join(folder,"packet.json"));
    const attestation=readJson(join(folder,"attestation.json"));
    const finalText=readProtected(join(folder,"final.txt"),ARTIFACT_MAX);
    const result=verifySecureReviewIntake({
      packet,attestation,currentFinalArtifact:finalText,trustRegistry:registry,now,
    });
    if (result.state !== "READY_FOR_EXISTING_GATES") {
      return outcome("HOLD","independent review verification did not clear");
    }
    return outcome("VERIFIED_STAGING_ONLY",
      "numeric review verified; production and human approvals not granted",{
      packetId:result.packetId,brand:result.brand,
      verifiedScore:result.score,registryRevision:result.trustRegistryRevision,
    });
  } catch {
    // No error or input text enters stdout/logs; stage fails closed.
    return outcome("HOLD","protected review files unavailable or invalid");
  }
}

if (process.argv[1] &&
    resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  const result=runIsolatedVerifier({
    root:process.env.DEVON_Q90_STAGE_ROOT,
    reviewId:process.argv[2],
  });
  process.stdout.write(JSON.stringify(result)+"\n");
  if (result.state!=="VERIFIED_STAGING_ONLY") process.exitCode=2;
}
