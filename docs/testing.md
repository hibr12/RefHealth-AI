# Testing and acceptance

Use separate test databases and temporary model directories. Repository tests must never run against a clinical database. The implementation run used an isolated PostgreSQL instance on `127.0.0.1:55432`, database `coecare_test`, under ignored `.local/`; it did not alter the user's existing PostgreSQL server on port 5432.

## AI regression and integration contracts

```bash
cd ai-service
source venv/Scripts/activate
python -m unittest discover -s tests -v
```

The original 38 tests exercise actual models, leakage safety, chronological validation, synthetic-versus-real evidence, model integrity, outcome verification, candidate training and promotion gates. Added bridge tests exercise registered-hospital eligibility, missing/stale data, authenticated access, provider output validation, semantic retrieval contracts and idempotent verified observation imports. Provider tests use isolated test doubles; they do not establish connectivity to a live paid provider.

The assistant provider contract tests verify Gemini query/document embedding requests, vector-dimension checks, retrieval failure behavior, Groq final-response generation, history/source forwarding, citation validation and Groq media routing. They use mocked HTTP responses. The optional live browser test below verifies actual credentials and provider availability with synthetic questions; these calls may incur provider charges and are skipped by default.

## Real backend/AI/database workflow

Start an isolated AI process:

```bash
cd ai-service
export CORECARE_API_KEY='choose-an-isolated-test-service-key'
export CORECARE_ADMIN_TOKEN='choose-a-separate-test-operator-key'
export CORECARE_DATABASE='../.local/ai-integration.db'
export CORECARE_MODEL_DIR='../.local/ai-models'
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The automated integration suite does not load a provider `.env` file or make live provider calls. If manually verifying a configured local provider, add `--env-file .env` to the Uvicorn command and use synthetic, non-sensitive questions.

Then run:

```bash
cd backend
export DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/coecare_test'
export JWT_SECRET='choose-an-isolated-secret-at-least-32-characters'
export AI_SERVICE_KEY='choose-an-isolated-test-service-key'
export NODE_ENV=test
npm run generate
npm run migrate
npm run build
npm test
```

Tests use Fastify injection with the real Prisma client and real PostgreSQL records. AI prediction calls use the running Python service; the assistant gateway contract is tested with a controlled HTTP response, while provider request/response behavior is tested with mocks in the Python suite. They cover role restrictions, hospital approval, profile updates, patient isolation, all normal lifecycle transitions, rejected invalid transitions, concurrent transition protection, feedback ownership, knowledge approval, assistant request forwarding and private conversation persistence, service outage, token rotation/logout/suspension, recovery token reuse and service-only learning exports. Separate tests exercise public-source network restrictions and insufficient-data metrics.

## Frontend checks

```bash
cd frontend
npm test
npm run build
npx playwright test
```

Browser tests require the backend and frontend dev servers, the isolated AI service, and a test-only platform administrator matching `frontend/tests/workflow.spec.ts`. Tests exercise registration/approval, account login and refresh, profile/capacity edits, desktop/mobile layout and a human-selected referral completed across two hospital browser sessions.

## Optional live assistant verification

`frontend/tests/assistant-live.spec.ts` exercises the complete browser → backend → AI service → Gemini → Groq path without intercepting chat requests. Each case creates a synthetic hospital and approved private notice. The directory regression asks “how many hospitals are registered in this system”, “ok what is your purpose in this system”, then “which are the active hospital currently”. It compares the count and every returned hospital name against the authenticated, paginated hospital directory; checks HTTP 200, directory citations, the uncited purpose explanation and absence of an error alert; and reloads to verify all three saved replies. The other case asks about the three AI components and desk opening days, checks citations and a follow-up question, then reloads to verify saved replies. It also sends a short greeting and verifies that reply persists. Tests are skipped unless `REFHEALTH_LIVE_PROVIDER_TEST=1` and check that `DATABASE_URL` names `coecare_test` before creating records.

`ai-service/tests/test_provider_http.py` tests transient recovery, bounded retries, retry-delay handling, shared deadlines, response-size limits, certificate failures and secret-safe diagnostics with an HTTP mock transport. Integration tests check embedding-cache scope, edits, removed sources, credential rotation, expiry and batch bounds. They also cover the purpose follow-up, 12 help paraphrases, mixed questions that still require citations, invented citation rejection and media routing. Frontend component tests check short-message submission and draft preservation after a failed request.

The directory/response regressions additionally check strict source-ID schemas, malformed optional proposal handling, complete directory context beyond eight retrieval matches, exclusion of non-approved registrations and private fields, and a 250-hospital snapshot split into bounded documents. The database workflow compares the forwarded snapshot to the actual approved rows.

Start the backend against that isolated database and the AI service with isolated storage plus `--env-file .env` to load the configured provider keys. Use matching service keys. Set the frontend's `REFHEALTH_BACKEND_URL` to the test backend and its origin in the backend's `CORS_ORIGIN`. Keep provider keys exclusively in the AI service. Seed the test administrator described above, then run from `frontend/`:

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:55433/coecare_test'
export PLAYWRIGHT_BASE_URL='http://127.0.0.1:5175'
export REFHEALTH_LIVE_PROVIDER_TEST=1
npx playwright test tests/assistant-live.spec.ts
```

