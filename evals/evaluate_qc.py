from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from app.services.data_store import TrialDataStore
from app.services.review import summarize_trial


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="benchmark_data")
    args = parser.parse_args()

    data_dir = Path(args.data)

    store = TrialDataStore()
    store.load_from_folder(data_dir)

    summary = summarize_trial(store)

    predicted = {
        (finding.subject_id, finding.rule_id)
        for review in summary.subject_summaries
        for finding in review.findings
    }

    gt_df = pd.read_csv(data_dir / "ground_truth.csv")
    truth = {
        (str(row.subject_id), str(row.rule_id))
        for row in gt_df.itertuples(index=False)
    }

    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    print("TrialGuard QC Benchmark")
    print("=======================")
    print(f"Ground-truth anomalies: {len(truth)}")
    print(f"Predicted anomalies:    {len(predicted)}")
    print(f"True positives:         {tp}")
    print(f"False positives:        {fp}")
    print(f"False negatives:        {fn}")
    print(f"Precision:              {precision:.3f}")
    print(f"Recall:                 {recall:.3f}")
    print(f"F1:                     {f1:.3f}")

    if fp:
        print("\nFalse positives:")
        for item in sorted(predicted - truth):
            print(" -", item)

    if fn:
        print("\nFalse negatives:")
        for item in sorted(truth - predicted):
            print(" -", item)


if __name__ == "__main__":
    main()
