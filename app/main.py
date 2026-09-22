from io import BytesIO
import logging
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile

from app.agents.investigation import run_investigation
from app.config import Settings
from app.logging_config import configure_logging
from app.models.schemas import (
    AgentInvestigationRequest,
    AgentInvestigationResponse,
    AuditEvent,
    ReviewDecisionRequest,
    ReviewRecord,
    ReviewStatus,
    ReviewSyncResponse,
    StudyInfo,
    StudyListResponse,
    SubjectReview,
    TrialSummary,
    TrialValidation,
)
from app.services.persistent_review import PersistentHumanReviewStore
from app.services.review import review_subject, summarize_trial
from app.services.study_repository import StudyRepository
from app.services.validation import validate_trial

settings = Settings.from_env()
configure_logging(settings.log_level)
logger = logging.getLogger("trialguard.api")

app = FastAPI(
    title="TrialGuard AI",
    version="0.7.0",
    description=(
        "Multi-study clinical-trial QC with persistent review/audit state, "
        "guarded AI investigation, and reviewer dashboard support."
    ),
)

studies = StudyRepository(settings.data_dir)
reviews = PersistentHumanReviewStore(studies.db_path)
DEFAULT_DATA_FOLDER = Path("generated_data")


def _read_csv_upload(upload: UploadFile) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(upload.file.read()))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse {upload.filename} as CSV: {exc}",
        ) from exc


def _study_store_or_404(study_id: str):
    store = studies.load_store(study_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Study not found.")
    return store


@app.middleware("http")
async def request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.exception(
            "request_failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": duration_ms,
            },
        )
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/health")
def health():
    """Liveness check: the API process is running."""
    return {"status": "ok", "version": "0.7.0"}


@app.get("/ready")
def readiness():
    """Readiness check for core deterministic/persistent functionality."""
    checks = {"database": False, "data_dir": False}
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.data_dir / ".readiness-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks["data_dir"] = True

        with sqlite3.connect(studies.db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        checks["database"] = True
    except Exception as exc:
        logger.exception("readiness_failed")
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "checks": checks, "error": str(exc)},
        ) from exc

    return {
        "status": "ready",
        "version": "0.7.0",
        "checks": checks,
        "agent_dependency": {
            "type": "ollama",
            "base_url": settings.ollama_base_url,
            "required_for_core_readiness": False,
        },
    }


@app.get("/studies", response_model=StudyListResponse)
def list_studies():
    return StudyListResponse(studies=studies.list())


@app.get("/studies/{study_id}", response_model=StudyInfo)
def get_study(study_id: str):
    study = studies.get(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail="Study not found.")
    return study


@app.post("/studies/demo", response_model=StudyInfo)
def create_demo_study(name: str = "TrialGuard Demo Study"):
    if not DEFAULT_DATA_FOLDER.exists():
        raise HTTPException(
            status_code=400,
            detail="generated_data folder not found. Run: python synthetic_data/generate.py",
        )
    # Validate before persisting.
    from app.services.data_store import TrialDataStore

    temp = TrialDataStore()
    temp.load_from_folder(DEFAULT_DATA_FOLDER)
    validation = validate_trial(temp.frames())
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump())
    return studies.create_from_frames(
        name=name,
        dm=temp.dm,
        ae=temp.ae,
        lb=temp.lb,
        ex=temp.ex,
    )


@app.post("/studies/upload", response_model=StudyInfo)
def upload_study(
    name: str,
    dm: UploadFile = File(...),
    ae: UploadFile = File(...),
    lb: UploadFile = File(...),
    ex: UploadFile = File(...),
):
    frames = {
        "DM": _read_csv_upload(dm),
        "AE": _read_csv_upload(ae),
        "LB": _read_csv_upload(lb),
        "EX": _read_csv_upload(ex),
    }
    validation = validate_trial(frames)
    if not validation.valid:
        raise HTTPException(status_code=422, detail=validation.model_dump())
    return studies.create_from_frames(
        name=name,
        dm=frames["DM"],
        ae=frames["AE"],
        lb=frames["LB"],
        ex=frames["EX"],
    )


@app.get("/studies/{study_id}/validation", response_model=TrialValidation)
def study_validation(study_id: str):
    return validate_trial(_study_store_or_404(study_id).frames())


@app.get("/studies/{study_id}/subjects")
def study_subjects(study_id: str):
    return {"subjects": _study_store_or_404(study_id).all_subject_ids()}


@app.get(
    "/studies/{study_id}/subjects/{subject_id}/review",
    response_model=SubjectReview,
)
def get_subject_review(study_id: str, subject_id: str):
    store = _study_store_or_404(study_id)
    if subject_id not in set(store.all_subject_ids()):
        raise HTTPException(status_code=404, detail="Subject not found.")
    return review_subject(store, subject_id)


@app.get("/studies/{study_id}/summary", response_model=TrialSummary)
def get_trial_summary(study_id: str):
    return summarize_trial(_study_store_or_404(study_id))


@app.post(
    "/studies/{study_id}/agent/investigate",
    response_model=AgentInvestigationResponse,
)
def investigate_subject(study_id: str, request: AgentInvestigationRequest):
    store = _study_store_or_404(study_id)
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


@app.post(
    "/studies/{study_id}/human-review/sync",
    response_model=ReviewSyncResponse,
)
def sync_human_review_findings(study_id: str):
    store = _study_store_or_404(study_id)
    created, total = reviews.sync_from_trial(study_id, store)
    return ReviewSyncResponse(created=created, total=total)


@app.get(
    "/studies/{study_id}/human-review/findings",
    response_model=list[ReviewRecord],
)
def list_human_review_findings(
    study_id: str,
    status: ReviewStatus | None = None,
):
    if studies.get(study_id) is None:
        raise HTTPException(status_code=404, detail="Study not found.")
    return reviews.list_records(study_id, status=status)


@app.get(
    "/studies/{study_id}/human-review/findings/{finding_id}",
    response_model=ReviewRecord,
)
def get_human_review_finding(study_id: str, finding_id: str):
    if studies.get(study_id) is None:
        raise HTTPException(status_code=404, detail="Study not found.")
    record = reviews.get(study_id, finding_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Review finding not found.")
    return record


@app.patch(
    "/studies/{study_id}/human-review/findings/{finding_id}",
    response_model=ReviewRecord,
)
def update_human_review_finding(
    study_id: str,
    finding_id: str,
    request: ReviewDecisionRequest,
):
    if studies.get(study_id) is None:
        raise HTTPException(status_code=404, detail="Study not found.")
    reviewer = request.reviewer.strip()
    if not reviewer:
        raise HTTPException(status_code=422, detail="Reviewer is required.")
    record = reviews.update(
        study_id,
        finding_id,
        status=request.status,
        reviewer=reviewer,
        note=request.note,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Review finding not found.")
    return record


@app.get(
    "/studies/{study_id}/human-review/findings/{finding_id}/audit",
    response_model=list[AuditEvent],
)
def get_human_review_audit(study_id: str, finding_id: str):
    if studies.get(study_id) is None:
        raise HTTPException(status_code=404, detail="Study not found.")
    events = reviews.audit_events(study_id, finding_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Review finding not found.")
    return events
