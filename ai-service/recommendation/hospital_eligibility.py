import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_PATH = BASE_DIR / "datasets" / "raw" / "hospitals.csv"


def find_eligible_hospitals(required_service):

    df = pd.read_csv(DATASET_PATH)

    # Find hospitals providing the required service
    eligible = df[
        (df["service"].str.lower() == required_service.lower()) &
        (df["service_available"] == 1) &
        (df["available_beds"] > 0)
    ].copy()

    # Display relevant hospital information
    eligible = eligible[
    [
        "hospital_id",
        "hospital_name",
        "distance_km",
        "service",
        "hospital_workload",
        "pending_referrals",
        "service_available",
        "available_beds"
    ]
]

    return eligible


if __name__ == "__main__":

    print("\nRefHealth AI")
    print("HOSPITAL ELIGIBILITY ANALYSIS")
    print("=" * 50)

    required_service = "Emergency"

    print("\nREQUIRED SERVICE:", required_service)

    hospitals = find_eligible_hospitals(required_service)

    if hospitals.empty:
        print("\nNO ELIGIBLE HOSPITALS FOUND.")

    else:
        print("\nELIGIBLE HOSPITALS:")
        print(hospitals.to_string(index=False))

        print("\nTOTAL ELIGIBLE HOSPITALS:", len(hospitals))