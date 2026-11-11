"""Prepare V6 features using the same implementation used during inference."""
import pandas as pd
from corecare.config import ROOT
from corecare.features import build_features

INPUT_FILE = ROOT / "datasets/raw/hospital_daily_history_v6.csv"
OUTPUT_FILE = ROOT / "datasets/processed/workload_v6_features.csv"


def prepare_dataset(output=OUTPUT_FILE):
    data = build_features(pd.read_csv(INPUT_FILE))
    output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output, index=False)
    print(f"Saved {data.shape} to {output}")
    return data


if __name__ == "__main__":
    prepare_dataset()
