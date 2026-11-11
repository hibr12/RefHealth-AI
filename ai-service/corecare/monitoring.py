from datetime import datetime, timedelta, timezone
import json
import numpy as np
import pandas as pd
from corecare import registry, storage
from corecare.config import CLASSES
from training.experiments import metrics


def performance_summary(component, group):
    classes = [0, 1] if component == "delay" else CLASSES
    actual, predicted, probability_rows = [], [], []
    baseline_actual, baseline_predicted, model_predicted = [], [], []
    review_count = 0
    for row in group:
        result, inputs = json.loads(row["result"]), json.loads(row["inputs"])
        label = json.loads(row["payload"])["actual_result"]
        prediction = result["prediction" if component == "delay" else "predicted_workload"]
        actual.append(label)
        predicted.append(prediction)
        review_count += bool(result.get("review", {}).get("requires_human_review", False))
        probabilities = result.get("class_probabilities", {})
        if all(str(c) in probabilities for c in classes):
            probability_rows.append((label, prediction, [probabilities[str(c)] for c in sorted(classes)]))
        previous = inputs.get("features", inputs).get("workload_level")
        if component == "workload" and previous in CLASSES:
            baseline_actual.append(label)
            baseline_predicted.append(previous)
            model_predicted.append(prediction)
    report = metrics(actual, predicted, classes=classes)
    enough = len(group) >= 30 and all(report["per_class"][str(c)]["support"] >= 10 for c in classes)
    alerts = []
    if enough and report["critical_events"]["recall"] < .5:
        alerts.append("critical_event_recall_below_engineering_floor")
    if enough and report["macro_f1"] < .6:
        alerts.append("macro_f1_below_engineering_floor")
    if baseline_actual:
        baseline = metrics(baseline_actual, baseline_predicted, classes=classes)
        matched = metrics(baseline_actual, model_predicted, classes=classes)
        report["persistence_comparison"] = {"records": len(baseline_actual), "baseline": baseline, "model": matched}
        comparison_enough = len(baseline_actual) >= 30 and all(matched["per_class"][str(c)]["support"] >= 10 for c in classes)
        if comparison_enough and (matched["macro_f1"] < baseline["macro_f1"] or
                matched["critical_events"]["recall"] < baseline["critical_events"]["recall"]):
            alerts.append("worse_than_persistence")
    if probability_rows:
        labels, predictions, probabilities = zip(*probability_rows)
        scores = metrics(labels, predictions, np.asarray(probabilities), classes)
        report["probability_quality"] = {key: scores[key] for key in ("log_loss", "multiclass_brier", "confidence_bins")}
        report["probability_quality"]["records"] = len(probability_rows)
    report.update(status="insufficient_data" if not enough else ("review_performance" if alerts else "observed"),
                  alerts=alerts, human_review_predictions=review_count)
    return report


