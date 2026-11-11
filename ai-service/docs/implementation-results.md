# Implementation and recorded evidence

## Delivered software

- Shared V6 training/inference feature generation and a passing leakage audit.
- Chronological comparison of four workload algorithms, temporal sigmoid calibration, final evaluation, baselines and hospital-level reports.
- Exploratory referral model comparisons with explicit 15-record limitations.
- Unified prediction, recommendation, daily data, feedback, verification, monitoring and model catalog APIs.
- Recommendations integrating learned delay/workload risks with service eligibility and operational comparison reasons.
- Persistent prediction IDs, versions and selected-referral links.
- Verified-only daily learning worker with dataset fingerprints, readiness checks and candidate-only output.
- Immutable artifacts, checksum checks, evaluation-gated approval, active-version comparison and rollback history.
- Isolated automated tests, pinned environment requirements and integration documentation.

## Reliability and collection improvements

- Persisted review decisions and reasons accompany delay, V6 workload and legacy workload predictions, and flow into recommendations. Synthetic training, failed gates, uncalibrated or ambiguous probabilities, and unknown/out-of-range training coverage remain visible even for a numerically confident prediction. All results still require staff review.
- Referral observations can be recorded and verified without loading a model. Real timestamps determine outcomes; duplicates across observations and shadow predictions are counted once, conflicting verified records stop learning, and verified test data remains excluded.
- New training experiments compare additional High-sensitive tree candidates on chronological development data. Current promotion checks explicitly prevent critical-recall regression against persistence/active models and are rechecked when approving older candidates. Misses and false alarms appear in evaluations.
- Training coverage profiles and the known-hospital list come only from fitting records, excluding calibration and final validation. A hospital first seen in validation is not treated as a trained hospital.
- Monitoring adds recent 7/30-day performance by hospital and model, matched persistence comparisons, probability quality, and outcome-collection counts. Collection readiness includes hospital-level dates, gaps and class counts.
- Recommendation comparisons use estimated travel time when all eligible candidates provide it. Daily intake accepts optional staffing and staffed-bed context for later feature experiments; existing model inputs remain unchanged.

These changes improve the collection, training and review workflow. They do not establish a new real-world accuracy estimate. The archived V6 results below are unchanged, and no model was activated as part of this update. New verified hospital records and an independent evaluation are still needed to measure improvement.

## V6 experiment

Candidate: `workload-5c18c15a9c4d4122`.

| Measure | Calibrated Extra Trees | Persistence |
|---|---:|---:|
| Accuracy | 0.7667 | 0.7472 |
| Macro F1 | 0.6703 | 0.6668 |
| Weighted F1 | 0.7608 | 0.7474 |
| Low recall | 0.6476 | 0.7048 |
| Medium recall | 0.8634 | 0.7974 |
| High recall | 0.4286 | 0.5000 |

Validation contains 105 Low, 227 Medium and 28 High records. The candidate improves Medium recall but reduces Low and High recall. Its macro F1 improvement is too small for the configured gate. It remains inactive. No validation-driven second tuning round was performed to inflate this result.

The full experiment is under `reports/experiments/workload-5c18c15a9c4d4122/evaluation.json`, with a frozen feature/target snapshot. Audit results are in `reports/v6_feature_audit.json`.

## Delay experiment

Candidate: `delay-a93a7c3bd373466d`. The report compares Random Forest, Extra Trees and Logistic Regression using three stratified folds on 15 synthetic records. Selection and reporting use the same exploratory folds, so these scores are not independent final performance estimates. Calibration and promotion are blocked by insufficient evidence. The original delay model remains served through its immutable legacy snapshot.

## Learning status

The supplied database has five historical test predictions, three completed test outcomes and no verified real records. Historical records are preserved and imported as unverified test observations. The daily worker therefore returns `awaiting_verified_data` for both model components. Tests of real-data workflows use isolated temporary databases only.

No experimental candidate was promoted. No frontend, Node.js backend, email, image or speech features were implemented. The worker is available as a command/long-running process; no OS schedule was registered or background process left running.

## Verification

`python -m unittest discover -s tests -v` passed all **38 tests**. Coverage includes the complete V6 audit, temporal feature parity, invalid histories, real model inference, unavailable models, checksum failures, verified-only learning, daily/forecast outcome linkage, recommendation exclusions and selections, authentication, candidate deduplication, explicit approval and rollback. Added checks cover review reasons, critical-recall promotion gates, timestamp boundaries, model-independent referral collection, duplicate/conflicting sources, travel-data completeness, recent monitoring, optional operational inputs and fitting-only coverage profiles.

The new training path is exercised end to end with a separate synthetic fixture, temporary database, artifacts and reports; its numbers are not hospital-performance estimates. Worker orchestration also retains an isolated mock-trainer test. The archived V6 and delay experiments described above predate this update.

The installed Starlette test transport emits an httpx deprecation notice; this did not fail the tests. The original five database predictions and three original outcomes remain intact. The project database contains no real records created by testing. Its only active managed models are the two preserved legacy models.

## Remaining evidence and operating decisions

The implemented software can collect, verify, train, evaluate and serve the AI components. Real-world readiness still requires representative verified hospital data, professional review of targets and acceptance thresholds, better workload evidence relative to persistence, and an approved model. Automated collection starts when the main application sends events to this service and an operator runs the worker.

The service is not a validated clinical decision maker, and the recommendation policy is not evidence of better patient outcomes.
