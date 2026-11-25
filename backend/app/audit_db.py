"""SQLite persistence for incidents, approval requests and the append-only audit log."""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.schemas import ApprovalRequest, AuditEntry, Incident

_INCIDENT_COLUMNS = {
    "id",
    "timestamp",
    "severity",
    "category",
    "title",
    "plain_english_explanation",
    "correlated_device_ids",
    "prompt_injection_detected",
    "sanitized_excerpt",
    "proposed_action",
    "approval_status",
}
_APPROVAL_COLUMNS = {
    "id",
    "incident_id",
    "created_at",
    "target_device_id",
    "recommended_action",
    "risk_summary",
    "status",
}


class AuditDB:
    """Small synchronous SQLite store guarded by a re-entrant lock."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sequence = 0
        self._connection = sqlite3.connect(
            str(self.db_path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self.initialize()

    @staticmethod
    def utc_now() -> str:
        """UTC ISO-8601 timestamp with a trailing Z, matching JS toISOString()."""
        return (
            datetime.now(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    def next_id(self, prefix: str) -> str:
        """Prefixed timestamp ID, e.g. inc-20261125T101500123456-0001."""
        with self._lock:
            self._sequence += 1
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            return f"{prefix}-{stamp}-{self._sequence:04d}"

    def initialize(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    plain_english_explanation TEXT NOT NULL,
                    correlated_device_ids TEXT NOT NULL,
                    prompt_injection_detected INTEGER NOT NULL,
                    sanitized_excerpt TEXT,
                    proposed_action TEXT NOT NULL,
                    approval_status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    target_device_id TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    risk_summary TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_timestamp
                    ON incidents(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_approvals_created_at
                    ON approvals(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_log(timestamp DESC);
                """
            )
            self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # ------------------------------- incidents ------------------------------

    def insert_incident(self, incident: Incident) -> Incident:
        values = incident.model_dump()
        values["correlated_device_ids"] = json.dumps(
            values["correlated_device_ids"]
        )
        values["prompt_injection_detected"] = int(
            values["prompt_injection_detected"]
        )
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO incidents (
                    id, timestamp, severity, category, title,
                    plain_english_explanation, correlated_device_ids,
                    prompt_injection_detected, sanitized_excerpt,
                    proposed_action, approval_status
                ) VALUES (
                    :id, :timestamp, :severity, :category, :title,
                    :plain_english_explanation, :correlated_device_ids,
                    :prompt_injection_detected, :sanitized_excerpt,
                    :proposed_action, :approval_status
                )
                """,
                values,
            )
            self._connection.commit()
        return incident

    def list_incidents(self) -> list[Incident]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM incidents ORDER BY timestamp DESC"
            ).fetchall()
        return [self._incident_from_row(row) for row in rows]

    def update_incident(
        self, incident_id: str, patch: dict[str, Any]
    ) -> Incident | None:
        return self._update_row(
            "incidents",
            incident_id,
            patch,
            _INCIDENT_COLUMNS,
            self._incident_from_row,
        )

    # ------------------------------- approvals ------------------------------

    def insert_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO approvals (
                    id, incident_id, created_at, target_device_id,
                    recommended_action, risk_summary, status
                ) VALUES (
                    :id, :incident_id, :created_at, :target_device_id,
                    :recommended_action, :risk_summary, :status
                )
                """,
                approval.model_dump(),
            )
            self._connection.commit()
        return approval

    def list_approvals(self) -> list[ApprovalRequest]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM approvals ORDER BY created_at DESC"
            ).fetchall()
        return [ApprovalRequest(**dict(row)) for row in rows]

    def update_approval(
        self, approval_id: str, patch: dict[str, Any]
    ) -> ApprovalRequest | None:
        return self._update_row(
            "approvals",
            approval_id,
            patch,
            _APPROVAL_COLUMNS,
            lambda row: ApprovalRequest(**dict(row)),
        )

    # -------------------------------- audit log -----------------------------

    def insert_audit(self, entry: AuditEntry) -> AuditEntry:
        """Append-only: intentionally no matching update or delete helper."""
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO audit_log (id, timestamp, actor, action, details)
                VALUES (:id, :timestamp, :actor, :action, :details)
                """,
                entry.model_dump(),
            )
            self._connection.commit()
        return entry

    def list_audit(self) -> list[AuditEntry]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC"
            ).fetchall()
        return [AuditEntry(**dict(row)) for row in rows]

    # --------------------------------- helpers ------------------------------

    def _update_row(
        self,
        table: str,
        row_id: str,
        patch: dict[str, Any],
        allowed: set[str],
        parser: Any,
    ) -> Any:
        updates = {key: value for key, value in patch.items() if key in allowed}
        if not updates:
            return None
        if table == "incidents" and "correlated_device_ids" in updates:
            updates["correlated_device_ids"] = json.dumps(
                updates["correlated_device_ids"]
            )
        if table == "incidents" and "prompt_injection_detected" in updates:
            updates["prompt_injection_detected"] = int(
                updates["prompt_injection_detected"]
            )
        assignments = ", ".join(f"{key} = :{key}" for key in updates)
        parameters: dict[str, Any] = {"row_id": row_id, **updates}
        with self._lock:
            cursor = self._connection.execute(
                f"UPDATE {table} SET {assignments} WHERE id = :row_id",
                parameters,
            )
            self._connection.commit()
            if cursor.rowcount == 0:
                return None
            row = self._connection.execute(
                f"SELECT * FROM {table} WHERE id = ?", (row_id,)
            ).fetchone()
        return parser(row) if row is not None else None

    @staticmethod
    def _incident_from_row(row: sqlite3.Row) -> Incident:
        values = dict(row)
        values["correlated_device_ids"] = json.loads(
            values["correlated_device_ids"]
        )
        values["prompt_injection_detected"] = bool(
            values["prompt_injection_detected"]
        )
        return Incident(**values)
