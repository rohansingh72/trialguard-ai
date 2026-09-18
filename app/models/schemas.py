from typing import Literal
from pydantic import BaseModel

Severity = Literal["low", "medium", "high"]

class Finding(BaseModel):
    rule_id: str
    subject_id: str
    domain: str
    severity: Severity
    title: str
    description: str
    evidence: dict

class SubjectReview(BaseModel):
    subject_id: str
    findings: list[Finding]
    finding_count: int

class DomainValidation(BaseModel):
    domain: str
    valid: bool
    row_count: int
    missing_columns: list[str]

class TrialValidation(BaseModel):
    valid: bool
    domains: list[DomainValidation]

class TrialSummary(BaseModel):
    subject_count: int
    finding_count: int
    subjects_with_findings: int
    findings_by_rule: dict[str, int]
    findings_by_domain: dict[str, int]
    findings_by_severity: dict[str, int]
    subject_summaries: list[SubjectReview]


class AgentInvestigationRequest(BaseModel):
    subject_id: str
    question: str = "Investigate this subject for possible data-quality issues."


class AgentInvestigationResponse(BaseModel):
    subject_id: str
    question: str
    answer: str
    tools_used: list[str]
