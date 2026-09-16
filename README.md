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
