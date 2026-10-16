"""The Support article import: no write without a flag, no approval without Tee typing the id."""

import json
import os
import shutil

import pytest

from scripts import support_article_import as imp

AID = "how-we-answer-video-questions-v1"


class FakeServer:
    """Just enough of the Support API: owner scoped list, create, approve."""

    def __init__(self, rows=None, fail_create=False, lose_create=False):
        self.rows = {r["article_id"]: dict(r) for r in (rows or [])}
        self.calls = []
        self.fail_create = fail_create
        self.lose_create = lose_create

    def __call__(self, method, path, payload, token):
        self.calls.append((method, path, payload, token))
        if path == "/auth/login":
            return 200, {"access_token": "SECRET-TOKEN", "token_type": "bearer", "expires_in": 60}
        if method == "GET":
            return 200, list(self.rows.values())
        if method == "POST" and path == imp.ARTICLES:
            if self.fail_create:
                return 500, "boom"
            if not self.lose_create:
                self.rows[payload["article_id"]] = dict(
                    payload, status="drafted", decided_by=None, decision_note=None)
            return 201, payload
        if method == "POST" and path.endswith("/approve"):
            row = self.rows[path.split("/")[-2]]
            row.update(status="approved", decided_by="tee@example.com",
                       decision_note=(payload or {}).get("note"))
            return 200, row
        return 404, None

    def writes(self):
        return [c for c in self.calls if c[0] == "POST" and c[1] != "/auth/login"]


@pytest.fixture
def article():
    return imp.load_article(AID)


def drafted(article, **over):
    row = {"article_id": AID, "title": article["title"], "body": article["body"],
           "status": "drafted", "decided_by": None, "decision_note": None}
    row.update(over)
    return row


def go(server, article, **kw):
    lines = []
    kw.setdefault("create", False)
    kw.setdefault("approve", False)
    kw.setdefault("confirm", lambda _p: "")
    kw.setdefault("note", None)
    rc = imp.run(server, article, "SECRET-TOKEN", out=lines.append, **kw)
    return rc, "\n".join(lines)


def test_the_stored_article_loads_and_matches_its_hash(article):
    assert article["title"] == "How we answer questions about our videos"
    assert article["body"].startswith("A useful answer should tell you")
    assert not article["body"].endswith("\n")


def test_read_only_by_default_writes_nothing(article):
    s = FakeServer()
    rc, out = go(s, article)
    assert rc == 0 and "ABSENT" in out and s.writes() == []


def test_create_stores_a_draft_and_reads_it_back(article):
    s = FakeServer()
    rc, out = go(s, article, create=True)
    assert rc == 0 and s.rows[AID]["status"] == "drafted"
    assert s.writes()[0][2] == {"article_id": AID, "title": article["title"], "body": article["body"]}
    assert "VERIFIED" in out and "status=drafted" in out and "approve" not in "".join(
        c[1] for c in s.calls if c[0] == "POST")


def test_a_create_that_reports_500_but_landed_is_read_before_it_is_claimed(article):
    s = FakeServer()
    orig = s.__call__

    def flaky(method, path, payload, token):
        status, out = orig(method, path, payload, token)
        return (500, "timeout") if (method, path) == ("POST", imp.ARTICLES) else (status, out)

    rc, out = go(flaky, article, create=True)
    assert rc == 0 and "did not confirm" in out and "VERIFIED" in out


def test_a_create_that_never_landed_is_not_claimed(article):
    s = FakeServer(lose_create=True)
    rc, out = go(s, article, create=True)
    assert rc == 1 and "STILL ABSENT" in out and "VERIFIED" not in out


def test_identical_text_is_reused_without_a_second_write(article):
    s = FakeServer([drafted(article)])
    rc, out = go(s, article, create=True)
    assert rc == 0 and s.writes() == [] and "PRESENT" in out


def test_different_text_under_the_same_id_is_never_overwritten(article):
    s = FakeServer([drafted(article, body=article["body"] + " extra")])
    rc, out = go(s, article, create=True, approve=True, confirm=lambda _p: AID)
    assert rc == 1 and "CONFLICT" in out and s.writes() == []


def test_approve_needs_the_id_typed_back(article):
    s = FakeServer([drafted(article)])
    rc, out = go(s, article, approve=True, confirm=lambda _p: "yes")
    assert rc == 1 and "No approval recorded" in out and s.writes() == []
    assert s.rows[AID]["status"] == "drafted"


def test_approve_records_the_decision_and_reads_it_back(article):
    s = FakeServer([drafted(article)])
    rc, out = go(s, article, approve=True, confirm=lambda _p: AID, note="Approved 2026-10-16")
    assert rc == 0 and s.rows[AID]["status"] == "approved"
    assert s.writes()[0][2] == {"note": "Approved 2026-10-16"}
    assert "status=approved decided_by=tee@example.com" in out


def test_without_the_approve_flag_a_draft_stays_a_draft(article):
    s = FakeServer([drafted(article)])
    rc, out = go(s, article, confirm=lambda _p: AID)
    assert rc == 0 and s.writes() == [] and "not citable" in out


def test_an_already_approved_article_is_left_alone(article):
    s = FakeServer([drafted(article, status="approved", decided_by="tee@example.com")])
    rc, out = go(s, article, approve=True, confirm=lambda _p: AID)
    assert rc == 0 and s.writes() == [] and "Already approved" in out


def test_the_token_never_reaches_the_output(article):
    s = FakeServer()
    _, out = go(s, article, create=True)
    assert "SECRET-TOKEN" not in out


def _copy_to(tmp_path):
    for ext in (".json", ".md"):
        shutil.copy(os.path.join(imp.REPO, "support_articles", AID + ext), tmp_path)
    return str(tmp_path)


def test_a_body_edited_after_approval_is_refused(tmp_path):
    d = _copy_to(tmp_path)
    p = os.path.join(d, AID + ".md")
    open(p, "w", encoding="utf-8").write(open(p, encoding="utf-8").read() + " ")
    with pytest.raises(imp.ImportRefusal, match="approved hash"):
        imp.load_article(AID, d)


def test_a_banned_dash_is_refused_even_with_a_matching_hash(tmp_path):
    import hashlib
    d = _copy_to(tmp_path)
    p = os.path.join(d, AID + ".md")
    body = open(p, encoding="utf-8").read().replace("Keep passwords", "Keep passwords — ")
    open(p, "w", encoding="utf-8").write(body)
    m = json.load(open(os.path.join(d, AID + ".json")))
    m["body_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    json.dump(m, open(os.path.join(d, AID + ".json"), "w"))
    with pytest.raises(imp.ImportRefusal, match="repo rules"):
        imp.load_article(AID, d)


def test_sign_in_failure_is_a_refusal_without_the_password():
    with pytest.raises(imp.ImportRefusal, match="HTTP 401") as e:
        imp.sign_in(lambda *a: (401, {"detail": "Incorrect email or password"}), "a@b.c", "pw-secret")
    assert "pw-secret" not in str(e.value)
