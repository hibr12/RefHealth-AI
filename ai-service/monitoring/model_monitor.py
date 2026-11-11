import sqlite3
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)


# ==========================================
# 1. CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "datasets" / "feedback.db"

MINIMUM_RECORDS = 30

MINIMUM_RECALL = 0.80
MINIMUM_PRECISION = 0.70
MINIMUM_F1_SCORE = 0.75


# ==========================================
# 2. LOAD COMPLETED PREDICTIONS
# ==========================================

def load_completed_predictions():

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                model_version,
                record_type,
                predicted_result,
                actual_result
            FROM predictions
            WHERE actual_result IS NOT NULL
        """)

        return cursor.fetchall()

    finally:
        connection.close()


# ==========================================
# 3. CALCULATE PERFORMANCE METRICS
# ==========================================

def calculate_metrics(records):

    actual = [int(record[3]) for record in records]

    predicted = [int(record[2]) for record in records]

    accuracy = accuracy_score(actual, predicted)

    precision = precision_score(
        actual,
        predicted,
        zero_division=0
    )

    recall = recall_score(
        actual,
        predicted,
        zero_division=0
    )

    f1 = f1_score(
        actual,
        predicted,
        zero_division=0
    )

    matrix = confusion_matrix(
        actual,
        predicted,
        labels=[0, 1]
    )

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "confusion_matrix": matrix.tolist()
    }


# ==========================================
# 4. DETECT PERFORMANCE DEGRADATION
# ==========================================

def detect_performance_degradation(metrics):

    problems = []

    if metrics["recall"] < MINIMUM_RECALL:
        problems.append(
            "Recall is below the required threshold."
        )

    if metrics["precision"] < MINIMUM_PRECISION:
        problems.append(
            "Precision is below the required threshold."
        )

    if metrics["f1_score"] < MINIMUM_F1_SCORE:
        problems.append(
            "F1-score is below the required threshold."
        )

    if problems:
        return {
            "status": "PERFORMANCE WARNING",
            "problems": problems
        }

    return {
        "status": "PERFORMANCE ACCEPTABLE",
        "problems": []
    }


# ==========================================
# 5. MONITOR MODEL PERFORMANCE
# ==========================================

def monitor_models():

    print("\nRefHealth AI")
    print("AUTOMATED MODEL MONITORING")
    print("=" * 50)

    records = load_completed_predictions()

    if not records:
        print("\nNO COMPLETED PREDICTIONS FOUND.")
        print("Waiting for actual referral outcomes.")
        return

    # Validate database records
    valid_records = []

    for record in records:

        model_version, record_type, predicted, actual = record

        if predicted not in (0, 1) or actual not in (0, 1):
            print("Skipping invalid prediction record.")
            continue

        valid_records.append(record)

    if not valid_records:
        print("\nNO VALID COMPLETED PREDICTIONS FOUND.")
        return

    # Group records by model version and record type
    groups = {}

    for record in valid_records:

        key = (record[0], record[1])

        if key not in groups:
            groups[key] = []

        groups[key].append(record)

    # Evaluate each group
    for key, group_records in groups.items():

        model_version, record_type = key

        print("\nMODEL VERSION:", model_version)
        print("RECORD TYPE:", record_type)
        print("COMPLETED RECORDS:", len(group_records))

        print("-" * 50)

        metrics = calculate_metrics(group_records)

        print("Accuracy:", round(metrics["accuracy"], 4))
        print("Precision:", round(metrics["precision"], 4))
        print("Recall:", round(metrics["recall"], 4))
        print("F1-score:", round(metrics["f1_score"], 4))

        print(
            "Confusion Matrix:",
            metrics["confusion_matrix"]
        )

        # Insufficient data check
        if len(group_records) < MINIMUM_RECORDS:

            print("\nPERFORMANCE STATUS: INSUFFICIENT DATA")

            print(
                "WARNING: More completed records are required."
            )

        else:

            status = detect_performance_degradation(metrics)

            print("\nPERFORMANCE STATUS:", status["status"])

            for problem in status["problems"]:
                print("WARNING:", problem)

        # Data type notice
        if record_type == "test":

            print(
                "\nNOTICE: Test records are not clinical performance evidence."
            )

        elif record_type == "real":

            print(
                "\nNOTICE: Real-world metrics require data-quality "
                "and clinical validation."
            )

    print("\nMONITORING COMPLETED.")


# ==========================================
# 6. EXECUTION
# ==========================================

if __name__ == "__main__":

    try:
        monitor_models()

    except sqlite3.Error as error:
        print("\nDATABASE ERROR:", error)

    except FileNotFoundError as error:
        print("\nFILE ERROR:", error)

    except Exception as error:
        print("\nUNEXPECTED ERROR:", error)