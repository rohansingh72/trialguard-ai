from __future__ import annotations

from typing import Any

import pandas as pd
from langchain_core.tools import tool

from app.services.data_store import TrialDataStore
from app.tools.qc import (
    check_ae_before_first_dose,
    check_birth_after_consent,
    check_duplicate_ae,
    check_exposure_after_discontinuation,
    check_low_potassium_without_ae,
)


def _clean_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    clean = df.copy()
    clean = clean.where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


def _serialize_findings(findings) -> dict[str, Any]:
    return {
        "finding_count": len(findings),
        "findings": [finding.model_dump(mode="json") for finding in findings],
    }


def build_investigation_tools(store: TrialDataStore):
    """Build read-only investigation tools over the current in-memory trial."""

    @tool
    def get_subject_overview(subject_id: str) -> dict[str, Any]:
        """Return the available DM, AE, LB, and EX records for one subject. Use this for context, not for changing data."""
        return {
            "subject_id": subject_id,
            "DM": _clean_records(store.dm[store.dm["USUBJID"].astype(str) == str(subject_id)]) if not store.dm.empty else [],
            "AE": _clean_records(store.ae[store.ae["USUBJID"].astype(str) == str(subject_id)]) if not store.ae.empty else [],
            "LB": _clean_records(store.lb[store.lb["USUBJID"].astype(str) == str(subject_id)]) if not store.lb.empty else [],
            "EX": _clean_records(store.ex[store.ex["USUBJID"].astype(str) == str(subject_id)]) if not store.ex.empty else [],
        }

    @tool
    def review_adverse_events(subject_id: str) -> dict[str, Any]:
        """Run deterministic adverse-event QC for one subject, including treatment-emergent timing and duplicate AE checks."""
        findings = []
        findings.extend(check_ae_before_first_dose(store.ae, store.ex, subject_id))
        findings.extend(check_duplicate_ae(store.ae, subject_id))
        return _serialize_findings(findings)

    @tool
    def review_labs(subject_id: str) -> dict[str, Any]:
        """Run deterministic laboratory QC for one subject, currently including low-potassium review."""
        findings = check_low_potassium_without_ae(store.lb, store.ae, subject_id)
        return _serialize_findings(findings)

    @tool
    def review_exposure(subject_id: str) -> dict[str, Any]:
        """Run deterministic exposure QC for one subject, including dosing after discontinuation."""
        findings = check_exposure_after_discontinuation(store.dm, store.ex, subject_id)
        return _serialize_findings(findings)

    @tool
    def review_demographics(subject_id: str) -> dict[str, Any]:
        """Run deterministic demographic/date QC for one subject, including impossible birth/consent chronology."""
        findings = check_birth_after_consent(store.dm, subject_id)
        return _serialize_findings(findings)

    return [
        get_subject_overview,
        review_adverse_events,
        review_labs,
        review_exposure,
        review_demographics,
    ]
