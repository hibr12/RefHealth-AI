# Data, features and controlled learning

## Dataset inventory

`referrals.csv` has 15 synthetic binary examples (8 non-delayed, 7 delayed). It lacks timestamps and cannot independently establish the two-hour target. `hospitals.csv` has 10 service rows for five demonstration hospitals. `hospital_daily_history.csv` is a header-only placeholder. The original daily demonstration has 450 rows (90 days per hospital); versions V2–V6 have 1,825 rows each.

V6 covers 2025-11-05 through 2026-11-04: Low 470, Medium 1,171, High 184. The five hospitals retain different distributions; H004 has no High examples. Workload labels are derived from simulated operational measurements and are not approved clinical thresholds. The raw generators use the run date, so regenerating them later does not reproduce the original calendar. Preserve the archived CSVs and their hashes for reproduction.

The original workload experiment uses a different dataset and feature schema. Its results, including macro F1 0.6939, must not be attributed to V6. `datasets/processed` retains those earlier reports.

## V6 input contract

Forecasts are made only after the observation day is complete. Inputs for date D predict workload on D+1. Calendar features for D+1 are known at prediction time.

| Feature group | Definitions |
|---|---|
| Identity | Hospital ID is categorical; unknown hospitals are rejected |
| Current operations | Patient volume, incoming referrals, pending referrals, available beds, total beds, observed workload |
| Bed occupancy proxy | `(total_beds - available_beds) / total_beds` |
| Pending pressure | `pending_referrals / total_beds` |
| Referral ratio | `incoming_referrals / max(patient_volume, 1)` |
| Previous day | Patient volume, incoming referrals, pending referrals, available beds and workload at D−1 |
| Three/seven-day averages | Patient volume, incoming referrals, pending referrals and available beds; windows end on D |
| Trends | Current patient volume/pending referrals minus previous day values |
| Calendar | D+1 weekday and month |

The exact 27-column whitelist is `corecare.features.FEATURES`. `record_id`, `record_date`, `target_date`, and `next_day_workload` are never model inputs. All histories are sorted and checked for hospital/date duplicates, missing dates, non-finite values, labels, and bed constraints. No interpolation or future backfilling is performed.

An occupancy proxy includes unavailable beds and should not be described as a measured patient occupancy rate. Current-day workload is legitimate historical information for D+1, assuming it was finalized by the forecast cutoff.

The legacy API's `pending_per_available_bed` divides by available beds and is a different feature from V6's `pending_per_bed`. The legacy 18-feature model cannot be used with V6's 27-input schema.

## Audit and evaluation

`training.audit_workload_v6_features` compares the stored CSV to the shared builder, checks tomorrow's labels and past windows independently, perturbs future data, isolates hospitals, shuffles input order, and checks the explicit model inputs and chronological split.

V6 training contains 1,425 records through record date 2026-08-22, with targets through 2026-08-23. Five records at 2026-08-23 are excluded. Final validation contains 360 records from 2026-08-24 through 2026-11-03, with targets through 2026-11-04.

The archived V6 experiment compared Random Forest, Extra Trees, HistGradientBoosting and Gradient Boosting on two expanding chronological development folds. New workload experiments also compare two exploratory tree models with class weights Low=1, Medium=1, High=6. These are engineering search candidates, not agreed clinical error costs. Selection first prefers candidates whose mean development critical-class recall reaches 0.5 and the mean development baseline recall, then maximizes mean macro F1 and uses variability as a tie-break. If none meets the development recall floor, the report explicitly records that fact and evaluates the best macro-F1 candidate without promising eligibility. Development folds must contain every target class.

The selected model is trained/calibrated using the first/last portions of the training period with another boundary exclusion. Final validation is evaluated after selection against the majority baseline, persistence baseline, and applicable active model. Changes motivated by the archived results require new untouched data for an independent performance claim; rerunning the bundled V6 CSV is only a synthetic diagnostic.

Reports contain accuracy, macro/weighted F1, class precision/recall/F1/support, confusion matrices, per-hospital results, log loss, multiclass Brier score, confidence bins, and development-only permutation importance. Absent classes have explicit zero support; per-hospital scores should be interpreted with that support. Permutation importance is predictive association, not a clinical causal explanation.

