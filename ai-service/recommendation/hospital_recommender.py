"""Operational recommendations using learned risks and Pareto ranking.

No synthetic clinical suitability labels or manually weighted workload scores.
The learned delay/workload risks change when approved models are updated.
"""
from datetime import datetime, timezone, timedelta
import pandas as pd
from corecare.config import ROOT, LIMITATION
from corecare.schemas import HospitalCandidate, WorkloadRequest, LOCAL_TIME
from corecare.inference import check_hospital, delay_result, workload_result
from corecare import registry, storage


def pareto_layers(rows, include_workload, use_travel=False):
    def cost(row):
        values = [row["delay_probability"], row["estimated_travel_minutes"] if use_travel else row["distance_km"],
                  row["pending_referrals"], -row["available_beds"]]
        if include_workload:
            values.append(row["workload_prediction"]["class_probabilities"]["High"])
        return values
    remaining = list(rows)
    layer = 1
    while remaining:
        front = []
        for candidate in remaining:
            costs = cost(candidate)
            dominated = any(all(a <= b for a,b in zip(cost(other),costs)) and
                            any(a < b for a,b in zip(cost(other),costs)) for other in remaining if other is not candidate)
            if not dominated:
                front.append(candidate)
        for row in front:
            row["pareto_layer"] = layer
            remaining.remove(row)
        layer += 1


