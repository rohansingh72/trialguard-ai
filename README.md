# TrialGuard AI — Milestone 1.1

This version adds real CSV upload, schema validation, subject-level review, and trial-level QC summaries.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python synthetic_data/generate.py
pytest
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## New endpoints

- `POST /upload-trial`
- `GET /trial/validation`
- `GET /trial/summary`
- `GET /subjects/{subject_id}/review`

`POST /upload-trial` accepts four CSV files: `dm`, `ae`, `lb`, and `ex`.

## Expected demo summary

The seeded demo trial contains 3 subjects and 5 total findings: one each for AE001, AE002, LB001, EX001, and DM001.


---

# Milestone 1.2 — Benchmarking

This milestone adds a reproducible synthetic benchmark with known seeded anomalies.

Generate a benchmark:

```bash
python synthetic_data/generate_benchmark.py --subjects 200 --seed 42
```

This creates:

```text
benchmark_data/
├── DM.csv
├── AE.csv
├── LB.csv
├── EX.csv
├── ground_truth.csv
└── metadata.json
```

Evaluate the QC engine:

```bash
python evals/evaluate_qc.py --data benchmark_data
```

The evaluator compares predicted `(subject_id, rule_id)` pairs against the seeded ground truth and reports:

- true positives
- false positives
- false negatives
- precision
- recall
- F1

Run the full test suite with:

```bash
python -m pytest
```

This benchmark becomes the baseline we will use later to test whether the agent/LLM layer improves investigation quality without increasing hallucinations or false positives.

---

# Milestone 2.0 — LangGraph Investigation Agent

TrialGuard now adds a read-only LangGraph investigation layer over the deterministic QC engine.

The LLM does **not** replace QC logic. It chooses which deterministic tools to call and explains the evidence those tools return.

```text
User question
     |
     v
LangGraph agent (Ollama)
     |
     +--> Subject overview
     +--> AE QC
     +--> Lab QC
     +--> Exposure QC
     +--> Demographic QC
     |
     v
Evidence-grounded explanation
     |
     v
Human review
```

## Local model

The default model is:

```text
llama3.2:3b
```

Confirm Ollama is running and the model is installed:

```bash
ollama pull llama3.2:3b
ollama list
```

Optional environment variables:

