"""Durable observation windows, review outbox and append-only operator audit.

No promotion, remote writes, credentials, raw transcripts or candidate code.
SQLite is held by the trusted operator, never mounted into a maker container.
"""

import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from tools.devon_rsi.kernel import Refused, candidate, canonical, digest, strict_load

WINDOW = 20
MAX_EVENTS = 100000
MAX_DAILY_SEARCHES = 2
ZERO = "0" * 64
SCHEMA = """
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, previous TEXT NOT NULL,
  payload BLOB NOT NULL, sha TEXT NOT NULL UNIQUE);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN
  SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN
  SELECT RAISE(ABORT,'append only'); END;
CREATE TABLE IF NOT EXISTS observations(seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL,
  stream TEXT NOT NULL, source_hash TEXT NOT NULL, failed INTEGER NOT NULL,
  window_id TEXT, UNIQUE(stream,source_hash));
CREATE TABLE IF NOT EXISTS windows(id TEXT PRIMARY KEY, stream TEXT NOT NULL,
  failed INTEGER NOT NULL, state TEXT NOT NULL, token TEXT, claimed_at TEXT,
  result_hash TEXT);
CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, candidate BLOB NOT NULL,
  decision_hash TEXT NOT NULL, source_hash TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL,
  receipt_hash TEXT NOT NULL UNIQUE, result BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS protocols(id TEXT PRIMARY KEY, experiment_id TEXT UNIQUE NOT NULL,
  family_id TEXT UNIQUE NOT NULL, freeze_hash TEXT NOT NULL, registered_at TEXT NOT NULL,
  submission_hash TEXT, result BLOB);
CREATE TABLE IF NOT EXISTS trial_receipts(id TEXT PRIMARY KEY, protocol_id TEXT NOT NULL,
  control_run TEXT UNIQUE NOT NULL, candidate_run TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS trial_runs(id TEXT PRIMARY KEY, protocol_id TEXT NOT NULL);
"""


def safe_hash(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise Refused("HASH_FORMAT")
    return value


def safe_path(path):
    path = Path(path).absolute()
    if path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents]):
        raise Refused("STATE_PATH")
    return path


