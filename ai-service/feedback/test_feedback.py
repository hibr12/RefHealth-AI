from feedback_store import (
    save_prediction,
    record_actual_outcome
)


# Sample referral information
referral = {

    "distance_km": 35,

    "hospital_workload": "High",

    "pending_referrals": 25,

    "service_available": 1,

    "submission_hour": 10,

    "submission_day": "Tuesday"

}


# Save prediction
prediction_id = save_prediction(

    referral_data=referral,

    predicted_result=1,

    delay_probability=0.88,
    model_version="test_only"

)


print("PREDICTION SAVED SUCCESSFULLY")

print("Prediction ID:", prediction_id)


# Simulate an actual outcome
# 0 = Not delayed
# 1 = Delayed

success = record_actual_outcome(

    prediction_id,

    actual_result=0

)


if success:

    print("ACTUAL OUTCOME SAVED SUCCESSFULLY")

else:

    print("PREDICTION NOT FOUND")
