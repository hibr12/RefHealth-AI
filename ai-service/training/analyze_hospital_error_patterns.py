import pandas as pd
import numpy as np
import joblib

from pathlib import Path

from prediction.workload_features import calculate_workload_features


# ==========================================================
# RefHealth AI
# HOSPITAL-SPECIFIC ERROR PATTERN INVESTIGATION
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_dataset.csv"
)

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "workload_prediction_feature_engineered_tuned_candidate.joblib"
)

OUTPUT_DIR = BASE_DIR / "datasets" / "processed"

ERROR_OUTPUT = (
    OUTPUT_DIR / "hospital_error_details.csv"
)

SUMMARY_OUTPUT = (
    OUTPUT_DIR / "hospital_error_pattern_summary.csv"
)


# ==========================================================
# 1. LOAD DATA AND MODEL
# ==========================================================

print("\nRefHealth AI")
print("HOSPITAL-SPECIFIC ERROR PATTERN INVESTIGATION")
print("=" * 70)

df = pd.read_csv(DATA_PATH)

df["record_date"] = pd.to_datetime(
    df["record_date"]
)

model = joblib.load(MODEL_PATH)

print("Dataset loaded:", len(df), "records")
print("Workload model loaded successfully.")


# ==========================================================
# 2. PREPARE HISTORICAL FEATURES
# ==========================================================

print("\nPREPARING HISTORICAL FEATURES...")

df = df.sort_values(
    ["hospital_id", "record_date"]
).copy()

df["day_of_week"] = (
    df["record_date"].dt.day_name()
)

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
).copy()

df = calculate_workload_features(df)


# ==========================================================
# 3. DEFINE MODEL FEATURES
# ==========================================================

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

target_column = "next_day_workload_level"


# ==========================================================
# 4. CREATE VALIDATION DATASET
# ==========================================================

print("\nCREATING VALIDATION DATASET...")

unique_dates = sorted(
    df["record_date"].unique()
)

train_end = int(
    len(unique_dates) * 0.70
)

validation_end = int(
    len(unique_dates) * 0.85
)

validation_dates = unique_dates[
    train_end:validation_end
]

validation_df = df[
    df["record_date"].isin(validation_dates)
].copy()

X_validation = validation_df[
    feature_columns
]

y_validation = validation_df[
    target_column
]

print(
    "Validation records:",
    len(validation_df)
)


# ==========================================================
# 5. GENERATE PREDICTIONS
# ==========================================================

print("\nGENERATING PREDICTIONS...")

validation_df["predicted_workload"] = (
    model.predict(X_validation)
)

validation_df["is_correct"] = (
    validation_df["predicted_workload"]
    == y_validation
)

validation_df["actual_workload"] = (
    y_validation
)

validation_df["workload_transition"] = (
    validation_df["workload_level"].astype(str)
    + " -> "
    + validation_df["actual_workload"].astype(str)
)

validation_df["prediction_error"] = (
    ~validation_df["is_correct"]
)

print("Predictions generated successfully.")


# ==========================================================
# 6. HOSPITAL ERROR SUMMARY
# ==========================================================

print("\nHOSPITAL ERROR SUMMARY")
print("=" * 70)

hospital_summary = (
    validation_df.groupby("hospital_id")
    .agg(
        total_predictions=("is_correct", "size"),
        correct_predictions=("is_correct", "sum"),
        average_patient_volume=("patient_volume", "mean"),
        average_pending_referrals=("pending_referrals", "mean"),
        average_available_beds=("available_beds", "mean"),
        incorrect_predictions=("prediction_error", "sum")
    )
    .reset_index()
)

hospital_summary["error_rate"] = (
    hospital_summary["incorrect_predictions"]
    / hospital_summary["total_predictions"]
)

hospital_summary["accuracy"] = (
    hospital_summary["correct_predictions"]
    / hospital_summary["total_predictions"]
)

print(
    hospital_summary.round(3).to_string(
        index=False
    )
)


# ==========================================================
# 7. ANALYZE WORKLOAD TRANSITIONS
# ==========================================================

print("\nWORKLOAD TRANSITION ERROR ANALYSIS")
print("=" * 70)

transition_summary = (
    validation_df.groupby(
        ["hospital_id", "workload_transition"]
    )
    .agg(
        total=("is_correct", "size"),
        correct=("is_correct", "sum")
    )
    .reset_index()
)

transition_summary["incorrect"] = (
    transition_summary["total"]
    - transition_summary["correct"]
)

transition_summary["error_rate"] = (
    transition_summary["incorrect"]
    / transition_summary["total"]
)

print(
    transition_summary.round(3).to_string(
        index=False
    )
)


