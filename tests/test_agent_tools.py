import pandas as pd

from app.agents.tools import build_investigation_tools
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
            },
            {
                "USUBJID": "S1",
                "AEDECOD": "Nausea",
                "AESTDTC": "2026-01-06",
                "AEENDTC": "2026-01-07",
                "AETRTEMFL": "Y",
            },
            {
                "USUBJID": "S1",
                "AEDECOD": "Nausea",
                "AESTDTC": "2026-01-06",
                "AEENDTC": "2026-01-07",
                "AETRTEMFL": "Y",
            },
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


def _tools_by_name():
    return {tool.name: tool for tool in build_investigation_tools(_store())}


def test_subject_overview_tool_returns_all_domains():
    result = _tools_by_name()["get_subject_overview"].invoke({"subject_id": "S1"})
    assert result["subject_id"] == "S1"
    assert len(result["DM"]) == 1
    assert len(result["AE"]) == 3
    assert len(result["LB"]) == 1
    assert len(result["EX"]) == 2


def test_adverse_event_tool_returns_seeded_rules():
    result = _tools_by_name()["review_adverse_events"].invoke({"subject_id": "S1"})
    rule_ids = {finding["rule_id"] for finding in result["findings"]}
    assert {"AE001", "AE002"}.issubset(rule_ids)


def test_lab_tool_returns_lb001():
    result = _tools_by_name()["review_labs"].invoke({"subject_id": "S1"})
    assert result["findings"][0]["rule_id"] == "LB001"


def test_exposure_tool_returns_ex001():
    result = _tools_by_name()["review_exposure"].invoke({"subject_id": "S1"})
    assert result["findings"][0]["rule_id"] == "EX001"


def test_demographic_tool_can_return_no_findings():
    result = _tools_by_name()["review_demographics"].invoke({"subject_id": "S1"})
    assert result["finding_count"] == 0
