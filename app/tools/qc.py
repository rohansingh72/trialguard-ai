from __future__ import annotations
import pandas as pd
from app.models.schemas import Finding

def _subject_rows(df: pd.DataFrame, subject_id: str) -> pd.DataFrame:
    if df.empty or "USUBJID" not in df.columns: return pd.DataFrame()
    return df[df["USUBJID"].astype(str) == str(subject_id)].copy()

def check_ae_before_first_dose(ae, ex, subject_id):
    ae_s, ex_s = _subject_rows(ae, subject_id), _subject_rows(ex, subject_id)
    if ae_s.empty or ex_s.empty: return []
    ex_s["EXSTDTC"] = pd.to_datetime(ex_s["EXSTDTC"], errors="coerce")
    ae_s["AESTDTC"] = pd.to_datetime(ae_s["AESTDTC"], errors="coerce")
    first_dose = ex_s["EXSTDTC"].min(); findings=[]
    for _, row in ae_s.iterrows():
        if row.get("AETRTEMFL") == "Y" and pd.notna(row["AESTDTC"]) and pd.notna(first_dose) and row["AESTDTC"] < first_dose:
            findings.append(Finding(rule_id="AE001", subject_id=str(subject_id), domain="AE", severity="high", title="Treatment-emergent AE starts before first dose", description="An adverse event is marked treatment-emergent even though its start date precedes the first recorded exposure.", evidence={"AEDECOD": row.get("AEDECOD"), "AESTDTC": str(row["AESTDTC"].date()), "AETRTEMFL": row.get("AETRTEMFL"), "FIRST_DOSE": str(first_dose.date())}))
    return findings

def check_exposure_after_discontinuation(dm, ex, subject_id):
    dm_s, ex_s = _subject_rows(dm, subject_id), _subject_rows(ex, subject_id)
    if dm_s.empty or ex_s.empty or "DMDISDTC" not in dm_s.columns: return []
    disc = pd.to_datetime(dm_s.iloc[0].get("DMDISDTC"), errors="coerce")
    ex_s["EXSTDTC"] = pd.to_datetime(ex_s["EXSTDTC"], errors="coerce")
    if pd.isna(disc): return []
    findings=[]
    for _, row in ex_s[ex_s["EXSTDTC"] > disc].iterrows():
        findings.append(Finding(rule_id="EX001", subject_id=str(subject_id), domain="EX", severity="high", title="Exposure recorded after discontinuation", description="A dosing record occurs after the subject discontinuation date.", evidence={"DMDISDTC": str(disc.date()), "EXSTDTC": str(row["EXSTDTC"].date()) if pd.notna(row["EXSTDTC"]) else None, "EXDOSE": row.get("EXDOSE")}))
    return findings

def check_low_potassium_without_ae(lb, ae, subject_id):
    lb_s, ae_s = _subject_rows(lb, subject_id), _subject_rows(ae, subject_id)
    if lb_s.empty: return []
    potassium = lb_s[lb_s["LBTESTCD"].astype(str).str.upper()=="K"].copy()
    potassium["LBSTRESN"] = pd.to_numeric(potassium["LBSTRESN"], errors="coerce")
    low = potassium[potassium["LBSTRESN"] < 3.0]
    ae_terms = " ".join(ae_s.get("AEDECOD", pd.Series(dtype=str)).astype(str).str.lower().tolist())
    if any(t in ae_terms for t in ["hypokal", "potassium"]): return []
    return [Finding(rule_id="LB001", subject_id=str(subject_id), domain="LB", severity="medium", title="Marked hypokalemia without corresponding AE", description="Potassium is below 3.0 mmol/L and no potassium-related adverse event is recorded.", evidence={"LBTESTCD": r.get("LBTESTCD"), "LBSTRESN": r.get("LBSTRESN"), "LBSTRESU": r.get("LBSTRESU"), "LBDTC": r.get("LBDTC")}) for _, r in low.iterrows()]

def check_duplicate_ae(ae, subject_id):
    ae_s = _subject_rows(ae, subject_id)
    if ae_s.empty: return []
    cols=[c for c in ["USUBJID","AEDECOD","AESTDTC","AEENDTC"] if c in ae_s.columns]
    if len(cols)<3: return []
    dups=ae_s[ae_s.duplicated(subset=cols, keep=False)]
    if dups.empty: return []
    return [Finding(rule_id="AE002", subject_id=str(subject_id), domain="AE", severity="medium", title="Potential duplicate adverse-event records", description="Multiple AE records share the same subject, term, and event dates.", evidence={"duplicate_rows": dups[cols].to_dict(orient="records")})]

def check_birth_after_consent(dm, subject_id):
    dm_s=_subject_rows(dm, subject_id)
    if dm_s.empty: return []
    birth=pd.to_datetime(dm_s.iloc[0].get("BRTHDTC"), errors="coerce"); consent=pd.to_datetime(dm_s.iloc[0].get("RFICDTC"), errors="coerce")
    if pd.notna(birth) and pd.notna(consent) and birth > consent:
        return [Finding(rule_id="DM001", subject_id=str(subject_id), domain="DM", severity="high", title="Birth date occurs after informed consent", description="The demographic dates are chronologically impossible.", evidence={"BRTHDTC": str(birth.date()), "RFICDTC": str(consent.date())})]
    return []

def run_subject_qc(dm, ae, lb, ex, subject_id):
    findings=[]
    findings += check_ae_before_first_dose(ae, ex, subject_id)
    findings += check_exposure_after_discontinuation(dm, ex, subject_id)
    findings += check_low_potassium_without_ae(lb, ae, subject_id)
    findings += check_duplicate_ae(ae, subject_id)
    findings += check_birth_after_consent(dm, subject_id)
    return findings