Use `--grep "active hospital list"` for just the three-turn directory regression. If a run hits provider HTTP 429, allow the provider's quota window to recover before making more requests; do not hide the failure with automatic whole-test retries. The final November 10 directory check used the new `assistant_directory_regression_20261110` schema in the isolated `coecare_test` database on port 55433: four synthetic approved hospital fixtures plus the hospital created by the browser test. Earlier accumulated test records were preserved. The backend and test runner must use the same `?schema=...` connection parameter. The final browser test used the repaired primary AI service at port 8000.

Both server configuration and these environment variables must point to the isolated test stack. The November 10 verification used frontend port 5175, backend port 3001, AI port 8003 and PostgreSQL port 55433. Provider/network failures fail the test rather than substitute a mock answer; inspect the reported error before rerunning.

## Optional live media verification

`frontend/tests/assistant-media-live.spec.ts` uses real provider responses and an isolated database. The image case uploads a blue-circle PNG through the actual browser compression path, checks the vision answer and a text follow-up, then reloads. The voice case uploads a WAV, records an 11-second speech sample through Chrome's real MediaRecorder using a fake microphone device, checks WebM transcription and transcript-bearing history, reloads, and exercises Listen/Stop through the native speech API. This does not record a physical microphone or prove physical speaker audibility.

