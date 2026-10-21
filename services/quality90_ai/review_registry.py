"""Read-only public-signature registry. This service never invokes or signs an AI review.
Model runs and private signing happen only in the local authorized CLI. GETs
return an authentic, non-sensitive compact receipt or HOLD; POST is forbidden.
Expose loopback only behind existing TLS and a narrowly scoped IP allowlist.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography.hazmat.primitives import serialization
from review_core import BRANDS, canonical, hold, verify_receipt
from review_gateway import SCOPES, rules_for

SCHEMA = "devon-ai-review-summary-v1"


def export_summary(root, run_id, key):
    root = pathlib.Path(root)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
        raise ValueError("unsafe review ID")
    folder = root / "runs" / run_id
    packet = json.loads((folder / "packet.json").read_text())
    receipt = json.loads((folder / "receipt.json").read_text())
    verified = verify_receipt(receipt, packet, key.public_key())
    p = receipt["payload"]
    scope = next(
        (s for s in SCOPES if packet["rubricVersion"] == f"{packet['brand'].lower()}-{s}-ai-v2"),
        None,
    )
    if not scope:
        raise ValueError("unbound scope; review must use host-bound current brand profile")
    payload = {
        k: p[k]
        for k in [
            "reviewKind",
            "issuer",
            "packetId",
            "artifactSha256",
            "policyVersion",
            "brand",
            "producerProvider",
            "reviewer",
            "rulesSha256",
            "rubricVersion",
            "reportSha256",
            "issuedAt",
            "expiresAt",
        ]
    }
    payload.update(
        {
            "schemaVersion": SCHEMA,
            "scope": scope,
            "reviewId": run_id,
            "state": verified["state"],
            "score": verified.get("score", 0),
            "observation": p["observation"],
            "humanApprovalRequired": True,
            "humanApproval": None,
            "publicationAuthorized": False,
            "spendAuthorized": False,
        }
    )
    raw = canonical(payload)
    envelope = {"payload": raw.decode(), "signature": base64.b64encode(key.sign(raw)).decode()}
    dest = root / "registry" / packet["brand"] / scope
    dest.mkdir(parents=True, mode=0o700, exist_ok=True)
    target = dest / (packet["artifactSha256"] + ".json")
    fd, temp = tempfile.mkstemp(dir=dest, prefix=".receipt-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(canonical(envelope))
        os.chmod(temp, 0o600)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return target


def lookup(root, brands, brand, scope, artifact_sha):
    root = pathlib.Path(root)
    try:
        if (
            brand not in BRANDS
            or scope not in SCOPES
            or not isinstance(artifact_sha, str)
            or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha)
        ):
            return hold("invalid registry identity")
        target = root / "registry" / brand / scope / (artifact_sha + ".json")
        if target.is_symlink():
            return hold("invalid registry storage")
        env = json.loads(target.read_text())
        payload = json.loads(env["payload"])
        public = serialization.load_pem_public_key(
            (root / "issuer/receipt-ed25519.pub.pem").read_bytes()
        )
        public.verify(base64.b64decode(env["signature"], validate=True), env["payload"].encode())
        if (
            payload.get("schemaVersion") != SCHEMA
            or payload.get("brand") != brand
            or payload.get("scope") != scope
            or payload.get("artifactSha256") != artifact_sha
        ):
            return hold("registry binding mismatch")
        run_id = payload["reviewId"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
            return hold("review identity invalid")
        folder = root / "runs" / run_id
        packet = json.loads((folder / "packet.json").read_text())
        receipt = json.loads((folder / "receipt.json").read_text())
        if (
            packet["packetId"] != payload["packetId"]
            or packet["artifactSha256"] != artifact_sha
            or packet["brandRules"] != rules_for(brand, scope, brands)
        ):
            return hold("final packet or applicable rules changed")
        checked = verify_receipt(receipt, packet, public)
        if checked["state"] != payload["state"] or checked["state"] != "READY_FOR_TEE_REVIEW":
            return hold("AI review did not clear or is expired")
        return env
    except Exception:
        return hold("verified AI receipt unavailable")


class RegistryServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, brands):
        self.root = root
        self.brands = brands
        super().__init__(address, RegistryHandler)


class RegistryHandler(BaseHTTPRequestHandler):
    server_version = "DEVON-AIReceipt/1"

    def log_message(self, *args):
        pass

    def answer(self, status, obj):
        raw = canonical(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/healthz":
            return self.answer(
                200, {"status": "ok", "mode": "READ_ONLY_AI_RECEIPTS", "modelCalls": False}
            )
        match = re.fullmatch(r"/receipt/([A-Z_]+)/([a-z_]+)/([a-f0-9]{64})", self.path)
        if not match:
            return self.answer(404, hold("registry route unavailable"))
        return self.answer(200, lookup(self.server.root, self.server.brands, *match.groups()))

    def do_POST(self):
        self.answer(405, hold("registry cannot run, sign or approve reviews"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="/opt/devon/quality90-ai-review")
    p.add_argument("--brands", default="/opt/creator-workspace/brands")
    p.add_argument("--port", type=int, default=7321)
    a = p.parse_args()
    RegistryServer(("127.0.0.1", a.port), a.root, a.brands).serve_forever()


if __name__ == "__main__":
    main()
