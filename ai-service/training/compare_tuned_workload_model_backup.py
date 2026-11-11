import pandas as pd
import joblib

from pathlib import Path

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

ORIGINAL_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_candidate.joblib"
)

TUNED_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_tuned_candidate.joblib"
)


def compare_models():

    print("\nRefHealth AI")
    print("TUNED WORKLOAD MODEL COMPARISON")
    print("=" * 65)

    # Load dataset
    df = pd.read_csv(DATASET_PATH)

    df["record_date"] = pd.to_datetime(df["record_date"])

    df = df.sort_values(
        ["hospital_id", "record_date"]
    ).reset_index(drop=True)

    # Recreate historical features
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

    df = df.dropna(
        subset=["previous_workload_level"]
    ).reset_index(drop=True)

    # Features
    feature_columns = [
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

    X = df[feature_columns]

    y = df["next_day_workload_level"]

    # Recreate chronological split
    unique_dates = sorted(
        df["record_date"].unique()
    )

    train_end = int(len(unique_dates) * 0.70)
    validation_end = int(len(unique_dates) * 0.85)

    validation_dates = unique_dates[
        train_end:validation_end
    ]

    validation_mask = df["record_date"].isin(
        validation_dates
    )

    X_validation = X.loc[validation_mask]
    y_validation = y.loc[validation_mask]

    # Load models
    original_model = joblib.load(
        ORIGINAL_MODEL_PATH
    )

    tuned_model = joblib.load(
        TUNED_MODEL_PATH
    )

    models = {
        "Original Random Forest": original_model,
        "Tuned Random Forest": tuned_model
    }

    comparison_results = []

    # Evaluate both models
    for model_name, model in models.items():

        print(f"\n{model_name.upper()}")
        print("-" * 55)

        predictions = model.predict(X_validation)

        accuracy = accuracy_score(
            y_validation,
            predictions
        )

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

        comparison_results.append({
            "model": model_name,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "macro_f1": macro_f1
        })

    # Save comparison
    results_df = pd.DataFrame(
        comparison_results
    )

    results_path = (
        BASE_DIR
        / "datasets"
        / "processed"
        / "tuned_model_comparison.csv"
    )

    results_df.to_csv(
        results_path,
        index=False
    )

    print("\nFINAL COMPARISON")
    print("=" * 65)

    print(
        results_df.to_string(index=False)
    )

    print("\nComparison saved to:", results_path)


if __name__ == "__main__":

    compare_models()