import pandas as pd
import joblib

from pathlib import Path

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
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

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_candidate.joblib"
)


def train_model():

    print("\nRefHealth AI")
    print("HOSPITAL WORKLOAD MODEL TRAINING")
    print("=" * 55)

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

    # ==========================================
    # HISTORICAL FEATURE ENGINEERING
    # ==========================================

    historical_columns = [
        "patient_volume",
        "pending_referrals",
        "available_beds",
        "workload_level"
    ]

    # Previous day's information
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

    # ==========================================
    # CHRONOLOGICAL DATA SPLITTING
    # ==========================================

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

    # ==========================================
    # FEATURES AND TARGET
    # ==========================================

    features = [
        "hospital_id",
        "day_of_week",
        "workload_level",
        "patient_volume",
        "incoming_referrals",
        "pending_referrals",
        "available_beds",
        "total_beds",

        # Previous-day historical features
        "previous_patient_volume",
        "previous_pending_referrals",
        "previous_available_beds",
        "previous_workload_level",

        # Three-day historical averages
        "average_3day_patient_volume",
        "average_3day_pending_referrals"
    ]

    target = "next_day_workload_level"

    X_train = train_df[features]
    y_train = train_df[target]

    X_validation = validation_df[features]
    y_validation = validation_df[target]

    # ==========================================
    # FEATURE PREPROCESSING
    # ==========================================

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

    # ==========================================
    # RANDOM FOREST MODEL
    # ==========================================

    model = Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    random_state=42
                )
            )
        ]
    )

    print("\nTRAINING RECORDS:", len(train_df))
    print("VALIDATION RECORDS:", len(validation_df))

    print("\nTRAINING MODEL...")

    model.fit(X_train, y_train)

    # ==========================================
    # VALIDATION
    # ==========================================

    predictions = model.predict(X_validation)

    # Persistence baseline
    baseline_predictions = validation_df[
        "workload_level"
    ]

    print("\nMODEL VALIDATION RESULTS")

    print(
        "Accuracy:",
        round(
            accuracy_score(
                y_validation,
                predictions
            ),
            4
        )
    )

    print(
        "Macro F1:",
        round(
            f1_score(
                y_validation,
                predictions,
                average="macro",
                zero_division=0
            ),
            4
        )
    )

    print("\nCLASSIFICATION REPORT:")

    print(
        classification_report(
            y_validation,
            predictions,
            zero_division=0
        )
    )

    print("\nCONFUSION MATRIX:")

    print(
        confusion_matrix(
            y_validation,
            predictions,
            labels=["Low", "Medium", "High"]
        )
    )

    # ==========================================
    # PERSISTENCE BASELINE COMPARISON
    # ==========================================

    print("\nPERSISTENCE BASELINE")

    print(
        "Baseline accuracy:",
        round(
            accuracy_score(
                y_validation,
                baseline_predictions
            ),
            4
        )
    )

    print(
        "Baseline Macro F1:",
        round(
            f1_score(
                y_validation,
                baseline_predictions,
                average="macro",
                zero_division=0
            ),
            4
        )
    )

    # ==========================================
    # SAVE CANDIDATE MODEL
    # ==========================================

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(model, MODEL_PATH)

    print("\nCANDIDATE MODEL SAVED.")

    print("LOCATION:", MODEL_PATH)

    print("\nNOTICE:")

    print("This model uses synthetic development data.")

    print("Validation results are not clinical evidence.")


if __name__ == "__main__":

    train_model()