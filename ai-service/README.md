# RefHealth AI

Python decision-support service for referral coordination and hospital operations in Ethiopia. The three AI components are referral acknowledgement delay prediction, hospital recommendation, and next-day hospital workload prediction. The project also includes a Node backend and React frontend; see the [root README](../README.md) and [platform integration guide](docs/platform-integration.md). The RefHealth AI Assistant uses Groq for final responses and Gemini for embeddings. Existing model, training, and prediction contracts are preserved.

The service now records daily activity, accepts actual outcomes, requires verification before using real records for learning, trains evaluated candidates, and requires explicit approval to activate eligible updates. It does not learn from its own unverified predictions.

Predictions now include human-review reasons for weak or unsupported evidence. Referral observations can be collected and verified without an available model. Training evaluates additional High-workload-sensitive candidates, and promotion rejects critical-recall regressions. Monitoring reports recent hospital-level misses, false alarms, probability quality and outcome coverage. These software improvements do not establish a new accuracy result; the archived evaluation below remains the measured evidence.

## Current evidence and readiness

All supplied hospital and referral datasets are synthetic. There are no verified real operational records in the supplied database. Software tests and synthetic evaluation do not establish clinical validity.

- The V6 feature audit passes: 1,790 rows, 27 model inputs, 1,425 training rows, 360 final validation rows, and five excluded boundary records.
- The V6 experiment selected Extra Trees on two expanding development folds, then calibrated probabilities on a chronological training tail. Final validation accuracy is **0.7667**, macro F1 **0.6703**, weighted F1 **0.7608**.
- Persistence achieves accuracy **0.7472**, macro F1 **0.6668**. The candidate's macro F1 gain is only **0.0034**, below the preconfigured 0.01 engineering gate. High recall is **0.4286**, compared with persistence's **0.5000**. This candidate is **not approved or active**.
- The 15-row delay experiment is exploratory three-fold cross-validation, with no independent final test or reliable calibration. Its candidate is also not eligible for activation.
- Existing delay and legacy workload behavior is preserved through immutable copies of the previously served artifacts. Their status remains `legacy_experimental`.

See [implementation results](docs/implementation-results.md), [API integration](docs/api.md), and [data and learning](docs/data-and-learning.md).

## Setup and run (Windows Git Bash)

From the project root:

```bash
cd ai-service
source venv/Scripts/activate
python -m uvicorn main:app --env-file .env --reload --reload-dir corecare --host 127.0.0.1 --port 8000
```

The existing environment is Python 3.14.3. On a new machine, create a virtual environment and install `requirements-dev.txt` for development or `requirements.txt` for serving. Never deserialize an untrusted joblib artifact. Serve through your organization's authenticated backend and infrastructure when handling real records.

Visit `http://127.0.0.1:8000/docs` for generated request schemas. `/health` checks storage and model artifacts. It reports `degraded` while no V6 model has been approved; delay and legacy workload demonstrations remain available.

The development command reloads `corecare/` changes. Restart the process after changing environment variables or dependencies, or code outside that directory. Check that the backend's `AI_SERVICE_URL` points to this process and its documentation is titled RefHealth AI.

Assistant provider requests reuse HTTPS connections and retry transient connection failures and selected 408/429/5xx responses up to three attempts within one 80-second budget. Authentication, certificate, payload and redirect errors are not retried. Provider retry delays are honored; delays longer than five seconds return an error for a later user retry. Unchanged document vectors are cached for at most 15 minutes, with 512 entries per process, isolated by requesting hospital, provider, model, credential fingerprint and document content. Authorization is checked by the backend for every request; cached entries cannot add sources absent from that request. Query vectors and generated answers are not cached. Short greetings and recognized questions about the assistant's purpose, identity, capabilities or limitations go directly to Groq with the system's application description. They need no hospital citation. Mixed hospital questions retain retrieval and citation checks; unknown citation IDs are always rejected.

Configuration uses environment variables:

| Variable | Purpose |
|---|---|
| `CORECARE_DATABASE` | SQLite path; defaults to `datasets/feedback.db` |
| `CORECARE_MODEL_DIR` | Immutable artifacts; defaults to `models/managed` |
| `CORECARE_REPORT_DIR` | New experiment reports and frozen snapshots; defaults to `reports/experiments` |
| `CORECARE_API_KEY` | Optional for local test mode; required for real data collection; send `X-API-Key` |
| `CORECARE_ADMIN_TOKEN` | Required for verification and monitoring; send `X-Admin-Token` |
| `PLATFORM_BACKEND_URL` | Authenticated verified-observation import from the PostgreSQL-backed platform |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | Groq endpoint, server-side key and final-response model; required for chat |
| `LLM_VISION_MODEL`, `LLM_AUDIO_MODEL` | Optional Groq vision and transcription models for attachments |
| `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL` | Gemini endpoint, server-side key and embedding model; without a key, explicitly labeled lexical retrieval is used |