```bash
export TRIALGUARD_OLLAMA_MODEL=llama3.2:3b
export TRIALGUARD_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

## Install updated dependencies

```bash
pip install -r requirements.txt
```

## Tests

```bash
python -m pytest
```

The deterministic benchmark remains separate from the LLM layer.

## Agent smoke test

First generate/load demo data if needed:

```bash
python synthetic_data/generate.py
python scripts_agent_smoke.py
```

## FastAPI

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Run `POST /load-demo-data`, then call:

```text
POST /agent/investigate
```

Example body:

```json
{
  "subject_id": "TG-001",
  "question": "Investigate this subject for possible data-quality issues."
}
```

The response contains both the final explanation and `tools_used`, which gives us a simple audit trail of the agent's decisions.

## Safety boundary

The agent is read-only. It cannot modify the trial datasets. Deterministic QC remains the source of factual anomaly detection, while the LLM is limited to orchestration and explanation.

## Agent guardrail update

Broad subject investigations now force coverage of every implemented deterministic QC domain before the LLM writes a summary. Narrow questions still use model-directed tool selection.

Raw subject rows are no longer supplied to the LLM for free-form interpretation during broad QC. The LLM receives deterministic finding objects plus record counts, which prevents unsupported reinterpretation of laboratory codes or values.

Expected broad smoke-test tool coverage:

```text
get_subject_overview
review_adverse_events
review_labs
review_exposure
review_demographics
```

---

# Milestone 3 — Human Review and Audit Trail

Milestone 3 adds a human-in-the-loop review workflow on top of deterministic QC and the guarded LangGraph investigation agent.

## Design principle

Clinical source data remain read-only. A reviewer changes only the status of a QC finding; DM, AE, LB, and EX are never silently edited by this workflow.

## Review statuses

- `pending`
- `approved`
- `rejected`
- `needs_followup`

## New endpoints

- `POST /human-review/sync` — snapshot current deterministic QC findings into the review queue.
- `GET /human-review/findings` — list review records; optionally filter with `?status=pending`.
- `GET /human-review/findings/{finding_id}` — retrieve one review record.
- `PATCH /human-review/findings/{finding_id}` — update status, reviewer, and note.
- `GET /human-review/findings/{finding_id}/audit` — retrieve the append-only audit events for the finding.

## Demo flow

```bash
python synthetic_data/generate.py
uvicorn app.main:app --reload
```

In Swagger:

1. `POST /load-demo-data`
2. `POST /human-review/sync`
3. `GET /human-review/findings`
4. Copy a `finding_id`
5. `PATCH /human-review/findings/{finding_id}` with:

```json
{
  "status": "needs_followup",
  "reviewer": "Rohan",
  "note": "Verify against source before closing."
}
```

6. `GET /human-review/findings/{finding_id}/audit`

The audit endpoint should show the original `created` event plus the subsequent `review_updated` event.

## Local smoke test

```bash
python synthetic_data/generate.py
python scripts_human_review_smoke.py
```

## Important limitation

Review state is still in memory in Milestone 3. Restarting the API clears it. Milestone 4 will move trial metadata, review records, and audit events into a persistent database and add study-level separation.

---

# Milestone 4 — Persistent multi-study storage

Milestone 4 removes the single global in-memory study limitation.

## What changed

- SQLite-backed study registry.
- Study-scoped persisted source datasets under `.trialguard/studies/<study_id>/`.
- Review decisions persist across API restarts.
- Audit events persist across API restarts.
- Every QC/review route is explicitly scoped to a `study_id`.
- Identical findings in different studies receive different finding IDs.
- `.trialguard/` is ignored by Git.

Clinical source CSVs remain immutable snapshots. SQLite stores study metadata and workflow state; reviewer decisions never silently modify DM/AE/LB/EX.

## New API flow

```text
POST /studies/demo
        ↓
returns STUDY-XXXXXXXX
        ↓
GET /studies/{study_id}/subjects
GET /studies/{study_id}/summary
POST /studies/{study_id}/human-review/sync
PATCH /studies/{study_id}/human-review/findings/{finding_id}
        ↓
restart FastAPI
        ↓
review state is still present
```

You can also create a study from four uploaded CSVs with `POST /studies/upload`.

## Local run

```bash
python synthetic_data/generate.py
python -m pytest
python scripts_persistence_smoke.py
uvicorn app.main:app --reload
```

The default persistent data directory is `.trialguard/`. To put it elsewhere:

```bash
export TRIALGUARD_DATA_DIR=/path/to/trialguard-data
```

## Swagger smoke test

1. `POST /studies/demo`
2. Copy the returned `study_id`.
3. `GET /studies`
4. `GET /studies/{study_id}/subjects`
5. `POST /studies/{study_id}/human-review/sync`
6. `GET /studies/{study_id}/human-review/findings`
7. Update one finding.
8. Stop and restart Uvicorn.
9. Repeat `GET /studies` and the finding endpoint. The study and review decision should still exist.

## Architecture

```text
                    ┌───────────────────────┐
CSV upload/demo ───►│ Study Repository      │
                    │ SQLite study metadata │
                    └──────────┬────────────┘
                               │
                               ▼
                 .trialguard/studies/STUDY-*/
                      DM / AE / LB / EX
                               │
                               ▼
                    Deterministic QC engine
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
             Guarded agent          Persistent review
                                    + audit in SQLite
```

## Next milestone

Milestone 5 adds a reviewer-facing web dashboard over these study-scoped APIs.
