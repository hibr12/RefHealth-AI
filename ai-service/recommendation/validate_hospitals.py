import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = BASE_DIR / "datasets" / "raw" / "hospitals.csv"

REQUIRED_COLUMNS = [
    "hospital_id",
    "hospital_name",
    "distance_km",
    "service",
    "hospital_workload",
    "pending_referrals",
    "service_available",
    "available_beds"
]


def validate_hospital_dataset():

    print("\nRefHealth AI")
    print("HOSPITAL DATASET VALIDATION")
    print("=" * 50)

    if not DATASET_PATH.exists():
        print("ERROR: Hospital dataset not found.")
        return

    df = pd.read_csv(DATASET_PATH)

    print("\nTOTAL RECORDS:", len(df))
    print("TOTAL COLUMNS:", len(df.columns))

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        print("\nMISSING COLUMNS:", missing_columns)
        return

    print("\nREQUIRED COLUMNS: VALID")

    missing_values = df[REQUIRED_COLUMNS].isnull().sum()

    print("\nMISSING VALUES:")
    print(missing_values)

    valid_workloads = ["Low", "Medium", "High"]

    invalid_workloads = df[
        ~df["hospital_workload"].isin(valid_workloads)
    ]

    print("\nINVALID WORKLOAD RECORDS:", len(invalid_workloads))

    invalid_availability = df[
        ~df["service_available"].isin([0, 1])
    ]

    print("INVALID SERVICE AVAILABILITY:", len(invalid_availability))

    invalid_distances = df[df["distance_km"] < 0]

    print("INVALID DISTANCES:", len(invalid_distances))

    invalid_beds = df[df["available_beds"] < 0]

    print("INVALID BED COUNTS:", len(invalid_beds))

    print("\nHOSPITALS FOUND:")
    print(df["hospital_name"].unique())

    print("\nSERVICES FOUND:")
    print(df["service"].unique())

    print("\nDATASET VALIDATION COMPLETED.")


if __name__ == "__main__":
    validate_hospital_dataset()