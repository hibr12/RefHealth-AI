"""Audit stored V6 features against raw history; never regenerates the datasets."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import pandas as pd
from corecare.config import ROOT
from corecare.features import FEATURES, TARGET, build_features, chronological_split


def audit(raw_path=None, processed_path=None):
    raw_path = Path(raw_path or ROOT / "datasets/raw/hospital_daily_history_v6.csv")
    processed_path = Path(processed_path or ROOT / "datasets/processed/workload_v6_features.csv")
    with processed_path.open(newline="", encoding="utf-8") as file:
        header = next(csv.reader(file))
    if len(header) != len(set(header)):
        raise ValueError("Duplicate CSV column names.")
    if len(FEATURES) != len(set(FEATURES)) or set(FEATURES) & {TARGET, "record_id", "record_date", "target_date"}:
        raise ValueError("Invalid feature whitelist.")
    raw = pd.read_csv(raw_path)
    expected = build_features(raw).sort_values(["hospital_id", "record_date"]).reset_index(drop=True)
    stored = pd.read_csv(processed_path, parse_dates=["record_date", "target_date"])
    stored = stored.sort_values(["hospital_id", "record_date"]).reset_index(drop=True)
    columns = ["record_id", "record_date", "target_date", *FEATURES, TARGET]
    pd.testing.assert_frame_equal(stored[columns], expected[columns], check_dtype=False, atol=1e-9, rtol=1e-9)
    # Independent per-row windows and tomorrow lookup check the shared implementation.
    for hospital, history in raw.groupby("hospital_id"):
        history = history.sort_values("record_date").reset_index(drop=True)
        rows = stored[stored.hospital_id == hospital]
        lookup = {d: i for i, d in enumerate(history.record_date)}
        for _, row in rows.iterrows():
            index = lookup[row.record_date.strftime("%Y-%m-%d")]
            if row[TARGET] != history.iloc[index+1].workload_level:
                raise ValueError("Target is not tomorrow's workload.")
            for column in ["patient_volume", "pending_referrals", "incoming_referrals", "available_beds"]:
                if row[f"previous_{column}"] != history.iloc[index-1][column]:
                    raise ValueError("Lag mismatch.")
                for days in (3, 7):
                    if abs(row[f"average_{days}day_{column}"] - history.iloc[index-days+1:index+1][column].mean()) > 1e-8:
                        raise ValueError("Rolling window mismatch.")
    # Changing future operations and labels must leave every earlier input unchanged.
    cutoff = "2026-05-01"
    altered = raw.copy()
    future = altered.record_date > cutoff
    altered.loc[future, "patient_volume"] += 1000
    altered.loc[future, "workload_level"] = "High"
    altered_features = build_features(altered, training=False)
    original_features = build_features(raw, training=False)
    left = original_features[original_features.record_date <= cutoff][FEATURES]
    right = altered_features[altered_features.record_date <= cutoff][FEATURES]
    pd.testing.assert_frame_equal(left, right)
    # Other hospitals cannot affect the first hospital's history.
    first = sorted(raw.hospital_id.unique())[0]
    alone = build_features(raw[raw.hospital_id == first])
    pd.testing.assert_frame_equal(expected[expected.hospital_id == first][FEATURES].reset_index(drop=True), alone[FEATURES])
    shuffled = build_features(raw.sample(frac=1, random_state=17))
    pd.testing.assert_frame_equal(expected[FEATURES], shuffled[FEATURES])
    train, validation, excluded = chronological_split(stored, "2026-08-24")
    return {"status": "passed", "scope": "synthetic V6 feature integrity and temporal leakage",
            "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "features_sha256": hashlib.sha256(processed_path.read_bytes()).hexdigest(),
            "features": FEATURES, "feature_count": len(FEATURES), "rows": len(stored),
            "checks": ["stored/raw agreement", "independent next-day targets and windows", "future perturbation",
                       "hospital isolation", "input sorting", "feature whitelist", "chronological embargo"],
            "split": {name: {"rows": len(data), "record_start": str(data.record_date.min().date()),
                              "record_end": str(data.record_date.max().date()),
                              "target_end": str(data.target_date.max().date()),
                              "classes": data[TARGET].value_counts().to_dict()}
                      for name, data in [("training", train), ("validation", validation), ("excluded", excluded)]},
            "prediction_cutoff": "After the complete record_date observations are finalized.",
            "limitations": ["Synthetic data only", "Hospital identity retained for known-hospital prediction",
                            "H004 has no High examples", "No clinical validation"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
