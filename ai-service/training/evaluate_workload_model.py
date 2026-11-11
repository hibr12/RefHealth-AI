import pandas as pd
import joblib
from prediction.workload_features import calculate_workload_features

from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score
)


BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_candidate.joblib"
)


def evaluate_workload_model():

    print("\nRefHealth AI")
    print("FINAL HOSPITAL WORKLOAD MODEL EVALUATION")
    print("=" * 60)

    # Load dataset
    df = pd.read_csv(DATASET_PATH)

    df["record_date"] = pd.to_datetime(
        df["record_date"]
    )

    # Extract day of the week
    df["day_of_week"] = (
        df["record_date"].dt.day_name()
    )

    # Sort historical records
    df = df.sort_values(
        ["hospital_id", "record_date"]
    ).copy()

    # Previous-day features
    historical_columns = [
        "patient_volume",
        "pending_referrals",
        "available_beds",
        "workload_level"
    ]

    for column in historical_columns:

        df[f"previous_{column}"] = (
            df.groupby("hospital_id")[column]
            .shift(1)
        )

    # Three-day rolling averages
    for column in [
        "patient_volume",
        "pending_referrals"
    ]:

        df[f"average_3day_{column}"] = (
            df.groupby("hospital_id")[column]
            .transform(
                lambda values: values.rolling(
                    window=3,
                    min_periods=1
                ).mean()
            )
        )

    # Remove records without historical information
    df = df.dropna(
        subset=["previous_workload_level"]
    ).copy()

    # Reproduce chronological split
    dates = sorted(
        df["record_date"].unique()
    )

    train_end = int(len(dates) * 0.70)

    validation_end = int(len(dates) * 0.85)

    test_dates = dates[validation_end:]

    test_df = df[
        df["record_date"].isin(test_dates)
    ].copy()

    # Features
    features = [
        "hospital_id",
        "day_of_week",
        "workload_level",
        "patient_volume",
        "incoming_referrals",
        "pending_referrals",
        "available_beds",
        "total_beds",
        "previous_patient_volume",
        "previous_pending_referrals",
        "previous_available_beds",
        "previous_workload_level",
        "average_3day_patient_volume",
        "average_3day_pending_referrals"
    ]

    target = "next_day_workload_level"

    test_df = calculate_workload_features(test_df)
    model = joblib.load(MODEL_PATH)
    features = list(model.feature_names_in_)
    X_test = test_df[features]

    y_test = test_df[target]

    # Load candidate model
    model = joblib.load(MODEL_PATH)

    print("\nTEST RECORDS:", len(test_df))

    print(
        "TEST PERIOD:",
        test_df["record_date"].min().date(),
        "TO",
        test_df["record_date"].max().date()
    )

    # Model predictions
    predictions = model.predict(X_test)

    # Persistence baseline
    baseline_predictions = test_df["workload_level"]

    # ======================================
    # MODEL EVALUATION
    # ======================================

    print("\nMODEL TEST RESULTS")

    print(
        "Accuracy:",
        round(
            accuracy_score(y_test, predictions),
            4
        )
    )

    print(
        "Precision:",
        round(
            precision_score(
                y_test,
                predictions,
                average="macro",
                zero_division=0
            ),
            4
        )
    )

    print(
        "Recall:",
        round(
            recall_score(
                y_test,
                predictions,
                average="macro",
                zero_division=0
            ),
            4
        )
    )

    print(
        "Macro F1:",
        round(
            f1_score(
                y_test,
                predictions,
                average="macro",
                zero_division=0
            ),
            4
        )
    )

    print("\nCLASSIFICATION REPORT")

    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0
        )
    )

    print("\nCONFUSION MATRIX")

    print(
        confusion_matrix(
            y_test,
            predictions,
            labels=["Low", "Medium", "High"]
        )
    )

    # ======================================
    # BASELINE COMPARISON
    # ======================================

    print("\nPERSISTENCE BASELINE RESULTS")

    print(
        "Baseline Accuracy:",
        round(
            accuracy_score(
                y_test,
                baseline_predictions
            ),
            4
        )
    )

    print(
        "Baseline Macro F1:",
        round(
            f1_score(
                y_test,
                baseline_predictions,
                average="macro",
                zero_division=0
            ),
            4
        )
    )

    print("\nFINAL EVALUATION COMPLETED.")

    print("\nNOTICE:")
    print("The evaluation uses synthetic development data.")
    print("Results are not clinical evidence.")


if __name__ == "__main__":

    evaluate_workload_model()
