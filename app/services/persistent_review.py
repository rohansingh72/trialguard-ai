from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.models.schemas import AuditEvent, Finding, ReviewRecord, ReviewStatus
from app.services.review import summarize_trial


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_iso(value: datetime) -> str:
    return value.isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def study_finding_id_for(study_id: str, finding: Finding) -> str:
    payload = {
        "study_id": study_id,
        "subject_id": finding.subject_id,
        "rule_id": finding.rule_id,
        "domain": finding.domain,
        "evidence": finding.evidence,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"F-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


class PersistentHumanReviewStore:
    """SQLite-backed review queue and append-only audit log, scoped by study."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_records (
                    study_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    finding_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reviewer TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(study_id, finding_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL,
                    finding_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    previous_status TEXT,
                    new_status TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    note TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_review_study_status "
                "ON review_records(study_id, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_study_finding "
                "ON audit_events(study_id, finding_id, timestamp)"
            )

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> ReviewRecord:
        return ReviewRecord(
            finding_id=row["finding_id"],
            finding=Finding.model_validate_json(row["finding_json"]),
            status=row["status"],
            reviewer=row["reviewer"],
            note=row["note"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    def sync_from_trial(self, study_id: str, trial_store) -> tuple[int, int]:
        summary = summarize_trial(trial_store)
        created = 0

        with self._connect() as conn:
            for subject_review in summary.subject_summaries:
                for finding in subject_review.findings:
                    finding_id = study_finding_id_for(study_id, finding)
                    exists = conn.execute(
                        "SELECT 1 FROM review_records WHERE study_id=? AND finding_id=?",
                        (study_id, finding_id),
                    ).fetchone()
                    if exists:
                        continue

                    now = _utc_now()
                    conn.execute(
                        """
                        INSERT INTO review_records(
                            study_id, finding_id, finding_json, status, reviewer,
                            note, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            study_id,
                            finding_id,
                            finding.model_dump_json(),
                            "pending",
                            None,
                            None,
                            _as_iso(now),
                            _as_iso(now),
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO audit_events(
                            event_id, study_id, finding_id, event_type,
                            previous_status, new_status, reviewer, note, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(uuid4()),
                            study_id,
                            finding_id,
                            "created",
                            None,
                            "pending",
                            "system",
                            "Finding synchronized from deterministic QC.",
                            _as_iso(now),
                        ),
                    )
                    created += 1

            total = conn.execute(
                "SELECT COUNT(*) FROM review_records WHERE study_id=?",
                (study_id,),
            ).fetchone()[0]
        return created, int(total)

    def list_records(
        self, study_id: str, status: ReviewStatus | None = None
    ) -> list[ReviewRecord]:
        sql = "SELECT * FROM review_records WHERE study_id=?"
        params: list[object] = [study_id]
        if status is not None:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY finding_json, finding_id"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        records = [self._record_from_row(row) for row in rows]
        return sorted(
            records,
            key=lambda r: (r.finding.subject_id, r.finding.rule_id, r.finding_id),
        )

    def get(self, study_id: str, finding_id: str) -> ReviewRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_records WHERE study_id=? AND finding_id=?",
                (study_id, finding_id),
            ).fetchone()
        return self._record_from_row(row) if row else None

    def update(
        self,
        study_id: str,
        finding_id: str,
        *,
        status: ReviewStatus,
        reviewer: str,
        note: str | None,
    ) -> ReviewRecord | None:
        current = self.get(study_id, finding_id)
        if current is None:
            return None

        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_records
                SET status=?, reviewer=?, note=?, updated_at=?
                WHERE study_id=? AND finding_id=?
                """,
                (status, reviewer, note, _as_iso(now), study_id, finding_id),
            )
            conn.execute(
                """
                INSERT INTO audit_events(
                    event_id, study_id, finding_id, event_type,
                    previous_status, new_status, reviewer, note, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    study_id,
                    finding_id,
                    "review_updated",
                    current.status,
                    status,
                    reviewer,
                    note,
                    _as_iso(now),
                ),
            )
        return self.get(study_id, finding_id)

    def audit_events(self, study_id: str, finding_id: str) -> list[AuditEvent] | None:
        if self.get(study_id, finding_id) is None:
            return None
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_events
                WHERE study_id=? AND finding_id=?
                ORDER BY timestamp, event_id
                """,
                (study_id, finding_id),
            ).fetchall()
        return [
            AuditEvent(
                event_id=row["event_id"],
                finding_id=row["finding_id"],
                event_type=row["event_type"],
                previous_status=row["previous_status"],
                new_status=row["new_status"],
                reviewer=row["reviewer"],
                note=row["note"],
                timestamp=_parse_dt(row["timestamp"]),
            )
            for row in rows
        ]
