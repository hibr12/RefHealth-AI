import pandas as pd

from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline

from sklearn.ensemble import (
    RandomForestClassifier,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    HistGradientBoostingClassifier
)

from sklearn.metrics import (
    accuracy_score,
    f1_score
)


BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)


def compare_workload_models():

    print("\nRefHealth AI")
    print("WORKLOAD MACHINE LEARNING MODEL COMPARISON")
    print("=" * 65)

    # Load dataset
    df = pd.read_csv(DATASET_PATH)

    df["record_date"] = pd.to_datetime(
        df["record_date"]
    )

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

    # Remove records without previous-day information
    df = df.dropna(
        subset=["previous_workload_level"]
    ).copy()

    # Chronological splitting
    dates = sorted(
        df["record_date"].unique()
    )

    train_end = int(len(dates) * 0.70)

    validation_end = int(len(dates) * 0.85)

    train_dates = dates[:train_end]

    validation_dates = dates[
        train_end:validation_end
    ]

    train_df = df[
        df["record_date"].isin(train_dates)
    ].copy()

    validation_df = df[
        df["record_date"].isin(validation_dates)
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

    X_train = train_df[features]
    y_train = train_df[target]

    X_validation = validation_df[features]
    y_validation = validation_df[target]

    # Feature types
    categorical_features = [
        "hospital_id",
        "day_of_week",
        "workload_level",
        "previous_workload_level"
    ]

    numerical_features = [
        "patient_volume",
        "incoming_referrals",
        "pending_referrals",
        "available_beds",
        "total_beds",
        "previous_patient_volume",
        "previous_pending_referrals",
        "previous_available_beds",
        "average_3day_patient_volume",
        "average_3day_pending_referrals"
    ]

    # Preprocessing
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features
            ),
            (
                "numerical",
                "passthrough",
                numerical_features
            )
        ]
    )

    # Candidate algorithms
    models = {

        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42
        ),

        "Extra Trees": ExtraTreesClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42
        ),

        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=2,
            random_state=42
        ),

        "Hist Gradient Boosting": Pipeline(
            steps=[
                (
                    "preprocessing",
                    ColumnTransformer(
                        transformers=[
                            (
                                "categorical",
                                OneHotEncoder(
                                    handle_unknown="ignore",
                                    sparse_output=False
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
                ),
                (
                    "classifier",
                    HistGradientBoostingClassifier(
                        max_iter=100,
                        learning_rate=0.05,
                        random_state=42
                    )
                )
            ]
        )
    }

    results = []

    print("\nTRAINING RECORDS:", len(train_df))
    print("VALIDATION RECORDS:", len(validation_df))

    print("\nTRAINING AND COMPARING MODELS...")

    for name, classifier in models.items():

        if name == "Hist Gradient Boosting":

            model = classifier

        else:

            model = Pipeline(
                steps=[
                    ("preprocessing", preprocessing),
                    ("classifier", classifier)
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

        results.append({
            "Model": name,
            "Accuracy": round(accuracy, 4),
            "Macro F1": round(macro_f1, 4)
        })

        print(f"\n{name}")
        print("Accuracy:", round(accuracy, 4))
        print("Macro F1:", round(macro_f1, 4))

    # Persistence baseline
    baseline_predictions = validation_df[
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

    results.append({
        "Model": "Persistence Baseline",
        "Accuracy": round(baseline_accuracy, 4),
        "Macro F1": round(baseline_f1, 4)
    })

    # Display comparison
    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by="Macro F1",
        ascending=False
    )

    print("\nFINAL MODEL COMPARISON")
    print("=" * 65)

    print(
        results_df.to_string(
            index=False
        )
    )

    # Save results
    output_path = (
        BASE_DIR
        / "datasets"
        / "processed"
        / "workload_model_comparison.csv"
    )

    results_df.to_csv(
        output_path,
        index=False
    )

    print("\nCOMPARISON RESULTS SAVED TO:")
    print(output_path)

    print("\nNOTICE:")
    print("All models use synthetic development data.")
    print("Validation results are not clinical evidence.")


if __name__ == "__main__":

    compare_workload_models()