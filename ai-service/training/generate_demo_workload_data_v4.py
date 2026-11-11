import csv
import random
from datetime import date, timedelta
from pathlib import Path


# ============================================================
# RefHealth AI
# V4 SYNTHETIC HOSPITAL WORKLOAD DATA GENERATOR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_v4.csv"
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
        "surge_probability": 0.08,
        "initial_occupancy": 0.55
    },

    "H002": {
        "total_beds": 120,
        "base_patients": 100,
        "referral_rate": 0.10,
        "completion_rate": 0.75,
        "admission_rate": 0.030,
        "discharge_rate": 0.16,
        "surge_probability": 0.05,
        "initial_occupancy": 0.50
    },

    "H003": {
        "total_beds": 80,
        "base_patients": 65,
        "referral_rate": 0.14,
        "completion_rate": 0.60,
        "admission_rate": 0.040,
        "discharge_rate": 0.13,
        "surge_probability": 0.12,
        "initial_occupancy": 0.60
    },

    "H004": {
        "total_beds": 100,
        "base_patients": 55,
        "referral_rate": 0.11,
        "completion_rate": 0.70,
        "admission_rate": 0.030,
        "discharge_rate": 0.16,
        "surge_probability": 0.07,
        "initial_occupancy": 0.45
    },

    "H005": {
        "total_beds": 70,
        "base_patients": 85,
        "referral_rate": 0.15,
        "completion_rate": 0.55,
        "admission_rate": 0.045,
        "discharge_rate": 0.12,
        "surge_probability": 0.15,
        "initial_occupancy": 0.65
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
# LATENT WORKLOAD TRANSITIONS
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
    Generate a new latent workload state.

    This state represents the simulated underlying
    operational pressure of the hospital.
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
    Derive the observed workload label from operational data.

    The latent state is deliberately not used as the label.
    """

    occupancy_proxy = (
        total_beds - available_beds
    ) / total_beds

    pending_pressure = (
        pending_referrals / total_beds
    )

    patient_pressure = (
        patient_volume / base_patients
    )

    # Combine three independent operational indicators.
    pressure_score = (
        0.40 * occupancy_proxy
        + 0.30 * min(pending_pressure / 0.40, 1.0)
        + 0.30 * min(patient_pressure / 1.65, 1.0)
    )

    if pressure_score >= 0.62:
        return "High"

    if pressure_score >= 0.36:
        return "Medium"

    return "Low"


# ============================================================
# PATIENT VOLUME SIMULATION
# ============================================================

def generate_patient_volume(
    base_patients,
    latent_workload,
    current_date,
    surge_probability
):

    workload_factors = {
        "Low": 0.85,
        "Medium": 1.10,
        "High": 1.45
    }

    workload_factor = workload_factors[
        latent_workload
    ]

    weekday_factor = (
        0.95
        if current_date.weekday() >= 5
        else 1.0
    )

    # Generic seasonal variation for demonstration only.
    seasonal_factor = (
        1.08
        if current_date.month in [6, 7, 8]
        else 1.0
    )

    normal_variation = random.uniform(
        0.90,
        1.10
    )

    surge_factor = 1.0

    if random.random() < surge_probability:
        surge_factor = random.uniform(
            1.20,
            1.60
        )

    patient_volume = int(
        base_patients
        * workload_factor
        * weekday_factor
        * seasonal_factor
        * normal_variation
        * surge_factor
    )

    return max(1, patient_volume)


# ============================================================
# REFERRAL QUEUE SIMULATION
# ============================================================

def update_pending_referrals(
    previous_pending,
    incoming_referrals,
    completion_rate
):

    total_queue = (
        previous_pending + incoming_referrals
    )

    processing_variation = random.uniform(
        0.85,
        1.15
    )

    effective_rate = (
        completion_rate * processing_variation
    )

    effective_rate = min(
        0.95,
        max(0.10, effective_rate)
    )

    completed_referrals = int(
        total_queue * effective_rate
    )

    pending = (
        total_queue - completed_referrals
    )

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

        initial_occupancy = config["initial_occupancy"]

        # ----------------------------------------------------
        # Initial hospital conditions
        # ----------------------------------------------------

        latent_workload = "Medium"

        pending_referrals = random.randint(3, 8)

        occupied_beds = int(
            total_beds * initial_occupancy
        )

        # ----------------------------------------------------
        # Generate 365 daily records
        # ----------------------------------------------------

        for day in range(DAYS):

            current_date = (
                start_date + timedelta(days=day)
            )

            # 1. Update latent workload state.
            if day > 0:

                latent_workload = next_workload(
                    latent_workload
                )

            # 2. Generate patient volume.
            patient_volume = generate_patient_volume(
                base_patients,
                latent_workload,
                current_date,
                surge_probability
            )

            # 3. Generate incoming referrals.
            incoming_referrals = max(
                1,
                int(
                    patient_volume
                    * referral_rate
                    * random.uniform(0.75, 1.25)
                )
            )

            # 4. Update pending referral queue.
            pending_referrals = update_pending_referrals(
                pending_referrals,
                incoming_referrals,
                completion_rate
            )

            # 5. Update bed availability.
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

            # 6. Derive workload from operational measurements.
            workload_level = classify_workload(
                patient_volume,
                base_patients,
                pending_referrals,
                available_beds,
                total_beds
            )

            # 7. Save the record.
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
        "V4 SYNTHETIC HOSPITAL WORKLOAD DATA GENERATOR"
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
        "Simulation parameters and workload thresholds "
        "are demonstration assumptions."
    )


if __name__ == "__main__":
    generate_data()