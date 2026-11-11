# ```python
import pandas as pd

from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    classification_report,
    confusion_matrix
)

from prediction.workload_features import calculate_workload_features


BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)

RESULTS_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "medium_workload_experiment.csv"
)


def run_experiment():

    print("\nRefHealth AI")
    print("MEDIUM WORKLOAD CLASS-WEIGHT EXPERIMENT")
    print("=" * 65)

    # --------------------------------------------------
    # 1. LOAD DATASET
    # --------------------------------------------------

    df = pd.read_csv(DATASET_PATH)

    required_columns = [
        "hospital_id",
        "record_date",
        "patient_volume",
        "incoming_referrals",
        "pending_referrals",
        "available_beds",
        "total_beds",
        "workload_level",
        "next_day_workload_level"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing dataset columns: {missing_columns}"
        )

    df["record_date"] = pd.to_datetime(df["record_date"])

    df["day_of_week"] = df["record_date"].dt.day_name()

    df = df.sort_values(
        ["hospital_id", "record_date"]
    ).reset_index(drop=True)

    # --------------------------------------------------
    # 2. CREATE HISTORICAL FEATURES
    # --------------------------------------------------

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

    # --------------------------------------------------
    # 3. FEATURE ENGINEERING
    # --------------------------------------------------

    df = calculate_workload_features(df)

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
        "average_3day_pending_referrals",
        "bed_occupancy_rate",
        "pending_per_available_bed",
        "referral_to_patient_ratio",
        "workload_trend"
    ]

    categorical_features = [
        "hospital_id",
        "day_of_week",
        "workload_level",
        "previous_workload_level"
    ]

    numerical_features = [
        column
        for column in feature_columns
        if column not in categorical_features
    ]

    X = df[feature_columns]

    y = df["next_day_workload_level"]

    # --------------------------------------------------
    # 4. CHRONOLOGICAL TRAINING / VALIDATION SPLIT
    # --------------------------------------------------

    unique_dates = sorted(
        df["record_date"].unique()
    )

    train_end = int(len(unique_dates) * 0.70)

    validation_end = int(len(unique_dates) * 0.85)

    train_dates = unique_dates[:train_end]

    validation_dates = unique_dates[
        train_end:validation_end
    ]

    train_mask = df["record_date"].isin(train_dates)

    validation_mask = df["record_date"].isin(
        validation_dates
    )

    X_train = X.loc[train_mask]
    y_train = y.loc[train_mask]

    X_validation = X.loc[validation_mask]
    y_validation = y.loc[validation_mask]

    if X_train.empty or X_validation.empty:
        raise ValueError(
            "Training or validation dataset is empty."
        )

    print("\nDATA SPLIT")
    print("-" * 45)

    print("Training records:", len(X_train))
    print("Validation records:", len(X_validation))
    print("Test records: Not used")

    print("\nTRAINING DISTRIBUTION")
    print(y_train.value_counts().to_string())

    print("\nVALIDATION DISTRIBUTION")
    print(y_validation.value_counts().to_string())

    # --------------------------------------------------
    # 5. DEFINE CLASS WEIGHT EXPERIMENTS
    # --------------------------------------------------

    configurations = [
        {
            "name": "balanced",
            "weights": "balanced"
        },
        {
            "name": "medium_1.5",
            "weights": {
                "Low": 1.0,
                "Medium": 1.5,
                "High": 1.0
            }
        },
        {
            "name": "medium_2.0",
            "weights": {
                "Low": 1.0,
                "Medium": 2.0,
                "High": 1.0
            }
        },
        {
            "name": "medium_2.5",
            "weights": {
                "Low": 1.0,
                "Medium": 2.5,
                "High": 1.0
            }
        },
        {
            "name": "medium_3.0",
            "weights": {
                "Low": 1.0,
                "Medium": 3.0,
                "High": 1.0
            }
        }
    ]

    results = []

    # --------------------------------------------------
    # 6. TRAIN AND EVALUATE MODELS
    # --------------------------------------------------

    for config in configurations:

        print("\n" + "=" * 65)

        print("TESTING:", config["name"])

        print("=" * 65)

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "categorical",
                    OneHotEncoder(
                        handle_unknown="ignore"
                    ),
                    categorical_features
                ),
                (
                    "numerical",
                    "passthrough",
                    numerical_features
                )
            ]
        )

        model = Pipeline(
            steps=[
                ("preprocessor", preprocessor),

                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=8,
                        min_samples_split=5,
                        min_samples_leaf=2,
                        class_weight=config["weights"],
                        random_state=42,
                        n_jobs=-1
                    )
                )
            ]
        )

        model.fit(
            X_train,
            y_train
        )

        predictions = model.predict(
            X_validation
        )

        accuracy = accuracy_score(
            y_validation,
            predictions
        )

        macro_f1 = f1_score(
            y_validation,
            predictions,
            labels=["Low", "Medium", "High"],
            average="macro",
            zero_division=0
        )

        medium_precision = precision_score(
            y_validation,
            predictions,
            labels=["Medium"],
            average="macro",
            zero_division=0
        )

        medium_recall = recall_score(
            y_validation,
            predictions,
            labels=["Medium"],
            average="macro",
            zero_division=0
        )

        medium_f1 = f1_score(
            y_validation,
            predictions,
            labels=["Medium"],
            average="macro",
            zero_division=0
        )

        print("\nPERFORMANCE")

        print("Accuracy:", round(accuracy, 4))

        print("Macro F1:", round(macro_f1, 4))

        print("Medium Precision:", round(medium_precision, 4))

        print("Medium Recall:", round(medium_recall, 4))

        print("Medium F1:", round(medium_f1, 4))

        print("\nCLASSIFICATION REPORT")

        print(
            classification_report(
                y_validation,
                predictions,
                labels=["Low", "Medium", "High"],
                zero_division=0
            )
        )

        print("\nCONFUSION MATRIX")

        print(
            confusion_matrix(
                y_validation,
                predictions,
                labels=["Low", "Medium", "High"]
            )
        )

        results.append({
            "configuration": config["name"],
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "medium_precision": medium_precision,
            "medium_recall": medium_recall,
            "medium_f1": medium_f1
        })

    # --------------------------------------------------
    # 7. COMPARE EXPERIMENT RESULTS
    # --------------------------------------------------

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by="macro_f1",
        ascending=False
    )

    print("\nFINAL EXPERIMENT COMPARISON")

    print("=" * 85)

    print(
        results_df.round(4).to_string(index=False)
    )

    # --------------------------------------------------
    # 8. SAVE RESULTS
    # --------------------------------------------------

    results_df.to_csv(
        RESULTS_PATH,
        index=False
    )

    print("\nRESULTS SAVED SUCCESSFULLY")

    print(RESULTS_PATH)

    print("\nEXPERIMENT COMPLETED.")


if __name__ == "__main__":

    run_experiment()
# ```
