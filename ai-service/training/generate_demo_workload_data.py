import csv
import random

from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

OUTPUT_PATH = (
    BASE_DIR
    / "datasets"
    / "raw"
    / "hospital_daily_history_demo.csv"
)

random.seed(42)

HOSPITALS = {
    "H001": {"total_beds": 60, "base_patients": 75},
    "H002": {"total_beds": 120, "base_patients": 100},
    "H003": {"total_beds": 80, "base_patients": 65},
    "H004": {"total_beds": 100, "base_patients": 55},
    "H005": {"total_beds": 70, "base_patients": 85},
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


def next_workload(current):

    transitions = {
        "Low": [
            ("Low", 0.80),
            ("Medium", 0.18),
            ("High", 0.02)
        ],
        "Medium": [
            ("Low", 0.15),
            ("Medium", 0.70),
            ("High", 0.15)
        ],
        "High": [
            ("Low", 0.05),
            ("Medium", 0.25),
            ("High", 0.70)
        ]
    }

    states = transitions[current]

    return random.choices(
        [state for state, probability in states],
        weights=[probability for state, probability in states],
        k=1
    )[0]


def generate_data():

    records = []

    start_date = date.today() - timedelta(days=89)

    record_id = 1

    workload_factors = {
        "Low": 0.75,
        "Medium": 1.0,
        "High": 1.30
    }

    for hospital_id, config in HOSPITALS.items():

        total_beds = config["total_beds"]
        base_patients = config["base_patients"]

        current_workload = "Medium"

        for day in range(90):

            current_date = start_date + timedelta(days=day)

            if day > 0:
                current_workload = next_workload(
                    current_workload
                )

            weekday_factor = (
                0.90
                if current_date.weekday() >= 5
                else 1.0
            )

            workload_factor = workload_factors[
                current_workload
            ]

            variation = random.uniform(0.90, 1.10)

            patient_volume = int(
                base_patients
                * workload_factor
                * weekday_factor
                * variation
            )

            incoming_referrals = max(
                1,
                int(
                    patient_volume
                    * random.uniform(0.08, 0.15)
                )
            )

            pending_factor = {
                "Low": 0.7,
                "Medium": 1.2,
                "High": 2.0
            }[current_workload]

            pending_referrals = max(
                0,
                int(
                    incoming_referrals
                    * pending_factor
                    * random.uniform(0.8, 1.2)
                )
            )

            occupancy_ranges = {
                "Low": (0.30, 0.55),
                "Medium": (0.55, 0.80),
                "High": (0.80, 0.97)
            }

            occupancy = random.uniform(
                *occupancy_ranges[current_workload]
            )

            occupied_beds = int(
                total_beds * occupancy
            )

            available_beds = (
                total_beds - occupied_beds
            )

            records.append([
                record_id,
                hospital_id,
                current_date.isoformat(),
                patient_volume,
                incoming_referrals,
                pending_referrals,
                available_beds,
                total_beds,
                current_workload
            ])

            record_id += 1

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
    print("SYNTHETIC HOSPITAL WORKLOAD DATA GENERATION")
    print("=" * 55)

    print("\nTOTAL HOSPITALS:", len(HOSPITALS))
    print("DAYS PER HOSPITAL: 90")
    print("TOTAL GENERATED RECORDS:", len(records))

    print("\nDATASET SAVED SUCCESSFULLY.")
    print("LOCATION:", OUTPUT_PATH)

    print("\nNOTICE: ALL GENERATED RECORDS ARE SYNTHETIC.")


if __name__ == "__main__":
    generate_data()