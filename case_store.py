"""SQLite-backed case and audit store for the showcase control room.

The original prototype drained audit rows into WebSocket payloads and then lost
them.  This store makes cases and audit events queryable after the tick that
created them.  SQLite is the local/default implementation; the schema is kept
simple so the same records can be moved to managed Postgres/Cosmos in a hosted
deployment.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import OUTPUT_DIR


def _json(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))


class CaseAuditStore:
    def __init__(self, path: Optional[str] = None) -> None:
        configured = path or os.getenv("PRIPYAT_DB_PATH")
        self.path = Path(configured or (Path(OUTPUT_DIR) / "pripyat.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_schema(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    created_ts TEXT NOT NULL,
                    sim_timestamp TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    action TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    reviewer TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT NOT NULL DEFAULT '',
                    executed INTEGER NOT NULL DEFAULT 0,
                    agent_input_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    trace_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_ts DESC);
                CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    sim_timestamp TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity, entity_id);
                """
            )

    def create_case(self, case: dict) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO cases (
                    id, run_id, created_ts, sim_timestamp, scope, status, action,
                    level, source, reasoning, agent_input_json, evidence_json, trace_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case["id"], case["run_id"], case["created_ts"],
                    case["sim_timestamp"], case.get("scope", "timeline"),
                    case["status"], case["action"], case["level"], case["source"],
                    case["reasoning"], _json(case.get("agent_input", {})),
                    _json(case.get("evidence", {})), _json(case.get("trace", [])),
                ),
            )

    def update_case_review(self, case_id: str, review: dict) -> None:
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                UPDATE cases SET status=?, action=?, reviewer=?, note=?, reviewed_at=?, executed=?
                WHERE id=? AND status='pending_review'
                """,
                (
                    review["status"], review["action"], review.get("reviewer", ""),
                    review.get("note", ""), review.get("reviewed_at", ""),
                    int(bool(review.get("executed"))), case_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("case is missing or already decided")

    def mark_case_executed(self, case_id: str) -> None:
        with self._lock, self._connect() as db:
            cursor = db.execute(
                """
                UPDATE cases SET executed=1
                WHERE id=? AND status IN ('approved', 'approved_with_edits') AND executed=0
                """,
                (case_id,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("approved case is missing or already executed")

    @staticmethod
    def _case(row: sqlite3.Row, full: bool = False) -> dict:
        result = dict(row)
        result["executed"] = bool(result["executed"])
        for column, key in (
            ("agent_input_json", "agent_input"),
            ("evidence_json", "evidence"),
            ("trace_json", "trace"),
        ):
            value = result.pop(column)
            if full:
                result[key] = json.loads(value or ("[]" if key == "trace" else "{}"))
        return result

    def list_cases(self, status: Optional[str] = None, limit: int = 100) -> list[dict]:
        query = "SELECT * FROM cases"
        params: list[Any] = []
        if status:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY created_ts DESC LIMIT ?"
        params.append(min(max(limit, 1), 500))
        with self._lock, self._connect() as db:
            return [self._case(row) for row in db.execute(query, params).fetchall()]

    def get_case(self, case_id: str) -> Optional[dict]:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            return self._case(row, full=True) if row else None

    def append_audit(self, run_id: str, entries: list[dict]) -> None:
        if not entries:
            return
        rows = []
        for entry in entries:
            entity = entry.get("entity") or "run"
            entity_id = str(entry.get("entity_id") or run_id)
            recorded_at = datetime.now(timezone.utc).isoformat()
            rows.append((
                run_id, recorded_at, entry.get("ts", ""),
                int(entry.get("tick", 0)), entry.get("agent", "system"),
                entry.get("type", "event"), entity, entity_id,
                entry.get("status", "ok"), _json(entry),
            ))
        with self._lock, self._connect() as db:
            db.executemany(
                """
                INSERT INTO audit_events (
                    run_id, ts, sim_timestamp, tick, actor, event_type,
                    entity, entity_id, status, detail_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def add_audit_event(
        self, run_id: str, ts: str, tick: int, actor: str, event_type: str,
        entity: str, entity_id: str, status: str, detail: dict,
    ) -> None:
        self.append_audit(run_id, [{
            "ts": ts, "tick": tick, "agent": actor, "type": event_type,
            "entity": entity, "entity_id": entity_id, "status": status,
            "data": detail,
        }])

    def list_audit(
        self, limit: int = 250, run_id: Optional[str] = None,
        entity_id: Optional[str] = None,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if run_id:
            clauses.append("run_id=?")
            params.append(run_id)
        if entity_id:
            clauses.append("entity_id=?")
            params.append(entity_id)
        query = "SELECT * FROM audit_events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(min(max(limit, 1), 1000))
        with self._lock, self._connect() as db:
            rows = db.execute(query, params).fetchall()
            result = []
            for row in rows:
                event = dict(row)
                event["detail"] = json.loads(event.pop("detail_json") or "{}")
                result.append(event)
            return result
