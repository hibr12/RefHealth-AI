import pandas as pd
import joblib
import numpy as np

from pathlib import Path

from prediction.workload_features import calculate_workload_features


# ==========================================================
# RefHealth AI
# HOSPITAL WORKLOAD PREDICTION CONFIDENCE ANALYSIS
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

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "processed"
    / "workload_prediction_confidence_analysis.csv"
)


# ==========================================================
# 1. LOAD DATA AND MODEL
# ==========================================================

print("\nRefHealth AI")
print("HOSPITAL WORKLOAD PREDICTION CONFIDENCE ANALYSIS")
print("=" * 65)

print("\nLOADING DATASET...")

df = pd.read_csv(DATA_PATH)

df["record_date"] = pd.to_datetime(df["record_date"])

print("Dataset loaded:", len(df), "records")

print("\nLOADING ACTIVE WORKLOAD MODEL...")

model = joblib.load(MODEL_PATH)

print("Model loaded successfully.")


# ==========================================================
# 2. PREPARE HISTORICAL FEATURES
# ==========================================================

print("\nPREPARING HISTORICAL FEATURES...")

df = df.sort_values(
    ["hospital_id", "record_date"]
).copy()

df["day_of_week"] = df["record_date"].dt.day_name()

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
# 4. CHRONOLOGICAL TRAINING / VALIDATION SPLIT
# ==========================================================

print("\nCREATING CHRONOLOGICAL VALIDATION SET...")

unique_dates = sorted(
    df["record_date"].unique()
)

train_end = int(len(unique_dates) * 0.70)

validation_end = int(len(unique_dates) * 0.85)

validation_dates = unique_dates[
    train_end:validation_end
]

validation_df = df[
    df["record_date"].isin(validation_dates)
].copy()

X_validation = validation_df[feature_columns]

y_validation = validation_df[target_column]

print("Validation records:", len(validation_df))

if validation_df.empty:
    raise ValueError(
        "Validation dataset is empty. Check the dataset and date split."
    )


# ==========================================================
# 5. GENERATE PREDICTIONS AND PROBABILITIES
# ==========================================================

print("\nGENERATING PREDICTIONS AND CONFIDENCE SCORES...")

predictions = model.predict(X_validation)

probabilities = model.predict_proba(X_validation)

classifier = model.named_steps["classifier"]

model_classes = classifier.classes_

probability_df = pd.DataFrame(
    probabilities,
    columns=[
        f"probability_{class_name}"
        for class_name in model_classes
    ],
    index=validation_df.index
)


# ==========================================================
# 6. BUILD CONFIDENCE ANALYSIS DATASET
# ==========================================================

results = validation_df[
    ["hospital_id", "record_date", target_column]
].copy()

results.rename(
    columns={
        target_column: "actual_workload"
    },
    inplace=True
)

results["predicted_workload"] = predictions

results = results.join(probability_df)

results["confidence"] = probabilities.max(axis=1)

# Sort probabilities for each prediction.
# The second-largest probability represents the runner-up class.

sorted_probabilities = np.sort(
    probabilities,
    axis=1
)

results["second_best_probability"] = (
    sorted_probabilities[:, -2]
)

results["confidence_gap"] = (
    results["confidence"]
    - results["second_best_probability"]
)

results["is_correct"] = (
    results["actual_workload"]
    == results["predicted_workload"]
)

results["top_two_classes"] = [
    " / ".join(
        [
            str(model_classes[index])
            for index in row.argsort()[-2:][::-1]
        ]
    )
    for row in probabilities
]


# ==========================================================
# 7. IDENTIFY UNCERTAIN PREDICTIONS
# ==========================================================

# These are experimental review thresholds only.
# They are NOT clinically validated thresholds.

results["low_confidence"] = (
    results["confidence"] < 0.60
)

results["small_confidence_gap"] = (
    results["confidence_gap"] < 0.15
)

results["medium_high_uncertainty"] = (
    results["top_two_classes"].apply(
        lambda value: set(value.split(" / "))
        == {"Medium", "High"}
    )
    & results["small_confidence_gap"]
)

results["needs_human_review"] = (
    results["low_confidence"]
    | results["small_confidence_gap"]
)


# ==========================================================
# 8. OVERALL CONFIDENCE ANALYSIS
# ==========================================================

print("\nOVERALL VALIDATION RESULTS")
print("=" * 65)

print("Validation records:", len(results))

print(
    "Correct predictions:",
    results["is_correct"].sum()
)

print(
    "Incorrect predictions:",
    (~results["is_correct"]).sum()
)

print(
    "Average confidence:",
    round(results["confidence"].mean(), 4)
)

print(
    "Average confidence on correct predictions:",
    round(
        results.loc[
            results["is_correct"],
            "confidence"
        ].mean(),
        4
    )
)

print(
    "Average confidence on incorrect predictions:",
    round(
        results.loc[
            ~results["is_correct"],
            "confidence"
        ].mean(),
        4
    )
)


# ==========================================================
# 9. UNCERTAIN PREDICTIONS
# ==========================================================

print("\nUNCERTAINTY ANALYSIS")
print("=" * 65)

print(
    "Low-confidence predictions:",
    results["low_confidence"].sum()
)

print(
    "Small confidence-gap predictions:",
    results["small_confidence_gap"].sum()
)

print(
    "Medium-versus-High uncertain predictions:",
    results["medium_high_uncertainty"].sum()
)

print(
    "Predictions flagged for human review:",
    results["needs_human_review"].sum()
)


# ==========================================================
# 10. DISPLAY PREDICTION DETAILS
# ==========================================================

print("\nPREDICTION DETAILS")
print("=" * 65)

display_columns = [
    "hospital_id",
    "actual_workload",
    "predicted_workload",
    "confidence",
    "confidence_gap",
    "is_correct",
    "top_two_classes",
    "needs_human_review"
]

print(
    results[display_columns].round(3).to_string(
        index=False
    )
)


# ==========================================================
# 11. DISPLAY HUMAN REVIEW CASES
# ==========================================================

print("\nPREDICTIONS REQUIRING HUMAN REVIEW")
print("=" * 65)

review_cases = results[
    results["needs_human_review"]
]

if review_cases.empty:

    print("No predictions were flagged for review.")

else:

    print(
        review_cases[display_columns].round(3).to_string(
            index=False
        )
    )


# ==========================================================
# 12. SAVE RESULTS
# ==========================================================

results.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\nANALYSIS COMPLETED")
print("=" * 65)

print("Results saved to:")
print(OUTPUT_PATH)

print("\nIMPORTANT:")
print(
    "Random Forest confidence scores are not necessarily "
    "calibrated probabilities."
)

print(
    "Human-review thresholds are experimental and must not "
    "be treated as clinical standards."
)

print(
    "The dataset is synthetic and does not demonstrate "
    "real-world hospital performance."
)