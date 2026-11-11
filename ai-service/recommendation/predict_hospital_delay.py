from datetime import datetime

from recommendation.hospital_eligibility import find_eligible_hospitals
from prediction.predict import predict_referral_delay


def predict_hospital_delays(required_service):

    hospitals = find_eligible_hospitals(required_service)

    if hospitals.empty:
        print("\nNO ELIGIBLE HOSPITALS FOUND.")
        return

    current_time = datetime.now()

    submission_hour = current_time.hour
    submission_day = current_time.strftime("%A")

    results = []

    print("\nRefHealth AI")
    print("PREDICTIVE HOSPITAL DELAY ANALYSIS")
    print("=" * 60)

    for _, hospital in hospitals.iterrows():

        referral_data = {
            "distance_km": float(hospital["distance_km"]),
            "hospital_workload": hospital["hospital_workload"],
            "pending_referrals": int(hospital["pending_referrals"]),
            "service_available": int(hospital["service_available"]),
            "submission_hour": submission_hour,
            "submission_day": submission_day
        }

        prediction = predict_referral_delay(referral_data)

        results.append({
            "hospital_id": hospital["hospital_id"],
            "hospital_name": hospital["hospital_name"],
            "distance_km": float(hospital["distance_km"]),
            "hospital_workload": hospital["hospital_workload"],
            "pending_referrals": int(hospital["pending_referrals"]),
            "available_beds": int(hospital["available_beds"]),
            "delay_probability": prediction["delay_probability"],
            "predicted_result": prediction["result"],
            "model_version": prediction["model_version"]
        })

    # Sort hospitals by predicted delay probability
    results.sort(
        key=lambda hospital: hospital["delay_probability"]
    )

    # Display hospital comparison
    print("\nPREDICTIVE HOSPITAL COMPARISON:")

    for index, result in enumerate(results, start=1):

        print(f"\nRANK: {index}")
        print("Hospital:", result["hospital_name"])
        print("Distance:", result["distance_km"], "km")
        print("Workload:", result["hospital_workload"])
        print("Pending referrals:", result["pending_referrals"])
        print("Available beds:", result["available_beds"])
        print("Predicted delay probability:", result["delay_probability"])
        print("Prediction:", result["predicted_result"])
        print("Model version:", result["model_version"])

        print("-" * 45)

    print("\nTOTAL HOSPITALS ANALYZED:", len(results))


if __name__ == "__main__":

    service = input(
        "\nEnter required medical service (Emergency/Surgery): "
    ).strip()

    predict_hospital_delays(service)