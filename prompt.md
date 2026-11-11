# RefHealth AI — COMPLETE PROJECT DEVELOPMENT PROMPT

## 1. YOUR ROLE

Act as a senior AI/ML engineer, machine-learning researcher, Python developer, and AI systems architect.

Your responsibility is to inspect, improve, complete, train, evaluate, test, and prepare the entire AI system for a project called **RefHealth AI**.

You are responsible ONLY for the AI development inside the existing Python AI service.

Do not implement the frontend or the main Node.js backend. Another developer or agent will handle those parts.

Work directly with the existing project files. Understand the current implementation before making changes. Preserve working functionality and avoid unnecessarily replacing existing code.

Your goal is to help complete a reliable, well-structured, documented, testable AI system that can eventually be integrated with a healthcare referral management platform in Ethiopia.

---

# 2. PROJECT OVERVIEW

## Project Name

RefHealth AI

## Project Purpose

RefHealth AI is an AI-powered healthcare referral coordination and hospital operational intelligence system designed to support healthcare facilities in Ethiopia.

The system should learn from historical hospital operational data, referral records, and verified referral outcomes to identify patterns and generate useful predictions.

Its purpose is to help healthcare workers and referral coordinators:

* Predict whether a hospital is likely to delay acknowledging an incoming referral.
* Identify hospitals that may be more suitable for a particular referral.
* Predict future hospital workload.
* Anticipate operational pressure before it becomes severe.
* Improve referral coordination using historical data and machine-learning predictions.
* Improve its predictive performance over time through verified feedback and controlled model retraining.

This is a healthcare decision-support system.

It must NOT replace healthcare professionals, make independent clinical decisions, or automatically determine patient treatment.

---

# 3. FINAL AI DEVELOPMENT SCOPE

We have decided to concentrate on THREE main AI components.

Do not introduce additional image, audio, or multimodal AI components.

## COMPONENT 1: REFERRAL DELAY PREDICTION

### Objective

Build a machine-learning model that predicts whether a hospital is likely to delay acknowledging a referral.

The initial target definition is:

* 0 = Referral acknowledged within two hours.
* 1 = Referral not acknowledged within two hours.

The two-hour threshold is a provisional demonstration assumption and must eventually be reviewed and approved by healthcare professionals.

### Expected inputs

Depending on the final available data:

* Distance to hospital.
* Hospital workload.
* Number of pending referrals.
* Service availability.
* Referral urgency, if available.
* Submission hour.
* Submission day.
* Other legitimate information available when the referral is submitted.

Do not use information that becomes available only after the prediction is made.

### Expected output

The model should return:

* Prediction.
* Delay probability.
* Prediction confidence, where appropriate.
* Model version.
* Prediction ID.
* Relevant explanation or contributing factors, if supportable.

### Current progress

A preliminary Random Forest model has already been developed using a very small synthetic dataset of 15 records.

The existing model is experimental and has not been clinically or operationally validated.

Do not present its initial accuracy as evidence of real-world performance.

Your task is to inspect the existing implementation, improve the training and evaluation pipeline, and prepare a reliable approach for training with larger, verified historical data when available.

---

## COMPONENT 2: INTELLIGENT HOSPITAL RECOMMENDATION

### Objective

Develop an intelligent hospital recommendation system that identifies and ranks suitable hospitals for a particular referral.

This must be more than a basic rule-based sorting algorithm.

It should use available hospital information and predictions from the other AI components.

### Important inputs

* Required medical service or department.
* Hospital service availability.
* Hospital workload.
* Pending referrals.
* Available beds.
* Distance.
* Predicted referral delay.
* Other relevant operational information.

### Expected functionality

1. Identify hospitals that provide the required service.
2. Exclude hospitals that do not provide the required service.
3. Evaluate the operational suitability of eligible hospitals.
4. Use the referral delay prediction model to estimate acknowledgement delay risk.
5. Use the workload prediction component when appropriate.
6. Rank eligible hospitals based on their suitability.
7. Explain why a hospital received its recommendation position.

### Important requirement

The recommendation system should become increasingly data-driven.

Use historical hospital and referral patterns to improve recommendations rather than relying entirely on manually assigned workload scores or fixed weights.

Do not claim that a recommendation guarantees better clinical outcomes.

### Current progress

An initial recommendation prototype already exists.

Existing files include:

