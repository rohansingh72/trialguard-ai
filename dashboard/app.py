from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.api_client import TrialGuardAPI, TrialGuardAPIError
from dashboard.utils import REVIEW_STATUSES, filter_records, flatten_review_records, review_metrics


st.set_page_config(
    page_title="TrialGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🛡️ TrialGuard AI")
st.caption("Clinical trial QC, human review, auditability, and guarded AI investigation")


@st.cache_data(ttl=10, show_spinner=False)
def get_studies(base_url: str):
    return TrialGuardAPI(base_url).studies()


@st.cache_data(ttl=5, show_spinner=False)
def get_summary(base_url: str, study_id: str):
    return TrialGuardAPI(base_url).summary(study_id)


@st.cache_data(ttl=5, show_spinner=False)
def get_findings(base_url: str, study_id: str):
    return TrialGuardAPI(base_url).findings(study_id)


@st.cache_data(ttl=10, show_spinner=False)
def get_subjects(base_url: str, study_id: str):
    return TrialGuardAPI(base_url).subjects(study_id)


with st.sidebar:
    st.header("Connection")
    api_url = st.text_input(
        "FastAPI URL",
        value=os.getenv("TRIALGUARD_API_URL", "http://127.0.0.1:8000"),
    ).rstrip("/")
    api = TrialGuardAPI(api_url)

    try:
        health = api.health()
        st.success(f"API online · v{health.get('version', '?')}")
    except TrialGuardAPIError as exc:
        st.error(str(exc))
        st.stop()

    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    studies = get_studies(api_url)
    if not studies:
        st.info("No studies yet.")
        demo_name = st.text_input("Demo study name", value="TrialGuard Demo Study")
        if st.button("Create demo study", use_container_width=True):
            try:
                with st.spinner("Creating demo study..."):
                    api.create_demo_study(demo_name)
                st.cache_data.clear()
                st.rerun()
            except TrialGuardAPIError as exc:
                st.error(str(exc))
        st.stop()

    study_labels = {
        f"{s['name']} · {s['study_id']}": s["study_id"]
        for s in studies
    }
    selected_label = st.selectbox("Study", list(study_labels))
    study_id = study_labels[selected_label]

    if st.button("Sync deterministic findings", use_container_width=True):
        try:
            result = api.sync_findings(study_id)
            st.success(f"Review queue synced: {result['created']} new, {result['total']} total")
            st.cache_data.clear()
        except TrialGuardAPIError as exc:
            st.error(str(exc))

try:
    summary = get_summary(api_url, study_id)
    records = get_findings(api_url, study_id)
except TrialGuardAPIError as exc:
    st.error(str(exc))
    st.stop()

metrics = review_metrics(records)

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Subjects", summary.get("subject_count", 0))
k2.metric("QC findings", summary.get("finding_count", 0))
k3.metric("Pending review", metrics["pending"])
k4.metric("Needs follow-up", metrics["needs_followup"])
k5.metric("Approved", metrics["approved"])

review_tab, agent_tab, overview_tab = st.tabs(
    ["Review Queue", "AI Investigation", "Study Overview"]
)

