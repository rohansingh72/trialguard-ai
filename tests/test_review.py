import pandas as pd
from app.services.data_store import TrialDataStore
from app.services.review import summarize_trial

def test_trial_summary_counts_findings():
    s=TrialDataStore(); s.load_frames(
        pd.DataFrame([{"USUBJID":"S1","BRTHDTC":"1990-01-01","RFICDTC":"2026-01-01","DMDISDTC":"2026-01-10"}]),
        pd.DataFrame([{"USUBJID":"S1","AEDECOD":"Headache","AESTDTC":"2026-01-01","AEENDTC":"2026-01-02","AETRTEMFL":"Y"}]),
        pd.DataFrame([{"USUBJID":"S1","LBTESTCD":"K","LBSTRESN":4.0,"LBSTRESU":"mmol/L","LBDTC":"2026-01-05"}]),
        pd.DataFrame([{"USUBJID":"S1","EXSTDTC":"2026-01-03","EXDOSE":100},{"USUBJID":"S1","EXSTDTC":"2026-01-12","EXDOSE":100}]))
    summary=summarize_trial(s); assert summary.subject_count==1 and summary.finding_count==2
    assert summary.findings_by_rule["AE001"]==1 and summary.findings_by_rule["EX001"]==1
