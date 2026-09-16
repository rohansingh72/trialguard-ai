from pathlib import Path
import pandas as pd
OUT=Path("generated_data"); OUT.mkdir(exist_ok=True)
dm=pd.DataFrame([
{"USUBJID":"TG-001","SEX":"M","BRTHDTC":"1989-04-02","RFICDTC":"2026-01-05","DMDISDTC":"2026-01-20"},
{"USUBJID":"TG-002","SEX":"F","BRTHDTC":"1993-09-14","RFICDTC":"2026-01-05","DMDISDTC":""},
{"USUBJID":"TG-003","SEX":"F","BRTHDTC":"2027-01-01","RFICDTC":"2026-01-05","DMDISDTC":""}])
ae=pd.DataFrame([
{"USUBJID":"TG-001","AEDECOD":"Headache","AESTDTC":"2026-01-08","AEENDTC":"2026-01-09","AETRTEMFL":"Y"},
{"USUBJID":"TG-002","AEDECOD":"Nausea","AESTDTC":"2026-01-12","AEENDTC":"2026-01-13","AETRTEMFL":"Y"},
{"USUBJID":"TG-002","AEDECOD":"Nausea","AESTDTC":"2026-01-12","AEENDTC":"2026-01-13","AETRTEMFL":"Y"}])
lb=pd.DataFrame([
{"USUBJID":"TG-001","LBTESTCD":"K","LBSTRESN":2.7,"LBSTRESU":"mmol/L","LBDTC":"2026-01-16"},
{"USUBJID":"TG-002","LBTESTCD":"K","LBSTRESN":4.1,"LBSTRESU":"mmol/L","LBDTC":"2026-01-16"}])
ex=pd.DataFrame([
{"USUBJID":"TG-001","EXSTDTC":"2026-01-10","EXDOSE":100},
{"USUBJID":"TG-001","EXSTDTC":"2026-01-25","EXDOSE":100},
{"USUBJID":"TG-002","EXSTDTC":"2026-01-10","EXDOSE":100},
{"USUBJID":"TG-003","EXSTDTC":"2026-01-10","EXDOSE":100}])
for name,df in [("DM",dm),("AE",ae),("LB",lb),("EX",ex)]: df.to_csv(OUT/f"{name}.csv", index=False)
print(f"Wrote demo datasets to {OUT.resolve()}")
