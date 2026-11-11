import pandas as pd
import joblib

from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix
)

from prediction.workload_features import calculate_workload_features


# ==========================================================
# RefHealth AI
# HOSPITAL WORKLOAD MODEL RELIABILITY ANALYSIS
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
    / "hospital_workload_reliability.csv"
)


# ==========================================================
# 1. LOAD DATASET AND MODEL
# ==========================================================

print("\nRefHealth AI")
print("HOSPITAL WORKLOAD MODEL RELIABILITY ANALYSIS")
print("=" * 70)

print("\nLOADING DATASET...")

df = pd.read_csv(DATA_PATH)

df["record_date"] = pd.to_datetime(df["record_date"])

print("Dataset records:", len(df))

print("\nLOADING WORKLOAD MODEL...")

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
# 4. CREATE CHRONOLOGICAL VALIDATION SET
# ==========================================================

print("\nCREATING VALIDATION DATASET...")

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
    raise ValueError("Validation dataset is empty.")


# ==========================================================
# 5. GENERATE PREDICTIONS
# ==========================================================

print("\nGENERATING WORKLOAD PREDICTIONS...")

predictions = model.predict(X_validation)

results = validation_df[
    ["hospital_id", "record_date"]
].copy()

results["actual_workload"] = y_validation

results["predicted_workload"] = predictions

results["is_correct"] = (
    results["actual_workload"]
    == results["predicted_workload"]
)

print("Predictions generated successfully.")


# ==========================================================
# 6. ANALYZE EACH HOSPITAL
# ==========================================================

print("\nHOSPITAL RELIABILITY RESULTS")
print("=" * 70)

hospital_results = []

hospital_ids = sorted(
    results["hospital_id"].unique()
)

class_labels = [
    "Low",
    "Medium",
    "High"
]

for hospital_id in hospital_ids:

    hospital_data = results[
        results["hospital_id"] == hospital_id
    ]

    actual = hospital_data["actual_workload"]

    predicted = hospital_data["predicted_workload"]

    total = len(hospital_data)

    correct = (
        hospital_data["is_correct"].sum()
    )

    incorrect = total - correct

    accuracy = accuracy_score(
        actual,
        predicted
    )

    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            actual,
            predicted,
            labels=class_labels,
            average="macro",
            zero_division=0
        )
    )

    hospital_results.append({
        "hospital_id": hospital_id,
        "total_predictions": total,
        "correct_predictions": correct,
        "incorrect_predictions": incorrect,
        "accuracy": accuracy,
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1
    })

    print(f"\nHOSPITAL: {hospital_id}")
    print("-" * 55)

    print("Total predictions:", total)

    print("Correct predictions:", correct)

    print("Incorrect predictions:", incorrect)

    print("Accuracy:", round(accuracy, 4))

    print("Macro Precision:", round(precision, 4))

    print("Macro Recall:", round(recall, 4))

    print("Macro F1:", round(f1, 4))


# ==========================================================
# 7. DISPLAY HOSPITAL COMPARISON
# ==========================================================

hospital_summary = pd.DataFrame(
    hospital_results
)

print("\n\nHOSPITAL PERFORMANCE COMPARISON")
print("=" * 70)

print(
    hospital_summary.round(4).to_string(
        index=False
    )
)


# ==========================================================
# 8. IDENTIFY THE STRONGEST AND WEAKEST HOSPITAL
# ==========================================================

print("\n\nHOSPITAL RELIABILITY RANKING")
print("=" * 70)

ranked_hospitals = hospital_summary.sort_values(
    by="macro_f1",
    ascending=False
)

print(
    ranked_hospitals[
        [
            "hospital_id",
            "accuracy",
            "macro_f1",
            "total_predictions"
        ]
    ].round(4).to_string(index=False)
)

best_hospital = ranked_hospitals.iloc[0]

worst_hospital = ranked_hospitals.iloc[-1]

print("\nBEST PERFORMING HOSPITAL:")

print(best_hospital["hospital_id"])

print("Macro F1:", round(best_hospital["macro_f1"], 4))

print("\nLOWEST PERFORMING HOSPITAL:")

print(worst_hospital["hospital_id"])

print("Macro F1:", round(worst_hospital["macro_f1"], 4))


# ==========================================================
# 9. ANALYZE WORKLOAD CLASS PERFORMANCE PER HOSPITAL
# ==========================================================

print("\n\nWORKLOAD CLASS PERFORMANCE BY HOSPITAL")
print("=" * 70)

for hospital_id in hospital_ids:

    hospital_data = results[
        results["hospital_id"] == hospital_id
    ]

    print(f"\nHOSPITAL: {hospital_id}")
    print("-" * 55)

    print(
        classification_report(
            hospital_data["actual_workload"],
            hospital_data["predicted_workload"],
            labels=class_labels,
            zero_division=0
        )
    )


# ==========================================================
# 10. CONFUSION MATRICES PER HOSPITAL
# ==========================================================

print("\nHOSPITAL CONFUSION MATRICES")
print("=" * 70)

for hospital_id in hospital_ids:

    hospital_data = results[
        results["hospital_id"] == hospital_id
    ]

    matrix = confusion_matrix(
        hospital_data["actual_workload"],
        hospital_data["predicted_workload"],
        labels=class_labels
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

    print(f"\n{hospital_id}")

    print(matrix_df.to_string())


# ==========================================================
# 11. SAVE HOSPITAL RELIABILITY RESULTS
# ==========================================================

hospital_summary.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\n\nANALYSIS COMPLETED")
print("=" * 70)

print("Hospital reliability results saved to:")

print(OUTPUT_PATH)

print("\nIMPORTANT:")
print(
    "Each hospital's evaluation uses a relatively small "
    "validation sample."
)

print(
    "Hospital rankings are experimental and may change "
    "with additional historical data."
)

print(
    "The dataset is synthetic and does not represent "
    "real-world hospital performance."
)