# ==========================================================
# 8. COMPARE CORRECT AND INCORRECT PREDICTIONS
# ==========================================================

print("\nCORRECT VS INCORRECT PREDICTION FEATURES")
print("=" * 70)

comparison = (
    validation_df.groupby("is_correct")
    .agg(
        records=("hospital_id", "size"),
        average_patient_volume=("patient_volume", "mean"),
        average_incoming_referrals=("incoming_referrals", "mean"),
        average_pending_referrals=("pending_referrals", "mean"),
        average_available_beds=("available_beds", "mean"),
        average_bed_occupancy_proxy=("bed_occupancy_rate", "mean")
    )
)

comparison.index = [
    "Incorrect" if not value else "Correct"
    for value in comparison.index
]

print(
    comparison.round(3).to_string()
)


# ==========================================================
# 9. ANALYZE WORKLOAD CHANGES
# ==========================================================

print("\nWORKLOAD CHANGE ANALYSIS")
print("=" * 70)

workload_mapping = {
    "Low": 1,
    "Medium": 2,
    "High": 3
}

validation_df["current_workload_numeric"] = (
    validation_df["workload_level"].map(
        workload_mapping
    )
)

validation_df["actual_workload_numeric"] = (
    validation_df["actual_workload"].map(
        workload_mapping
    )
)

validation_df["workload_change"] = (
    validation_df["actual_workload_numeric"]
    - validation_df["current_workload_numeric"]
)

validation_df["absolute_workload_change"] = (
    validation_df["workload_change"].abs()
)

validation_df["sudden_change"] = (
    validation_df["absolute_workload_change"] >= 2
)

print(
    validation_df.groupby("sudden_change")
    .agg(
        records=("is_correct", "size"),
        correct=("is_correct", "sum"),
        accuracy=("is_correct", "mean")
    )
    .round(3)
    .to_string()
)


# ==========================================================
# 10. INVESTIGATE H005
# ==========================================================

print("\nH005 DETAILED ERROR INVESTIGATION")
print("=" * 70)

h005 = validation_df[
    validation_df["hospital_id"] == "H005"
]

if not h005.empty:

    print("H005 validation records:", len(h005))

    print(
        "H005 accuracy:",
        round(h005["is_correct"].mean(), 4)
    )

    print("\nH005 prediction errors:")

    h005_errors = h005[
        ~h005["is_correct"]
    ]

    h005_columns = [
        "record_date",
        "workload_level",
        "actual_workload",
        "predicted_workload",
        "patient_volume",
        "incoming_referrals",
        "pending_referrals",
        "available_beds"
    ]

    if h005_errors.empty:

        print("No incorrect predictions.")

    else:

        print(
            h005_errors[h005_columns].to_string(
                index=False
            )
        )

else:

    print("H005 was not found in validation data.")


# ==========================================================
# 11. IDENTIFY REPEATED ERROR PATTERNS
# ==========================================================

print("\nMOST COMMON HOSPITAL ERROR PATTERNS")
print("=" * 70)

error_patterns = validation_df[
    ~validation_df["is_correct"]
].groupby(
    [
        "hospital_id",
        "actual_workload",
        "predicted_workload"
    ]
).size().reset_index(
    name="error_count"
)

error_patterns = error_patterns.sort_values(
    by="error_count",
    ascending=False
)

if error_patterns.empty:

    print("No incorrect predictions found.")

else:

    print(
        error_patterns.to_string(
            index=False
        )
    )


# ==========================================================
# 12. SAVE ANALYSIS RESULTS
# ==========================================================

error_columns = [
    "hospital_id",
    "record_date",
    "workload_level",
    "actual_workload",
    "predicted_workload",
    "is_correct",
    "patient_volume",
    "incoming_referrals",
    "pending_referrals",
    "available_beds",
    "total_beds",
    "workload_transition",
    "workload_change",
    "absolute_workload_change",
    "sudden_change"
]

validation_df[error_columns].to_csv(
    ERROR_OUTPUT,
    index=False
)

hospital_summary.to_csv(
    SUMMARY_OUTPUT,
    index=False
)


# ==========================================================
# 13. COMPLETION
# ==========================================================

print("\nANALYSIS COMPLETED")
print("=" * 70)

print("\nDetailed errors saved to:")
print(ERROR_OUTPUT)

print("\nHospital summary saved to:")
print(SUMMARY_OUTPUT)

print("\nIMPORTANT:")
print(
    "This analysis identifies associations, not proof "
    "that individual features cause prediction errors."
)

print(
    "The hospital dataset is synthetic and does not "
    "represent real-world clinical performance."
)