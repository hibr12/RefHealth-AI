# ```python
import csv
import random

from datetime import date, timedelta
from pathlib import Path


# ==========================================================
# PROJECT CONFIGURATION
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_v2.csv"
)

random.seed(2026)

DAYS = 365


# ==========================================================
# HOSPITAL CONFIGURATION
# ==========================================================

HOSPITALS = {
    "H001": {
        "total_beds": 60,
        "base_patients": 75,
        "referral_rate": 0.12,
        "recovery_rate": 0.65,
        "surge_risk": 0.08
    },
    "H002": {
        "total_beds": 120,
        "base_patients": 100,
        "referral_rate": 0.10,
        "recovery_rate": 0.75,
        "surge_risk": 0.05
    },
    "H003": {
        "total_beds": 80,
        "base_patients": 65,
        "referral_rate": 0.14,
        "recovery_rate": 0.60,
        "surge_risk": 0.12
    },
    "H004": {
        "total_beds": 100,
        "base_patients": 55,
        "referral_rate": 0.11,
        "recovery_rate": 0.70,
        "surge_risk": 0.07
    },
    "H005": {
        "total_beds": 70,
        "base_patients": 85,
        "referral_rate": 0.15,
        "recovery_rate": 0.55,
        "surge_risk": 0.15
    }
}


COLUMNS = [
    "record_id",
    "hospital_id",
    "record_date",
    "patient_volume",
    "incoming_referrals",
    "pending_referrals",
    "available_beds",
    "total_beds",
    "workload_level"
]


# ==========================================================
# WORKLOAD TRANSITION MODEL
# ==========================================================

TRANSITIONS = {
    "Low": [
        ("Low", 0.72),
        ("Medium", 0.24),
        ("High", 0.04)
    ],

    "Medium": [
        ("Low", 0.20),
        ("Medium", 0.60),
        ("High", 0.20)
    ],

    "High": [
        ("Low", 0.10),
        ("Medium", 0.30),
        ("High", 0.60)
    ]
}


def next_workload(current):

    states = TRANSITIONS[current]

    return random.choices(
        [state for state, probability in states],
        weights=[probability for state, probability in states],
        k=1
    )[0]


# ==========================================================
# WORKLOAD CLASSIFICATION
# ==========================================================

def classify_workload(
    patient_volume,
    pending_referrals,
    available_beds,
    total_beds
):

    occupancy_proxy = (
        (total_beds - available_beds) / total_beds
    )

    if (
        occupancy_proxy >= 0.80
        or pending_referrals >= 20
        or patient_volume >= 110
    ):
        return "High"

    if (
        occupancy_proxy >= 0.55
        or pending_referrals >= 8
        or patient_volume >= 70
    ):
        return "Medium"

    return "Low"


# ==========================================================
# GENERATE HOSPITAL DAILY RECORDS
# ==========================================================

def generate_data():

    records = []

    record_id = 1

    start_date = date.today() - timedelta(days=DAYS - 1)

    for hospital_id, config in HOSPITALS.items():

        total_beds = config["total_beds"]

        base_patients = config["base_patients"]

        referral_rate = config["referral_rate"]

        recovery_rate = config["recovery_rate"]

        surge_risk = config["surge_risk"]

        current_workload = "Medium"

        pending_referrals = random.randint(3, 8)

        occupied_beds = int(total_beds * 0.60)

        for day in range(DAYS):

            current_date = start_date + timedelta(days=day)

            # --------------------------------------------------
            # 1. WORKLOAD TRANSITIONS
            # --------------------------------------------------

            if day > 0:

                current_workload = next_workload(
                    current_workload
                )

            workload_factors = {
                "Low": 0.75,
                "Medium": 1.00,
                "High": 1.30
            }

            workload_factor = workload_factors[
                current_workload
            ]

            # --------------------------------------------------
            # 2. WEEKDAY AND SEASONAL VARIATION
            # --------------------------------------------------

            weekday_factor = (
                0.90
                if current_date.weekday() >= 5
                else 1.00
            )

            seasonal_factor = (
                1.10
                if current_date.month in [6, 7, 8]
                else 1.00
            )

            normal_variation = random.uniform(0.90, 1.10)

            # --------------------------------------------------
            # 3. UNEXPECTED PATIENT SURGES
            # --------------------------------------------------

            surge_factor = 1.0

            surge_event = (
                random.random() < surge_risk
            )

            if surge_event:

                surge_factor = random.uniform(
                    1.20,
                    1.65
                )

            patient_volume = int(
                base_patients
                * workload_factor
                * weekday_factor
                * seasonal_factor
                * normal_variation
                * surge_factor
            )

            patient_volume = max(
                1,
                patient_volume
            )

            # --------------------------------------------------
            # 4. INCOMING REFERRALS
            # --------------------------------------------------

            incoming_referrals = max(
                1,
                int(
                    patient_volume
                    * referral_rate
                    * random.uniform(0.75, 1.35)
                )
            )

            # --------------------------------------------------
            # 5. PENDING REFERRAL PRESSURE
            # --------------------------------------------------

            completed_referrals = int(
                pending_referrals
                * recovery_rate
                * random.uniform(0.70, 1.20)
            )

            pending_referrals = max(
                0,
                pending_referrals
                + incoming_referrals
                - completed_referrals
            )

            # --------------------------------------------------
            # 6. BED AVAILABILITY CHANGES
            # --------------------------------------------------

        # Simulate daily hospital admissions and discharges.

            new_admissions = int(
                patient_volume
                * random.uniform(0.04, 0.09)
            )

            discharged_patients = int(
                occupied_beds
                * random.uniform(0.08, 0.16)
            )

            occupied_beds = (
                occupied_beds
                + new_admissions
                - discharged_patients
            )

            occupied_beds = max(
                0,
                min(total_beds, occupied_beds)
            )

            # Some beds may temporarily be unavailable.
            unavailable_beds = int(
                total_beds
                * random.uniform(0.00, 0.05)
            )

            available_beds = max(
                0,
                total_beds
                - occupied_beds
                - unavailable_beds
            )
            # --------------------------------------------------
            # 7. FINAL WORKLOAD LABEL
            # --------------------------------------------------

            workload_level = classify_workload(
                patient_volume,
                pending_referrals,
                available_beds,
                total_beds
            )

            # --------------------------------------------------
            # 8. SAVE DAILY RECORD
            # --------------------------------------------------

            records.append([
                record_id,
                hospital_id,
                current_date.isoformat(),
                patient_volume,
                incoming_referrals,
                pending_referrals,
                available_beds,
                total_beds,
                workload_level
            ])

            record_id += 1

    # ======================================================
    # SAVE DATASET
    # ======================================================

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_PATH,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow(COLUMNS)

        writer.writerows(records)

    print("\nRefHealth AI")

    print("IMPROVED SYNTHETIC WORKLOAD DATA GENERATOR")

    print("=" * 60)

    print("\nTOTAL HOSPITALS:", len(HOSPITALS))

    print("DAYS PER HOSPITAL:", DAYS)

    print("TOTAL GENERATED RECORDS:", len(records))

    print("\nDATASET SAVED SUCCESSFULLY.")

    print("LOCATION:", OUTPUT_PATH)

    print("\nNOTICE: ALL GENERATED RECORDS ARE SYNTHETIC.")


if __name__ == "__main__":

    generate_data()
# ```
