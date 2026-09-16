from pathlib import Path
import subprocess
import sys

import pandas as pd

from app.services.data_store import TrialDataStore
from app.services.review import summarize_trial


def test_seeded_benchmark_is_detected(tmp_path: Path):
    out = tmp_path / "benchmark"

    subprocess.run(
        [
            sys.executable,
            "synthetic_data/generate_benchmark.py",
            "--subjects",
            "60",
            "--seed",
            "42",
            "--out",
            str(out),
        ],
        check=True,
    )

    store = TrialDataStore()
    store.load_from_folder(out)
    summary = summarize_trial(store)

    predicted = {
        (finding.subject_id, finding.rule_id)
        for review in summary.subject_summaries
        for finding in review.findings
    }

    gt_df = pd.read_csv(out / "ground_truth.csv")
    truth = {
        (str(row.subject_id), str(row.rule_id))
        for row in gt_df.itertuples(index=False)
    }

    assert truth.issubset(predicted)
