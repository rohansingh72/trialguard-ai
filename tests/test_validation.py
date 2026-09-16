import pandas as pd
from app.services.validation import validate_trial

def test_valid_trial_schema():
    frames={"DM":pd.DataFrame(columns=["USUBJID","BRTHDTC","RFICDTC","DMDISDTC"]),"AE":pd.DataFrame(columns=["USUBJID","AEDECOD","AESTDTC","AEENDTC","AETRTEMFL"]),"LB":pd.DataFrame(columns=["USUBJID","LBTESTCD","LBSTRESN","LBSTRESU","LBDTC"]),"EX":pd.DataFrame(columns=["USUBJID","EXSTDTC","EXDOSE"])}
    assert validate_trial(frames).valid is True

def test_invalid_trial_schema_reports_missing_columns():
    frames={"DM":pd.DataFrame(columns=["USUBJID"]),"AE":pd.DataFrame(columns=["USUBJID","AEDECOD","AESTDTC","AEENDTC","AETRTEMFL"]),"LB":pd.DataFrame(columns=["USUBJID","LBTESTCD","LBSTRESN","LBSTRESU","LBDTC"]),"EX":pd.DataFrame(columns=["USUBJID","EXSTDTC","EXDOSE"])}
    result=validate_trial(frames); assert result.valid is False
    dm_result=next(x for x in result.domains if x.domain=="DM")
    assert "BRTHDTC" in dm_result.missing_columns
