from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from uuid import uuid4

from sqlalchemy import text

from app.models.schemas import AuditEvent, Finding, ReviewRecord, ReviewStatus
from app.services.database import create_database_engine, database_url_from_target
from app.services.review import summarize_trial


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_iso(value: datetime) -> str:
    return value.isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _enum_value(value):
    return getattr(value, "value", value)


def study_finding_id_for(study_id: str, finding: Finding) -> str:
    payload = {
        "study_id": study_id,
        "subject_id": finding.subject_id,
        "rule_id": finding.rule_id,
        "domain": finding.domain,
        "evidence": finding.evidence,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return f"F-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


class PersistentHumanReviewStore:
    """
    Persistent human-review queue and append-only audit log.

    Supports SQLite for local development/testing and PostgreSQL
    for production deployments.
    """

    def __init__(self, database: str | Path) -> None:
        self.database_url = database_url_from_target(database)
        self.engine = create_database_engine(self.database_url)
        self._init_db()

    def _init_db(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
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
            )

            conn.execute(
                text(
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
            )

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_review_study_status
                    ON review_records(study_id, status)
                    """
                )
            )

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_audit_study_finding
                    ON audit_events(study_id, finding_id, timestamp)
                    """
                )
            )

    @staticmethod
    def _record_from_row(row: Mapping[str, object]) -> ReviewRecord:
        return ReviewRecord(
            finding_id=str(row["finding_id"]),
            finding=Finding.model_validate_json(str(row["finding_json"])),
            status=str(row["status"]),
            reviewer=(
                str(row["reviewer"]) if row["reviewer"] is not None else None
            ),
            note=str(row["note"]) if row["note"] is not None else None,
            created_at=_parse_dt(str(row["created_at"])),
            updated_at=_parse_dt(str(row["updated_at"])),
        )

    def sync_from_trial(self, study_id: str, trial_store) -> tuple[int, int]:
        summary = summarize_trial(trial_store)
        created = 0

        with self.engine.begin() as conn:
            for subject_review in summary.subject_summaries:
                for finding in subject_review.findings:
                    finding_id = study_finding_id_for(study_id, finding)

                    exists = conn.execute(
                        text(
                            """
                            SELECT 1
                            FROM review_records
                            WHERE study_id = :study_id
                              AND finding_id = :finding_id
                            """
                        ),
                        {
                            "study_id": study_id,
                            "finding_id": finding_id,
                        },
                    ).first()

                    if exists:
                        continue

                    now = _utc_now()

                    conn.execute(
                        text(
                            """
                            INSERT INTO review_records(
                                study_id,
                                finding_id,
                                finding_json,
                                status,
                                reviewer,
                                note,
                                created_at,
                                updated_at
                            )
                            VALUES (
                                :study_id,
                                :finding_id,
                                :finding_json,
                                :status,
                                :reviewer,
                                :note,
                                :created_at,
                                :updated_at
                            )
                            """
                        ),
                        {
                            "study_id": study_id,
                            "finding_id": finding_id,
                            "finding_json": finding.model_dump_json(),
                            "status": "pending",
                            "reviewer": None,
                            "note": None,
                            "created_at": _as_iso(now),
                            "updated_at": _as_iso(now),
                        },
                    )

                    conn.execute(
                        text(
                            """
                            INSERT INTO audit_events(
                                event_id,
                                study_id,
                                finding_id,
                                event_type,
                                previous_status,
                                new_status,
                                reviewer,
                                note,
                                timestamp
                            )
                            VALUES (
                                :event_id,
                                :study_id,
                                :finding_id,
                                :event_type,
                                :previous_status,
                                :new_status,
                                :reviewer,
                                :note,
                                :timestamp
                            )
                            """
                        ),
                        {
                            "event_id": str(uuid4()),
                            "study_id": study_id,
                            "finding_id": finding_id,
                            "event_type": "created",
                            "previous_status": None,
                            "new_status": "pending",
                            "reviewer": "system",
                            "note": "Finding synchronized from deterministic QC.",
                            "timestamp": _as_iso(now),
                        },
                    )

                    created += 1

            total = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM review_records
                    WHERE study_id = :study_id
                    """
                ),
                {"study_id": study_id},
            ).scalar_one()

        return created, int(total)

    def list_records(
        self,
        study_id: str,
        status: ReviewStatus | None = None,
    ) -> list[ReviewRecord]:
        params: dict[str, object] = {"study_id": study_id}

        sql = """
            SELECT *
            FROM review_records
            WHERE study_id = :study_id
        """

        if status is not None:
            sql += " AND status = :status"
            params["status"] = _enum_value(status)

        sql += " ORDER BY finding_json, finding_id"

        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()

        records = [self._record_from_row(row) for row in rows]

        return sorted(
            records,
            key=lambda r: (
                r.finding.subject_id,
                r.finding.rule_id,
                r.finding_id,
            ),
        )

    def get(self, study_id: str, finding_id: str) -> ReviewRecord | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        """
                        SELECT *
                        FROM review_records
                        WHERE study_id = :study_id
                          AND finding_id = :finding_id
                        """
                    ),
                    {
                        "study_id": study_id,
                        "finding_id": finding_id,
                    },
                )
                .mappings()
                .first()
            )

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
        new_status = _enum_value(status)
        previous_status = _enum_value(current.status)

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE review_records
                    SET status = :status,
                        reviewer = :reviewer,
                        note = :note,
                        updated_at = :updated_at
                    WHERE study_id = :study_id
                      AND finding_id = :finding_id
                    """
                ),
                {
                    "status": new_status,
                    "reviewer": reviewer,
                    "note": note,
                    "updated_at": _as_iso(now),
                    "study_id": study_id,
                    "finding_id": finding_id,
                },
            )

            conn.execute(
                text(
                    """
                    INSERT INTO audit_events(
                        event_id,
                        study_id,
                        finding_id,
                        event_type,
                        previous_status,
                        new_status,
                        reviewer,
                        note,
                        timestamp
                    )
                    VALUES (
                        :event_id,
                        :study_id,
                        :finding_id,
                        :event_type,
                        :previous_status,
                        :new_status,
                        :reviewer,
                        :note,
                        :timestamp
                    )
                    """
                ),
                {
                    "event_id": str(uuid4()),
                    "study_id": study_id,
                    "finding_id": finding_id,
                    "event_type": "review_updated",
                    "previous_status": previous_status,
                    "new_status": new_status,
                    "reviewer": reviewer,
                    "note": note,
                    "timestamp": _as_iso(now),
                },
            )

        return self.get(study_id, finding_id)

    def audit_events(
        self,
        study_id: str,
        finding_id: str,
    ) -> list[AuditEvent] | None:
        if self.get(study_id, finding_id) is None:
            return None

        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                        SELECT *
                        FROM audit_events
                        WHERE study_id = :study_id
                          AND finding_id = :finding_id
                        ORDER BY timestamp, event_id
                        """
                    ),
                    {
                        "study_id": study_id,
                        "finding_id": finding_id,
                    },
                )
                .mappings()
                .all()
            )

        return [
            AuditEvent(
                event_id=str(row["event_id"]),
                finding_id=str(row["finding_id"]),
                event_type=str(row["event_type"]),
                previous_status=(
                    str(row["previous_status"])
                    if row["previous_status"] is not None
                    else None
                ),
                new_status=str(row["new_status"]),
                reviewer=str(row["reviewer"]),
                note=str(row["note"]) if row["note"] is not None else None,
                timestamp=_parse_dt(str(row["timestamp"])),
            )
            for row in rows
        ]
