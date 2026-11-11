"""Engineering evidence checks; these do not authorize autonomous decisions."""
import math


def training_profile(frame, features, categorical):
    """Capture only the model fitting period, never calibration or test data."""
    return {
        "numeric": {name: {"min": float(frame[name].min()), "max": float(frame[name].max())}
                    for name in features if name not in categorical},
        "categorical": {name: sorted(str(value) for value in frame[name].unique())
                        for name in categorical},
    }


def assess_prediction(probabilities, inputs, metadata):
    values = sorted((float(value) for value in probabilities.values()), reverse=True)
    if (len(values) < 2 or any(not math.isfinite(p) or not 0 <= p <= 1 for p in values)
            or not math.isclose(sum(values), 1., abs_tol=1e-6)):
        raise RuntimeError("Model returned invalid class probabilities.")
    reasons = []
    if metadata.get("data_source") != "verified_real":
        reasons.append("model_not_trained_on_verified_real_data")
    if not metadata.get("promotion_eligible", False):
        reasons.append("model_evaluation_gates_not_passed")
    if not metadata.get("calibrated", False):
        reasons.append("probabilities_not_calibrated")
    # Visible engineering heuristics, not claimed clinical acceptance thresholds.
    if values[0] < .7:
        reasons.append("low_model_confidence")
    if values[0] - values[1] < .15:
        reasons.append("similar_class_probabilities")
    profile = metadata.get("training_profile")
    outside = []
    if inputs.get("hospital_id") and inputs["hospital_id"] not in metadata.get("known_hospitals", []):
        reasons.append("hospital_training_coverage_unknown")
    if not profile:
        reasons.append("training_input_coverage_unknown")
    else:
        for name, bounds in profile.get("numeric", {}).items():
            value = inputs.get(name)
            if value is None or not bounds["min"] <= float(value) <= bounds["max"]:
                outside.append(name)
        for name, known in profile.get("categorical", {}).items():
            if str(inputs.get(name)) not in known:
                outside.append(name)
        if outside:
            reasons.append("input_outside_training_coverage")
    return {"status": "review_required" if reasons else "decision_support",
            "requires_human_review": True, "autonomous_use_supported": False,
            "reasons": reasons, "outside_training_features": sorted(set(outside)),
            "probability_margin": values[0] - values[1],
            "policy": {"version": "engineering-review-v1", "minimum_confidence": .7,
                       "minimum_margin": .15, "clinically_validated": False},
            "message": "Review these limitations before using the prediction." if reasons
                       else "No engineering warning triggered; staff must still review the decision."}