* recommendation/validate_hospitals.py
* recommendation/hospital_eligibility.py
* recommendation/recommendation_input.py
* recommendation/recommendation_engine.py
* recommendation/hospital_analysis.py
* recommendation/predict_hospital_delay.py

An illustrative hospitals dataset exists:

datasets/raw/hospitals.csv

It contains five example hospitals and their services, distances, workloads, pending referrals, service availability, and available beds.

These records are synthetic demonstration data.

Inspect and improve the existing implementation instead of unnecessarily rebuilding everything.

---

## COMPONENT 3: HOSPITAL WORKLOAD PREDICTION

### Objective

Develop a machine-learning system that predicts the workload level of a hospital for the following day.

The model must learn from historical hospital operational patterns.

It should not simply calculate today's workload and return it as tomorrow's prediction.

### Workload classes

* Low
* Medium
* High

### Historical operational inputs

The existing dataset contains:

* Hospital ID.
* Record date.
* Patient volume.
* Incoming referrals.
* Pending referrals.
* Available beds.
* Total beds.
* Workload level.

The model also uses engineered historical features, including:

* Previous patient volume.
* Previous incoming referrals.
* Previous pending referrals.
* Previous available beds.
* Previous workload level.
* Three-day averages.
* Seven-day averages.
* Patient volume trends.
* Pending referral trends.
* Calendar information for the prediction date.

### Expected output

For each hospital:

* Predicted next-day workload.
* Probability for Low workload.
* Probability for Medium workload.
* Probability for High workload.
* Predicted class.
* Model version.
* Prediction date.
* Confidence information, where appropriate.

### Important requirements

* Use chronological training and validation.
* Prevent target leakage.
* Evaluate all three workload classes.
* Pay particular attention to Medium workload because it is the majority class.
* Evaluate performance separately for each hospital.
* Compare appropriate machine-learning algorithms.
* Do not rely on accuracy alone.
* Use macro F1, per-class precision, recall, F1, and confusion matrices.
* Consider probability calibration if the model's probabilities will be used for decision support.

The model must learn historical patterns, not simply reproduce a manually defined workload formula.

---

# 4. WORK ALREADY COMPLETED

Before implementing anything, inspect the repository and verify these completed activities.

Do not assume every file is identical to this description. The actual repository is the source of truth.

## A. Referral Delay Prediction

* Created an initial referral dataset.
* Developed an initial Random Forest model.
* Implemented model saving and loading.
* Implemented a prediction function.
* Created a model registry.
* Exposed prediction functionality through FastAPI.
* Tested prediction requests through Swagger UI.
* Implemented prediction IDs and model-version tracking.
* Started feedback collection and monitoring.

The initial dataset contains only 15 synthetic records.

The current model is experimental.

## B. Intelligent Hospital Recommendation

* Created a synthetic hospital dataset.
* Implemented hospital data validation.
* Implemented service eligibility checking.
* Implemented recommendation input preparation.
* Implemented an initial recommendation engine.
* Connected the recommendation prototype to referral delay prediction.
* Implemented hospital analysis.

This component requires further improvement and validation.

## C. Hospital Workload Prediction

Several synthetic dataset versions were generated and investigated.

### V4

* 1,825 records.
* Five hospitals.
* 365 days.
* Structural validation completed.
* Identified hospital-specific workload imbalance.

### V5

* 1,825 records.
* Five hospitals.
* 365 days.
* Structural validation completed.
* Investigated workload distribution.
* Identified remaining class and hospital-specific issues.

### V6 — Current dataset

The current dataset is:

datasets/raw/hospital_daily_history_v6.csv

It contains:

* 1,825 records.
* Five hospitals.
* 365 days per hospital.
* Date range: 2025-11-05 to 2026-11-04.
* No missing values.
* No duplicate records.
* No negative operational values.
* No invalid bed-capacity values.
* No invalid workload labels.

Workload distribution:

* Low: 470 records.
* Medium: 1,171 records.
* High: 184 records.

The five hospitals have different operational patterns. Do not artificially force identical workload distributions across hospitals.

We have investigated:

* Hospital-specific workload distributions.
* Operational pressure scores.
* H004's relatively low workload.
* Workload transitions.
* Workload streak durations.
* A prolonged High workload period at H005.
* Recovery after prolonged high workload.
* Label consistency.
* Correlations between operational measurements and workload.

