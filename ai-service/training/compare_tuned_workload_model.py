import pandas as pd
import joblib

from pathlib import Path

from prediction.workload_features import calculate_workload_features

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)


BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = BASE_DIR / "datasets" / "processed" / "workload_prediction_dataset.csv"

OLD_MODEL_PATH = BASE_DIR / "models" / "workload_prediction_tuned_candidate.joblib"

NEW_MODEL_PATH = BASE_DIR / "models" / "workload_prediction_feature_engineered_tuned_candidate.joblib"


def compare_models():

    print("\nRefHealth AI")
    print("WORKLOAD MODEL COMPARISON")
    print("=" * 60)

    # Check required files
    for path in [DATASET_PATH, OLD_MODEL_PATH, NEW_MODEL_PATH]:
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    # Load dataset
    df = pd.read_csv(DATASET_PATH)

    required_columns = [
        "record_date",
        "hospital_id",
        "patient_volume",
        "pending_referrals",
        "available_beds",
        "total_beds",
        "incoming_referrals",
        "workload_level",
        "next_day_workload_level"
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Dataset is missing columns: {missing_columns}"
        )

    df["record_date"] = pd.to_datetime(df["record_date"])

    df = df.sort_values(
        ["hospital_id", "record_date"]
    ).reset_index(drop=True)

    # Create historical features
    grouped = df.groupby("hospital_id")

    df["day_of_week"] = df["record_date"].dt.day_name()

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

    # Remove records without previous workload information
    df = df.dropna(
        subset=["previous_workload_level"]
    ).reset_index(drop=True)

    # Generate the four additional features
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
    new_features = old_features + [
        "bed_occupancy_rate",
        "pending_per_available_bed",
        "referral_to_patient_ratio",
        "workload_trend"
    ]

    # Prepare input and target data
    X_old = df[old_features]
    X_new = df[new_features]
    y = df["next_day_workload_level"]

    # Chronological validation split
    unique_dates = sorted(df["record_date"].unique())

    train_end = int(len(unique_dates) * 0.70)
    validation_end = int(len(unique_dates) * 0.85)

    validation_dates = unique_dates[
        train_end:validation_end
    ]

    validation_mask = df["record_date"].isin(validation_dates)

    X_old_validation = X_old.loc[validation_mask]
    X_new_validation = X_new.loc[validation_mask]
    y_validation = y.loc[validation_mask]

    if len(y_validation) == 0:
        raise ValueError("Validation dataset is empty.")

    print("\nVALIDATION INFORMATION")
    print("-" * 45)
    print("Validation records:", len(y_validation))
    print("Old model features:", len(old_features))
    print("New model features:", len(new_features))

    # Load models
    old_model = joblib.load(OLD_MODEL_PATH)
    new_model = joblib.load(NEW_MODEL_PATH)

    models = [
        (
            "Previous Tuned Model (14 Features)",
            old_model,
            X_old_validation
        ),
        (
            "Feature-Engineered Tuned Model (18 Features)",
            new_model,
            X_new_validation
        )
    ]

    results = []

    # Evaluate models
    for model_name, model, X_validation in models:

        print(f"\n{model_name.upper()}")
        print("-" * 55)

        predictions = model.predict(X_validation)

        accuracy = accuracy_score(y_validation, predictions)

        precision = precision_score(
            y_validation,
            predictions,
            average="macro",
            zero_division=0
        )

        recall = recall_score(
            y_validation,
            predictions,
            average="macro",
            zero_division=0
        )

        macro_f1 = f1_score(
            y_validation,
            predictions,
            average="macro",
            zero_division=0
        )

        print("Accuracy:", round(accuracy, 4))
        print("Precision:", round(precision, 4))
        print("Recall:", round(recall, 4))
        print("Macro F1:", round(macro_f1, 4))

        print("\nCLASSIFICATION REPORT")

        print(
            classification_report(
                y_validation,
                predictions,
                labels=["Low", "Medium", "High"],
                zero_division=0
            )
        )

        print("CONFUSION MATRIX")

        print(
            confusion_matrix(
                y_validation,
                predictions,
                labels=["Low", "Medium", "High"]
            )
        )

        results.append({
            "model": model_name,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "macro_f1": macro_f1
        })

    # Save comparison results
    results_df = pd.DataFrame(results)

    results_path = (
        BASE_DIR
        / "datasets"
        / "processed"
        / "feature_engineered_model_comparison.csv"
    )

    results_df.to_csv(results_path, index=False)

    print("\nFINAL MODEL COMPARISON")
    print("=" * 60)

    print(results_df.to_string(index=False))

    print("\nResults saved to:", results_path)

    print("\nMODEL COMPARISON COMPLETED.")


if __name__ == "__main__":
    compare_models()