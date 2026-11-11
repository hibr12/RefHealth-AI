from datetime import date, datetime, timedelta, timezone
import pandas as pd
from corecare.config import ROOT, DELAY_FEATURES, LIMITATION
from corecare.features import FEATURES, RAW_COLUMNS, inference_features
from corecare.schemas import ReferralFeatures, ReferralRequest, WorkloadRequest, LOCAL_TIME
from corecare import registry, storage
from corecare.evidence import assess_prediction


def check_hospital(hospital_id):
    hospitals = pd.read_csv(ROOT / "datasets/raw/hospitals.csv")
    if hospital_id not in set(hospitals.hospital_id):
        raise LookupError("Unknown hospital; register its service catalog before requesting predictions.")


def model_for(component, version, record_type):
    model, metadata = registry.load(component, version)
    if record_type == "real" and metadata["version"] != registry.active_version(component):
        raise ValueError("Real predictions must use an approved active model.")
    return model, metadata


def delay_result(data, version=None, record_type="test"):
    features = ReferralFeatures.model_validate({k: data[k] for k in DELAY_FEATURES}).model_dump()
    model, metadata = model_for("delay", version, record_type)
    frame = pd.DataFrame([features])[metadata["features"]]
    predicted = int(model.predict(frame)[0])
    probabilities = {int(c): float(p) for c, p in zip(model.classes_, model.predict_proba(frame)[0])}
    return {"prediction": predicted, "result": "Delayed" if predicted else "Not Delayed",
            "delay_probability": probabilities[1], "class_probabilities": {str(k): v for k,v in probabilities.items()},
            "confidence": probabilities[predicted], "calibrated": metadata.get("calibrated", False),
            "model_version": metadata["version"], "model_status": metadata["status"],
            "data_source": metadata["data_source"], "delay_threshold_hours": 2,
            "review": assess_prediction(probabilities, {**features, "hospital_id": data.get("hospital_id")}, metadata),
            "explanation": {"type": "input_context", "observed_factors": features,
                            "note": "Inputs are context, not causal feature attributions."}, "limitations": [LIMITATION]}


def predict_delay(request: ReferralRequest):
    if request.hospital_id:
        check_hospital(request.hospital_id)
    payload = request.model_dump(mode="json")
    result = delay_result(payload, request.model_version, request.record_type)
    identifier = storage.save_prediction("delay", payload, result, request.record_type, request.hospital_id)
    return {"success": True, "prediction_id": identifier, "component": "Referral Delay Prediction", "model_version": result["model_version"], "data": result}


def workload_result(request: WorkloadRequest):
    check_hospital(request.hospital_id)
    if request.record_type == "real":
        if request.history is not None:
            raise ValueError("Real workload predictions use verified daily records from the service.")
        if request.as_of_date != datetime.now(LOCAL_TIME).date()-timedelta(days=1):
            raise ValueError("Real next-day forecasts must use yesterday's finalized observations.")
        history = storage.verified_daily(request.hospital_id, request.as_of_date)
        # Only the last seven days are needed; old gaps cannot invalidate a complete recent window.
        history = history[-7:]
    elif request.history is None:
        raw = pd.read_csv(ROOT / "datasets/raw/hospital_daily_history_v6.csv")
        history = raw[(raw.hospital_id == request.hospital_id) & (raw.record_date <= str(request.as_of_date))].tail(7).to_dict("records")
    else:
        history = [r.model_dump(mode="json") for r in request.history]
    row = inference_features(history, request.hospital_id, request.as_of_date)
    model, metadata = model_for("workload", request.model_version, request.record_type)
    if request.hospital_id not in metadata.get("known_hospitals", []):
        raise ValueError("The model has no training history for this hospital.")
    probabilities = {str(c): float(p) for c,p in zip(model.classes_, model.predict_proba(row[FEATURES])[0])}
    predicted = str(model.predict(row[FEATURES])[0])
    result = {"hospital_id": request.hospital_id, "prediction_date": str(request.as_of_date+timedelta(days=1)),
              "predicted_workload": predicted, "class_probabilities": probabilities,
              "confidence": probabilities[predicted], "calibrated": metadata.get("calibrated", False),
              "model_version": metadata["version"], "model_status": metadata["status"],
              "data_source": metadata["data_source"], "limitations": [LIMITATION]}
    result["review"] = assess_prediction(probabilities, row[FEATURES].iloc[0].to_dict(), metadata)
    inputs = {"hospital_id": request.hospital_id, "as_of_date": str(request.as_of_date),
              "features": row[FEATURES].to_dict("records")[0], "history_record_ids": [str(r.get("record_id", "inline")) for r in history]}
    return result, inputs


def predict_workload(request):
    result, inputs = workload_result(request)
    identifier = storage.save_prediction("workload", inputs, result, request.record_type, request.hospital_id, result["prediction_date"])
    return {"success": True, "prediction_id": identifier, "model_version": result["model_version"], "data": result, **result}


def validate_outcome(prediction_id, submission):
    prediction = storage.prediction(prediction_id)
    return validate_record_outcome(prediction, submission)


def validate_record_outcome(prediction, submission):
    value = submission.actual_result
    if prediction["component"] == "delay":
        if value not in (0,1):
            raise ValueError("Delay outcome must be 0 or 1.")
        if prediction["record_type"] == "real":
            if bool(submission.acknowledged_at) == bool(submission.observed_until):
                raise ValueError("Provide exactly one acknowledgement or observation timestamp.")
            submitted = datetime.fromisoformat(prediction["inputs"]["submitted_at"])
            observed = submission.acknowledged_at or submission.observed_until
            if not observed or not submission.source_reference:
                raise ValueError("Real delay outcomes need observation timestamps and source evidence.")
            if observed < submitted or observed > datetime.now(timezone.utc):
                raise ValueError("Invalid outcome observation timestamp.")
            deadline = submitted + timedelta(hours=2)
            if submission.acknowledged_at:
                expected = int(submission.acknowledged_at > deadline)
            else:
                if observed <= deadline:
                    raise ValueError("An unacknowledged referral must be observed beyond the two-hour deadline.")
                expected = 1
            if value != expected:
                raise ValueError("Outcome disagrees with acknowledgement timestamps.")
    elif prediction["component"] == "workload":
        if value not in ("Low", "Medium", "High") or str(submission.target_date) != prediction["target_date"]:
            raise ValueError("Workload outcome must match the prediction target date and valid classes.")
        if prediction["record_type"] == "real":
            if submission.target_date >= datetime.now(LOCAL_TIME).date() or not submission.source_reference:
                raise ValueError("Real workload outcomes require a completed target day and evidence.")
    else:
        raise ValueError("Recommendation outcomes are attached to the selected referral prediction.")
    return submission.model_dump(mode="json")
