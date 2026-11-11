from recommendation.hospital_eligibility import find_eligible_hospitals


def analyze_hospitals(required_service):

    hospitals = find_eligible_hospitals(required_service)

    if hospitals.empty:
        print("NO ELIGIBLE HOSPITALS FOUND.")
        return

    print("\nRefHealth AI")
    print("HOSPITAL CAPACITY ANALYSIS")
    print("=" * 60)

    for _, hospital in hospitals.iterrows():

        print("\nHospital:", hospital["hospital_name"])
        print("Distance:", hospital["distance_km"], "km")
        print("Workload:", hospital["hospital_workload"])
        print("Pending referrals:", hospital["pending_referrals"])
        print("Available beds:", hospital["available_beds"])

        print("-" * 40)

    print("\nTOTAL HOSPITALS ANALYZED:", len(hospitals))


if __name__ == "__main__":

    service = input(
        "Enter required medical service (Emergency/Surgery): "
    ).strip()

    analyze_hospitals(service)