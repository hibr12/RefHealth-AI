from recommendation.recommendation_input import get_recommendation_input
from recommendation.hospital_eligibility import find_eligible_hospitals


def generate_recommendations():

    referral = get_recommendation_input()

    if referral is None:
        return

    required_service = referral["required_service"]

    eligible_hospitals = find_eligible_hospitals(required_service)

    print("\nRefHealth AI")
    print("HOSPITAL RECOMMENDATION ENGINE")
    print("=" * 60)

    if eligible_hospitals.empty:
        print("\nNO ELIGIBLE HOSPITALS FOUND.")
        return

    print("\nREFERRAL SERVICE:", required_service.upper())

    print("\nELIGIBLE HOSPITALS:")
    print(
        eligible_hospitals.to_string(index=False)
    )

    print("\nTOTAL ELIGIBLE HOSPITALS:", len(eligible_hospitals))


if __name__ == "__main__":
    generate_recommendations()