class Store:
    def __init__(self, path):
        self.path = safe_path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)
        self.path.chmod(0o600)
        self.verify()

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def append(self, event):
        if not self.db.in_transaction:
            raise Refused("AUDIT_TRANSACTION_REQUIRED")
        raw = canonical(event)
        strict_load(raw)
        last = self.db.execute("SELECT seq,sha FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (last["seq"] + 1, last["sha"]) if last else (0, ZERO)
        if seq >= MAX_EVENTS:
            raise Refused("AUDIT_CAPACITY")
        sha = digest({"seq": seq, "previous": previous, "event": event})
        self.db.execute("INSERT INTO audit VALUES(?,?,?,?)", (seq, previous, raw, sha))
        return sha

    def verify(self, expected_head=None):
        previous = ZERO
        for seq, row in enumerate(self.db.execute("SELECT * FROM audit ORDER BY seq")):
            event = strict_load(row["payload"])
            if row["seq"] != seq or row["previous"] != previous or row["sha"] != digest(
                    {"seq": seq, "previous": previous, "event": event}):
                raise Refused("AUDIT_DRIFT")
            previous = row["sha"]
        if expected_head is not None and previous != safe_hash(expected_head):
            raise Refused("AUDIT_HEAD")
        return previous

    def observe(self, event_id, source_hash, failed, stream="fixture"):
        """A run is one observation, not fifty independent statistical trials."""
        safe_hash(event_id)
        safe_hash(source_hash)
        if stream not in {"fixture", "operator_observation"} or type(failed) is not bool:
            raise Refused("OBSERVATION_SCHEMA")
        with self.transaction():
            old = self.db.execute("SELECT * FROM observations WHERE id=?", (event_id,)).fetchone()
            if old:
                if (old["source_hash"], old["failed"], old["stream"]) != (source_hash, int(failed), stream):
                    raise Refused("OBSERVATION_DRIFT")
                return {"inserted": False, "windows": []}
            duplicate = self.db.execute("SELECT id FROM observations WHERE stream=? AND source_hash=?",
                                        (stream, source_hash)).fetchone()
            if duplicate:
                return {"inserted": False, "windows": []}
            if self.db.execute("SELECT count(*) FROM observations").fetchone()[0] >= MAX_EVENTS:
                raise Refused("OBSERVATION_CAPACITY")
            self.db.execute("INSERT INTO observations(id,stream,source_hash,failed) VALUES(?,?,?,?)",
                            (event_id, stream, source_hash, int(failed)))
            self.append({"kind": "observation", "id": event_id, "source_hash": source_hash,
                         "stream": stream, "failed": failed})
            rows = self.db.execute("SELECT * FROM observations WHERE window_id IS NULL AND stream=? ORDER BY seq LIMIT ?",
                                   (stream, WINDOW)).fetchall()
            windows = []
            if len(rows) == WINDOW:
                identity = digest({"stream": stream, "ids": [r["id"] for r in rows]})
                failures = sum(r["failed"] for r in rows)
                # Operational observations request review. Only fixture data can
                # trigger automatic, network-disabled fixture search.
                state = "PENDING" if failures and stream == "fixture" else "REVIEW" if failures else "QUIET"
                self.db.execute("INSERT INTO windows(id,stream,failed,state) VALUES(?,?,?,?)",
                                (identity, stream, failures, state))
                self.db.executemany("UPDATE observations SET window_id=? WHERE id=?",
                                    [(identity, r["id"]) for r in rows])
                self.append({"kind": "window", "id": identity, "count": WINDOW,
                             "failures": failures, "state": state})
                windows.append(identity)
            return {"inserted": True, "windows": windows}

    def claim(self, now=None):
        """Commit intent before search. RUNNING jobs are NEVER automatically retried."""
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise Refused("TIMEZONE_REQUIRED")
        today = now.astimezone(timezone.utc).date().isoformat()
        with self.transaction():
            count = self.db.execute("SELECT count(*) FROM windows WHERE substr(claimed_at,1,10)=?", (today,)).fetchone()[0]
            if count >= MAX_DAILY_SEARCHES:
                return None
            row = self.db.execute("SELECT id FROM windows WHERE state='PENDING' ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            self.db.execute("UPDATE windows SET state='RUNNING',token=?,claimed_at=? WHERE id=?",
                            (token, now.astimezone(timezone.utc).isoformat(), row["id"]))
            self.append({"kind": "search_intent", "window": row["id"], "token_hash": digest(token), "day": today})
            return {"window": row["id"], "token": token}

    def finish(self, claim, report):
        """Atomic result/outbox/audit commit, fenced by the one-time claim."""
        if report.get("promoted") is not False or report.get("gain_claim") is not False or report.get("production_effects") != []:
            raise Refused("REPORT_AUTHORITY")
        if report.get("mode") != "synthetic_fixture" or report.get("status") not in {"REJECT", "ACCEPT_FOR_HUMAN_REVIEW"}:
            raise Refused("REPORT_MODE")
        result_hash = digest(report)
        with self.transaction():
            row = self.db.execute("SELECT * FROM windows WHERE id=?", (claim["window"],)).fetchone()
            if not row or row["state"] != "RUNNING" or row["token"] != claim["token"]:
                raise Refused("STALE_CLAIM")
            self.db.execute("UPDATE windows SET state='COMPLETE',result_hash=?,token=NULL WHERE id=?",
                            (result_hash, row["id"]))
            proposal_id = None
            if report["status"] == "ACCEPT_FOR_HUMAN_REVIEW":
                proposed = candidate(report["best"]["candidate"])
                proposal_id = digest(proposed)
                self.db.execute("INSERT OR IGNORE INTO proposals VALUES(?,?,?,?,?)",
                                (proposal_id, canonical(proposed), result_hash,
                                 safe_hash(report["release_manifest_sha256"]), "AWAITING_INDEPENDENT_REVIEW"))
            self.append({"kind": "search_result", "window": row["id"],
                         "decision_hash": result_hash, "proposal_id": proposal_id})
        return proposal_id

    def import_proposal(self, report):
        """An observed fixture recommendation goes to review; it is not approval."""
        if report.get("status") != "ACCEPT_FOR_HUMAN_REVIEW":
            return None
        if report.get("mode") != "synthetic_fixture" or report.get("promoted") is not False or report.get("gain_claim") is not False or report.get("production_effects") != []:
            raise Refused("REPORT_AUTHORITY")
        proposed = candidate(report["best"]["candidate"])
        identity = digest(proposed)
        with self.transaction():
            cursor = self.db.execute("INSERT OR IGNORE INTO proposals VALUES(?,?,?,?,?)",
                                     (identity, canonical(proposed), digest(report),
                                      safe_hash(report["release_manifest_sha256"]), "AWAITING_INDEPENDENT_REVIEW"))
            if cursor.rowcount:
                self.append({"kind": "review_requested", "proposal_id": identity, "decision_hash": digest(report)})
        return identity

    def snapshot(self):
        with self.transaction():
            return {"schema": "devon-rsi-ops-v1", "audit_head": self.verify(),
                    "observation_count": self.db.execute("SELECT count(*) FROM observations").fetchone()[0],
                    "incomplete_observations": self.db.execute("SELECT count(*) FROM observations WHERE window_id IS NULL").fetchone()[0],
                    "window_count": self.db.execute("SELECT count(*) FROM windows").fetchone()[0],
                    "windows": [dict(r) for r in self.db.execute("SELECT id,stream,failed,state,result_hash FROM windows ORDER BY rowid DESC LIMIT 100")],
                    "review_queue": [{**dict(r), "candidate": strict_load(r["candidate"])} for r in self.db.execute("SELECT * FROM proposals ORDER BY rowid LIMIT 32")],
                    "experiments": [{"protocol_sha256": r["id"], "registered_at": r["registered_at"],
                                     "result": strict_load(r["result"]) if r["result"] else None}
                                    for r in self.db.execute("SELECT * FROM protocols ORDER BY rowid DESC LIMIT 100")],
                    "reviews": [strict_load(r["result"]) for r in self.db.execute("SELECT result FROM reviews ORDER BY rowid DESC LIMIT 100")],
                    "gain_claim": False, "promoted": False}
