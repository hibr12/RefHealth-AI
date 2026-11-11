# Python AI service integration

The main application calls this FastAPI service over HTTP. Requests and responses are JSON. OpenAPI is available at `/openapi.json`, with interactive documentation at `/docs`. No frontend or Node.js implementation is included.

When configured, send `X-API-Key` on every request. Verification, monitoring, and learning status also require `X-Admin-Token`. Keep these credentials in the backend. Model activation is an explicit operator CLI operation, not an HTTP action accessible to referral clients.

## Endpoints

| Method and route | Function |
|---|---|
| `GET /health` | Database and artifact checks; degraded when no approved V6 model exists |
| `GET /models` | Versions, active flags, evaluation metadata and artifact checksums |
| `POST /predict/delay` | Referral prediction and persistent prediction ID |
| `POST /predict/workload` | Compatible legacy 14-input demonstration API |
| `POST /predict/workload/next-day` | V6 prediction from seven consecutive daily observations |
| `POST /recommendations` | Ranked eligible hospitals, exclusions, reasons, contributing model versions |
| `POST /recommendations/{id}/selection` | Link a recommendation to the actual selected referral prediction |
| `POST /feedback/{id}/outcome` | Submit an unverified actual outcome |
| `POST /feedback/{id}/verify` | Verify an outcome with operator and evidence |
| `POST /operations/daily` | Submit daily operational data, initially unverified |
| `POST /operations/daily/{id}/verify` | Verify daily data and resolve matching workload predictions |
| `POST /operations/referrals` | Record a prospective referral without running any model |
| `POST /operations/referrals/{id}/outcome` | Attach an observed acknowledgement outcome |
| `POST /operations/referrals/{id}/verify` | Verify the referral and outcome for learning; administrator required |
| `GET /monitoring` | Verified performance groups and real-input drift signals |
| `GET /learning/status` | Verified-data counts and reasons learning is waiting |

## Referral example

```bash
curl -X POST http://127.0.0.1:8000/predict/delay \
  -H 'Content-Type: application/json' \
  -d '{"distance_km":12,"hospital_workload":"Low","pending_referrals":8,"service_available":1,"submission_hour":8,"submission_day":"Monday","hospital_id":"H002","record_type":"test"}'
```

Response shape (the probability below is illustrative, not a recorded evaluation result):

```json
{
  "success": true,
  "prediction_id": "UUID",
  "component": "Referral Delay Prediction",
  "model_version": "legacy-delay-v1",
  "data": {
    "prediction": 0,
    "result": "Not Delayed",
    "delay_probability": 0.2,
    "class_probabilities": {"0": 0.8, "1": 0.2},
    "confidence": 0.8,
    "calibrated": false,
    "model_version": "legacy-delay-v1",
    "model_status": "legacy_experimental",
    "data_source": "synthetic",
    "delay_threshold_hours": 2,
    "explanation": {"type": "input_context", "observed_factors": {}, "note": "Input context is not causal attribution."},
    "limitations": ["Experimental decision support."]
  }
}
```

For real referrals, also supply `submitted_at`, `feature_observed_at`, and `source_reference`. Timestamps must include a timezone. The request must arrive within 15 minutes of submission; input observations must precede submission and be at most two hours old. The service derives the model's submission hour/day in UTC+03:00. Historical replay belongs in test mode; future real-data import should be a separately reviewed offline workflow.

`prediction=1` means acknowledgement exceeded two hours. This is a provisional operational definition requiring professional approval. `confidence` is the probability assigned to the predicted class, not a clinical confidence guarantee.

Predictions also return a persisted `review` object. Its `status` is `review_required` when engineering warnings are present, otherwise `decision_support`. `reasons` identifies synthetic training, failed evaluation gates, uncalibrated probabilities, low confidence, similar class probabilities, unknown hospital coverage, unavailable training profiles, or inputs outside the model-fitting range. Old models without a saved profile report unknown coverage. `requires_human_review` remains true and `autonomous_use_supported` false in both statuses. Clients should show this information alongside the prediction and keep staff in control.