The workload labels are derived from simulated operational measurements.

This is synthetic data, not verified real hospital data.

The validation establishes internal consistency of the simulation, not real-world clinical validity.

## D. V6 Feature Engineering

The feature engineering script is:

training/prepare_workload_v6_features.py

The processed dataset is:

datasets/processed/workload_v6_features.csv

Current dataset shape:

1,790 rows × 31 columns.

There are 358 records per hospital.

The target is:

next_day_workload

The target distribution is:

* Medium: 1,144 records.
* Low: 464 records.
* High: 182 records.

The engineered features include:

* Current operational measurements.
* Current workload.
* Bed occupancy rate.
* Pending referrals per bed.
* Referral-to-patient ratio.
* Previous-day measurements.
* Previous workload.
* Three-day and seven-day rolling averages.
* Patient volume trend.
* Pending referral trend.
* Next-day weekday.
* Next-day month.

The rolling features were designed to use current and previous observations only.

Verify this implementation before relying on it.

## E. Chronological Split

The leakage-safe chronological split has already been investigated.

Training:

* 1,425 records.
* Record dates: 2025-11-11 to 2026-08-22.
* Target dates end at 2026-08-23.

Validation:

* 360 records.
* Record dates: 2026-08-24 to 2026-11-03.
* Target dates: 2026-08-25 to 2026-11-04.

Five boundary records were excluded to prevent the training and validation target periods from overlapping.

Training class distribution:

* Medium: 914.
* Low: 357.
* High: 154.

Validation class distribution:

* Medium: 227.
* Low: 105.
* High: 28.

## F. Previous Workload Model

An earlier feature-engineered Random Forest model achieved approximately 0.6939 Macro F1 on its validation experiment.

A class-weighting experiment was performed.

The balanced model was retained rather than using aggressive Medium-class weighting.

This earlier result belongs to an earlier experiment. Do not assume it is the performance of the current V6 dataset.

The V6 model still needs to be developed and evaluated.

## G. Feedback and Monitoring

Initial feedback and monitoring functionality has been implemented.

Existing tests showed:

* Three completed test records.
* Accuracy approximately 0.3333.
* Precision approximately 0.3333.
* Recall 1.0.
* F1 approximately 0.5.

The monitoring system correctly identified that the available data was insufficient.

Drift monitoring also requires more baseline and recent records.

Do not treat these few test records as meaningful evidence of model performance.

Do not retrain models using unverified feedback.

---

# 5. CURRENT PROJECT STRUCTURE

The existing AI service is located at:

~/Desktop/corecare-health AI/ai-service

The project contains directories such as:

* datasets/
* training/
* models/
* prediction/
* recommendation/
* monitoring/
* feedback/
* notebooks/

Inspect the actual directory structure before making changes.

The main AI technology stack is:

* Python.
* pandas.
* NumPy.
* scikit-learn.
* Random Forest and other suitable ML algorithms.
* FastAPI.
* Pydantic.
* joblib.
* matplotlib.
* Other appropriate Python libraries when genuinely necessary.

The project already uses a Python virtual environment.

The developer works on Windows using VS Code and Git Bash.

Provide commands compatible with Git Bash.

---

# 6. IMMEDIATE NEXT TASK

The current unfinished task is:

## V6 FEATURE LEAKAGE AUDIT

The next file planned is:

training/audit_workload_v6_features.py

The initial audit should verify:

* Correct target selection.
* Target exclusion from input features.
* Exclusion of record IDs.
* Exclusion of date identifiers.
* No duplicate feature names.
* No missing feature values.
* No missing targets.
* Correct feature selection.

However, do not stop at this basic audit.

Perform a deeper leakage investigation:

1. Verify that rolling features use only current and past records.
2. Verify that historical features are grouped by hospital.
3. Verify that records are sorted chronologically before feature engineering.
4. Verify that no future observations are used.
5. Verify that next-day calendar features are legitimately known at prediction time.
6. Verify that the current workload is used only as historical information when predicting the following day.
7. Verify that the target is tomorrow's workload, not today's workload.
8. Verify that the training/validation split respects chronological order.

Do not remove legitimate current-day operational features simply because they were also used to calculate today's workload label. The prediction target is the following day's workload, so current-day measurements can be valid predictors.

Once the audit is complete and approved, proceed to the V6 model development.

