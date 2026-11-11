import pandas as pd

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)


def inspect_split():

    print("\nRefHealth AI")
    print("CHRONOLOGICAL WORKLOAD DATASET SPLIT")
    print("=" * 55)

    df = pd.read_csv(DATASET_PATH)

    df["record_date"] = pd.to_datetime(
        df["record_date"]
    )

    dates = sorted(df["record_date"].unique())

    total_dates = len(dates)

    train_end = int(total_dates * 0.70)
    validation_end = int(total_dates * 0.85)

    train_dates = dates[:train_end]

    validation_dates = dates[
        train_end:validation_end
    ]

    test_dates = dates[validation_end:]

    train_df = df[
        df["record_date"].isin(train_dates)
    ]

    validation_df = df[
        df["record_date"].isin(validation_dates)
    ]

    test_df = df[
        df["record_date"].isin(test_dates)
    ]

    print("\nTOTAL UNIQUE DATES:", total_dates)

    for name, dataset in [
        ("TRAINING", train_df),
        ("VALIDATION", validation_df),
        ("TESTING", test_df)
    ]:

        print(f"\n{name} DATASET")

        print("Records:", len(dataset))
        print("First date:", dataset["record_date"].min().date())
        print("Last date:", dataset["record_date"].max().date())

        print("\nTarget distribution:")

        print(
            dataset["next_day_workload_level"]
            .value_counts()
        )

    print("\nCHRONOLOGICAL SPLIT INSPECTION COMPLETED.")


if __name__ == "__main__":
    inspect_split()