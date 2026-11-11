import csv
import random
from datetime import date, timedelta
from pathlib import Path


# ============================================================
# RefHealth AI
# V3 SYNTHETIC HOSPITAL WORKLOAD DATA GENERATOR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_v3.csv"
)

random.seed(2026)

DAYS = 365


# ============================================================
# HOSPITAL CONFIGURATIONS
# ============================================================

HOSPITALS = {
    "H001": {
        "total_beds": 60,
        "base_patients": 75,
        "referral_rate": 0.12,
        "completion_rate": 0.65,
        "admission_rate": 0.035,
        "discharge_rate": 0.14,
        "surge_probability": 0.08
    },

    "H002": {
        "total_beds": 120,
        "base_patients": 100,
        "referral_rate": 0.10,
        "completion_rate": 0.75,
        "admission_rate": 0.030,
        "discharge_rate": 0.16,
        "surge_probability": 0.05
    },

    "H003": {
        "total_beds": 80,
        "base_patients": 65,
        "referral_rate": 0.14,
        "completion_rate": 0.60,
        "admission_rate": 0.040,
        "discharge_rate": 0.13,
        "surge_probability": 0.12
    },

    "H004": {
        "total_beds": 100,
        "base_patients": 55,
        "referral_rate": 0.11,
        "completion_rate": 0.70,
        "admission_rate": 0.030,
        "discharge_rate": 0.16,
        "surge_probability": 0.07
    },

    "H005": {
        "total_beds": 70,
        "base_patients": 85,
        "referral_rate": 0.15,
        "completion_rate": 0.55,
        "admission_rate": 0.045,
        "discharge_rate": 0.12,
        "surge_probability": 0.15
    }
}


# ============================================================
# DATASET COLUMNS
# ============================================================

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


# ============================================================
# WORKLOAD TRANSITION PROBABILITIES
# ============================================================

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
    """
    Generate the next workload state using
    the previous day's workload.
    """

    states = TRANSITIONS[current]

    return random.choices(
        [state for state, probability in states],
        weights=[
            probability
            for state, probability in states
        ],
        k=1
    )[0]


# ============================================================
# WORKLOAD CLASSIFICATION
# ============================================================

def classify_workload(
    patient_volume,
    base_patients,
    pending_referrals,
    available_beds,
    total_beds
):
    """
    Classify workload using multiple operational indicators.

    These thresholds are synthetic demonstration assumptions.
    They are not clinically validated thresholds.
    """

    occupancy_proxy = (
        total_beds - available_beds
    ) / total_beds

    pending_per_bed = (
        pending_referrals / total_beds
    )

    patient_pressure = (
        patient_volume / base_patients
    )

    # High workload
    if (
        occupancy_proxy >= 0.82
        or pending_per_bed >= 0.40
        or patient_pressure >= 1.65
    ):
        return "High"

    # Medium workload
    if (
        occupancy_proxy >= 0.60
        or pending_per_bed >= 0.20
        or patient_pressure >= 1.15
    ):
        return "Medium"

    return "Low"


# ============================================================
# REFERRAL QUEUE SIMULATION
# ============================================================

def update_pending_referrals(
    previous_pending,
    incoming_referrals,
    completion_rate
):
    """
    Simulate referral processing.

    Completed referrals depend on the total available queue.
    This creates a more stable queue than using only
    previous pending referrals.
    """

    total_queue = previous_pending + incoming_referrals

    processing_variation = random.uniform(0.85, 1.15)

    effective_completion_rate = (
        completion_rate * processing_variation
    )

    effective_completion_rate = min(
        0.95,
        max(0.10, effective_completion_rate)
    )

    completed_referrals = int(
        total_queue * effective_completion_rate
    )

    pending = total_queue - completed_referrals

    return max(0, pending)


# ============================================================
# BED AVAILABILITY SIMULATION
# ============================================================

