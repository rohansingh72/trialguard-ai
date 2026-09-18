import pandas as pd

from app.agents.investigation import (
    BROAD_REVIEW_TOOL_NAMES,
    _is_broad_investigation,
    _run_broad_qc,
)
from app.services.data_store import TrialDataStore


def _store() -> TrialDataStore:
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
                "LBSTRESN": 2.8,
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


def test_broad_question_is_detected():
    assert _is_broad_investigation(
        "Investigate this subject for possible data-quality issues."
    )


def test_narrow_question_is_not_broad():
    assert not _is_broad_investigation(
        "Are there duplicate adverse events for this subject?"
    )


def test_broad_qc_forces_all_review_tools():
    evidence, tools_used = _run_broad_qc(_store(), "S1")

    assert tools_used == BROAD_REVIEW_TOOL_NAMES
    assert evidence["overview"]["record_counts"] == {
        "DM": 1,
        "AE": 1,
        "LB": 1,
        "EX": 2,
    }

    assert evidence["qc"]["review_adverse_events"]["finding_count"] == 1
    assert evidence["qc"]["review_labs"]["finding_count"] == 1
    assert evidence["qc"]["review_exposure"]["finding_count"] == 1
    assert evidence["qc"]["review_demographics"]["finding_count"] == 0