Engineering promotion policy `engineering-v2` requires at least 10 final validation examples per class, recall of at least 0.2 for every class, macro F1 at least 0.01 above the strongest baseline, and no macro F1 regression against the applicable active model. In addition, recall for High workload or delayed referrals must be at least 0.5 and cannot regress against persistence or the active model where available. The majority baseline is compared by macro F1, since an always-positive classifier's perfect recall alone is not a useful requirement. Reports explicitly count misses and false alarms. Promotion recomputes the current checks, including for older candidates, rather than trusting a stored eligibility flag. An incomplete report or failed check blocks activation. These are demonstration gates, not professional acceptance criteria; operating teams still need to agree on acceptable misses and false alarms. A candidate evaluated against an outdated active version cannot be promoted until reevaluated.

New temporal candidates save numeric fitting-data ranges and known categorical values. Calibration and final validation do not expand those profiles. Inference uses them to flag unfamiliar inputs, alongside confidence and evidence checks. These warnings are not a guarantee that unflagged predictions will be correct. Existing artifacts without profiles stay usable for demonstrations and explicitly report unknown coverage.

## Everyday learning lifecycle

SQLite tables are additive; the original `predictions` table is preserved. Legacy records are imported with their original IDs as test observations with unverified outcomes. Original model files are copied once into the managed registry to preserve serving behavior.

- `ai_predictions`: component, immutable inputs/results, IDs, model versions, record type and timestamps.
- `ai_outcomes`: submitted actual outcomes, verification status, verifier, evidence and verification time.
- `daily_operations`: daily source records with independent verification and uniqueness constraints.
- `recommendation_selections`: actual selected referral links; unselected candidates never receive invented labels.
- `referral_observations`: prospective referral features and verified outcomes collected without any model dependency; unique hospital/type/source references prevent ingestion duplicates.
- `model_versions`, `active_models`, `model_events`: artifact provenance, active pointers and approval/rollback history.

The learning worker consumes only verified real outcomes/operations, including model-independent referral observations. Test records remain excluded after verification. A real delay prediction or observation must be prospective and have submission-time features. Timestamp evidence determines whether acknowledgement exceeded two hours. Incomplete historic feedback is not silently promoted into the verified training data. A referral recorded both as an observation and a shadow prediction contributes only once when the hospital/source reference, features and outcome agree. Conflicting verified duplicates stop learning for investigation; they are not silently overwritten.

Delay learning requires at least 100 verified outcomes, 20 examples per class, and 60 distinct submission dates. Workload learning requires at least 60 consecutive verified days per included hospital and 20 target examples per class across the data. Further temporal partition requirements may keep a seemingly large dataset in waiting status. Thresholds should be revisited using the real collection process and learning curves.

The worker checks each component separately, fingerprints its verified input, and skips datasets already consumed by a candidate. It builds models from real records without mixing synthetic rows into real evaluation. Real candidates must pass chronological validation and active-model comparison before approval can even be requested. Updates are never activated by the worker.

Approved new delay and workload models automatically influence subsequent recommendation risks. The current ranking policy uses model predictions and transparent operational comparisons; it is not a separately trained causal ranking model. Learning a recommendation-specific objective requires representative selection/outcome data, an agreed operational utility, and correction for selection bias.

Daily intake also preserves optional staff-on-duty and staffed-bed counts for future feature evaluation. They are not inputs to the existing model schema. Recommendations can compare supplied travel estimates when all eligible candidates have them; otherwise they consistently use distance. Neither change fabricates missing operational values.

## Operational limits

No live hospital feed, external identity provider, clinical validation, or OS scheduler is supplied. The integrating backend must submit real events and operate the worker. The current service catalog covers five example hospital IDs. New hospitals, services, approved workload labels, two-hour targets, acceptable error rates, and privacy/retention procedures require agreement with the operating organization.

Run a single daily worker per database. SQLite is appropriate for this local prototype; concurrent large-scale deployment needs workload-specific operational review. Outcomes and daily records are immutable after verification; an audited correction/retraction workflow would be required before enabling routine edits to verified source data.

For backups, preserve the SQLite database together with `models/managed` and the experiment reports. Artifact checksum failures stop loading. Never activate a newly trained model by manually replacing a managed file.
