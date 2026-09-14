"""Content-addressed snapshots and SQLite transactional publication/outbox.

Database transactions publish revision and event together. Readers reconstruct
fresh objects; branches never share mutable Python state. File blobs are atomic,
hash-checked, and may be orphaned by a failed transaction without corrupting state.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import tempfile
import time
import uuid
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


class Conflict(ValueError):
    pass


class IntegrityError(ValueError):
    pass


TERMINAL_RUN_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED", "CRASHED", "MISSING_INPUTS",
                                 "NO_INCUMBENT_FOUND", "BUDGET_EXHAUSTED", "UNSUPPORTED_OPERATION", "TIMED_OUT"})


class _Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


class Store:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.blobs = self.directory / "blobs"
        self.blobs.mkdir(exist_ok=True)
        self.database = self.directory / "oma.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO metadata VALUES('schema_version','1');
                CREATE TABLE IF NOT EXISTS projects(
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, revision INTEGER NOT NULL,
                    state_root TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions(
                    project_id TEXT NOT NULL, revision INTEGER NOT NULL, root TEXT NOT NULL,
                    parent_root TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
                    candidate_id TEXT, PRIMARY KEY(project_id, revision),
                    FOREIGN KEY(project_id) REFERENCES projects(id));
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    payload TEXT NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id));
                CREATE INDEX IF NOT EXISTS event_project ON events(project_id, seq);
                CREATE TABLE IF NOT EXISTS requests(
                    project_id TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
                    response TEXT NOT NULL, PRIMARY KEY(project_id,key));
                CREATE TABLE IF NOT EXISTS runs(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, base_revision INTEGER NOT NULL,
                    base_root TEXT NOT NULL, status TEXT NOT NULL, desired_action TEXT NOT NULL,
                    operation TEXT NOT NULL, request TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, detail TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id));
                CREATE TABLE IF NOT EXISTS candidates(
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
                    base_revision INTEGER NOT NULL, state_root TEXT NOT NULL, status TEXT NOT NULL,
                    payload TEXT NOT NULL, report_root TEXT, created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id));
                CREATE TABLE IF NOT EXISTS run_owners(
                    run_id TEXT NOT NULL, role TEXT NOT NULL, pid INTEGER NOT NULL,
                    process_created REAL NOT NULL, hostname TEXT NOT NULL, claimed_at TEXT NOT NULL,
                    PRIMARY KEY(run_id,role), FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE TABLE IF NOT EXISTS asset_aliases(
                    original_path TEXT PRIMARY KEY, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS run_controls(
                    run_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL, consumed INTEGER NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id));
                CREATE TABLE IF NOT EXISTS check_executions(
                    execution_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
                    binding TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL,
                    finished_at TEXT, evidence_root TEXT, report_root TEXT,
                    FOREIGN KEY(candidate_id) REFERENCES candidates(id));
                CREATE TABLE IF NOT EXISTS candidate_check_executions(
                    candidate_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES candidates(id),
                    FOREIGN KEY(execution_id) REFERENCES check_executions(execution_id));
            """)
            version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
            if version != "1":
                raise IntegrityError(f"Unsupported database schema {version}; refusing implicit migration")

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=30, isolation_level=None, factory=_Connection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def put(self, value: Any) -> str:
        raw = canonical(value)
        root = hashlib.sha256(raw).hexdigest()
        target = self.blobs / f"{root}.json.z"
        if target.exists():
            self.get(root)  # Existing corrupt content is never silently trusted.
            return root
        fd, path = tempfile.mkstemp(prefix=".pending-", dir=self.blobs)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(zlib.compress(raw, level=3))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(path, target)
        finally:
            if os.path.exists(path):
                os.unlink(path)
        return root

    def get(self, root: str) -> Any:
        if len(root) != 64 or any(c not in "0123456789abcdef" for c in root):
            raise IntegrityError("Invalid content root")
        try:
            raw = zlib.decompress((self.blobs / f"{root}.json.z").read_bytes())
        except (OSError, zlib.error) as exc:
            raise IntegrityError(f"Missing or corrupt artifact {root}") from exc
        if hashlib.sha256(raw).hexdigest() != root:
            raise IntegrityError(f"Artifact hash mismatch {root}")
        return json.loads(raw)

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve relocated bytes separately from immutable, hash-bound provenance."""
        path = Path(value).expanduser()
        with self.connect() as db:
            alias = db.execute("SELECT relative_path FROM asset_aliases WHERE original_path=?", (str(path),)).fetchone()
            row = db.execute("SELECT value FROM metadata WHERE key='relocation_roots'").fetchone()
        if alias:
            target = (self.directory / alias[0]).resolve()
            if not target.is_relative_to(self.directory):
                raise IntegrityError("Asset alias escapes the restored store")
            return target
        for original in json.loads(row[0]) if row else []:
            if path.is_relative_to(Path(original)):
                return self.directory / path.relative_to(Path(original))
        return path

    @staticmethod
    def _owner_alive(row) -> bool:
        import platform
        import psutil
        if row["hostname"] != platform.node():
            return False
        try:
            process = psutil.Process(row["pid"])
            return process.is_running() and abs(process.create_time() - row["process_created"]) < .001
        except psutil.NoSuchProcess:
            return False
        except psutil.AccessDenied:
            # Lack of inspection permission is not evidence of worker death.
            return True

    def claim_run(self, run_id: str, role: str = "worker"):
        import platform
        import psutil
        process = psutil.Process()
        with self.transaction() as db:
            prior = db.execute("SELECT * FROM run_owners WHERE run_id=? AND role=?", (run_id, role)).fetchone()
            if prior and self._owner_alive(prior) and (prior["pid"] != process.pid or abs(prior["process_created"] - process.create_time()) >= .001):
                raise Conflict(f"Run already has a live {role}")
            db.execute("INSERT OR REPLACE INTO run_owners VALUES(?,?,?,?,?,?)",
                       (run_id, role, process.pid, process.create_time(), platform.node(), utcnow()))

    def _event(self, db: sqlite3.Connection, project_id: str, **fields) -> dict:
        event = {"project_id": project_id, "run_id": None, "branch_id": "main", "state_root": None,
                 "candidate_id": None, "timestamp": utcnow(), "stage": "state", "status": "UNKNOWN",
                 "message": "", "changed_ids": [], "artifacts": [], "payload": {}, **fields}
        cursor = db.execute("INSERT INTO events(project_id,payload) VALUES(?,?)", (project_id, canonical(event).decode()))
        event["seq"] = cursor.lastrowid
        return event

    def append_event(self, project_id: str, **fields) -> dict:
        with self.transaction() as db:
            return self._event(db, project_id, **fields)

    def create_project(self, name: str, state: dict, project_id: str | None = None) -> dict:
        project_id = project_id or uuid.uuid4().hex
        state = {**state, "project_id": project_id}
        root = self.put(state)
        created = utcnow()
        with self.transaction() as db:
            db.execute("INSERT INTO projects VALUES(?,?,0,?,'IMPORTED',?)", (project_id, name, root, created))
            db.execute("INSERT INTO revisions VALUES(?,0,?,NULL,'IMPORTED',?,NULL)", (project_id, root, created))
            self._event(db, project_id, state_root=root, stage="import", status="IMPORTED", message="Original import persisted", artifacts=[root])
        return self.project(project_id)

    def create_import(self, name: str, state: dict, paths: list[str], idempotency_key: str | None = None) -> dict:
        """Publish initial project, import job and retry response in one transaction."""
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 256:
            raise ValueError("An idempotency key must contain 1 to 256 characters")
        request_hash = digest({"name": name, "state": state, "paths": paths})
        project_id, run_id, created = uuid.uuid4().hex, uuid.uuid4().hex, utcnow()
        root = self.put({**state, "project_id": project_id})
        request = {"operation": "import", "paths": paths, "budget_seconds": 3600}
        with self.transaction() as db:
            if idempotency_key:
                prior = db.execute("SELECT * FROM requests WHERE project_id='__imports__' AND key=?", (idempotency_key,)).fetchone()
                if prior:
                    if prior["request_hash"] != request_hash:
                        raise Conflict("Import retry key has different source paths, name or state")
                    return json.loads(prior["response"])
            db.execute("INSERT INTO projects VALUES(?,?,0,?,'IMPORTED',?)", (project_id, name, root, created))
            db.execute("INSERT INTO revisions VALUES(?,0,?,NULL,'IMPORTED',?,NULL)", (project_id, root, created))
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (run_id, project_id, 0, root, "QUEUED", "run", "import", canonical(request).decode(), created, created, ""))
            self._event(db, project_id, run_id=run_id, state_root=root, stage="import", status="QUEUED", message="Project and import job committed atomically", artifacts=[root])
            response = {"id": project_id, "name": name, "revision": 0, "state_root": root, "status": "IMPORTED", "created_at": created, "import_run_id": run_id}
            if idempotency_key:
                db.execute("INSERT INTO requests VALUES('__imports__',?,?,?)", (idempotency_key, request_hash, canonical(response).decode()))
        self.claim_run(run_id, "submitter")
        return response

    def projects(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created_at DESC")]

    def project(self, project_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise KeyError(project_id)
        return dict(row)

    def events(self, project_id: str, after: int = 0, limit: int = 200) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT seq,payload FROM events WHERE project_id=? AND seq>? ORDER BY seq LIMIT ?", (project_id, max(0, after), min(max(limit, 1), 1000))).fetchall()
        return [{**json.loads(r["payload"]), "seq": r["seq"]} for r in rows]

    def history(self, project_id: str) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM revisions WHERE project_id=? ORDER BY revision DESC", (project_id,))]

    def publish(self, project_id: str, state: dict, expected_revision: int, idempotency_key: str,
                *, status: str = "BASELINE", candidate_id: str | None = None,
                changed_ids: list[str] | None = None, _verified_report_root: str | None = None) -> dict:
        if not idempotency_key or len(idempotency_key) > 256:
            raise ValueError("An idempotency key of 1–256 characters is required")
        if state.get("project_id") != project_id:
            raise IntegrityError("State belongs to a different project")
        root = self.put(state)
        if status == "ACCEPTED":
            if not _verified_report_root:
                raise IntegrityError("Acceptance requires independent persisted checker evidence")
            from .models import VerificationReport, Verdict
            report = VerificationReport.model_validate(self.get(_verified_report_root))
            if report.status != Verdict.PASS or report.candidate_root != root:
                raise IntegrityError("Report is not a passing check for this exact candidate")
            mission = state.get("mission")
            if not mission or report.mission_hash != digest(mission) or report.rule_hash != mission.get("rule_hash"):
                raise IntegrityError("Mission/rule applicability mismatch")
        request_hash = digest({"root": root, "expected": expected_revision, "status": status, "candidate": candidate_id,
                               "report": _verified_report_root, "changed_ids": changed_ids or []})
        derivation_root = None
        predecessor = self.project(project_id)
        if state.get("schema_version") == 1 and predecessor["revision"] == expected_revision:
            from .project_dependencies import derive_transition
            from .build_identity import checker_version
            derivation = derive_transition(self.get(predecessor["state_root"]), state, executable=checker_version(),
                after_report=self.get(_verified_report_root) if _verified_report_root else None)
            if not derivation["cold_equivalent"]:
                raise IntegrityError("Incremental project derivations differ from a fresh cold rebuild")
            derivation_root = self.put(derivation)
        with self.transaction() as db:
            prior = db.execute("SELECT * FROM requests WHERE project_id=? AND key=?", (project_id, idempotency_key)).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise Conflict("Idempotency key reused with different request content")
                return json.loads(prior["response"])
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise KeyError(project_id)
            if project["revision"] != expected_revision:
                raise Conflict(f"Expected revision {expected_revision}, current revision is {project['revision']}")
            if status == "ACCEPTED":
                current = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
                if (not current or current["project_id"] != project_id or current["base_revision"] != expected_revision
                        or current["state_root"] != root or current["status"] != "CHECKED"
                        or current["report_root"] != _verified_report_root
                        or json.loads(current["payload"]).get("changed_ids", []) != (changed_ids or [])):
                    raise IntegrityError("Candidate verification changed before the acceptance transaction")
                execution = db.execute("SELECT e.* FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?", (candidate_id,)).fetchone()
                if execution and (execution["status"] != "COMPLETED" or execution["report_root"] != _verified_report_root):
                    raise IntegrityError("Candidate has no completed current verification execution")
                if execution:
                    binding = json.loads(execution["binding"])
                    if (binding.get("candidate_payload_root") != digest(json.loads(current["payload"]))
                            or binding["candidate_root"] != root or binding["checker_version"] != report.checker_version):
                        raise IntegrityError("Candidate scope changed after its completed verification execution")
            revision = expected_revision + 1
            created = utcnow()
            db.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?,?)", (project_id, revision, root, project["state_root"], status, created, candidate_id))
            db.execute("UPDATE projects SET revision=?,state_root=?,status=? WHERE id=?", (revision, root, status, project_id))
            event = self._event(db, project_id, state_root=root, candidate_id=candidate_id, status=status,
                                message=f"Revision {revision} committed", changed_ids=changed_ids or [],
                                artifacts=[root] + ([_verified_report_root] if _verified_report_root else []) + ([derivation_root] if derivation_root else []),
                                payload={"revision": revision, "parent_root": project["state_root"], "derivation_root": derivation_root})
            response = {"project_id": project_id, "revision": revision, "state_root": root, "status": status, "event_seq": event["seq"]}
            db.execute("INSERT INTO requests VALUES(?,?,?,?)", (project_id, idempotency_key, request_hash, canonical(response).decode()))
            return response

    def revert(self, project_id: str, revision: int, expected_revision: int, idempotency_key: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM revisions WHERE project_id=? AND revision=?", (project_id, revision)).fetchone()
        if not row:
            raise KeyError(f"Revision {revision}")
        # A historical check need not be applicable under current software/rules.
        return self.publish(project_id, self.get(row["root"]), expected_revision, idempotency_key, status="BASELINE")

    def create_run(self, project_id: str, request: dict) -> dict:
        run_id = uuid.uuid4().hex
        created = utcnow()
        key = request.get("idempotency_key")
        if key is not None and not 1 <= len(key) <= 256:
            raise ValueError("An idempotency key must contain 1 to 256 characters")
        request_hash = digest(request)
        with self.transaction() as db:
            if key:
                prior = db.execute("SELECT * FROM requests WHERE project_id=? AND key=?", (project_id, f"run:{key}")).fetchone()
                if prior:
                    if prior["request_hash"] != request_hash:
                        raise Conflict("Run retry key has different request content")
                    return self.run(json.loads(prior["response"])["run_id"])
            project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
            if not project:
                raise KeyError(project_id)
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (run_id, project_id, project["revision"], project["state_root"], "QUEUED", "run", request.get("operation", "check"), canonical(request).decode(), created, created, ""))
            self._event(db, project_id, run_id=run_id, state_root=project["state_root"], stage="queue", status="QUEUED", message="Run queued")
            if key:
                db.execute("INSERT INTO requests VALUES(?,?,?,?)", (project_id, f"run:{key}", request_hash, canonical({"run_id": run_id}).decode()))
        self.claim_run(run_id, "submitter")
        return self.run(run_id)

    def run(self, run_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        result = dict(row)
        result["request"] = json.loads(result["request"])
        return result

    def runs(self, project_id: str) -> list[dict]:
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM runs WHERE project_id=? ORDER BY created_at DESC", (project_id,))]
        return [self.run(r) for r in ids]

    def control(self, run_id: str, action: str) -> dict:
        if action not in {"pause", "resume", "cancel", "step"}:
            raise ValueError("Unknown worker control")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            if row["status"] in {"COMPLETED", "FAILED", "CANCELLED", "CRASHED", "MISSING_INPUTS", "NO_INCUMBENT_FOUND", "BUDGET_EXHAUSTED", "UNSUPPORTED_OPERATION", "TIMED_OUT"}:
                raise Conflict(f"Run is already {row['status']}")
            desired = "run" if action == "resume" else action
            db.execute("INSERT INTO run_controls VALUES(?,1,0) ON CONFLICT(run_id) DO UPDATE SET sequence=sequence+1", (run_id,))
            db.execute("UPDATE runs SET desired_action=?,updated_at=? WHERE id=?", (desired, utcnow(), run_id))
            self._event(db, row["project_id"], run_id=run_id, state_root=row["base_root"], stage="control", status="REQUESTED", message=f"{action.capitalize()} requested; awaiting worker acknowledgement")
        return self.run(run_id)

    def consume_step(self, run_id: str) -> bool:
        """One durable Step request grants exactly one checkpoint across processes."""
        with self.transaction() as db:
            row = db.execute("SELECT c.*,r.desired_action FROM run_controls c JOIN runs r ON r.id=c.run_id WHERE c.run_id=?", (run_id,)).fetchone()
            if not row or row["desired_action"] != "step" or row["consumed"] == row["sequence"]:
                return False
            db.execute("UPDATE run_controls SET consumed=sequence WHERE run_id=?", (run_id,))
            return True

    def update_run(self, run_id: str, status: str, detail: str = "", stage: str = "compute", **event_fields) -> dict:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            if row["status"] in TERMINAL_RUN_STATUSES:
                return self.run(run_id)
            db.execute("UPDATE runs SET status=?,detail=?,updated_at=? WHERE id=?", (status, detail, utcnow(), run_id))
            self._event(db, row["project_id"], run_id=run_id, state_root=row["base_root"], stage=stage, status=status, message=detail, **event_fields)
        return self.run(run_id)

    def add_candidate(self, run_id: str, state: dict, payload: dict) -> dict:
        run = self.run(run_id)
        if state.get("project_id") != run["project_id"]:
            raise IntegrityError("Candidate belongs to a different project")
        root = self.put(state)
        candidate_id = uuid.uuid4().hex
        created = utcnow()
        with self.transaction() as db:
            db.execute("INSERT INTO candidates VALUES(?,?,?,?,?,'CANDIDATE',?,NULL,?)", (candidate_id, run["project_id"], run_id, run["base_revision"], root, canonical(payload).decode(), created))
            self._event(db, run["project_id"], run_id=run_id, candidate_id=candidate_id, state_root=root, stage="candidate", status="CANDIDATE", message="Candidate persisted for independent verification", artifacts=[root], payload=payload)
        return self.candidate(candidate_id)

    def candidate(self, candidate_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise KeyError(candidate_id)
        result = dict(row)
        payload = json.loads(result.pop("payload"))
        return {**payload, **result}

    def candidates(self, project_id: str) -> list[dict]:
        with self.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM candidates WHERE project_id=? ORDER BY created_at", (project_id,))]
        return [self.candidate(c) for c in ids]

    def begin_check_execution(self, candidate_id: str, execution_id: str, *, checker_version: str, control_run_id: str | None = None, deadline: float | None = None) -> dict:
        """Fence one candidate before launching a checker; older tokens lose authority."""
        from .build_identity import checker_version as current_version
        if not isinstance(execution_id, str) or not 1 <= len(execution_id) <= 128:
            raise ValueError("A bounded unique verification execution identity is required")
        if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
            raise ValueError("Checker execution deadline must be a finite monotonic timestamp")
        if checker_version != current_version():
            raise IntegrityError("Verification execution does not name the current executable")
        with self.transaction() as db:
            candidate = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
            if not candidate:
                raise KeyError(candidate_id)
            origin = db.execute("SELECT * FROM runs WHERE id=?", (candidate["run_id"],)).fetchone()
            owner_id = control_run_id or candidate["run_id"]
            owner = db.execute("SELECT * FROM runs WHERE id=?", (owner_id,)).fetchone()
            if (not origin or not owner or origin["project_id"] != candidate["project_id"]
                    or owner["project_id"] != candidate["project_id"] or origin["base_revision"] != candidate["base_revision"]):
                raise IntegrityError("Verification candidate and origin/control project identities disagree")
            if owner_id != candidate["run_id"]:
                request = json.loads(owner["request"])
                if owner["operation"] != "recheck" or request.get("candidate_id") != candidate_id:
                    raise IntegrityError("Control run does not own this candidate recheck")
            if owner["status"] in TERMINAL_RUN_STATUSES or owner["desired_action"] == "cancel":
                raise IntegrityError("Verification owner is terminal or cancelled; a fresh recheck run is required")
            state = self.get(candidate["state_root"])
            baseline = self.get(origin["base_root"])
            if state.get("project_id") != candidate["project_id"] or baseline.get("project_id") != candidate["project_id"]:
                raise IntegrityError("Verification candidate or baseline root belongs to a different project")
            binding = {"execution_id": execution_id, "candidate_id": candidate_id,
                "candidate_root": candidate["state_root"], "state_root": candidate["state_root"],
                "candidate_payload_root": digest(json.loads(candidate["payload"])),
                "project_id": candidate["project_id"], "base_revision": candidate["base_revision"],
                "run_id": candidate["run_id"], "origin_run_id": candidate["run_id"], "base_root": origin["base_root"],
                "request_root": digest(json.loads(origin["request"])), "control_run_id": owner_id,
                "control_request_root": digest(json.loads(owner["request"])), "control_operation": owner["operation"],
                "control_base_root": owner["base_root"], "control_base_revision": owner["base_revision"], "deadline": deadline,
                "checker_version": checker_version, "mission_hash": digest(state.get("mission")),
                "rule_hash": (state.get("mission") or {}).get("rule_hash", "baseline-unapproved-contact-policy"),
                "source_manifest_hash": digest(state.get("sources", [])),
                "prior_status": candidate["status"], "prior_report_root": candidate["report_root"]}
            if db.execute("SELECT 1 FROM check_executions WHERE execution_id=?", (execution_id,)).fetchone():
                raise Conflict("Verification execution identity was already used")
            old = db.execute("SELECT execution_id FROM candidate_check_executions WHERE candidate_id=?", (candidate_id,)).fetchone()
            if old:
                db.execute("UPDATE check_executions SET status='SUPERSEDED',finished_at=? WHERE execution_id=? AND status='RUNNING'", (utcnow(), old["execution_id"]))
            db.execute("INSERT INTO check_executions VALUES(?,?,?,'RUNNING',?,NULL,NULL,NULL)",
                (execution_id, candidate_id, canonical(binding).decode(), utcnow()))
            db.execute("INSERT INTO candidate_check_executions VALUES(?,?) ON CONFLICT(candidate_id) DO UPDATE SET execution_id=excluded.execution_id", (candidate_id, execution_id))
            db.execute("UPDATE candidates SET status='CHECKING' WHERE id=?", (candidate_id,))
            self._event(db, candidate["project_id"], run_id=owner_id, candidate_id=candidate_id,
                state_root=candidate["state_root"], stage="check_execution", status="CHECKING",
                message="Fresh checker execution owns this candidate; no pending report is acceptance authority",
                artifacts=[candidate["report_root"]] if candidate["report_root"] else [], payload=binding)
        return binding

    def _check_execution_guard(self, db, candidate, execution_id, *, report=None, complete=False):
        execution = db.execute("SELECT e.* FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?", (candidate["id"],)).fetchone()
        if (not execution or execution["execution_id"] != execution_id or execution["candidate_id"] != candidate["id"]
                or execution["status"] != "RUNNING"):
            raise IntegrityError("Verification execution is stale, completed, or no longer owns this candidate")
        binding = json.loads(execution["binding"])
        if not complete:
            return binding
        origin = db.execute("SELECT * FROM runs WHERE id=?", (binding["origin_run_id"],)).fetchone()
        owner = db.execute("SELECT * FROM runs WHERE id=?", (binding["control_run_id"],)).fetchone()
        if (not origin or not owner or candidate["state_root"] != binding["candidate_root"]
                or candidate["run_id"] != binding["origin_run_id"] or candidate["project_id"] != binding["project_id"]
                or digest(json.loads(candidate["payload"])) != binding.get("candidate_payload_root")
                or candidate["base_revision"] != binding["base_revision"] or candidate["status"] != "CHECKING"
                or origin["project_id"] != binding["project_id"] or origin["base_root"] != binding["base_root"]
                or origin["base_revision"] != binding["base_revision"]
                or digest(json.loads(origin["request"])) != binding["request_root"]
                or owner["project_id"] != binding["project_id"] or owner["operation"] != binding["control_operation"]
                or owner["base_root"] != binding["control_base_root"] or owner["base_revision"] != binding["control_base_revision"]
                or digest(json.loads(owner["request"])) != binding["control_request_root"]):
            raise IntegrityError("Verification execution candidate, origin, or owning request changed")
        if owner["status"] in TERMINAL_RUN_STATUSES or owner["desired_action"] not in {"run", "step"}:
            raise IntegrityError("Verification owner stopped, paused, or cancelled before report publication")
        if binding["deadline"] is not None and time.monotonic() >= binding["deadline"]:
            raise IntegrityError("Verification deadline expired before report publication")
        if (report is None or report.candidate_root != binding["candidate_root"]
                or report.checker_version != binding["checker_version"] or report.mission_hash != binding["mission_hash"]
                or report.rule_hash != binding["rule_hash"]):
            raise IntegrityError("Verification report does not bind this execution's exact inputs and executable")
        return binding

    def finish_check_execution(self, candidate_id: str, execution_id: str, *, status: str, report=None, evidence_root: str | None = None) -> dict:
        """Promote only a completed owned execution; retain incomplete evidence."""
        if not isinstance(status, str) or not 1 <= len(status) <= 64 or status in {"RUNNING", "CHECKING"}:
            raise ValueError("A final checker process disposition is required")
        if evidence_root is not None:
            self.get(evidence_root)
        if status == "COMPLETED":
            if report is None:
                raise IntegrityError("Completed execution has no independent report")
            return self.record_verification(candidate_id, report, _execution_id=execution_id, _execution_evidence_root=evidence_root)
        pending_root = self.put(report) if report is not None else None
        with self.transaction() as db:
            candidate = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
            if not candidate:
                raise KeyError(candidate_id)
            binding = self._check_execution_guard(db, candidate, execution_id)
            db.execute("UPDATE check_executions SET status=?,finished_at=?,evidence_root=?,report_root=? WHERE execution_id=?",
                (status, utcnow(), evidence_root, pending_root, execution_id))
            db.execute("UPDATE candidates SET status='UNKNOWN',report_root=NULL WHERE id=?", (candidate_id,))
            self._event(db, candidate["project_id"], run_id=binding["control_run_id"], candidate_id=candidate_id,
                state_root=candidate["state_root"], stage="check_execution", status=status,
                message="Incomplete checker execution retained without verification or acceptance authority",
                artifacts=[root for root in (binding["prior_report_root"], pending_root, evidence_root) if root],
                payload={"execution_id": execution_id, "prior_report_root": binding["prior_report_root"],
                    "pending_report_root": pending_root, "candidate_status": "UNKNOWN"})
        return self.candidate(candidate_id)

    def record_verification(self, candidate_id: str, report, *, _execution_id: str | None = None, _execution_evidence_root: str | None = None) -> dict:
        from .models import VerificationReport, Verdict
        report = VerificationReport.model_validate(report)
        if report.checker_version.startswith("oma-independent-checker/"):
            from .build_identity import checker_version
            if report.checker_version != checker_version():
                raise IntegrityError("Executable checker changed during verification; rerun on a stable build")
        report_root = self.put(report)
        from .project_assurance import build_report_assurance
        assurance = build_report_assurance(self, self.candidate(candidate_id), report_root,
            executable=report.checker_version, assessment_time=report.created_at)
        assurance_root = self.put(assurance)
        # Assurance construction may be expensive; publication checks below run
        # after it and share the candidate update transaction with token/control
        # validation. Orphaned blobs confer no current candidate authority.
        if report.checker_version.startswith("oma-independent-checker/"):
            if report.checker_version != checker_version():
                raise IntegrityError("Executable checker changed while preparing report publication")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row or row["state_root"] != report.candidate_root:
                raise IntegrityError("Checker report root does not match persisted candidate")
            if _execution_id is not None:
                binding = self._check_execution_guard(db, row, _execution_id, report=report, complete=True)
                db.execute("UPDATE check_executions SET status='COMPLETED',finished_at=?,evidence_root=?,report_root=? WHERE execution_id=?",
                    (utcnow(), _execution_evidence_root, report_root, _execution_id))
            elif db.execute("SELECT 1 FROM candidate_check_executions WHERE candidate_id=?", (candidate_id,)).fetchone():
                raise IntegrityError("Managed candidate requires its current completed checker execution")
            status = "CHECKED" if report.status == Verdict.PASS else ("REJECTED" if report.status == Verdict.FAIL else report.status.value)
            db.execute("UPDATE candidates SET status=?,report_root=? WHERE id=?", (status, report_root, candidate_id))
            from collections import Counter
            self._event(db, row["project_id"], run_id=row["run_id"], candidate_id=candidate_id, state_root=row["state_root"], stage="verification", status=status, message=f"Independent check: {report.status}", artifacts=[report_root, assurance_root], payload={"check": {"status": report.status.value, "scope": report.scope, "counts": dict(Counter(r.status.value for r in report.results)), "objective": report.objective, "report_root": report_root}, "assurance": {"root": assurance_root, "status": assurance["support_status"], "scope": assurance["scope"]}})
            if _execution_id is not None:
                self._event(db, row["project_id"], run_id=binding["control_run_id"], candidate_id=candidate_id,
                    state_root=row["state_root"], stage="check_execution", status="COMPLETED",
                    message="Owned checker process completed; applicable independent report atomically published",
                    artifacts=[root for root in (report_root, assurance_root, _execution_evidence_root) if root],
                    payload={"execution_id": _execution_id, "report_root": report_root, "candidate_status": status})
        return self.candidate(candidate_id)

    def accept(self, project_id: str, candidate_id: str, expected_revision: int, idempotency_key: str, *, checker_version: str) -> dict:
        if checker_version.startswith("oma-independent-checker/"):
            from .build_identity import checker_version as current_version
            checker_version = current_version()
        candidate = self.candidate(candidate_id)
        if candidate["project_id"] != project_id:
            raise IntegrityError("Candidate belongs to another project")
        from .validation_advisories import candidate_advisories
        if candidate_advisories(self, candidate):
            raise IntegrityError("IFC-PORT-001: prior authored port semantics require regeneration and a fresh independent check")
        if candidate["base_revision"] != expected_revision:
            raise Conflict("Candidate was computed from a different revision; rebase and recheck required")
        if candidate["status"] != "CHECKED" or not candidate["report_root"]:
            raise IntegrityError("Candidate has no complete passing independent report")
        report = self.get(candidate["report_root"])
        if report["checker_version"] != checker_version:
            raise IntegrityError("Checker version changed; recheck required")
        result = self.publish(project_id, self.get(candidate["state_root"]), expected_revision, idempotency_key,
                              status="ACCEPTED", candidate_id=candidate_id, changed_ids=candidate.get("changed_ids", []),
                              _verified_report_root=candidate["report_root"])
        return result

    def recover(self) -> list[str]:
        recovered = []
        with self.transaction() as db:
            rows = db.execute("SELECT * FROM runs WHERE status IN ('QUEUED','RUNNING','PAUSED','CHECKING','PAUSING','CANCELLING')").fetchall()
            for row in rows:
                owners = db.execute("SELECT * FROM run_owners WHERE run_id=?", (row["id"],)).fetchall()
                # A started worker takes precedence over a lingering submitting CLI.
                workers = [o for o in owners if o["role"] == "worker"]
                if any(self._owner_alive(o) for o in (workers or owners)):
                    continue
                db.execute("UPDATE runs SET status='CRASHED',detail=?,updated_at=? WHERE id=?", ("Worker process interrupted; persisted candidates remain inspectable", utcnow(), row["id"]))
                self._event(db, row["project_id"], run_id=row["id"], state_root=row["base_root"], stage="recovery", status="CRASHED", message="Interrupted worker recovered without publishing candidate")
                recovered.append(row["id"])
        return recovered

    def backup(self, destination: str | Path) -> Path:
        from .backup import backup_store
        return backup_store(self, destination)
