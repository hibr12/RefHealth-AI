import pandas as pd

from prediction.workload_features import calculate_workload_features
from corecare.evidence import assess_prediction

from prediction.workload_model_registry import (
    get_active_workload_model
)


def predict_hospital_workload(hospital_data):

    required_features = [
        "hospital_id",
        "day_of_week",
        "workload_level",
        "patient_volume",
        "incoming_referrals",
        "pending_referrals",
        "available_beds",
        "total_beds",
        "previous_patient_volume",
        "previous_pending_referrals",
        "previous_available_beds",
        "previous_workload_level",
        "average_3day_patient_volume",
        "average_3day_pending_referrals"
    ]

    # Validate input
    if not isinstance(hospital_data, dict):
        raise TypeError(
            "Hospital data must be provided as a dictionary."
        )

    missing_features = [
        feature
        for feature in required_features
        if feature not in hospital_data
    ]

    if missing_features:
        raise ValueError(
            f"Missing required features: {missing_features}"
        )

    # Prepare input data
    input_data = pd.DataFrame(
        [hospital_data]
    )

    input_data = input_data[required_features]

    # Generate four engineered features
    input_data = calculate_workload_features(
        input_data
    )

    # Get active model
    model, model_version = get_active_workload_model()

    # Generate prediction
    prediction = model.predict(input_data)[0]

    probabilities = model.predict_proba(input_data)[0]

    # Get model classes
    if hasattr(model, "named_steps"):
        classifier = model.named_steps["classifier"]
    else:
        classifier = model

    classes = classifier.classes_

    probability_results = {
        str(class_name): round(float(probability), 4)
        for class_name, probability in zip(
            classes,
            probabilities
        )
    }

    return {
        "success": True,
        "hospital_id": hospital_data["hospital_id"],
        "predicted_workload": str(prediction),
        "class_probabilities": probability_results,
        "review": assess_prediction({str(c): float(p) for c, p in zip(classes, probabilities)},
                                    hospital_data, {"data_source": "synthetic", "calibrated": False}),
        "model_version": model_version
    }


if __name__ == "__main__":

    print(
        "This module provides the hospital workload prediction function."
    )

    print(
        "Call predict_hospital_workload() with all 14 required input features."
    )
