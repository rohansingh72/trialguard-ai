from pathlib import Path

import pandas as pd

from app.services.persistent_review import (
    PersistentHumanReviewStore,
    study_finding_id_for,
)
from app.services.review import review_subject
from app.services.study_repository import StudyRepository


def _frames(subject_id: str = "S1"):
    return {
        "dm": pd.DataFrame([
            {
                "USUBJID": subject_id,
                "BRTHDTC": "1990-01-01",
                "RFICDTC": "2026-01-01",
                "DMDISDTC": "2026-01-10",
            }
        ]),
        "ae": pd.DataFrame([
            {
                "USUBJID": subject_id,
                "AEDECOD": "Headache",
                "AESTDTC": "2026-01-01",
                "AEENDTC": "2026-01-02",
                "AETRTEMFL": "Y",
            }
        ]),
        "lb": pd.DataFrame([
            {
                "USUBJID": subject_id,
                "LBTESTCD": "K",
                "LBSTRESN": 2.7,
                "LBSTRESU": "mmol/L",
                "LBDTC": "2026-01-05",
            }
        ]),
        "ex": pd.DataFrame([
            {"USUBJID": subject_id, "EXSTDTC": "2026-01-03", "EXDOSE": 100},
            {"USUBJID": subject_id, "EXSTDTC": "2026-01-12", "EXDOSE": 100},
        ]),
    }


def test_study_survives_repository_restart(tmp_path: Path):
    repo = StudyRepository(tmp_path / "tg")
    study = repo.create_from_frames(name="Study A", **_frames("A-001"))

    reopened = StudyRepository(tmp_path / "tg")
    loaded = reopened.load_store(study.study_id)

    assert reopened.get(study.study_id).name == "Study A"
    assert loaded.all_subject_ids() == ["A-001"]


def test_multiple_studies_are_isolated(tmp_path: Path):
    repo = StudyRepository(tmp_path / "tg")
    a = repo.create_from_frames(name="Study A", **_frames("A-001"))
    b = repo.create_from_frames(name="Study B", **_frames("B-001"))

    assert repo.load_store(a.study_id).all_subject_ids() == ["A-001"]
    assert repo.load_store(b.study_id).all_subject_ids() == ["B-001"]
    assert {s.study_id for s in repo.list()} == {a.study_id, b.study_id}


def test_review_decision_survives_restart(tmp_path: Path):
    repo = StudyRepository(tmp_path / "tg")
    study = repo.create_from_frames(name="Study A", **_frames())
    trial = repo.load_store(study.study_id)

    reviews = PersistentHumanReviewStore(repo.db_path)
    reviews.sync_from_trial(study.study_id, trial)
    record = reviews.list_records(study.study_id)[0]
    reviews.update(
        study.study_id,
        record.finding_id,
        status="approved",
        reviewer="Rohan",
        note="Verified.",
    )

    reopened = PersistentHumanReviewStore(repo.db_path)
    saved = reopened.get(study.study_id, record.finding_id)
    events = reopened.audit_events(study.study_id, record.finding_id)

    assert saved.status == "approved"
    assert saved.reviewer == "Rohan"
    assert len(events) == 2
    assert events[-1].new_status == "approved"


def test_identical_findings_in_two_studies_get_distinct_ids(tmp_path: Path):
    repo = StudyRepository(tmp_path / "tg")
    a = repo.create_from_frames(name="A", **_frames())
    b = repo.create_from_frames(name="B", **_frames())

    finding_a = review_subject(repo.load_store(a.study_id), "S1").findings[0]
    finding_b = review_subject(repo.load_store(b.study_id), "S1").findings[0]

    assert study_finding_id_for(a.study_id, finding_a) != study_finding_id_for(
        b.study_id, finding_b
    )
