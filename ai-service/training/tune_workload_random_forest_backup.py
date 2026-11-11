import pandas as pd
import joblib

from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score


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
    / "workload_random_forest_tuning.csv"
)

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_tuned_candidate.joblib"
)


def tune_random_forest():

    print("\nRefHealth AI")
    print("RANDOM FOREST HYPERPARAMETER OPTIMIZATION")
    print("=" * 65)

    # 1. Load dataset
    df = pd.read_csv(DATASET_PATH)

    df["record_date"] = pd.to_datetime(df["record_date"])

    df["day_of_week"] = df["record_date"].dt.day_name()

    df = df.sort_values(
        ["hospital_id", "record_date"]
    ).reset_index(drop=True)

    # 2. Create historical features
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

    # 3. Define features and target
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

    # 4. Chronological train/validation split
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

    print("\nDATA SPLIT")
    print("-" * 45)

    print("Training records:", len(X_train))
    print("Validation records:", len(X_validation))
    print("Test records: Not used during tuning")

    # 5. Define model configurations
    configurations = [
        {
            "n_estimators": 200,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "class_weight": None
        },
        {
            "n_estimators": 300,
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "class_weight": None
        },
        {
            "n_estimators": 300,
            "max_depth": 8,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "class_weight": None
        },
        {
            "n_estimators": 300,
            "max_depth": 5,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "class_weight": None
        },
        {
            "n_estimators": 300,
            "max_depth": 8,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "class_weight": None
        },
        {
            "n_estimators": 300,
            "max_depth": 5,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "class_weight": None
        },
        {
            "n_estimators": 300,
            "max_depth": 8,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "class_weight": "balanced"
        },
        {
            "n_estimators": 300,
            "max_depth": 5,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "class_weight": "balanced"
        }
    ]

    results = []

    best_score = -1
    best_model = None
    best_configuration = None

    # 6. Train and evaluate configurations
    for index, params in enumerate(
        configurations,
        start=1
    ):

        print(f"\nTesting configuration {index}/8")

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
                        **params,
                        random_state=42
                    )
                )
            ]
        )

        model.fit(X_train, y_train)

        predictions = model.predict(X_validation)

        accuracy = accuracy_score(
            y_validation,
            predictions
        )

        macro_f1 = f1_score(
            y_validation,
            predictions,
            average="macro",
            zero_division=0
        )

        print("Accuracy:", round(accuracy, 4))
        print("Macro F1:", round(macro_f1, 4))

        results.append({
            "configuration": index,
            **params,
            "validation_accuracy": accuracy,
            "validation_macro_f1": macro_f1
        })

        # Select using validation macro F1
        if macro_f1 > best_score:

            best_score = macro_f1
            best_model = model
            best_configuration = params

    # 7. Persistence baseline
    baseline_predictions = X_validation[
        "workload_level"
    ]

    baseline_accuracy = accuracy_score(
        y_validation,
        baseline_predictions
    )

    baseline_f1 = f1_score(
        y_validation,
        baseline_predictions,
        average="macro",
        zero_division=0
    )

    print("\nPERSISTENCE BASELINE")
    print("-" * 45)

    print("Accuracy:", round(baseline_accuracy, 4))
    print("Macro F1:", round(baseline_f1, 4))

    # 8. Save tuning results
    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        "validation_macro_f1",
        ascending=False
    )

    results_df.to_csv(
        RESULTS_PATH,
        index=False
    )

    # 9. Save best model separately
    joblib.dump(
        best_model,
        MODEL_PATH
    )

    print("\nBEST CONFIGURATION")
    print("=" * 45)

    print("Parameters:", best_configuration)
    print("Validation Macro F1:", round(best_score, 4))

    print("\nTUNING RESULTS")
    print("-" * 65)

    print(
        results_df[
            [
                "configuration",
                "n_estimators",
                "max_depth",
                "min_samples_split",
                "min_samples_leaf",
                "class_weight",
                "validation_accuracy",
                "validation_macro_f1"
            ]
        ].to_string(index=False)
    )

    print("\nSAVED FILES")
    print("Results:", RESULTS_PATH)
    print("Best model:", MODEL_PATH)

    print("\nHYPERPARAMETER OPTIMIZATION COMPLETED.")


if __name__ == "__main__":

    tune_random_forest()