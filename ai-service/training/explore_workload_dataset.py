import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_demo.csv"
)


def explore_dataset():

    print("\nRefHealth AI")
    print("HOSPITAL WORKLOAD DATASET EXPLORATION")
    print("=" * 55)

    df = pd.read_csv(DATASET_PATH)

    print("\nDATASET SHAPE:", df.shape)

    print("\nFIRST FIVE RECORDS:")
    print(df.head())

    print("\nDATA TYPES:")
    print(df.dtypes)

    print("\nMISSING VALUES:")
    print(df.isnull().sum())

    print("\nUNIQUE HOSPITALS:")
    print(df["hospital_id"].nunique())

    print("\nRECORDS PER HOSPITAL:")
    
    print(df.groupby("hospital_id").size())

    print("\nWORKLOAD DISTRIBUTION:")
    print("\nWORKLOAD DISTRIBUTION BY HOSPITAL:")

    print(
        pd.crosstab(
            df["hospital_id"],
            df["workload_level"]
        )
    )
    print(df["workload_level"].value_counts())

    print("\nNUMERICAL STATISTICS:")
    print(
        df[
            [
                "patient_volume",
                "incoming_referrals",
                "pending_referrals",
                "available_beds",
                "total_beds"
            ]
        ].describe().round(2)
    )

    print("\nDATASET EXPLORATION COMPLETED.")


if __name__ == "__main__":
    explore_dataset()