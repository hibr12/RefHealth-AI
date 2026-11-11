import csv
import random
from datetime import date, timedelta
from pathlib import Path


# ============================================================
# RefHealth AI
# V6 SYNTHETIC HOSPITAL WORKLOAD DATA GENERATOR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_v6.csv"
)

random.seed(20261106)

DAYS = 365


# ============================================================
# HOSPITAL CONFIGURATIONS
# ============================================================

HOSPITALS = {
    "H001": {
        "total_beds": 60,
        "base_patients": 75,
        "referral_rate": 0.12,
        "completion_rate": 0.70,
        "admission_rate": 0.045,
        "discharge_rate": 0.13,
        "initial_occupancy": 0.45
    },

    "H002": {
        "total_beds": 120,
        "base_patients": 100,
        "referral_rate": 0.11,
        "completion_rate": 0.74,
        "admission_rate": 0.045,
        "discharge_rate": 0.12,
        "initial_occupancy": 0.45
    },

    "H003": {
        "total_beds": 80,
        "base_patients": 65,
        "referral_rate": 0.14,
        "completion_rate": 0.66,
        "admission_rate": 0.050,
        "discharge_rate": 0.13,
        "initial_occupancy": 0.48
    },

    "H004": {
        "total_beds": 100,
        "base_patients": 55,
        "referral_rate": 0.12,
        "completion_rate": 0.72,
        "admission_rate": 0.050,
        "discharge_rate": 0.14,
        "initial_occupancy": 0.45
    },

    "H005": {
        "total_beds": 70,
        "base_patients": 85,
        "referral_rate": 0.14,
        "completion_rate": 0.66,
        "admission_rate": 0.045,
        "discharge_rate": 0.13,
        "initial_occupancy": 0.48
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
        ("Low", 0.65),
        ("Medium", 0.28),
        ("High", 0.07)
    ],

    "Medium": [
        ("Low", 0.25),
        ("Medium", 0.55),
        ("High", 0.20)
    ],

    "High": [
        ("Low", 0.18),
        ("Medium", 0.37),
        ("High", 0.45)
    ]
}


def next_workload(current):

    states = TRANSITIONS[current]

    return random.choices(
        [state for state, _ in states],
        weights=[weight for _, weight in states],
        k=1
    )[0]


# ============================================================
# DYNAMIC HOSPITAL OPERATIONAL SCENARIOS
# ============================================================

def generate_operational_scenario():

    duration = random.randint(30, 75)

    scenario = {
        "remaining_days": duration,
        "demand_multiplier": random.uniform(0.78, 1.35),
        "capacity_multiplier": random.uniform(0.72, 1.18)
    }

    return scenario


def update_operational_scenario(scenario):

    scenario["remaining_days"] -= 1

    if scenario["remaining_days"] <= 0:

        scenario = generate_operational_scenario()

    return scenario


# ============================================================
# PATIENT DEMAND
# ============================================================

def generate_patient_volume(
    base_patients,
    latent_workload,
    current_date,
    demand_multiplier,
    temporary_surge
):

    workload_factors = {
        "Low": 0.78,
        "Medium": 1.10,
        "High": 1.48
    }

    weekday_factor = (
        0.92 if current_date.weekday() >= 5 else 1.0
    )

    seasonal_factor = (
        1.12 if current_date.month in [6, 7, 8]
        else 0.94 if current_date.month in [1, 2]
        else 1.0
    )

    random_variation = random.uniform(0.82, 1.18)

    surge_factor = (
        random.uniform(1.20, 1.65)
        if temporary_surge
        else 1.0
    )

    patient_volume = int(
        base_patients
        * workload_factors[latent_workload]
        * weekday_factor
        * seasonal_factor
        * random_variation
        * demand_multiplier
        * surge_factor
    )

    return max(1, patient_volume)


# ============================================================
# REFERRAL QUEUE
# ============================================================

def update_pending_referrals(
    previous_pending,
    incoming_referrals,
    completion_rate,
    capacity_factor
):

    total_queue = previous_pending + incoming_referrals

    effective_rate = (
        completion_rate
        * capacity_factor
        * random.uniform(0.85, 1.15)
    )

    effective_rate = min(
        0.95,
        max(0.10, effective_rate)
    )

    completed = int(total_queue * effective_rate)

    return max(0, total_queue - completed)


# ============================================================
# BED AVAILABILITY
# ============================================================

