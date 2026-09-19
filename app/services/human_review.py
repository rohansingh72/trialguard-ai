from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from app.models.schemas import AuditEvent, Finding, ReviewRecord, ReviewStatus
from app.services.review import summarize_trial


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def finding_id_for(finding: Finding) -> str:
    """Create a stable ID for one deterministic finding snapshot."""
    payload = {
        "subject_id": finding.subject_id,
        "rule_id": finding.rule_id,
        "domain": finding.domain,
        "evidence": finding.evidence,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"F-{digest}"


class HumanReviewStore:
    """In-memory human-review workflow for deterministic QC findings.

    Milestone 3 intentionally keeps review state separate from the clinical
    source data. Milestone 4 will persist this state in a database.
    """

    def __init__(self) -> None:
        self._records: dict[str, ReviewRecord] = {}
        self._audit: dict[str, list[AuditEvent]] = {}

    def reset(self) -> None:
        self._records.clear()
        self._audit.clear()

    def sync_from_trial(self, trial_store) -> tuple[int, int]:
        summary = summarize_trial(trial_store)
        created = 0

        for subject_review in summary.subject_summaries:
            for finding in subject_review.findings:
                finding_id = finding_id_for(finding)
                if finding_id in self._records:
                    continue

                now = _utc_now()
                record = ReviewRecord(
                    finding_id=finding_id,
                    finding=finding,
                    status="pending",
                    reviewer=None,
                    note=None,
                    created_at=now,
                    updated_at=now,
                )
                self._records[finding_id] = record
                self._audit[finding_id] = [
                    AuditEvent(
                        event_id=str(uuid4()),
                        finding_id=finding_id,
                        event_type="created",
                        previous_status=None,
                        new_status="pending",
                        reviewer="system",
                        note="Finding synchronized from deterministic QC.",
                        timestamp=now,
                    )
                ]
                created += 1

        return created, len(self._records)

    def list_records(self, status: ReviewStatus | None = None) -> list[ReviewRecord]:
        records = list(self._records.values())
        if status is not None:
            records = [record for record in records if record.status == status]
        return sorted(
            records,
            key=lambda record: (
                record.finding.subject_id,
                record.finding.rule_id,
                record.finding_id,
            ),
        )

    def get(self, finding_id: str) -> ReviewRecord | None:
        return self._records.get(finding_id)

    def update(
        self,
        finding_id: str,
        *,
        status: ReviewStatus,
        reviewer: str,
        note: str | None,
    ) -> ReviewRecord | None:
        record = self._records.get(finding_id)
        if record is None:
            return None

        now = _utc_now()
        previous_status = record.status
        updated = record.model_copy(
            update={
                "status": status,
                "reviewer": reviewer,
                "note": note,
                "updated_at": now,
            }
        )
        self._records[finding_id] = updated
        self._audit.setdefault(finding_id, []).append(
            AuditEvent(
                event_id=str(uuid4()),
                finding_id=finding_id,
                event_type="review_updated",
                previous_status=previous_status,
                new_status=status,
                reviewer=reviewer,
                note=note,
                timestamp=now,
            )
        )
        return updated

    def audit_events(self, finding_id: str) -> list[AuditEvent] | None:
        events = self._audit.get(finding_id)
        if events is None:
            return None
        return list(events)
