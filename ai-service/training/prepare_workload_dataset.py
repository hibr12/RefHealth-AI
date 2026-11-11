import pandas as pd

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_demo.csv"
)

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)


def prepare_dataset():

    print("\nRefHealth AI")
    print("NEXT-DAY WORKLOAD DATASET PREPARATION")
    print("=" * 55)

    df = pd.read_csv(INPUT_PATH)

    # Convert dates
    df["record_date"] = pd.to_datetime(df["record_date"])

    # Sort records chronologically for each hospital
    df = df.sort_values(
        ["hospital_id", "record_date"]
    )

    # Create tomorrow's workload as the prediction target
    df["next_day_workload_level"] = (
        df.groupby("hospital_id")["workload_level"]
        .shift(-1)
    )

    # Remove records without a next-day target
    df = df.dropna(
        subset=["next_day_workload_level"]
    )

    # Save processed dataset
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print("\nORIGINAL RECORDS:", 450)
    print("PROCESSED RECORDS:", len(df))

    print("\nNEXT-DAY WORKLOAD DISTRIBUTION:")

    print(
        df["next_day_workload_level"].value_counts()
    )
    print("\nWORKLOAD TRANSITION MATRIX:")

    print(
    pd.crosstab(
        df["workload_level"],
        df["next_day_workload_level"],
        rownames=["Today's Workload"],
        colnames=["Tomorrow's Workload"]
         )
    )

    print("\nWORKLOAD TRANSITION PERCENTAGES:")

    transition_percentages = pd.crosstab(
    df["workload_level"],
    df["next_day_workload_level"],
    normalize="index"
    ) * 100

    print(transition_percentages.round(2))
    print("\nFIRST FIVE RECORDS:")

    print(
        df[
            [
                "hospital_id",
                "record_date",
                "workload_level",
                "next_day_workload_level"
            ]
        ].head()
    )

    print("\nDATASET SAVED SUCCESSFULLY.")
    print("LOCATION:", OUTPUT_PATH)


if __name__ == "__main__":
    prepare_dataset()