Set secrets in your deployment environment, not committed files. Real records are rejected when service authentication is not configured. The verification token represents a trusted operator; the supplied reviewer identifies that operator for the audit trail. Connect this to the main backend's identity controls.

## Run the audit and candidate experiments

```bash
python -m training.audit_workload_v6_features --output reports/v6_feature_audit.json
python -m training.train_workload_v6
python -m training.train_delay_candidates
python -m training.manage_models list
```

Experiments create unique candidate versions, frozen CSV snapshots, JSON evaluations, and checksummed artifacts. They never update an active pointer. Repeatedly tuning against final validation would invalidate the evidence; select new settings using training development folds and reserve new data for a future final evaluation.

The training implementation now includes additional candidates and stricter gates, so rerunning the bundled synthetic CSV does not reproduce the historical model selection exactly and cannot establish an independent improvement over it. Use new verified records for that comparison. Automated tests exercise the new training path with a separate synthetic fixture and temporary artifacts.

`training.prepare_workload_v6_features` uses the shared feature builder and can explicitly regenerate the processed CSV. Audit does not rewrite raw or processed datasets. Existing datasets and original model artifacts are preserved.

## Exercise the V6 candidate

List `/models` and copy a workload candidate version. Supply it explicitly in a test prediction:

```json
{
  "hospital_id": "H001",
  "as_of_date": "2026-11-04",
  "record_type": "test",
  "model_version": "workload-5c18c15a9c4d4122"
}
```

POST this to `/predict/workload/next-day`. With no inline test history, it uses the bundled synthetic daily history. The result predicts 2026-11-05. Omitting `model_version` requires an approved active V6 model; the service returns 503 until one exists. Candidate inference never activates that model.

## Daily learning

1. Submit prospective referrals through `/operations/referrals` (collection without a model) or `/predict/delay`, and daily records through `/operations/daily`, as `real` with source references and observation times. Use the same stable referral source reference if collecting both an observation and a shadow prediction.
2. Submit observed acknowledgement outcomes. The service derives/checks the two-hour label from timestamps.
3. An authorized reviewer verifies the outcome or daily record. Verification of a completed daily record also resolves matching workload forecasts.
4. Run the worker once, or leave the daily worker running under your chosen process supervisor:

```bash
python -m training.learning_cycle
python -m training.learning_cycle --watch
```

The one-shot command is suitable for Windows Task Scheduler. `--watch` checks immediately and then once every 24 hours. No background worker or OS schedule is installed automatically. Run one worker per database. Logs are JSON on stdout; failures should be monitored by the supervisor.

The worker checks minimum record and class counts, data continuity, temporal development/calibration/validation partitions, baseline comparisons, and the current active model. Unchanged verified data does not produce another candidate. Insufficient data produces a structured waiting status. A successful training run still leaves a candidate inactive.

## Review, activation, and rollback

Read the candidate's evaluation report before invoking either command:

```bash
python -m training.manage_models approve --component workload --version VERSION \
  --reviewer OPERATOR --reason "Reviewed evaluation and operational acceptance" --confirm APPROVE
python -m training.manage_models rollback --component workload \
  --reviewer OPERATOR --reason "Observed regression" --confirm ROLLBACK
```

Synthetic candidates additionally require `--allow-experimental`; this does not bypass failed evaluation gates. The current V6 candidate is blocked by its evaluation gate. Real clinical/operational acceptance thresholds still require professional review. All promotions record previous/current versions, operator, reason, and timestamp. Rollback requires a prior approved version.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and artifact directories, cover actual model predictions, and do not add simulated real records to the project database. The installed Starlette emits a deprecation notice for its httpx test transport; the tests currently run successfully with the pinned environment.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `corecare/features.py` | Shared historical features, data validation, temporal split |
| `corecare/schemas.py` | Typed API contracts and timestamp/range validation |
| `corecare/inference.py` | Predictions, provenance, outcome validation |
| `corecare/storage.py` | Additive SQLite tables, verification, forecast/outcome linkage |
| `corecare/registry.py` | Immutable artifacts, checksums, active pointers, promotion and rollback |
| `corecare/monitoring.py` | Verified performance, drift signals, dependency health |
| `recommendation/hospital_recommender.py` | Service eligibility, learned risks, transparent operational ranking |
| `training/experiments.py` | Candidate training, calibration, evaluation and reports |
| `training/learning_cycle.py` | Daily verified-data readiness and candidate generation |
| `main.py` | Unified FastAPI routes and consistent errors |

Older exploratory scripts and their reports remain available. Their filenames and results refer to earlier datasets unless explicitly marked V6. The original delay training command now writes a separate legacy candidate. Existing retraining, feedback export, evaluation, and approval entry points use the controlled workflow.