The confidence floor of 0.7 and probability-margin floor of 0.15 are visible engineering heuristics, not validated clinical thresholds or guarantees of correctness. Training ranges detect some unfamiliar inputs; staying inside them does not prove that an input is supported. The legacy workload endpoint returns review information as well.

## Referral collection without a model

To collect observations before a model is available, send the same prospective referral fields to `POST /operations/referrals`, with `hospital_id` and `source_reference` required and no `model_version`. Authentication and timestamp rules match real prediction requests. The response contains `observation_id` and `status: awaiting_outcome`; no model is loaded and no prediction is invented.

Submit the outcome to `/operations/referrals/OBSERVATION_ID/outcome`, then the administrator verification to `/operations/referrals/OBSERVATION_ID/verify`, using the payloads below. Real outcomes must provide exactly one of `acknowledged_at` or `observed_until`. Invalid timestamps or labels are rejected before storage. An observation can be verified only after its outcome exists. Verified test observations remain excluded from training.

Use a stable source reference for each actual referral. The observation endpoint rejects duplicate hospital/type/source combinations with 409. If the same referral also receives a shadow prediction, use the same source reference: learning counts matching verified records once and stops on conflicting features or outcomes. Do not include patient names or other unnecessary identifiers in source references.

## Outcomes and verification

Test outcome:

```json
{"actual_result": 0}
```

For real referrals, supply `acknowledged_at` and `source_reference`. If still unacknowledged, provide `observed_until` after the two-hour deadline instead. The service rejects disagreement between the binary label and timestamps. Exactly two hours counts as within the threshold.

POST the outcome to `/feedback/PREDICTION_ID/outcome`, then submit a separate authorized verification:

```json
{"reviewer": "operator-identifier", "evidence": "Checked acknowledgement timestamp against referral register reference ABC."}
```

Verification does not turn test data into real data. Duplicate outcomes or repeated verification return 409. Existing outcomes are immutable; conflicting source records require an operator-led correction process before further use.

For workload outcomes, use a workload label and the precise prediction date:

```json
{"actual_result": "Medium", "target_date": "2026-11-05", "source_reference": "daily-register-reference"}
```

Real outcomes are accepted only after that day ends. Verifying a daily record automatically provides the actual workload for matching real workload predictions. A disagreement with an existing outcome aborts verification for investigation.

## Daily operational record

```json
{
  "hospital_id": "H001",
  "record_date": "2026-11-04",
  "patient_volume": 75,
  "incoming_referrals": 9,
  "pending_referrals": 6,
  "available_beds": 20,
  "total_beds": 60,
  "workload_level": "Medium",
  "record_type": "test",
  "observed_at": "2026-11-05T07:00:00+03:00",
  "source_reference": "demonstration-register"
}
```

Daily records are unique by hospital, date, and record type. Real daily records must represent a finalized day. The workload label is an observed, reviewed operational label; the service does not silently apply the synthetic label formula to real hospitals.

Optional nonnegative integer fields `staff_on_duty` and `staffed_beds` capture additional operational context; staffed beds cannot exceed total beds. Existing models do not consume these fields. They are preserved for a future feature-schema experiment when verified data supports evaluating them.

## Next-day workload

```json
{"hospital_id":"H001","as_of_date":"2026-11-04","record_type":"test","model_version":"workload-5c18c15a9c4d4122"}
```

The response includes `prediction_id`, `model_version`, `prediction_date`, `predicted_workload`, Low/Medium/High probabilities, confidence, calibration status and limitations. The same prediction is under `data` for consistency; top-level workload fields support existing clients.

Test mode accepts an optional `history` array of daily measurements, or uses the bundled synthetic history. Real mode uses verified records from storage, requires yesterday as the observation date, and predicts today's workload after yesterday's measurements have been finalized. Caller-supplied real history is rejected. The last seven dates must be consecutive and end exactly at `as_of_date`.