---

# 7. REMAINING DEVELOPMENT ROADMAP

Complete the following work systematically.

## PHASE 1 — Finish V6 Workload Feature Audit

* Inspect the feature engineering implementation.
* Complete the leakage audit.
* Correct any identified problems.
* Verify chronological splitting.
* Approve the feature dataset for model experiments.

## PHASE 2 — Develop V6 Workload Prediction Models

Experiment with appropriate algorithms, such as:

* Random Forest.
* Extra Trees.
* HistGradientBoosting.
* Gradient Boosting.
* Other suitable scikit-learn classifiers.

Use the same leakage-safe chronological validation strategy when comparing models.

Evaluate:

* Accuracy.
* Macro F1.
* Weighted F1.
* Per-class precision.
* Per-class recall.
* Per-class F1.
* Confusion matrix.
* Per-hospital performance.

Investigate feature importance and model explanations carefully.

Do not select a model simply because it achieves the highest accuracy.

Select a model based on balanced performance, stability, and practical usefulness.

Save experimental models separately from the active production model.

Do not automatically replace the active model with an experimental candidate.

## PHASE 3 — Improve Referral Delay Prediction

Inspect the existing referral delay model.

* Audit the dataset.
* Audit the target definition.
* Inspect features for leakage.
* Improve the training pipeline.
* Evaluate class imbalance.
* Compare appropriate algorithms.
* Evaluate probabilities and calibration.
* Improve prediction explanations.
* Add robust model versioning.

Keep the limitations of the small synthetic dataset explicit.

Prepare a clear data schema for future real referral records.

## PHASE 4 — Improve Intelligent Hospital Recommendation

Inspect the existing recommendation implementation.

Build a data-driven recommendation workflow that integrates:

* Service eligibility.
* Hospital operational information.
* Referral delay prediction.
* Next-day workload prediction, when relevant.
* Distance.
* Pending referrals.
* Bed availability.

The recommendation system should distinguish between:

* Hospitals that are ineligible because the required service is unavailable.
* Hospitals that are eligible but operationally less suitable.
* Hospitals that are more suitable based on the available evidence.

Produce ranked results with understandable reasons.

Do not fabricate clinical suitability or claim that the AI can assess medical urgency unless an appropriate validated clinical dataset and approved model exist.

## PHASE 5 — Complete Feedback and Continuous Learning

Improve the feedback system so it can:

1. Store model predictions.
2. Store prediction IDs.
3. Record model versions.
4. Collect actual verified outcomes.
5. Distinguish verified outcomes from unverified feedback.
6. Prepare approved records for future training.
7. Monitor model performance.
8. Detect potential data drift.
9. Generate retraining candidates.
10. Compare candidate models against the active model.
11. Require evaluation and approval before deployment.

Important:

Never automatically promote a newly trained model simply because it was trained successfully.

Require adequate verified data, evaluation, model comparison, and explicit approval.

Use versioned model artifacts and preserve rollback capability.

## PHASE 6 — Integrate the AI Components

All three components must operate through the existing Python AI service.

Review the existing FastAPI structure and improve it where necessary.

Provide clear API endpoints for:

* Referral delay prediction.
* Hospital recommendation.
* Hospital workload prediction.
* Feedback submission.
* Model monitoring and health status.

Use consistent response formats.

Include:

* Success status.
* Prediction ID.
* Model version.
* Prediction result.
* Probabilities where applicable.
* Meaningful error messages.

Do not implement the Node.js backend or frontend.

Prepare API documentation and example request/response payloads so another developer can integrate the service.

## PHASE 7 — Final Testing and Documentation

Run tests for all three components.

Test:

* Normal predictions.
* Missing fields.
* Invalid values.
* Unknown hospitals.
* Unavailable services.
* Model loading failures.
* Prediction errors.
* Feedback submission.
* Model version tracking.
* API error handling.
* Monitoring behavior.

Add automated tests where appropriate.

Create or update documentation covering:

* AI architecture.
* Dataset descriptions.
* Feature definitions.
* Training instructions.
* Model evaluation results.
* API endpoints.
* Example API requests.
* Model versioning.
* Feedback workflow.
* Limitations.
* How to integrate the AI service with the main application.

---

# 8. EMAIL NOTIFICATIONS — DEFERRED

Do not work on email notifications now.