def update_bed_availability(
    occupied_beds,
    total_beds,
    patient_volume,
    admission_rate,
    discharge_rate,
    capacity_factor
):

    admissions = int(
        patient_volume
        * admission_rate
        * random.uniform(0.80, 1.25)
    )

    discharges = int(
        occupied_beds
        * discharge_rate
        * capacity_factor
        * random.uniform(0.80, 1.20)
    )

    occupied_beds += admissions - discharges

    occupied_beds = max(
        0,
        min(total_beds, occupied_beds)
    )

    unavailable_beds = int(
        total_beds * random.uniform(0.00, 0.06)
    )

    available_beds = max(
        0,
        total_beds - occupied_beds - unavailable_beds
    )

    return occupied_beds, available_beds


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

    occupancy_proxy = (
        total_beds - available_beds
    ) / total_beds

    pending_pressure = (
        pending_referrals / total_beds
    )

    patient_pressure = (
        patient_volume / base_patients
    )

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
# DATA GENERATION
# ============================================================

def generate_data():

    records = []

    record_id = 1

    start_date = date.today() - timedelta(days=DAYS - 1)

    for hospital_id, config in HOSPITALS.items():

        total_beds = config["total_beds"]

        base_patients = config["base_patients"]

        latent_workload = random.choice(
            ["Low", "Medium", "High"]
        )

        pending_referrals = random.randint(2, 8)

        occupied_beds = int(
            total_beds * config["initial_occupancy"]
        )

        # Each hospital begins with its own operational scenario.
        scenario = generate_operational_scenario()

        surge_remaining = 0

        recovery_remaining = 0

        for day in range(DAYS):

            current_date = start_date + timedelta(days=day)

            # ------------------------------------------------
            # UPDATE LATENT WORKLOAD
            # ------------------------------------------------

            if day > 0:

                latent_workload = next_workload(
                    latent_workload
                )

            # ------------------------------------------------
            # UPDATE OPERATIONAL SCENARIO
            # ------------------------------------------------

            if day > 0:

                scenario = update_operational_scenario(
                    scenario
                )

            demand_multiplier = scenario["demand_multiplier"]

            capacity_multiplier = scenario["capacity_multiplier"]

            # ------------------------------------------------
            # TEMPORARY DEMAND SURGES
            # ------------------------------------------------

            if (
                surge_remaining == 0
                and recovery_remaining == 0
                and random.random() < 0.08
            ):

                surge_remaining = random.randint(2, 5)

            temporary_surge = False

            if surge_remaining > 0:

                temporary_surge = True

                surge_remaining -= 1

                recovery_remaining = 3

            elif recovery_remaining > 0:

                recovery_remaining -= 1

            # ------------------------------------------------
            # DAILY PROCESSING CAPACITY
            # ------------------------------------------------

            daily_capacity_factor = random.uniform(
                0.90,
                1.10
            )

            # Temporary operational disruption.
            if random.random() < 0.10:

                daily_capacity_factor *= random.uniform(
                    0.65,
                    0.85
                )

            capacity_factor = (
                daily_capacity_factor
                * capacity_multiplier
            )

            capacity_factor = min(
                1.20,
                max(0.45, capacity_factor)
            )

            # ------------------------------------------------
            # PATIENT VOLUME
            # ------------------------------------------------

            patient_volume = generate_patient_volume(
                base_patients,
                latent_workload,
                current_date,
                demand_multiplier,
                temporary_surge
            )

            # ------------------------------------------------
            # INCOMING REFERRALS
            # ------------------------------------------------

            incoming_referrals = max(
                1,
                int(
                    patient_volume
                    * config["referral_rate"]
                    * random.uniform(0.75, 1.25)
                )
            )

            # ------------------------------------------------
            # PENDING REFERRALS
            # ------------------------------------------------

            pending_referrals = update_pending_referrals(
                pending_referrals,
                incoming_referrals,
                config["completion_rate"],
                capacity_factor
            )

            # ------------------------------------------------
            # BED AVAILABILITY
            # ------------------------------------------------

            occupied_beds, available_beds = update_bed_availability(
                occupied_beds,
                total_beds,
                patient_volume,
                config["admission_rate"],
                config["discharge_rate"],
                capacity_factor
            )

            # ------------------------------------------------
            # WORKLOAD CLASSIFICATION
            # ------------------------------------------------

            workload_level = classify_workload(
                patient_volume,
                base_patients,
                pending_referrals,
                available_beds,
                total_beds
            )

            # ------------------------------------------------
            # SAVE RECORD
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

    print("V6 SYNTHETIC HOSPITAL WORKLOAD DATA GENERATOR")

    print("=" * 65)

    print("TOTAL HOSPITALS:", len(HOSPITALS))

    print("DAYS PER HOSPITAL:", DAYS)

    print("TOTAL GENERATED RECORDS:", len(records))

    print("\nDATASET SAVED SUCCESSFULLY.")

    print("LOCATION:", OUTPUT_PATH)

    print("\nNOTICE: ALL GENERATED RECORDS ARE SYNTHETIC.")

    print("Simulation parameters are demonstration assumptions.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    generate_data()