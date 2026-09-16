from io import BytesIO
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from app.models.schemas import SubjectReview, TrialSummary, TrialValidation
from app.services.data_store import TrialDataStore
from app.services.review import review_subject, summarize_trial
from app.services.validation import validate_trial

app = FastAPI(title="TrialGuard AI", version="0.2.0", description="Clinical-trial data quality review API with upload, schema validation, and deterministic QC.")
store = TrialDataStore(); DEFAULT_DATA_FOLDER = Path("generated_data")

def _read_csv_upload(upload: UploadFile) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(upload.file.read()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse {upload.filename} as CSV: {exc}") from exc

@app.get("/health")
def health(): return {"status":"ok","version":"0.2.0"}

@app.post("/load-demo-data", response_model=TrialValidation)
def load_demo_data():
    if not DEFAULT_DATA_FOLDER.exists():
        raise HTTPException(status_code=400, detail="generated_data folder not found. Run: python synthetic_data/generate.py")
    store.load_from_folder(DEFAULT_DATA_FOLDER)
    validation=validate_trial(store.frames())
    if not validation.valid: raise HTTPException(status_code=422, detail=validation.model_dump())
    return validation

@app.post("/upload-trial", response_model=TrialValidation)
def upload_trial(dm: UploadFile=File(...), ae: UploadFile=File(...), lb: UploadFile=File(...), ex: UploadFile=File(...)):
    frames={"DM":_read_csv_upload(dm),"AE":_read_csv_upload(ae),"LB":_read_csv_upload(lb),"EX":_read_csv_upload(ex)}
    validation=validate_trial(frames)
    if not validation.valid: raise HTTPException(status_code=422, detail=validation.model_dump())
    store.load_frames(frames["DM"],frames["AE"],frames["LB"],frames["EX"])
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