We deliberately postponed this feature to prioritize the three core AI components.

Return to email notification integration only after:

1. Referral Delay Prediction is sufficiently developed.
2. Intelligent Hospital Recommendation is sufficiently developed.
3. Hospital Workload Prediction is sufficiently developed.
4. Feedback and monitoring are working.
5. The AI service is tested and documented.

---

# 9. EXPLICITLY EXCLUDED COMPONENTS

The following components have been removed from the project scope:

1. Medical Image Understanding.
2. Amharic Speech Recognition.
3. Multimodal AI.

Do not develop them.

Do not create folders, models, datasets, endpoints, or roadmap tasks for these components.

Do not include them in project progress calculations.

Concentrate entirely on the three remaining AI components.

---

# 10. IMPORTANT ENGINEERING AND DATA REQUIREMENTS

Follow these requirements throughout development.

### A. Do not fabricate real-world evidence

The existing datasets are synthetic demonstration data.

Never describe synthetic model performance as real hospital performance.

Clearly distinguish:

* Synthetic data.
* Real operational data.
* Verified outcomes.
* Unverified feedback.
* Experimental model results.
* Validated model results.

### B. Prevent data leakage

Never allow future operational measurements or future outcomes to enter the features used for an earlier prediction.

Use chronological validation for time-dependent predictions.

### C. Avoid artificial performance improvement

Do not manipulate datasets or labels simply to obtain higher accuracy.

Do not oversample the validation dataset.

Do not select models using validation results in a way that causes repeated overfitting.

### D. Maintain model versions

Keep experimental, candidate, and active models separate.

Use explicit model metadata.

### E. Preserve existing functionality

Before editing a file:

* Inspect it.
* Understand its purpose.
* Identify dependencies.
* Check whether other components use it.

Avoid destructive changes.

Do not delete existing datasets or models without a clear technical reason and explicit reporting.

### F. Build maintainable code

Use:

* Clear module responsibilities.
* Reusable functions.
* Appropriate error handling.
* Input validation.
* Logging.
* Type hints where useful.
* Configuration files where appropriate.
* Automated tests.

Do not introduce unnecessary complexity.

---

# 11. HOW YOU SHOULD WORK

I want you to take responsibility for completing the AI development systematically.

Start by inspecting the complete existing repository.

Then:

1. Report the actual project structure.
2. Identify which completed features work.
3. Identify unfinished features.
4. Identify bugs and inconsistencies.
5. Identify missing files and dependencies.
6. Compare the real implementation against this project description.
7. Produce a prioritized development plan.
8. Begin with the unfinished V6 feature leakage audit.
9. Continue through the remaining roadmap.

You are authorized to create and edit files inside the existing AI service.

However:

* Do not make unnecessary changes to working files.
* Do not silently change project objectives.
* Do not skip important evaluation steps.
* Do not mark a component complete just because its endpoint exists.
* Do not invent successful test results.
* Do not hide errors.
* Do not claim production readiness without appropriate evidence.

If you encounter a problem, explain it, investigate the cause, and fix it where possible.

If an important decision requires real healthcare data or professional approval, document the limitation rather than inventing an answer.

You may work through multiple files and related tasks independently, but provide clear progress reports and meaningful checkpoints.

---

# 12. FINAL DEFINITION OF SUCCESS

The AI development will be considered complete when the following deliverables exist:

### Referral Delay Prediction

A tested, documented, versioned machine-learning component with a clear training and prediction workflow.

### Intelligent Hospital Recommendation

A working recommendation component that uses hospital eligibility, operational information, and the other AI predictions to rank hospitals transparently.

### Hospital Workload Prediction

A properly evaluated next-day workload prediction model using historical operational features and leakage-safe chronological validation.

### Feedback and Continuous Learning

A controlled system for recording predictions, collecting verified outcomes, monitoring performance, preparing candidate models, and approving model updates.

### Unified Python AI Service

A documented FastAPI service exposing the three core AI components with consistent request and response formats.

### Testing and Documentation

Automated tests, reproducible training instructions, evaluation reports, API documentation, and clear limitations.

The final objective is to deliver a coherent, data-driven healthcare referral coordination and hospital operational intelligence AI system—not merely three disconnected machine-learning demonstrations.

**Start by inspecting the actual repository and reporting the current implementation status. Then proceed with the V6 feature leakage audit as the first unfinished task.**
