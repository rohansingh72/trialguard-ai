from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd


def generate_subject_ids(n: int) -> list[str]:
    return [f"TG-{i:04d}" for i in range(1, n + 1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subjects", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="benchmark_data")
    args = parser.parse_args()

    random.seed(args.seed)
    out = Path(args.out)
    out.mkdir(exist_ok=True)

    subjects = generate_subject_ids(args.subjects)

    dm_rows = []
    ae_rows = []
    lb_rows = []
    ex_rows = []
    ground_truth = []

    for i, sid in enumerate(subjects, start=1):
        consent = pd.Timestamp("2026-01-05") + pd.Timedelta(days=i % 10)
        birth = pd.Timestamp("1985-01-01") + pd.Timedelta(days=(i * 37) % 8000)

        discontinued = (i % 7 == 0)
        disc_date = consent + pd.Timedelta(days=20) if discontinued else pd.NaT

        dm_rows.append({
            "USUBJID": sid,
            "SEX": "M" if i % 2 else "F",
            "BRTHDTC": birth.date().isoformat(),
            "RFICDTC": consent.date().isoformat(),
            "DMDISDTC": "" if pd.isna(disc_date) else disc_date.date().isoformat(),
        })

        first_dose = consent + pd.Timedelta(days=2)
        ex_rows.append({
            "USUBJID": sid,
            "EXSTDTC": first_dose.date().isoformat(),
            "EXDOSE": 100,
        })

        # Normal AE
        if i % 3 == 0:
            ae_rows.append({
                "USUBJID": sid,
                "AEDECOD": "Headache",
                "AESTDTC": (first_dose + pd.Timedelta(days=3)).date().isoformat(),
                "AEENDTC": (first_dose + pd.Timedelta(days=4)).date().isoformat(),
                "AETRTEMFL": "Y",
            })

        # Normal potassium
        lb_rows.append({
            "USUBJID": sid,
            "LBTESTCD": "K",
            "LBSTRESN": 4.0,
            "LBSTRESU": "mmol/L",
            "LBDTC": (first_dose + pd.Timedelta(days=5)).date().isoformat(),
        })

    # Deterministically seed five anomaly types.
    anomaly_groups = {
        "AE001": subjects[0:10],
        "EX001": subjects[10:20],
        "LB001": subjects[20:30],
        "AE002": subjects[30:40],
        "DM001": subjects[40:50],
    }

    # AE001: treatment-emergent AE before first dose
    for sid in anomaly_groups["AE001"]:
        consent = pd.to_datetime(next(r["RFICDTC"] for r in dm_rows if r["USUBJID"] == sid))
        first_dose = consent + pd.Timedelta(days=2)
        ae_rows.append({
            "USUBJID": sid,
            "AEDECOD": "Dizziness",
            "AESTDTC": (first_dose - pd.Timedelta(days=1)).date().isoformat(),
            "AEENDTC": first_dose.date().isoformat(),
            "AETRTEMFL": "Y",
        })
        ground_truth.append({"subject_id": sid, "rule_id": "AE001"})

    # EX001: exposure after discontinuation
    for sid in anomaly_groups["EX001"]:
        dm = next(r for r in dm_rows if r["USUBJID"] == sid)
        disc = pd.to_datetime(dm["RFICDTC"]) + pd.Timedelta(days=10)
        dm["DMDISDTC"] = disc.date().isoformat()
        ex_rows.append({
            "USUBJID": sid,
            "EXSTDTC": (disc + pd.Timedelta(days=2)).date().isoformat(),
            "EXDOSE": 100,
        })
        ground_truth.append({"subject_id": sid, "rule_id": "EX001"})

    # LB001: low potassium without corresponding AE
    for sid in anomaly_groups["LB001"]:
        lb_rows.append({
            "USUBJID": sid,
            "LBTESTCD": "K",
            "LBSTRESN": 2.7,
            "LBSTRESU": "mmol/L",
            "LBDTC": "2026-02-01",
        })
        ground_truth.append({"subject_id": sid, "rule_id": "LB001"})

    # AE002: duplicate AE
    for sid in anomaly_groups["AE002"]:
        row = {
            "USUBJID": sid,
            "AEDECOD": "Nausea",
            "AESTDTC": "2026-02-02",
            "AEENDTC": "2026-02-03",
            "AETRTEMFL": "Y",
        }
        ae_rows.append(row.copy())
        ae_rows.append(row.copy())
        ground_truth.append({"subject_id": sid, "rule_id": "AE002"})

    # DM001: birth after consent
    for sid in anomaly_groups["DM001"]:
        dm = next(r for r in dm_rows if r["USUBJID"] == sid)
        consent = pd.to_datetime(dm["RFICDTC"])
        dm["BRTHDTC"] = (consent + pd.Timedelta(days=30)).date().isoformat()
        ground_truth.append({"subject_id": sid, "rule_id": "DM001"})

    pd.DataFrame(dm_rows).to_csv(out / "DM.csv", index=False)
    pd.DataFrame(ae_rows).to_csv(out / "AE.csv", index=False)
    pd.DataFrame(lb_rows).to_csv(out / "LB.csv", index=False)
    pd.DataFrame(ex_rows).to_csv(out / "EX.csv", index=False)

    pd.DataFrame(ground_truth).to_csv(out / "ground_truth.csv", index=False)

    metadata = {
        "subjects": args.subjects,
        "seed": args.seed,
        "seeded_anomalies": len(ground_truth),
        "counts_by_rule": {
            rule: sum(1 for x in ground_truth if x["rule_id"] == rule)
            for rule in sorted(set(x["rule_id"] for x in ground_truth))
        },
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote benchmark to {out.resolve()}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
