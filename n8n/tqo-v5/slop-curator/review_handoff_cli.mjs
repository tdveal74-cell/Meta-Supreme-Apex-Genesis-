#!/usr/bin/env node
/**
 * Offline operator entry point. No ChatGPT API calls, provider charges,
 * n8n mutation or signing operation. The independent verifier is a separate
 * authorized service, not this CLI. Never echo scripts or HMAC secrets.
 *
 * node review_handoff_cli.mjs prepare final-input.json /safe/private/packet.json
 * TQO_REVIEW_SIGNING_SECRET=<injected secret> node review_handoff_cli.mjs verify packet.json signed-return.json
 */
import { readFileSync, openSync, writeFileSync, closeSync } from "node:fs";
import { prepareChatgptReviewHandoff, verifySignedChatgptReview } from "./chatgpt_review_handoff.mjs";

const [mode, ...args] = process.argv.slice(2);
const output = obj => process.stdout.write(JSON.stringify(obj) + "\n");
const readJson = path => JSON.parse(readFileSync(path, "utf8"));
const failure = () => { process.exitCode = 2; };

try {
  if (mode === "prepare" && args.length === 2) {
    const packet = prepareChatgptReviewHandoff(readJson(args[0]));
    // A new private file only. Never overwrite an existing review packet.
    const handle = openSync(args[1], "wx", 0o600);
    try { writeFileSync(handle, JSON.stringify(packet, null, 2) + "\n", "utf8"); }
    finally { closeSync(handle); }
    output({ state: packet.status, packetId: packet.packetId, draftSha256: packet.scriptSha256 });
  } else if (mode === "verify" && args.length === 2) {
    const result = verifySignedChatgptReview({
      packet: readJson(args[0]),
      signedReturn: readJson(args[1]),
      signingSecret: process.env.TQO_REVIEW_SIGNING_SECRET,
    });
    // Verify only. A READY verdict never automatically approves or publishes.
    output(result);
    if (result.state !== "READY_FOR_EXISTING_GATES") failure();
  } else {
    output({ state: "HOLD", reason: "usage: prepare <input.json> <private-packet.json> | verify <packet.json> <signed-return.json>" });
    failure();
  }
} catch (e) {
  // Emit only a generic failure marker, not paths, scripts, keys or file contents.
  output({ state: "HOLD", reason: "handoff preparation/verification failed" });
  failure();
}
