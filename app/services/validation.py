import pandas as pd
from app.models.schemas import DomainValidation, TrialValidation
from app.services.data_store import REQUIRED_COLUMNS

def validate_domain(domain: str, df: pd.DataFrame) -> DomainValidation:
    missing = sorted(REQUIRED_COLUMNS[domain] - set(df.columns))
    return DomainValidation(domain=domain, valid=not missing, row_count=len(df), missing_columns=missing)

def validate_trial(frames: dict[str, pd.DataFrame]) -> TrialValidation:
    results = [validate_domain(d, frames[d]) for d in ["DM", "AE", "LB", "EX"]]
    return TrialValidation(valid=all(r.valid for r in results), domains=results)