def update_bed_availability(
    occupied_beds,
    total_beds,
    patient_volume,
    admission_rate,
    discharge_rate
):
    """
    Simulate hospital admissions, discharges,
    and temporarily unavailable beds.

    The occupancy value is simulated, not actual hospital data.
    """

    new_admissions = int(
        patient_volume
        * admission_rate
        * random.uniform(0.80, 1.20)
    )

    discharged_patients = int(
        occupied_beds
        * discharge_rate
        * random.uniform(0.85, 1.15)
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

    unavailable_beds = int(
        total_beds * random.uniform(0.00, 0.04)
    )

    available_beds = max(
        0,
        total_beds
        - occupied_beds
        - unavailable_beds
    )

    return occupied_beds, available_beds


# ============================================================
# MAIN DATA GENERATOR
# ============================================================

def generate_data():

    records = []

    record_id = 1

    start_date = (
        date.today()
        - timedelta(days=DAYS - 1)
    )

    for hospital_id, config in HOSPITALS.items():

        total_beds = config["total_beds"]
        base_patients = config["base_patients"]

        referral_rate = config["referral_rate"]
        completion_rate = config["completion_rate"]

        admission_rate = config["admission_rate"]
        discharge_rate = config["discharge_rate"]

        surge_probability = config["surge_probability"]

        # Initial hospital conditions
        current_workload = "Medium"

        pending_referrals = random.randint(3, 8)

        occupied_beds = int(total_beds * 0.55)

        for day in range(DAYS):

            current_date = (
                start_date + timedelta(days=day)
            )

            # ------------------------------------------------
            # 1. Determine workload state
            # ------------------------------------------------

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

            # ------------------------------------------------
            # 2. Daily patient volume
            # ------------------------------------------------

            weekday_factor = (
                0.95
                if current_date.weekday() >= 5
                else 1.00
            )

            normal_variation = random.uniform(
                0.90,
                1.10
            )

            surge_factor = 1.00

            if random.random() < surge_probability:

                surge_factor = random.uniform(
                    1.20,
                    1.60
                )

            patient_volume = int(
                base_patients
                * workload_factor
                * weekday_factor
                * normal_variation
                * surge_factor
            )

            patient_volume = max(
                1,
                patient_volume
            )

            # ------------------------------------------------
            # 3. Incoming referrals
            # ------------------------------------------------

            incoming_referrals = max(
                1,
                int(
                    patient_volume
                    * referral_rate
                    * random.uniform(0.75, 1.25)
                )
            )

            # ------------------------------------------------
            # 4. Pending referrals
            # ------------------------------------------------

            pending_referrals = update_pending_referrals(
                pending_referrals,
                incoming_referrals,
                completion_rate
            )

            # ------------------------------------------------
            # 5. Bed availability
            # ------------------------------------------------

            (
                occupied_beds,
                available_beds
            ) = update_bed_availability(
                occupied_beds,
                total_beds,
                patient_volume,
                admission_rate,
                discharge_rate
            )

            # ------------------------------------------------
            # 6. Workload classification
            # ------------------------------------------------

            workload_level = classify_workload(
                patient_volume,
                base_patients,
                pending_referrals,
                available_beds,
                total_beds
            )

            # Important:
            # The next day's transition starts from the
            # workload label saved for this day.
            current_workload = workload_level

            # ------------------------------------------------
            # 7. Save daily hospital record
            # ------------------------------------------------

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

    # ========================================================
    # SAVE DATASET
    # ========================================================

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

    # ========================================================
    # GENERATION REPORT
    # ========================================================

    print("\nRefHealth AI")

    print(
        "V3 SYNTHETIC HOSPITAL WORKLOAD DATA GENERATOR"
    )

    print("=" * 65)

    print("\nTOTAL HOSPITALS:", len(HOSPITALS))

    print("DAYS PER HOSPITAL:", DAYS)

    print("TOTAL GENERATED RECORDS:", len(records))

    print("\nDATASET SAVED SUCCESSFULLY.")

    print("LOCATION:", OUTPUT_PATH)

    print(
        "\nNOTICE: ALL GENERATED RECORDS ARE SYNTHETIC."
    )

    print(
        "The workload thresholds and simulation rates "
        "are demonstration assumptions."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    generate_data()