def monitoring_report():
    with storage.connection() as db:
        rows = db.execute("SELECT p.*,o.payload,o.status AS outcome_status FROM ai_predictions p LEFT JOIN ai_outcomes o USING(prediction_id)").fetchall()
        daily = db.execute("SELECT record_type,status,count(*) AS n FROM daily_operations GROUP BY record_type,status").fetchall()
        referrals = db.execute("SELECT record_type,status,count(*) AS n FROM referral_observations GROUP BY record_type,status").fetchall()
        selections = db.execute("""SELECT count(*) FROM recommendation_selections s JOIN ai_predictions p
          ON p.prediction_id=s.referral_prediction_id JOIN ai_outcomes o ON o.prediction_id=p.prediction_id
          WHERE p.record_type='real' AND o.status='verified'""").fetchone()[0]
    groups = {}
    for row in rows:
        if row["outcome_status"] != "verified" or row["component"] not in ("delay", "workload"):
            continue
        key = (row["component"], row["model_version"], row["record_type"])
        groups.setdefault(key, []).append(dict(row))
    performance = []
    for (component, version, kind), group in groups.items():
        result = performance_summary(component, group)
        if kind != "real":
            result.update(status="insufficient_data", alerts=[])
        performance.append({"component": component, "model_version": version, "record_type": kind,
                            **result})
    recent_performance, coverage = [], []
    now = datetime.now(timezone.utc)
    for days in (7, 30):
        recent = [dict(r) for r in rows if r["record_type"] == "real" and r["component"] in ("delay", "workload")
                  and now-timedelta(days=days) <= datetime.fromisoformat(r["predicted_at"]) <= now]
        coverage.append({"window_days": days, "predictions": len(recent),
            "verified_outcomes": sum(r["outcome_status"] == "verified" for r in recent),
            "pending_verification": sum(r["outcome_status"] == "pending" for r in recent),
            "without_outcome": sum(r["outcome_status"] is None for r in recent)})
        subsets = {}
        for row in recent:
            if row["outcome_status"] == "verified":
                key = (row["component"], row["model_version"], row["hospital_id"])
                subsets.setdefault(key, []).append(row)
        for (component, version, hospital), group in subsets.items():
            recent_performance.append({"window_days": days, "component": component,
                "model_version": version, "hospital_id": hospital, **performance_summary(component, group)})
    # Input drift is measured on real prospective predictions, independent of outcome availability.
    drift = []
    now = datetime.now(timezone.utc)
    for component in ("delay", "workload"):
        data = []
        for r in rows:
            if r["component"] != component or r["record_type"] != "real":
                continue
            inputs = json.loads(r["inputs"])
            data.append({**inputs.get("features", inputs), "timestamp": datetime.fromisoformat(r["predicted_at"])})
        baseline = [r for r in data if now-timedelta(days=30) <= r["timestamp"] < now-timedelta(days=7)]
        recent = [r for r in data if now-timedelta(days=7) <= r["timestamp"] <= now]
        entry = {"component": component, "baseline_records": len(baseline), "recent_records": len(recent), "status": "insufficient_data", "signals": []}
        if min(len(baseline),len(recent)) >= 30:
            old, new = pd.DataFrame(baseline), pd.DataFrame(recent)
            numeric = ["distance_km", "pending_referrals", "submission_hour"] if component == "delay" else ["patient_volume", "pending_referrals", "available_beds"]
            categorical = ["hospital_workload", "service_available", "submission_day"] if component == "delay" else ["hospital_id", "workload_level"]
            for feature in numeric:
                scale = max(float(old[feature].std(ddof=0)), 1.)
                change = abs(float(new[feature].mean()-old[feature].mean()))/scale
                if change > 1:
                    entry["signals"].append({"feature": feature, "standardized_mean_change": change})
            for feature in categorical:
                a,b = old[feature].value_counts(normalize=True), new[feature].value_counts(normalize=True)
                change = max(abs(float(a.get(k,0)-b.get(k,0))) for k in set(a.index)|set(b.index))
                if change > .3:
                    entry["signals"].append({"feature": feature, "maximum_proportion_change": change})
            entry["status"] = "possible_drift" if entry["signals"] else "no_threshold_breach"
        drift.append(entry)
    return {"performance": performance, "recent_performance": recent_performance,
            "outcome_coverage": coverage, "referral_observations": [dict(r) for r in referrals],
            "drift": drift, "daily_records": [dict(r) for r in daily],
            "verified_selected_referral_outcomes": selections,
            "limitations": ["Drift thresholds are engineering heuristics.", "Recommendation outcomes are observational and subject to selection bias."]}


def health():
    issues, models = [], []
    try:
        with storage.connection() as db:
            db.execute("SELECT count(*) FROM ai_predictions").fetchone()
    except Exception:
        return {"status": "unhealthy", "issues": ["Database unavailable"], "models": []}
    for component in ("delay", "workload_legacy", "workload"):
        try:
            _, meta = registry.load(component)
            models.append({"component": component, "version": meta["version"], "status": meta["status"]})
        except Exception as error:
            issues.append({"component": component, "reason": str(error)})
    return {"status": "degraded" if issues else "healthy", "issues": issues, "models": models,
            "note": "Service health does not indicate clinical validation."}
