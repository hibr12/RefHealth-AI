import json
import pandas as pd
from corecare.config import ROOT
from corecare.storage import initialize
from training.audit_workload_v6_features import audit
from training.experiments import train_temporal


def main():
    initialize()
    audit()
    result = train_temporal(pd.read_csv(ROOT / "datasets/raw/hospital_daily_history_v6.csv"), "workload")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
