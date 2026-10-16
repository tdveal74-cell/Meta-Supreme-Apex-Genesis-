"""Place one approved Support article in the production knowledge base.

The article and its content decision live in `support_articles/<id>.json` and
`<id>.md`. This script moves that exact text into the Support API as the
signed-in account and reads it back. The account that signs in is the owner of
the article and, on `--approve`, the recorded decider, so Tee runs it himself.

    python3 scripts/support_article_import.py how-we-answer-video-questions-v1
    python3 scripts/support_article_import.py how-we-answer-video-questions-v1 --create
    python3 scripts/support_article_import.py how-we-answer-video-questions-v1 --approve

With no flag it only reads: it signs in, lists the account's articles and says
what it would do. `--create` writes when the id is absent and never rewrites an
id that already holds different text. `--approve` records the human decision
and needs the id typed back, because an answered prompt is the only thing that
separates Tee approving from a script approving. The password is read without
echo and the token lives in memory for the run. Neither is printed or stored.
After a failed or uncertain write the script reads before it reports.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from services.company.knowledge import create_article  # noqa: E402
from services.company.marketing import QueueRefusal  # noqa: E402

DEFAULT_BASE = "https://api-production-5644.up.railway.app/api/v1"
ARTICLES = "/company/support/articles"

Transport = Callable[[str, str, Optional[dict], Optional[str]], Tuple[int, object]]


class ImportRefusal(Exception):
    pass


def load_article(article_id: str, directory: Optional[str] = None) -> Dict[str, str]:
    """Read the stored article, check its hash and run the repo's own rules."""
    directory = directory or os.path.join(REPO, "support_articles")
    with open(os.path.join(directory, article_id + ".json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    if manifest["article_id"] != article_id:
        raise ImportRefusal("the manifest names a different article id")
    with open(os.path.join(directory, manifest["body_file"]), encoding="utf-8") as fh:
        body = fh.read()
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if digest != manifest["body_sha256"]:
        raise ImportRefusal(
            "the body no longer matches the approved hash: %s is not %s"
            % (digest, manifest["body_sha256"])
        )
    try:
        create_article(article_id=article_id, title=manifest["title"], body=body)
    except QueueRefusal as exc:
        raise ImportRefusal("the repo rules refuse this article: %s" % exc) from None
    return {"article_id": article_id, "title": manifest["title"], "body": body,
            "sha256": digest}


def http(base: str) -> Transport:
    def call(method: str, path: str, payload: Optional[dict], token: Optional[str]):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(raw)
            except ValueError:
                return exc.code, raw
    return call


def sign_in(call: Transport, email: str, password: str) -> str:
    status, out = call("POST", "/auth/login", {"email": email, "password": password}, None)
    if status != 200 or not isinstance(out, dict) or "access_token" not in out:
        raise ImportRefusal("sign in refused with HTTP %s" % status)
    return out["access_token"]


def read_article(call: Transport, token: str, article_id: str) -> Optional[dict]:
    status, out = call("GET", ARTICLES, None, token)
    if status != 200 or not isinstance(out, list):
        raise ImportRefusal("could not list articles: HTTP %s" % status)
    for row in out:
        if row.get("article_id") == article_id:
            return row
    return None


def same_text(row: dict, article: Dict[str, str]) -> bool:
    return row.get("title") == article["title"] and row.get("body") == article["body"]


def run(call: Transport, article: Dict[str, str], token: str, *, create: bool,
        approve: bool, confirm: Callable[[str], str], note: Optional[str], out=print) -> int:
    aid = article["article_id"]
    row = read_article(call, token, aid)
    if row is None:
        out("ABSENT   %s is not in this account's knowledge base" % aid)
        if not create:
            out("Nothing written. Re-run with --create to store it as a draft.")
            return 0
        status, resp = call("POST", ARTICLES, {"article_id": aid, "title": article["title"],
                                                "body": article["body"]}, token)
        out("CREATE   HTTP %s" % status)
        if status not in (200, 201):
            out("The write did not confirm, so the account is read before anything is claimed.")
        row = read_article(call, token, aid)
        if row is None:
            out("STILL ABSENT after the write. Nothing is stored.")
            return 1
    if not same_text(row, article):
        out("CONFLICT %s holds different text (status %s). Nothing was changed." % (aid, row.get("status")))
        return 1
    out("PRESENT  %s status=%s decided_by=%s" % (aid, row.get("status"), row.get("decided_by")))
    if row.get("status") == "approved":
        out("Already approved. Nothing more to do.")
    elif approve:
        if row.get("status") != "drafted":
            out("Not approvable: status is %s." % row.get("status"))
            return 1
        if confirm("Type the article id to record YOUR approval of this exact text: ") != aid:
            out("Not confirmed. No approval recorded.")
            return 1
        body = {"note": note} if note else {}
        status, _ = call("POST", "%s/%s/approve" % (ARTICLES, aid), body, token)
        out("APPROVE  HTTP %s" % status)
        row = read_article(call, token, aid)
        if row is None or not same_text(row, article):
            out("READBACK failed after the approval. Check the account before relying on it.")
            return 1
    else:
        out("Drafted, not citable. Re-run with --approve to record your decision.")
    out("VERIFIED id=%s title_ok=True body_sha256=%s status=%s decided_by=%s note=%s" % (
        aid, hashlib.sha256(row["body"].encode("utf-8")).hexdigest(), row.get("status"),
        row.get("decided_by"), row.get("decision_note")))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("article_id")
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--email")
    ap.add_argument("--note", help="optional note stored with the approval")
    ap.add_argument("--base", default=DEFAULT_BASE)
    args = ap.parse_args(argv)
    try:
        article = load_article(args.article_id)
        email = args.email or input("Account email: ").strip()
        password = getpass.getpass("Password (hidden): ")
        call = http(args.base)
        token = sign_in(call, email, password)
        return run(call, article, token, create=args.create, approve=args.approve,
                   confirm=input, note=args.note)
    except ImportRefusal as exc:
        print("REFUSED  %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
