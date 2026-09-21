from dashboard.utils import filter_records, flatten_review_records, review_metrics


def _records():
    return [
        {
            "finding_id": "F1",
            "status": "pending",
            "reviewer": None,
            "updated_at": "2026-01-01T00:00:00Z",
            "finding": {
                "subject_id": "S1",
                "rule_id": "AE001",
                "domain": "AE",
                "severity": "high",
                "title": "AE issue",
            },
        },
        {
            "finding_id": "F2",
            "status": "approved",
            "reviewer": "Reviewer",
            "updated_at": "2026-01-02T00:00:00Z",
            "finding": {
                "subject_id": "S2",
                "rule_id": "LB001",
                "domain": "LB",
                "severity": "medium",
                "title": "Lab issue",
            },
        },
    ]


def test_review_metrics_counts_statuses():
    metrics = review_metrics(_records())
    assert metrics["total"] == 2
    assert metrics["pending"] == 1
    assert metrics["approved"] == 1
    assert metrics["rejected"] == 0


def test_flatten_review_records_prioritizes_high_severity():
    rows = flatten_review_records(_records())
    assert rows[0]["finding_id"] == "F1"
    assert rows[0]["severity"] == "high"


def test_filter_records_combines_filters():
    rows = filter_records(
        _records(),
        statuses={"approved"},
        severities={"medium"},
        domains={"LB"},
        subjects={"S2"},
    )
    assert [r["finding_id"] for r in rows] == ["F2"]
