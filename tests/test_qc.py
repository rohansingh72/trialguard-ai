import pandas as pd
from app.tools.qc import check_ae_before_first_dose, check_birth_after_consent, check_duplicate_ae, check_exposure_after_discontinuation, check_low_potassium_without_ae

def test_ae_before_first_dose():
    ae=pd.DataFrame([{"USUBJID":"S1","AEDECOD":"Headache","AESTDTC":"2026-01-01","AETRTEMFL":"Y"}]); ex=pd.DataFrame([{"USUBJID":"S1","EXSTDTC":"2026-01-03","EXDOSE":10}])
    f=check_ae_before_first_dose(ae,ex,"S1"); assert len(f)==1 and f[0].rule_id=="AE001"

def test_exposure_after_discontinuation():
    dm=pd.DataFrame([{"USUBJID":"S1","DMDISDTC":"2026-01-10"}]); ex=pd.DataFrame([{"USUBJID":"S1","EXSTDTC":"2026-01-12","EXDOSE":10}])
    f=check_exposure_after_discontinuation(dm,ex,"S1"); assert len(f)==1 and f[0].rule_id=="EX001"

def test_low_potassium_without_ae():
    lb=pd.DataFrame([{"USUBJID":"S1","LBTESTCD":"K","LBSTRESN":2.8,"LBSTRESU":"mmol/L","LBDTC":"2026-01-10"}]); ae=pd.DataFrame(columns=["USUBJID","AEDECOD"])
    f=check_low_potassium_without_ae(lb,ae,"S1"); assert len(f)==1 and f[0].rule_id=="LB001"

def test_duplicate_ae():
    ae=pd.DataFrame([{"USUBJID":"S1","AEDECOD":"Nausea","AESTDTC":"2026-01-01","AEENDTC":"2026-01-02"},{"USUBJID":"S1","AEDECOD":"Nausea","AESTDTC":"2026-01-01","AEENDTC":"2026-01-02"}])
    f=check_duplicate_ae(ae,"S1"); assert len(f)==1 and f[0].rule_id=="AE002"

def test_birth_after_consent():
    dm=pd.DataFrame([{"USUBJID":"S1","BRTHDTC":"2027-01-01","RFICDTC":"2026-01-01"}])
    f=check_birth_after_consent(dm,"S1"); assert len(f)==1 and f[0].rule_id=="DM001"