with review_tab:
    st.subheader("Human review queue")

    if not records:
        st.info("No review records yet. Use **Sync deterministic findings** in the sidebar.")
    else:
        domains = sorted({r["finding"]["domain"] for r in records})
        subjects_all = sorted({r["finding"]["subject_id"] for r in records})

        f1, f2, f3, f4 = st.columns(4)
        with f1:
            status_filter = st.multiselect("Status", REVIEW_STATUSES, default=REVIEW_STATUSES)
        with f2:
            severity_filter = st.multiselect(
                "Severity", ["high", "medium", "low"], default=["high", "medium", "low"]
            )
        with f3:
            domain_filter = st.multiselect("Domain", domains, default=domains)
        with f4:
            subject_filter = st.multiselect("Subject", subjects_all, default=subjects_all)

        filtered = filter_records(
            records,
            statuses=set(status_filter),
            severities=set(severity_filter),
            domains=set(domain_filter),
            subjects=set(subject_filter),
        )
        flat = flatten_review_records(filtered)

        if not flat:
            st.warning("No findings match the current filters.")
        else:
            st.dataframe(
                pd.DataFrame(flat)[
                    [
                        "severity",
                        "subject_id",
                        "domain",
                        "rule_id",
                        "title",
                        "status",
                        "reviewer",
                        "updated_at",
                    ]
                ],
                hide_index=True,
                use_container_width=True,
            )

            label_to_id = {
                f"[{row['severity'].upper()}] {row['subject_id']} · {row['rule_id']} · {row['title']}": row["finding_id"]
                for row in flat
            }
            selected_finding_label = st.selectbox("Open finding", list(label_to_id))
            finding_id = label_to_id[selected_finding_label]
            record = next(r for r in records if r["finding_id"] == finding_id)
            finding = record["finding"]

            left, right = st.columns([3, 2])
            with left:
                st.markdown(f"### {finding['rule_id']} · {finding['title']}")
                st.write(finding["description"])
                st.markdown(
                    f"**Subject:** `{finding['subject_id']}`  ·  "
                    f"**Domain:** `{finding['domain']}`  ·  "
                    f"**Severity:** `{finding['severity']}`"
                )
                st.markdown("**Deterministic evidence**")
                st.json(finding.get("evidence", {}), expanded=True)

            with right:
                st.markdown("### Review decision")
                reviewer_default = record.get("reviewer") or st.session_state.get("reviewer_name", "")
                reviewer = st.text_input("Reviewer", value=reviewer_default, key=f"reviewer_{finding_id}")
                if reviewer:
                    st.session_state["reviewer_name"] = reviewer

                current_status = record.get("status", "pending")
                status = st.selectbox(
                    "Status",
                    REVIEW_STATUSES,
                    index=REVIEW_STATUSES.index(current_status),
                    key=f"status_{finding_id}",
                )
                note = st.text_area(
                    "Reviewer note",
                    value=record.get("note") or "",
                    key=f"note_{finding_id}",
                    height=120,
                )

                if st.button("Save review decision", type="primary", use_container_width=True):
                    if not reviewer.strip():
                        st.error("Reviewer name is required.")
                    else:
                        try:
                            api.update_finding(
                                study_id,
                                finding_id,
                                status=status,
                                reviewer=reviewer.strip(),
                                note=note.strip() or None,
                            )
                            st.cache_data.clear()
                            st.success("Review decision saved.")
                            st.rerun()
                        except TrialGuardAPIError as exc:
                            st.error(str(exc))

            st.markdown("### Audit history")
            try:
                audit = api.audit(study_id, finding_id)
                audit_rows = []
                for event in audit:
                    audit_rows.append(
                        {
                            "timestamp": event.get("timestamp"),
                            "event": event.get("event_type"),
                            "previous": event.get("previous_status"),
                            "new": event.get("new_status"),
                            "reviewer": event.get("reviewer"),
                            "note": event.get("note"),
                        }
                    )
                st.dataframe(pd.DataFrame(audit_rows), hide_index=True, use_container_width=True)
            except TrialGuardAPIError as exc:
                st.error(str(exc))

with agent_tab:
    st.subheader("Guarded AI investigation")
    st.caption(
        "Broad investigations force deterministic QC coverage. Targeted questions allow selective tool routing."
    )
    try:
        subjects = get_subjects(api_url, study_id)
    except TrialGuardAPIError as exc:
        st.error(str(exc))
        subjects = []

    if subjects:
        subject_id = st.selectbox("Subject", subjects, key="agent_subject")
        question = st.text_area(
            "Investigation question",
            value="Investigate this subject for possible data-quality issues.",
            height=100,
        )
        if st.button("Run investigation", type="primary"):
            try:
                with st.spinner("Running guarded investigation..."):
                    result = api.investigate(study_id, subject_id, question)
                st.markdown("### Agent answer")
                st.write(result.get("answer", ""))
                tools_used = result.get("tools_used", [])
                st.markdown("**Tools used:** " + (", ".join(f"`{t}`" for t in tools_used) or "None"))
            except TrialGuardAPIError as exc:
                st.error(str(exc))

with overview_tab:
    st.subheader("Study overview")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Findings by severity")
        severity_data = summary.get("findings_by_severity", {})
        if severity_data:
            st.bar_chart(pd.DataFrame.from_dict(severity_data, orient="index", columns=["count"]))
        else:
            st.info("No QC findings.")
    with c2:
        st.markdown("#### Findings by domain")
        domain_data = summary.get("findings_by_domain", {})
        if domain_data:
            st.bar_chart(pd.DataFrame.from_dict(domain_data, orient="index", columns=["count"]))
        else:
            st.info("No QC findings.")

    st.markdown("#### Findings by rule")
    rule_data = summary.get("findings_by_rule", {})
    if rule_data:
        st.dataframe(
            pd.DataFrame(
                [{"rule_id": rule, "count": count} for rule, count in sorted(rule_data.items())]
            ),
            hide_index=True,
            use_container_width=True,
        )

    st.caption(f"Dashboard refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