def recommend(request):
    if request.record_type == "real":
        if request.candidates is None or not request.operational_snapshot_at or not request.source_reference:
            raise ValueError("Real recommendations require supplied operational candidates, snapshot time and source reference.")
        if not timedelta(0) <= datetime.now(timezone.utc)-request.submitted_at <= timedelta(minutes=15):
            raise ValueError("Real recommendations must be prospective.")
        if request.operational_snapshot_at > request.submitted_at or request.submitted_at-request.operational_snapshot_at > timedelta(hours=2):
            raise ValueError("Operational snapshot must precede submission and be at most two hours old.")
    candidates = request.candidates or [HospitalCandidate.model_validate(r) for r in pd.read_csv(ROOT / "datasets/raw/hospitals.csv").to_dict("records")]
    local = request.submitted_at.astimezone(LOCAL_TIME)
    if request.workload_as_of_date and request.workload_as_of_date+timedelta(days=1) != local.date():
        raise ValueError("Requested workload forecast must apply to the referral submission date.")
    eligible, excluded = [], []
    seen = set()
    for hospital in candidates:
        key = (hospital.hospital_id, hospital.service.casefold().strip())
        if key in seen:
            raise ValueError("Duplicate hospital/service candidate.")
        seen.add(key)
        check_hospital(hospital.hospital_id)
        if hospital.service.casefold().strip() != request.required_service.casefold().strip():
            excluded.append({"hospital_id": hospital.hospital_id, "service": hospital.service, "reason": "required_service_not_provided"})
            continue
        if not hospital.service_available:
            excluded.append({"hospital_id": hospital.hospital_id, "service": hospital.service, "reason": "required_service_unavailable"})
            continue
        data = hospital.model_dump()
        delay = delay_result({**data, "submission_hour": local.hour, "submission_day": local.strftime("%A")}, request.delay_model_version, request.record_type)
        workload = None
        workload_note = "Next-day workload was not requested."
        if request.workload_as_of_date is not None:
            try:
                workload, _ = workload_result(WorkloadRequest(hospital_id=hospital.hospital_id,
                    as_of_date=request.workload_as_of_date, record_type=request.record_type, model_version=request.workload_model_version))
                workload_note = "Forecast applies to " + workload["prediction_date"]
            except ValueError as error:
                workload_note = str(error)
            # Model loading failures deliberately propagate rather than producing misleading rankings.
        row = {**data, "delay_probability": delay["delay_probability"], "delay_model_version": delay["model_version"],
               "delay_review": delay["review"],
               "workload_prediction": workload, "workload_note": workload_note,
               "operational_status": "limited_capacity" if hospital.available_beds == 0 else "capacity_reported"}
        eligible.append(row)
    # Compare forecasts only when all eligible candidates have them, avoiding missing-data advantage.
    use_workload = bool(eligible) and all(r["workload_prediction"] is not None for r in eligible)
    use_travel = bool(eligible) and all(r["estimated_travel_minutes"] is not None for r in eligible)
    travel_field = "estimated_travel_minutes" if use_travel else "distance_km"
    for limited in (False, True):
        pareto_layers([r for r in eligible if (r["available_beds"] == 0) == limited], use_workload, use_travel)
    eligible.sort(key=lambda r: (r["available_beds"] == 0, r["pareto_layer"], r["delay_probability"], r[travel_field], r["hospital_id"]))
    for index, row in enumerate(eligible, 1):
        row["rank"] = index
        row["reasons"] = ["Required service is available.",
            f"Predicted acknowledgement delay risk: {row['delay_probability']:.1%}.",
            f"Reported available beds: {row['available_beds']}; distance: {row['distance_km']} km.",
            f"Operational comparison layer: {row['pareto_layer']}; ties use delay risk, then {travel_field}."]
        if use_travel:
            row["reasons"].append(f"Estimated travel time: {row['estimated_travel_minutes']} minutes.")
        if row["available_beds"] == 0:
            row["reasons"].append("No beds reported available; ranked after candidates reporting capacity.")
        if use_workload:
            row["reasons"].append(f"Forecast High workload risk: {row['workload_prediction']['class_probabilities']['High']:.1%}.")
    versions = sorted({r["delay_model_version"] for r in eligible} | {r["workload_prediction"]["model_version"] for r in eligible if r["workload_prediction"]})
    review_reasons = set()
    for row in eligible:
        review_reasons.update(row["delay_review"]["reasons"])
        if row["workload_prediction"]:
            review_reasons.update(row["workload_prediction"]["review"]["reasons"])
    if not eligible:
        review_reasons.add("no_eligible_hospital")
    elif all(r["available_beds"] == 0 for r in eligible):
        review_reasons.add("no_reported_beds")
    if request.workload_as_of_date and not use_workload:
        review_reasons.add("requested_workload_evidence_incomplete")
    result = {"model_version": "pareto-risk-v2:" + ",".join(versions), "ranking_method": f"capacity, Pareto layers, learned delay risk, {travel_field}",
              "model_versions": versions, "ranked_hospitals": eligible, "excluded": excluded,
              "workload_used_in_ranking": use_workload,
              "travel_measure": travel_field,
              "review": {"status": "review_required", "requires_human_review": True,
                         "autonomous_use_supported": False, "reasons": sorted(review_reasons)},
              "limitations": [LIMITATION, "Operational suitability does not establish clinical suitability or improved outcomes.",
                              "Ranking policy is explicit; learned risks improve through verified outcomes, not counterfactual labels."]}
    identifier = storage.save_prediction("recommendation", request.model_dump(mode="json"), result, request.record_type)
    return {"success": True, "prediction_id": identifier, "model_version": result["model_version"], "data": result}


def record_selection(prediction_id, selection):
    recommendation = storage.prediction(prediction_id)
    referral = storage.prediction(selection.referral_prediction_id)
    if recommendation["component"] != "recommendation" or referral["component"] != "delay":
        raise ValueError("Selection must link a recommendation to an actual delay prediction.")
    if referral["hospital_id"] != selection.hospital_id or referral["record_type"] != recommendation["record_type"]:
        raise ValueError("Selected hospital and record type must match the actual referral.")
    if referral["predicted_at"] < recommendation["predicted_at"]:
        raise ValueError("Selected referral must follow the recommendation.")
    if selection.hospital_id not in {r["hospital_id"] for r in recommendation["result"]["ranked_hospitals"]}:
        raise ValueError("Selected hospital was not eligible.")
    import sqlite3
    with storage.connection() as db:
        try:
            db.execute("INSERT INTO recommendation_selections VALUES (?,?,?,?)",
                       (prediction_id, selection.hospital_id, selection.referral_prediction_id, storage.now()))
        except sqlite3.IntegrityError as error:
            raise FileExistsError("Recommendation selection already recorded.") from error
