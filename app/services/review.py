from collections import Counter
from app.models.schemas import SubjectReview, TrialSummary
from app.tools.qc import run_subject_qc

def review_subject(store, subject_id: str) -> SubjectReview:
    findings = run_subject_qc(store.dm, store.ae, store.lb, store.ex, subject_id)
    return SubjectReview(subject_id=subject_id, findings=findings, finding_count=len(findings))

def summarize_trial(store) -> TrialSummary:
    reviews=[review_subject(store, sid) for sid in store.all_subject_ids()]
    findings=[f for r in reviews for f in r.findings]
    return TrialSummary(subject_count=len(reviews), finding_count=len(findings), subjects_with_findings=sum(r.finding_count>0 for r in reviews), findings_by_rule=dict(Counter(f.rule_id for f in findings)), findings_by_domain=dict(Counter(f.domain for f in findings)), findings_by_severity=dict(Counter(f.severity for f in findings)), subject_summaries=reviews)
