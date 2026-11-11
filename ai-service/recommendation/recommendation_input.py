def get_recommendation_input():

    print("\nRefHealth AI")
    print("HOSPITAL RECOMMENDATION INPUT")
    print("=" * 50)

    required_service = input(
        "\nEnter required medical service (Emergency/Surgery): "
    ).strip()

    try:
        distance_km = float(
            input("Enter distance from referring facility (km): ")
        )

        if distance_km < 0:
            raise ValueError

    except ValueError:
        print("\nINVALID DISTANCE.")
        return None

    try:
        pending_referrals = int(
            input("Enter referring facility's pending referrals: ")
        )

        if pending_referrals < 0:
            raise ValueError

    except ValueError:
        print("\nINVALID NUMBER OF REFERRALS.")
        return None

    return {
        "required_service": required_service,
        "distance_km": distance_km,
        "pending_referrals": pending_referrals
    }


if __name__ == "__main__":

    referral = get_recommendation_input()

    if referral:
        print("\nREFERRAL INFORMATION:")
        print(referral)