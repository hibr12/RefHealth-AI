import sqlite3
import json

from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "datasets" / "feedback.db"

# Monitor real records only.
# Change to "test" temporarily if you want to inspect test records.
RECORD_TYPE_TO_MONITOR = "real"

BASELINE_DAYS = 30
RECENT_DAYS = 7

MINIMUM_BASELINE_RECORDS = 5
MINIMUM_RECENT_RECORDS = 5

DISTANCE_CHANGE_THRESHOLD = 10
PENDING_CHANGE_THRESHOLD = 15
CATEGORICAL_CHANGE_THRESHOLD = 0.30

FEATURES = [
    "distance_km",
    "pending_referrals",
    "hospital_workload",
    "service_available",
    "submission_hour",
    "submission_day"
]


def load_referral_data():

    if not DATABASE_PATH.exists():
        raise FileNotFoundError("Feedback database not found.")

    connection = sqlite3.connect(DATABASE_PATH)

    try:

        cursor = connection.cursor()

        cursor.execute("""
            SELECT referral_data, predicted_at, record_type
            FROM predictions
            WHERE referral_data IS NOT NULL
            AND predicted_at IS NOT NULL
            AND record_type = ?
            ORDER BY predicted_at ASC
        """, (RECORD_TYPE_TO_MONITOR,))

        records = cursor.fetchall()

        referrals = []

        for record in records:

            try:

                referral = json.loads(record[0])

                if not all(feature in referral for feature in FEATURES):
                    continue

                referral["predicted_at"] = record[1]

                referrals.append(referral)

            except (json.JSONDecodeError, TypeError):
                continue

        return pd.DataFrame(referrals)

    finally:
        connection.close()


def split_data_by_time(data):

    now = datetime.now(timezone.utc)

    recent_start = now - timedelta(days=RECENT_DAYS)

    baseline_start = now - timedelta(days=BASELINE_DAYS)

    data["predicted_at"] = pd.to_datetime(
        data["predicted_at"],
        utc=True,
        errors="coerce"
    )

    data = data.dropna(subset=["predicted_at"])

    baseline = data[
        (data["predicted_at"] >= baseline_start)
        & (data["predicted_at"] < recent_start)
    ]

    recent = data[
        data["predicted_at"] >= recent_start
    ]

    return baseline, recent


def validate_data(baseline, recent):

    print("\nBASELINE RECORDS:", len(baseline))

    print("RECENT RECORDS:", len(recent))

    if len(baseline) < MINIMUM_BASELINE_RECORDS:

        print("\nINSUFFICIENT BASELINE DATA.")

        print("Required:", MINIMUM_BASELINE_RECORDS)

        print("Available:", len(baseline))

        return False

    if len(recent) < MINIMUM_RECENT_RECORDS:

        print("\nINSUFFICIENT RECENT DATA.")

        print("Required:", MINIMUM_RECENT_RECORDS)

        print("Available:", len(recent))

        return False

    return True


def check_numerical_drift(
    baseline,
    recent,
    feature,
    threshold
):

    baseline_mean = baseline[feature].mean()

    recent_mean = recent[feature].mean()

    difference = abs(recent_mean - baseline_mean)

    print("\nFEATURE:", feature)

    print("Baseline average:", round(baseline_mean, 2))

    print("Recent average:", round(recent_mean, 2))

    print("Difference:", round(difference, 2))

    if difference >= threshold:

        print("STATUS: POSSIBLE DATA DRIFT DETECTED")

        return True

    print("STATUS: NO THRESHOLD BREACH")

    return False


def check_categorical_drift(
    baseline,
    recent,
    feature
):

    baseline_distribution = (
        baseline[feature]
        .value_counts(normalize=True)
    )

    recent_distribution = (
        recent[feature]
        .value_counts(normalize=True)
    )

    categories = set(baseline_distribution.index) | set(
        recent_distribution.index
    )

    differences = {}

    for category in categories:

        baseline_value = baseline_distribution.get(category, 0)

        recent_value = recent_distribution.get(category, 0)

        differences[category] = abs(
            baseline_value - recent_value
        )

    maximum_difference = max(differences.values(), default=0)

    print("\nFEATURE:", feature)

    print("Baseline distribution:", baseline_distribution.to_dict())

    print("Recent distribution:", recent_distribution.to_dict())

    print("Maximum distribution change:", round(maximum_difference, 4))

    if maximum_difference >= CATEGORICAL_CHANGE_THRESHOLD:

        print("STATUS: POSSIBLE DISTRIBUTION DRIFT DETECTED")

        return True

    print("STATUS: NO CONFIGURED THRESHOLD BREACH")

    return False


def monitor_data_drift():

    print("\nRefHealth AI")

    print("TIME-BASED DATA DRIFT MONITORING")

    print("=" * 50)

    print("RECORD TYPE:", RECORD_TYPE_TO_MONITOR)

    data = load_referral_data()

    print("\nTOTAL RECORDS:", len(data))

    if data.empty:

        print("\nNO RECORDS AVAILABLE FOR MONITORING.")

        return

    baseline, recent = split_data_by_time(data)

    print("\nBASELINE PERIOD: Previous 30 days, excluding latest 7 days")

    print("RECENT PERIOD: Latest 7 days")

    if not validate_data(baseline, recent):

        print("\nDRIFT MONITORING CANNOT CONTINUE.")

        return

    baseline = baseline.reset_index(drop=True)

    recent = recent.reset_index(drop=True)

    print("\nNUMERICAL FEATURE MONITORING")

    print("-" * 50)

    drift_detected = False

    if check_numerical_drift(
        baseline,
        recent,
        "distance_km",
        DISTANCE_CHANGE_THRESHOLD
    ):

        drift_detected = True

    if check_numerical_drift(
        baseline,
        recent,
        "pending_referrals",
        PENDING_CHANGE_THRESHOLD
    ):

        drift_detected = True

    print("\nCATEGORICAL FEATURE MONITORING")

    print("-" * 50)

    for feature in [
        "hospital_workload",
        "service_available",
        "submission_day"
    ]:

        if check_categorical_drift(
            baseline,
            recent,
            feature
        ):

            drift_detected = True

    print("\nFINAL DRIFT REPORT")

    print("=" * 50)

    if drift_detected:

        print("POSSIBLE DATA DRIFT DETECTED.")

        print("Investigate changes in incoming referral patterns.")

    else:

        print("NO CONFIGURED DRIFT THRESHOLD WAS BREACHED.")

    print("\nDRIFT MONITORING COMPLETED.")


if __name__ == "__main__":

    try:

        monitor_data_drift()

    except sqlite3.Error as error:

        print("\nDATABASE ERROR:", error)

    except FileNotFoundError as error:

        print("\nFILE ERROR:", error)

    except Exception as error:

        print("\nUNEXPECTED ERROR:", error)