Omit `model_version` to use the approved active model. Explicit candidates are usable only in test mode unless they are already active. Unknown hospitals return 404; onboarding another hospital requires an updated service catalog and appropriately evaluated model/data coverage.

## Recommendations

```json
{
  "required_service": "Emergency",
  "record_type": "test",
  "submitted_at": "2026-11-05T08:00:00+03:00",
  "workload_as_of_date": "2026-11-04",
  "workload_model_version": "workload-5c18c15a9c4d4122"
}
```

Test requests may use `hospitals.csv`. Real requests must provide `candidates`, `operational_snapshot_at`, and `source_reference`. Each candidate supplies hospital ID/name, service, service availability, available beds, referring-location-specific distance, workload, and pending referrals. Snapshots must be at most two hours old.

Hospitals lacking the required available service are listed as exclusions. Zero beds is reported as limited capacity, with those candidates ranked after eligible candidates reporting beds. Eligible candidates are compared using Pareto layers: a hospital dominates another only when it is no worse on every included operational measure and better on at least one. Measures are learned delay probability, distance, pending referrals, available beds, and forecast High probability when all candidates have a forecast. Ties use delay probability and then distance.

Each result explains its service eligibility, risks, operational observations and ranking policy. If some histories are incomplete, workload forecasts are excluded from the whole comparison and availability notes explain the omission. A requested model loading failure is reported as an error.

Candidates may include `estimated_travel_minutes`. Travel time replaces distance in the comparison and final travel tie-break only when every eligible candidate supplies it. Otherwise all candidates are compared using distance. `travel_measure` identifies the field used. Candidate rows contain `delay_review`, workload forecasts carry their own `review`, and the overall result aggregates warnings. Missing requested workload evidence, no eligible hospitals, and no reported beds produce explicit review reasons. Rankings continue to require a staff decision.

Create an actual `/predict/delay` request for the selected hospital, then link it:

```json
{"hospital_id":"H001","referral_prediction_id":"ACTUAL_REFERRAL_PREDICTION_UUID"}
```

Only the selected referral's verified outcome enters learning. The system does not fabricate outcomes for hospitals that were not selected. No causal claim about recommendation benefit is made.

## Monitoring and collection progress

`GET /monitoring` preserves lifetime `performance` and `drift`, and adds:

- `recent_performance`: verified real results grouped by hospital and model for the last 7 and 30 days, based on prediction time. Reports include detected/missed delayed referrals or High-workload days, false alarms, probability-quality measurements when available, and matched persistence comparisons for workload.
- `outcome_coverage`: counts of real predictions with verified outcomes, pending verification, or no outcome for each recent window. Missing outcomes can reflect predictions whose target time has not passed; these counts are not automatically overdue alerts.
- `referral_observations`: collection counts by record type and verification state, separate from prediction accuracy.

Performance remains `insufficient_data` below 30 verified records or 10 examples of any class. Engineering alerts identify low critical-event recall, low macro F1, or performance below persistence on the same available records. Alerts are API report fields; the service does not send notifications. Low-support hospital groups do not produce claims of reliable performance.

`GET /learning/status` adds `per_hospital` collection counts, date ranges, missing dates and observed class counts. For referrals, missing dates describe calendar coverage, not necessarily missing referrals; for daily operations they expose continuity gaps. Collection readiness permits training an experiment; it does not imply approval. Workload observed class counts describe input days, while the training gate separately checks usable next-day targets.

## Errors

Errors use `success:false` with an `error` object. Validation errors include field locations. Expected statuses are 401 for service authentication, 403 for missing administrator credentials, 404 for unknown hospitals or predictions, 409 for duplicates, 422 for invalid inputs, and 503 for unavailable models/configuration/storage. Unexpected exceptions are logged and return a generic 500.

Prediction IDs are server-generated. Ingestion duplicates are rejected; prediction requests are not idempotent, so the integrating backend should avoid blindly retrying a successfully completed prediction request.