Prepare harmless fixtures explicitly from `ai-service/` with `python tests/prepare_media_fixtures.py`. It creates the geometric image and downloads the [public JFK speech sample used by whisper.cpp](https://github.com/ggml-org/whisper.cpp/blob/master/samples/jfk.wav), verifying its SHA-256 digest. Both files stay under ignored `.local/assistant-media/`. No patient image or private recording is used. From `frontend/`, set the isolated backend/frontend stack as above, then run:

```bash
export REFHEALTH_LIVE_MEDIA_TEST=1
export DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:55433/coecare_test?schema=assistant_directory_regression_20261110'
export PLAYWRIGHT_BASE_URL='http://127.0.0.1:5175'
npx playwright test tests/assistant-media-live.spec.ts
```

`REFHEALTH_TEST_IMAGE_FILE` and `REFHEALTH_TEST_AUDIO_FILE` override the fixture paths. The audio fixture must include the expected word “country” and be an 11-second 16-kHz mono WAV for the supplied recording assertions. Keep provider keys server-side. Both media cases are skipped unless explicitly enabled.

Frontend component tests additionally cover preparation/send races, M4A normalization, oversized/empty files, denied microphone permission, track cleanup, navigation during a pending permission request, transcript history and speech errors. Backend tests check private transcript persistence, rejection of missing transcription and absence of stored audio bytes. AI tests check MP4 transcription, typed-plus-voice instructions, empty transcription and ordinary citation enforcement for spoken hospital questions.

The separate `frontend/tests/assistant-speech.spec.ts` reuses synthetic media accounts from the live tests. Set `REFHEALTH_SPEECH_TEST=1` and run that file with the same isolated database/frontend settings. Its browser playback test replaces only the speech response with the known public WAV, then verifies real audio decoding, advancing playback time and Stop. It does not claim provider synthesis. Set `REFHEALTH_EXPECT_SPEECH_TERMS=1` only while reproducing the current unaccepted Groq model terms: that additional test makes a real speech request and verifies the setup error without losing the saved reply. Disable that diagnostic after the organization administrator accepts the terms. Never accept legal terms as part of an automated test.

Cloud-speech component tests cover fallback and cancellation of pending audio on navigation. Backend tests enforce both hospital and user ownership and segment length. AI tests enforce service authentication, input bounds, WAV responses and safe provider errors. The November 10 checks passed 48 AI, 16 backend and 12 frontend tests, plus both real image/voice workflows and both playback/setup-error browser tests. Live generated speech remains unverified pending provider terms acceptance.

## Saved chat history verification

Apply the chat-thread migration to the isolated test database before running the backend suite. Its regression covers separate chats, server-owned history, cross-user/cross-hospital denial, idempotent retries, conflicting simultaneous sends, stable message order, history cursors and reading beyond the latest forty replies. Frontend tests cover New chat, restoring an older chat, clearing drafts between chats, loading earlier messages, retry request IDs and media controls.

Set `REFHEALTH_LIVE_CHAT_THREADS_TEST=1` with `DATABASE_URL` pointing to `coecare_test` and `PLAYWRIGHT_BASE_URL` pointing to the isolated frontend. Run `npx playwright test tests/assistant-threads-live.spec.ts`. It uses real provider replies to create two chats, continue the first with its saved context, verify recent-activity ordering and reload persistence, and check desktop/390px phone layout. Screenshots are written to ignored `.local/chat-history/`. Existing live assistant/media tests now send thread IDs and versions rather than relying on browser-provided history.

During the November 11 migration, pre/post fingerprints of all original fields in User, Membership, Hospital, Conversation, KnowledgeRecord and Prediction matched in the application database and both test schemas. All 15 application messages, 49 general-test messages and 14 pre-existing browser-test messages were assigned to threads without changing their original content. These are migration-time counts; subsequent tests create additional isolated records.

## Hospital workspace context verification

The hospital-workspace expansion adds database-backed checks for fresh capacity, administrator/worker context differences, incoming-referral permission boundaries, exclusion of patient/clinical/credential/other-hospital private fields, model metadata minimization, and server-side citation reconstruction/rejection. Python regressions verify pinned exact facts, complete network comparisons and omission of irrelevant context for simple own-hospital questions.

For live verification, use the same isolated stack and set `REFHEALTH_LIVE_WORKSPACE_TEST=1`, then run `npx playwright test tests/assistant-workspace-live.spec.ts` from `frontend/`. It creates a synthetic hospital, asks about its current beds and role, changes the capacity through the authorized API, verifies the next answer uses the new value despite prior history, requests private information from other hospitals, and verifies the safe response and persistence after reload. It makes real provider calls; provider errors fail the test. It never changes production accounts or records.

## Acceptance boundaries

Software correctness tests do not establish clinical validity. Live provider availability must be rechecked for each deployment; Facebook/Telegram authorizations, production container builds, hosting credentials, backup restoration, load/penetration tests and professional model acceptance still need environment-specific validation. Deployment remains a separate operational acceptance step.


## Incoming queue verification (November 11)

Apply `202611110002_incoming_queue` to an isolated `coecare_test` database. Run the backend suite with the service-authenticated FastAPI service running; `incoming-queue.test.ts` covers exact receipt events, immutable timestamps, the five-referral priority/arrival example, pagination and filters, clinical-role checks, mandatory reasons, concurrent reviews, deadline boundaries, idempotent escalation, acknowledgement, rejection/cancellation/completion, unknown legacy receipt times and AI failure handling. Synthetic protocol rules exist only in disposable tests; they are not clinical evidence and are never loaded into the application database.

Run Python `python -m unittest discover -s tests -p 'test_*.py'` and frontend `npm test`. The rules-engine tests verify missing observations, units, rule precedence, authentication, and rejection of patient-identity/operational-prediction inputs. Frontend tests verify permission-dependent actions, disabled recommendations, local-time filters, priority review and server-side filtering.

Set `REFHEALTH_QUEUE_BROWSER_TEST=1`, `DATABASE_URL` to the isolated coecare_test schema, and `PLAYWRIGHT_BASE_URL` to the isolated frontend, then run `npx playwright test tests/incoming-queue.spec.ts`. It creates synthetic hospital users, grants clinical permission through the authorized API, configures operational policy through the UI, receives referrals, confirms priorities, checks live ordering/filtering/audit/acknowledgement, completes the referral workflow, checks reload persistence and automatic arrival refresh, and captures desktop/390px screenshots in `.local/incoming-queue/`. It preserves the rule forbidding self-granted membership changes.
