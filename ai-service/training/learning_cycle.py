"""Daily learning worker: verified observations -> evaluated candidates, never activation."""
import argparse
import hashlib
import json
import time
import pandas as pd
from corecare import storage, registry
from corecare.config import DELAY_FEATURES
from corecare.features import build_features
from training.experiments import train_temporal


def datasets():
    delay = []
    seen = {}
    for record in [*storage.verified_delay(), *storage.verified_referral_observations()]:
        inputs, outcome = record["inputs"], record["outcome"]
        # Defense in depth: legacy or incomplete feedback is never a training example.
        if not inputs.get("submitted_at") or not (outcome.get("acknowledged_at") or outcome.get("observed_until")):
            continue
        # An observed referral and a shadow prediction can describe the same event.
        key = (record["hospital_id"], inputs.get("source_reference"))
        signature = {"features": {k: inputs[k] for k in DELAY_FEATURES},
                     "submitted_at": pd.Timestamp(inputs["submitted_at"]).tz_convert("UTC").isoformat(),
                     "actual_result": outcome["actual_result"],
                     "observed_at": pd.Timestamp(outcome.get("acknowledged_at") or outcome["observed_until"]).tz_convert("UTC").isoformat()}
        if key in seen:
            if seen[key] != signature:
                raise ValueError("Conflicting verified referral records share a hospital/source reference.")
            continue
        seen[key] = signature
        delay.append({**{k: inputs[k] for k in DELAY_FEATURES}, "hospital_id": record["hospital_id"],
                      "delayed": outcome["actual_result"], "prediction_id": record["prediction_id"],
                      "verified_at": record["verified_at"], "verified_by": record["verified_by"],
                      "record_date": pd.to_datetime(inputs["submitted_at"], utc=True).tz_convert(None).normalize(),
                      "target_date": pd.to_datetime(outcome.get("acknowledged_at") or outcome["observed_until"], utc=True).tz_convert(None).normalize()})
    return {"delay": pd.DataFrame(delay), "workload": pd.DataFrame(storage.verified_daily())}


def readiness():
    data = datasets()
    result = {}
    for component, frame in data.items():
        reasons = []
        if component == "delay":
            if len(frame) < 100:
                reasons.append("At least 100 verified real referral outcomes required.")
            if frame.empty or any(frame.delayed.value_counts().get(c,0) < 20 for c in (0,1)):
                reasons.append("At least 20 verified examples per delay class required.")
            if frame.empty or frame.record_date.nunique() < 60:
                reasons.append("At least 60 distinct submission dates required for temporal evaluation.")
        else:
            if frame.empty or frame.groupby("hospital_id").size().min() < 60:
                reasons.append("At least 60 consecutive verified daily records per included hospital required.")
            if not frame.empty:
                try:
                    features = build_features(frame)
                    if any(features.next_day_workload.value_counts().get(c,0)<20 for c in ("Low","Medium","High")):
                        reasons.append("At least 20 target examples per workload class required across hospitals.")
                except ValueError as error:
                    reasons.append(str(error))
        by_hospital = []
        if not frame.empty:
            for hospital, group in frame.groupby("hospital_id"):
                dates = pd.to_datetime(group.record_date).dt.normalize().drop_duplicates().sort_values()
                label = "delayed" if component == "delay" else "workload_level"
                expected = pd.date_range(dates.min(), dates.max(), freq="D")
                missing = expected.difference(pd.DatetimeIndex(dates))
                by_hospital.append({"hospital_id": hospital, "verified_records": len(group),
                    "distinct_dates": len(dates), "first_date": str(dates.min().date()),
                    "last_date": str(dates.max().date()), "missing_dates": [str(d.date()) for d in missing],
                    "observed_class_counts": {str(k): int(v) for k,v in group[label].value_counts().items()}})
        result[component] = {"verified_records": len(frame), "ready": not reasons, "reasons": reasons,
                             "per_hospital": by_hospital,
                             "note": "Readiness permits an experiment; final evaluation and approval are still required."}
    return result


def run_cycle(component=None):
    storage.initialize()
    registry.adopt_legacy()
    state = readiness()
    data = datasets()
    results = {}
    catalog = registry.catalog()
    for name in ([component] if component else ["delay", "workload"]):
        if not state[name]["ready"]:
            results[name] = {"status": "awaiting_verified_data", **state[name]}
            continue
        fingerprint = hashlib.sha256(data[name].to_csv(index=False).encode()).hexdigest()
        if any(m["component"] == name and m["metadata"].get("source_fingerprint") == fingerprint for m in catalog):
            results[name] = {"status": "unchanged_verified_data"}
            continue
        try:
            result = train_temporal(data[name], name, "verified_real", source_fingerprint=fingerprint)
            results[name] = result
        except ValueError as error:
            results[name] = {"status": "awaiting_suitable_temporal_data", "reason": str(error)}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=["delay", "workload"])
    parser.add_argument("--watch", action="store_true", help="Run immediately, then once per day until stopped.")
    args = parser.parse_args()
    while True:
        print(json.dumps(run_cycle(args.component), indent=2), flush=True)
        if not args.watch:
            break
        # This is the user-run worker, not an agent tool wait.
        time.sleep(86400)


if __name__ == "__main__":
    main()
