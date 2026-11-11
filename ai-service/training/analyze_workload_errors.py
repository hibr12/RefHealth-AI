import pandas as pd
import joblib

from pathlib import Path

from prediction.workload_features import (
    calculate_workload_features
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)


BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)

# New 18-feature tuned model
MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_feature_engineered_tuned_candidate.joblib"
)


def analyze_workload_errors():

    print("\nRefHealth AI")
    print("HOSPITAL WORKLOAD PREDICTION ERROR ANALYSIS")
    print("=" * 65)

    # Check required files
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}"
        )

    # Load dataset
    df = pd.read_csv(DATASET_PATH)

    df["record_date"] = pd.to_datetime(
        df["record_date"]
    )

    # Sort historical records
    df = df.sort_values(
        ["hospital_id", "record_date"]
    ).reset_index(drop=True)

    # Generate day of week
    df["day_of_week"] = (
        df["record_date"].dt.day_name()
    )

    # Previous-day historical features
    grouped = df.groupby("hospital_id")

    df["previous_patient_volume"] = (
        grouped["patient_volume"].shift(1)
    )

    df["previous_pending_referrals"] = (
        grouped["pending_referrals"].shift(1)
    )

    df["previous_available_beds"] = (
        grouped["available_beds"].shift(1)
    )

    df["previous_workload_level"] = (
        grouped["workload_level"].shift(1)
    )

    # Three-day rolling averages
    df["average_3day_patient_volume"] = (
        df.groupby("hospital_id")["patient_volume"]
        .transform(
            lambda values: values.rolling(
                window=3,
                min_periods=1
            ).mean()
        )
    )

    df["average_3day_pending_referrals"] = (
        df.groupby("hospital_id")["pending_referrals"]
        .transform(
            lambda values: values.rolling(
                window=3,
                min_periods=1
            ).mean()
        )
    )

    # Remove records without previous-day information
    df = df.dropna(
        subset=["previous_workload_level"]
    ).reset_index(drop=True)

    # Generate four engineered features
    df = calculate_workload_features(df)

    # Original 14 features
    old_features = [
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

    # New 18 features
    features = old_features + [
        "bed_occupancy_rate",
        "pending_per_available_bed",
        "referral_to_patient_ratio",
        "workload_trend"
    ]

    target = "next_day_workload_level"

    # Chronological test split
    dates = sorted(
        df["record_date"].unique()
    )

    train_end = int(len(dates) * 0.70)

    validation_end = int(len(dates) * 0.85)

    test_dates = dates[validation_end:]

    test_df = df[
        df["record_date"].isin(test_dates)
    ].copy()

    if test_df.empty:
        raise ValueError(
            "Test dataset is empty. Check the dataset split."
        )

    X_test = test_df[features]

    y_test = test_df[target]

    # Load new tuned model
    print("\nLOADING FEATURE-ENGINEERED TUNED MODEL...")

    model = joblib.load(MODEL_PATH)

    print("MODEL LOADED SUCCESSFULLY")

    print("MODEL FEATURES:", len(features))

    # Generate predictions
    predictions = model.predict(X_test)

    test_df["predicted_workload"] = predictions

    test_df["actual_workload"] = y_test

    test_df["correct_prediction"] = (
        test_df["predicted_workload"]
        == test_df["actual_workload"]
    )

    # ======================================
    # OVERALL PERFORMANCE
    # ======================================

    print("\nOVERALL TEST PERFORMANCE")
    print("=" * 55)

    print("Test records:", len(test_df))

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

    # ======================================
    # CLASSIFICATION REPORT
    # ======================================

    print("\nCLASSIFICATION REPORT")

    print(
        classification_report(
            y_test,
            predictions,
            labels=["Low", "Medium", "High"],
            zero_division=0
        )
    )

    # ======================================
    # CONFUSION MATRIX
    # ======================================

    print("\nCONFUSION MATRIX")

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=["Low", "Medium", "High"]
    )

    matrix_df = pd.DataFrame(
        matrix,
        index=[
            "Actual Low",
            "Actual Medium",
            "Actual High"
        ],
        columns=[
            "Predicted Low",
            "Predicted Medium",
            "Predicted High"
        ]
    )

    print(matrix_df)

    # ======================================
    # ERRORS BY HOSPITAL
    # ======================================

    print("\nPREDICTION ERRORS BY HOSPITAL")

    hospital_errors = (
        test_df.groupby("hospital_id")
        .agg(
            total_predictions=(
                "correct_prediction",
                "count"
            ),
            correct_predictions=(
                "correct_prediction",
                "sum"
            )
        )
    )

    hospital_errors["errors"] = (
        hospital_errors["total_predictions"]
        - hospital_errors["correct_predictions"]
    )

    hospital_errors["error_rate"] = (
        hospital_errors["errors"]
        / hospital_errors["total_predictions"]
    )

    print(hospital_errors.round(4))

    # ======================================
    # ERRORS BY DAY
    # ======================================

    print("\nPREDICTION ERRORS BY DAY OF WEEK")

    day_errors = (
        test_df.groupby("day_of_week")
        .agg(
            total_predictions=(
                "correct_prediction",
                "count"
            ),
            correct_predictions=(
                "correct_prediction",
                "sum"
            )
        )
    )

    day_errors["errors"] = (
        day_errors["total_predictions"]
        - day_errors["correct_predictions"]
    )

    day_errors["error_rate"] = (
        day_errors["errors"]
        / day_errors["total_predictions"]
    )

    print(day_errors.round(4))

    # ======================================
    # INCORRECT PREDICTIONS
    # ======================================

    print("\nINCORRECT PREDICTIONS")

    incorrect = test_df[
        ~test_df["correct_prediction"]
    ]

    if incorrect.empty:

        print("No incorrect predictions.")

    else:

        print(
            incorrect[
                [
                    "record_date",
                    "hospital_id",
                    "workload_level",
                    "next_day_workload_level",
                    "predicted_workload",
                    "pending_referrals",
                    "available_beds",
                    "bed_occupancy_rate",
                    "workload_trend"
                ]
            ].to_string(index=False)
        )

    # ======================================
    # SAVE ERROR ANALYSIS
    # ======================================

    output_path = (
        BASE_DIR
        / "datasets"
        / "processed"
        / "workload_error_analysis.csv"
    )

    test_df.to_csv(
        output_path,
        index=False
    )

    print("\nERROR ANALYSIS SAVED TO:")
    print(output_path)

    print("\nANALYSIS COMPLETED.")

    print("\nNOTICE:")
    print("This analysis uses synthetic development data.")
    print("Results are not clinical evidence.")


if __name__ == "__main__":

    analyze_workload_errors()