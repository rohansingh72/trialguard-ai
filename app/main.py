from io import BytesIO
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from app.models.schemas import (
    AgentInvestigationRequest,
    AgentInvestigationResponse,
    SubjectReview,
    TrialSummary,
    TrialValidation,
    AuditEvent,
    ReviewDecisionRequest,
    ReviewRecord,
    ReviewStatus,
    ReviewSyncResponse,
)
from app.agents.investigation import run_investigation
from app.services.data_store import TrialDataStore
from app.services.review import review_subject, summarize_trial
from app.services.human_review import HumanReviewStore
from app.services.validation import validate_trial

app = FastAPI(title="TrialGuard AI", version="0.4.0", description="Clinical-trial QC, guarded AI investigation, and human-review audit workflow.")
store = TrialDataStore()
human_review_store = HumanReviewStore()
DEFAULT_DATA_FOLDER = Path("generated_data")

def _read_csv_upload(upload: UploadFile) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(upload.file.read()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse {upload.filename} as CSV: {exc}") from exc

@app.get("/health")
def health(): return {"status":"ok","version":"0.4.0"}

@app.post("/load-demo-data", response_model=TrialValidation)
def load_demo_data():
    if not DEFAULT_DATA_FOLDER.exists():
        raise HTTPException(status_code=400, detail="generated_data folder not found. Run: python synthetic_data/generate.py")
    store.load_from_folder(DEFAULT_DATA_FOLDER)
    human_review_store.reset()
    validation=validate_trial(store.frames())
    if not validation.valid: raise HTTPException(status_code=422, detail=validation.model_dump())
    return validation

@app.post("/upload-trial", response_model=TrialValidation)
def upload_trial(dm: UploadFile=File(...), ae: UploadFile=File(...), lb: UploadFile=File(...), ex: UploadFile=File(...)):
    frames={"DM":_read_csv_upload(dm),"AE":_read_csv_upload(ae),"LB":_read_csv_upload(lb),"EX":_read_csv_upload(ex)}
    validation=validate_trial(frames)
    if not validation.valid: raise HTTPException(status_code=422, detail=validation.model_dump())
    store.load_frames(frames["DM"],frames["AE"],frames["LB"],frames["EX"])
    human_review_store.reset()
    return validation

@app.get("/trial/validation", response_model=TrialValidation)
def trial_validation():
    if not store.loaded(): raise HTTPException(status_code=400, detail="No trial data loaded.")
    return validate_trial(store.frames())

@app.get("/subjects")
def subjects():
    if not store.loaded(): raise HTTPException(status_code=400, detail="No trial data loaded.")
    return {"subjects": store.all_subject_ids()}

@app.get("/subjects/{subject_id}/review", response_model=SubjectReview)
def get_subject_review(subject_id: str):
    if not store.loaded(): raise HTTPException(status_code=400, detail="No trial data loaded.")
    if subject_id not in set(store.all_subject_ids()): raise HTTPException(status_code=404, detail="Subject not found.")
    return review_subject(store, subject_id)

@app.get("/trial/summary", response_model=TrialSummary)
def get_trial_summary():
    if not store.loaded(): raise HTTPException(status_code=400, detail="No trial data loaded.")
    return summarize_trial(store)


@app.post("/agent/investigate", response_model=AgentInvestigationResponse)
def investigate_subject(request: AgentInvestigationRequest):
    if not store.loaded():
        raise HTTPException(status_code=400, detail="No trial data loaded.")

    if request.subject_id not in set(store.all_subject_ids()):
        raise HTTPException(status_code=404, detail="Subject not found.")

    try:
        return run_investigation(
            store=store,
            subject_id=request.subject_id,
            question=request.question,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Agent investigation failed. Confirm that Ollama is running and "
                "that TRIALGUARD_OLLAMA_MODEL is installed. "
                f"Underlying error: {exc}"
            ),
        ) from exc

@app.post("/human-review/sync", response_model=ReviewSyncResponse)
def sync_human_review_findings():
    if not store.loaded():
        raise HTTPException(status_code=400, detail="No trial data loaded.")
    created, total = human_review_store.sync_from_trial(store)
    return ReviewSyncResponse(created=created, total=total)


@app.get("/human-review/findings", response_model=list[ReviewRecord])
def list_human_review_findings(status: ReviewStatus | None = None):
    return human_review_store.list_records(status=status)


@app.get("/human-review/findings/{finding_id}", response_model=ReviewRecord)
def get_human_review_finding(finding_id: str):
    record = human_review_store.get(finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Review finding not found.")
    return record


@app.patch("/human-review/findings/{finding_id}", response_model=ReviewRecord)
def update_human_review_finding(finding_id: str, request: ReviewDecisionRequest):
    reviewer = request.reviewer.strip()
    if not reviewer:
        raise HTTPException(status_code=422, detail="Reviewer is required.")
    record = human_review_store.update(
        finding_id,
        status=request.status,
        reviewer=reviewer,
        note=request.note,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Review finding not found.")
    return record


@app.get("/human-review/findings/{finding_id}/audit", response_model=list[AuditEvent])
def get_human_review_audit(finding_id: str):
    events = human_review_store.audit_events(finding_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Review finding not found.")
    return events

