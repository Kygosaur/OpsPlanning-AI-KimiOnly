from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ScheduleRecord:
    id: str
    status: str
    created_at: str
    created_by: str
    result: dict[str, Any]


class PlanningDatabase:
    """SQLite persistence for schedule versions, users, approvals, and audit events."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def session(self):
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._lock, self.session() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','planner','viewer')),
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schedule_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK(status IN ('draft','approved','rejected')),
                    request_text TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    review_comment TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    details_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_schedule_created ON schedule_runs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp DESC);
            """)

    def get_user(self, username: str) -> sqlite3.Row | None:
        with self.session() as db:
            return db.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()

    def upsert_user(self, username: str, password_hash: str, role: str) -> None:
        if role not in {"admin", "planner", "viewer"}:
            raise ValueError("Invalid role")
        with self._lock, self.session() as db:
            db.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?) "
                "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, role=excluded.role, active=1",
                (username, password_hash, role, _now()),
            )
        self.audit(username, "USER_UPSERT", "user", username, {"role": role})

    def create_schedule(self, request_text: str, result: dict[str, Any], actor: str) -> str:
        identifier = str(uuid.uuid4())
        with self._lock, self.session() as db:
            db.execute(
                "INSERT INTO schedule_runs(id,status,request_text,result_json,created_by,created_at) VALUES(?,?,?,?,?,?)",
                (identifier, "draft", request_text, json.dumps(result), actor, _now()),
            )
        self.audit(actor, "SCHEDULE_CREATED", "schedule", identifier, {"status": "draft"})
        return identifier

    def review_schedule(self, identifier: str, decision: str, actor: str, comment: str = "") -> None:
        if decision not in {"approved", "rejected"}:
            raise ValueError("Decision must be approved or rejected")
        with self._lock, self.session() as db:
            cursor = db.execute(
                "UPDATE schedule_runs SET status=?,reviewed_by=?,reviewed_at=?,review_comment=? WHERE id=? AND status='draft'",
                (decision, actor, _now(), comment, identifier),
            )
            if cursor.rowcount != 1:
                raise KeyError("Draft schedule not found")
        self.audit(actor, f"SCHEDULE_{decision.upper()}", "schedule", identifier, {"comment": comment})

    def list_schedules(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.session() as db:
            rows = db.execute(
                "SELECT id,status,created_by,created_at,reviewed_by,reviewed_at,review_comment,result_json FROM schedule_runs ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [{**dict(row), "result": json.loads(row["result_json"])} for row in rows]

    def audit(self, actor: str, action: str, entity_type: str, entity_id: str | None, details: dict[str, Any]) -> None:
        with self._lock, self.session() as db:
            db.execute(
                "INSERT INTO audit_events(timestamp,actor,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?,?)",
                (_now(), actor, action, entity_type, entity_id, json.dumps(details)),
            )
