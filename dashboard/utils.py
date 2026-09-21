from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


REVIEW_STATUSES = ["pending", "approved", "rejected", "needs_followup"]
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def review_metrics(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    rows = list(records)
    counts = Counter(str(row.get("status", "pending")) for row in rows)
    return {
        "total": len(rows),
        "pending": counts.get("pending", 0),
        "approved": counts.get("approved", 0),
        "rejected": counts.get("rejected", 0),
        "needs_followup": counts.get("needs_followup", 0),
    }


def flatten_review_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for record in records:
        finding = record.get("finding") or {}
        flat.append(
            {
                "finding_id": record.get("finding_id"),
                "subject_id": finding.get("subject_id"),
                "rule_id": finding.get("rule_id"),
                "domain": finding.get("domain"),
                "severity": finding.get("severity"),
                "title": finding.get("title"),
                "status": record.get("status"),
                "reviewer": record.get("reviewer"),
                "updated_at": record.get("updated_at"),
            }
        )
    return sorted(
        flat,
        key=lambda row: (
            SEVERITY_ORDER.get(str(row.get("severity")), 99),
            str(row.get("subject_id") or ""),
            str(row.get("rule_id") or ""),
        ),
    )


def filter_records(
    records: Iterable[dict[str, Any]],
    *,
    statuses: set[str] | None = None,
    severities: set[str] | None = None,
    domains: set[str] | None = None,
    subjects: set[str] | None = None,
) -> list[dict[str, Any]]:
    result = []
    for record in records:
        finding = record.get("finding") or {}
        if statuses and record.get("status") not in statuses:
            continue
        if severities and finding.get("severity") not in severities:
            continue
        if domains and finding.get("domain") not in domains:
            continue
        if subjects and finding.get("subject_id") not in subjects:
            continue
        result.append(record)
    return result
