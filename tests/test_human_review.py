import pandas as pd

from app.services.data_store import TrialDataStore
from app.services.human_review import HumanReviewStore, finding_id_for
from app.services.review import review_subject


def _store_with_three_findings() -> TrialDataStore:
    store = TrialDataStore()
    store.load_frames(
        dm=pd.DataFrame([
            {
                "USUBJID": "S1",
                "BRTHDTC": "1990-01-01",
                "RFICDTC": "2026-01-01",
                "DMDISDTC": "2026-01-10",
            }
        ]),
        ae=pd.DataFrame([
            {
                "USUBJID": "S1",
                "AEDECOD": "Headache",
                "AESTDTC": "2026-01-01",
                "AEENDTC": "2026-01-02",
                "AETRTEMFL": "Y",
            }
        ]),
        lb=pd.DataFrame([
            {
                "USUBJID": "S1",
                "LBTESTCD": "K",
                "LBSTRESN": 2.7,
                "LBSTRESU": "mmol/L",
                "LBDTC": "2026-01-05",
            }
        ]),
        ex=pd.DataFrame([
            {"USUBJID": "S1", "EXSTDTC": "2026-01-03", "EXDOSE": 100},
            {"USUBJID": "S1", "EXSTDTC": "2026-01-12", "EXDOSE": 100},
        ]),
    )
    return store


def test_sync_creates_pending_review_records():
    trial = _store_with_three_findings()
    reviews = HumanReviewStore()

    created, total = reviews.sync_from_trial(trial)

    assert created == 3
    assert total == 3
    assert all(record.status == "pending" for record in reviews.list_records())


def test_sync_is_idempotent_and_preserves_review_state():
    trial = _store_with_three_findings()
    reviews = HumanReviewStore()
    reviews.sync_from_trial(trial)
    first = reviews.list_records()[0]
    reviews.update(first.finding_id, status="approved", reviewer="Rohan", note="Verified.")

    created, total = reviews.sync_from_trial(trial)

    assert created == 0
    assert total == 3
    assert reviews.get(first.finding_id).status == "approved"


def test_review_update_appends_immutable_audit_event():
    trial = _store_with_three_findings()
    reviews = HumanReviewStore()
    reviews.sync_from_trial(trial)
    record = reviews.list_records()[0]

    updated = reviews.update(
        record.finding_id,
        status="needs_followup",
        reviewer="Rohan",
        note="Source verification required.",
    )
    events = reviews.audit_events(record.finding_id)

    assert updated.status == "needs_followup"
    assert updated.reviewer == "Rohan"
    assert len(events) == 2
    assert events[0].event_type == "created"
    assert events[1].event_type == "review_updated"
    assert events[1].previous_status == "pending"
    assert events[1].new_status == "needs_followup"


def test_filter_by_status():
    trial = _store_with_three_findings()
    reviews = HumanReviewStore()
    reviews.sync_from_trial(trial)
    first = reviews.list_records()[0]
    reviews.update(first.finding_id, status="rejected", reviewer="Reviewer", note=None)

    rejected = reviews.list_records(status="rejected")
    pending = reviews.list_records(status="pending")

    assert len(rejected) == 1
    assert len(pending) == 2


def test_finding_id_is_stable():
    trial = _store_with_three_findings()
    finding = review_subject(trial, "S1").findings[0]
    assert finding_id_for(finding) == finding_id_for(finding.model_copy())
