# Implementation report — RefHealth AI

## Separate saved chats and left-side history — 11 November 2026

The assistant now has a **New chat** button and a **Chat history** panel to the left of the conversation. Saved chats are titled from their first message and ordered by latest activity. Selecting a chat restores its own ordered messages; continuing it moves it to the top. The selected chat survives reload through its URL. Older chat pages and earlier message pages can be loaded. The panel moves above the chat at phone widths.

The old implementation stored individual question/reply pairs in one continuous history, without conversation boundaries. Migration `202611110001_chat_threads` adds private threads, a sequence number and ownership constraints while preserving all original message fields and knowledge links. Older pairs are grouped per user/hospital under **Earlier conversations**; no historical topic boundaries are guessed. Before/after fingerprints matched for User, Membership, Hospital, Conversation, KnowledgeRecord and Prediction in the application database and both isolated test schemas. At migration time the application retained all **15 question/reply pairs, 13 users, 12 memberships, five hospitals, 11 knowledge records and three predictions** unchanged apart from the new thread associations on conversations.

### Behavior and protections

- Backend history comes from the last eight persisted question/reply pairs in the selected owned thread. Browser-provided `history` remains accepted for compatibility but is ignored; a new chat has empty model history. All older messages remain stored and accessible through pagination.
- Both user ID and hospital ID restrict list, read and append requests; a composite foreign key prevents messages from being associated with another owner's thread. Hospital administrators cannot read their workers' private chats. System administrators remain outside hospital chat.
- Message writes, thread versions, proposed knowledge and audit entries commit atomically. Version checks reject conflicting simultaneous sends. A stable client request ID and request fingerprint allow a retry to reuse the saved response without adding a duplicate.
- New empty drafts are saved when their first reply succeeds. Failed requests retain the current draft for retry. Sidebar switching is disabled while a request or recording/preparation is active. Switching unmounts the old pane and releases capture/playback resources. Media attachment type and voice transcript are retained; raw media is not stored.

### Files and verification

Main changes: `frontend/src/assistant.tsx` and `assistant.css` (new), extraction from `pages.tsx`, `backend/src/assistant-threads.ts` (new), `backend/src/intelligence.ts`, the Prisma schema/migration, regenerated backend OpenAPI, and regression fixtures/tests. Prisma now generates into `backend/generated/prisma`; application and seed imports use that directory. This avoided overwriting a DLL locked by the running Windows backend. The generated directory is ignored and must be generated/included in packaged builds; the existing Docker build generates it. No application account, role, credential, hospital profile or model artifact was reset or replaced.

| Check | Result |
|---|---|
| Backend database-backed suite | **18 passed**, including ownership, server-built context, retry deduplication, simultaneous writes and pagination beyond 40 replies |
| Frontend component suite | **14 passed**, including New chat, reopening history, older messages and media cleanup |
| Backend/frontend production builds | **Passed** |
| Updated live-test TypeScript checks | **Passed** |
| Real-provider saved-chat browser workflow | **Passed in 21.4 seconds overall**: two separate chats, continuing the first with its saved test-code context, activity ordering, reopening, reload and mobile overflow check |
| Existing cited-response browser rendering case | **Passed in 9.9 seconds overall** with its updated mocked response contract |
| Migration preservation | **Passed** for application and both test schemas; 15 / 49 / 14 pre-existing question/reply pairs respectively |
| Primary application readiness | Backend, frontend and authenticated AI health **HTTP 200**; new history routes loaded |

Desktop and 390px phone screenshots were inspected and remain under ignored `.local/chat-history/`. The database-writing behavioral tests used only synthetic accounts in `coecare_test` on port 55433. The application database received the preserving schema/history migration, not test accounts or conversations. AI/model code was unchanged for this feature, so the Python/model suites were not repeated. Existing provider quota/connectivity and cloud-speech model-term dependencies remain unchanged.

## Hospital workspace awareness and privacy boundaries — 11 November 2026

The assistant now receives current, role-filtered hospital workspace facts rather than only profiles and approved knowledge snippets. As requested, it remains available only in hospital workspaces; system administrators still cannot open hospital chat. A real three-turn browser conversation verified the user's role and current capacity, changed the capacity through the authorized application API, confirmed that the next answer used the new value, and received a safe refusal to a request for other hospitals' patient names and staff passwords. All three replies survived reload.

### Root causes and changes

The previous backend did not supply referral totals, today's activity, current role permissions, administration queues, team aggregates or model monitoring context. Semantic retrieval could also drop an exact current record behind eight other matches. Supplying every new summary on every turn initially exhausted Groq's token quota on a simple follow-up; the final retrieval design retains current access boundaries and the own-hospital profile while selecting additional exact summaries by topic.

- New `backend/src/assistant-context.ts` constructs a fresh database snapshot with authorized referral totals/statuses, UTC+03:00 daily activity, verified-outcome and prediction counts, latest saved workload forecast, full approved hospital catalogs/opening-hour text, and permitted capacity. Capacity remains unknown when missing or unshared. Administrator-only context adds aggregate team access, knowledge queues, external-source/job status and bounded audit action summaries. Existing receiving/review permissions determine worker context.
- Patient identity, clinical/outcome narrative, transition reasons, credentials, hashes, tokens, staff identities and other users' conversations are excluded from the new structured context. Other hospitals' private knowledge and capacity remain excluded. Explicitly selected referrals use the existing authorization scope. Model state/metrics are scoped and describe experimental or insufficient evidence accurately; no model is trained or activated.
- Updated `ai-service/corecare/integration.py` retains exact selected workspace summaries outside semantic top-eight retrieval, prioritizes current records over old chat answers, includes complete authorized profiles for network facility comparisons, and avoids unrelated hospital profiles on simple own-hospital questions. Prompts distinguish current observations, saved predictions, scope, date windows, missing evidence and privacy boundaries. General workflow guidance does not grant chat write access.
- Updated `backend/src/intelligence.ts` validates every returned source ID against this request's authorized context and rebuilds source content/attribution/timestamps on the server. Unknown sources are rejected before saving a conversation or proposal.
- Updated `frontend/src/pages.tsx` explains the expanded questions and privacy scope. No schema migration, account/role change or credential reset was required.

### Verification

| Check | Result |
|---|---|
| AI integration/provider tests | **52 passed** |
| Backend database-backed tests | **17 passed** |
| Frontend component tests | **12 passed** |
| Backend/frontend production builds | **Passed** |
| New browser test TypeScript check | **Passed** |
| Real provider/browser workspace regression | **Passed in 16.8 seconds overall**: 13 beds → authorized update → 9 beds, current role, privacy refusal, citations and reload persistence |

The regression additions cover fresh records, administrator/worker differences, incoming-referral restrictions, patient/private/credential field exclusion, forecast/registry metadata minimization, source forgery rejection without persistence, exact context retention, complete network comparisons and reduced irrelevant context. The first live attempt reached Groq HTTP 429 after a correct initial answer; it is not counted as passing. The final complete run used the optimized context with real provider responses and no intercepted chat requests.

Database-writing tests used synthetic accounts in `coecare_test` on port 55433; browser tests used its existing `assistant_directory_regression_20261110` schema. Existing application accounts, credentials, hospital records, permissions and model artifacts were preserved. The primary AI service was restarted with the final code; primary frontend/backend services remain running. Regression files are `backend/tests/workflow.test.ts`, `ai-service/tests/test_integration.py` and new `frontend/tests/assistant-workspace-live.spec.ts`; operating instructions are updated in the frontend README, platform integration, deployment and testing guides.

This improves supported system knowledge and enforces data boundaries; it does not guarantee universal factual correctness. Approved knowledge is bounded to the newest 300 authorized records, audit summaries to 20 events, selected-referral predictions to the latest three, and verified metrics to 5,000 predictions in 90 days. Those summaries must not be presented as unbounded history. Provider availability/quotas and the previously reported speech-model terms requirement remain operational dependencies. Unknown, stale or unauthorized facts must be acknowledged rather than invented.

## Image and voice conversation repair — 10 November 2026

Image questions, visual follow-ups, audio-file uploads and microphone recordings passed real browser/provider tests. Voice transcripts now persist as the private user message and reach subsequent chat turns. Spoken-reply playback is implemented and browser audio decoding/playback passed with a known WAV. **Live cloud speech generation remains blocked by the Groq account's unaccepted Orpheus model terms.**

### Causes and changes

- Voice transcription previously disappeared after generation: the saved question was the generic recording prompt. The AI now returns the transcript and normalized user message; Fastify requires and saves them, and React uses them immediately in history. Spoken questions follow the same purpose routing and citation validation as typed questions.
- Browser MP4/M4A recordings were inconsistent with the API MIME allowlist. The browser normalizes audio types and both APIs accept MP4. Audio-file upload now provides an alternative to microphone capture.
- Capture/preparation had lifecycle races. Sending is blocked until media is ready, microphone permission failures are actionable, recordings stop after 30 seconds, tracks stop on completion/error/navigation, and temporary object URLs are released. Images are bounded, resized and compressed before submission.
- Read-aloud failures were silent. Listen/Stop now selects a voice matching the application language, handles errors and cancels playback on navigation. If browser speech is unavailable or fails, it requests segmented WAV audio through the authenticated backend. The backend reads only the current user's saved reply in their current hospital, never arbitrary client-supplied speech text. The AI uses the existing server-side provider key; audio is not persisted. Speech requests retain authentication, ownership checks, bounded input/output, TLS verification and timeouts.

Main implementation files: `frontend/src/assistant-media.ts` (new), `frontend/src/pages.tsx`, `frontend/nginx.conf`, `backend/src/intelligence.ts`, and `ai-service/corecare/integration.py`. Updated examples/generated contracts: `ai-service/.env.example`, `ai-service/openapi.json`, `backend/docs/openapi.json`. Added/updated tests: `frontend/src/assistant-media.test.tsx`, `frontend/tests/assistant-media-live.spec.ts`, `frontend/tests/assistant-speech.spec.ts`, `backend/tests/workflow.test.ts`, `ai-service/tests/test_integration.py`, and `ai-service/tests/prepare_media_fixtures.py`. Media operation and reproduction instructions are in the frontend README, platform integration guide, deployment guide and testing guide.

### Verification and remaining setup

| Check | Result |
|---|---|
| AI integration/provider tests | **48 passed** |
| Backend tests against isolated PostgreSQL | **16 passed**, including cross-hospital and same-hospital/different-user speech denial |
| Frontend component tests | **12 passed**, including capture cleanup, transcript history, cloud fallback and cancellation |
| Backend/frontend production builds | **Passed** |
| Live image and voice browser workflows | **2 passed in 29.6 seconds overall**; actual Qwen vision, Whisper transcription and Groq chat; persisted visual follow-up and spoken history |
| Browser speech playback and setup-error checks | **2 passed in 7.1 seconds overall**; known-WAV decoding/playback/Stop, and real provider rejection shown without losing the saved reply |
| Live speech provider diagnostic | **Blocked**: HTTP 400 `model_terms_required` for `canopylabs/orpheus-v1-english` |

The browser playback success uses a known WAV fixture in place of generated speech; it does **not** prove live synthesis. A separate diagnostic tried all seven installed Windows voices: each returned `synthesis-failed` in this automated environment. The cloud fallback reaches the real provider but its organization administrator must accept the [Orpheus model terms in the Groq console](https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english). No terms were accepted or credentials changed. With the current Groq configuration the fallback defaults to that model and voice `troy`; optional `LLM_SPEECH_MODEL`/`LLM_SPEECH_VOICE` override them. The repair is deployed locally, but end-to-end generated spoken replies still require that external setup and a subsequent live check.

The first live media run failed on external provider connection errors. The same workflows subsequently passed; the failed run is not counted as successful. Voice tests use a public speech fixture through real Chrome MediaRecorder with a fake microphone, not a physical microphone. Actual speaker audibility, mobile Safari and the Nginx container were not tested. The original prediction/model tests were not rerun for this media change; prediction models and artifacts were untouched.

All database-writing checks used synthetic accounts in `coecare_test` on port 55433; media browser checks used its `assistant_directory_regression_20261110` schema. Application accounts, credentials, roles, hospital records and model artifacts were preserved. Raw uploaded media and generated playback audio are not retained by this application. The primary AI service was restarted with this implementation on port 8000; main frontend/backend services remain available.

## Active-hospital follow-up and response contract repair — 10 November 2026

The reported three-message sequence now passes in the live browser: registered-hospital count, assistant purpose, then “which are the active hospital currently”. The third response lists every approved hospital in the test database, cites the live directory, and remains saved after reload. A separate stateless AI check used a read-only snapshot of the actual application database and returned HTTP 200 with all five actual approved hospital names.

### Root causes and changes

- **Output contract was too loose.** The serving logs recorded both `Provider omitted citations for retrieved information` and `slice(None, 5, None)`. JSON-object mode allowed missing citations and an object in the optional `proposals` field; slicing that object caused a `KeyError`, which the app mislabeled with the same generic “invalid or ungrounded answer” message. Supported Groq models now receive a strict JSON schema with required typed fields and source IDs constrained to the current context. Local validation remains enabled. Malformed optional proposals are discarded and never converted into knowledge records, preserving an otherwise valid cited answer.
- **The data supplied to the assistant did not establish active status or a complete count.** Profiles omitted `status`, and similarity retrieval returned at most eight records. The backend now adds status to profiles and builds a fresh, complete snapshot of approved hospital IDs/names/statuses with the exact count and timestamp. Count/list requests and referring follow-ups receive every snapshot part, bypassing the top-eight limit for this directory context. Other records retain normal semantic retrieval. Active means approved for access to this system, not open now or accepting referrals. Non-approved hospitals and private contact/capacity/patient fields are excluded from the snapshot.

Changed implementation files: `ai-service/corecare/integration.py`, new `backend/src/assistant-directory.ts`, and `backend/src/intelligence.ts`. Updated regression coverage: `ai-service/tests/test_integration.py`, new `backend/tests/assistant-directory.test.ts`, `backend/tests/workflow.test.ts`, and `frontend/tests/assistant-live.spec.ts`. Operating/test guidance was updated in `ai-service/docs/platform-integration.md`, `docs/deployment.md`, `docs/testing.md`, and this report.

### Verification

| Check | Result |
|---|---|
| AI integration/provider tests | **42 passed** |
| Backend tests with isolated PostgreSQL and running AI | **14 passed** |
| Backend TypeScript build | **Passed** |
| Browser test TypeScript check | **Passed** |
| Live three-turn browser regression | **Passed in 38.8 seconds overall**; exact count, all five fixture hospital names, citations, history and persisted third reply |
| Actual application database snapshot → primary AI | **HTTP 200**; all five actual approved hospital names and a live-directory citation |
| Larger-directory regressions | Twelve hospitals retained beyond the retrieval limit; 250 hospitals retained across bounded source documents |

The first live browser attempt on the accumulated test dataset encountered Groq HTTP 429 on its third request, after the first two strict-schema responses succeeded. A separate cold-client diagnostic encountered an external connection failure. Neither is counted as a passing run. The final browser run used a fresh schema `assistant_directory_regression_20261110` inside the existing isolated `coecare_test` database on port 55433, seeded with four approved fixtures before the browser created its fifth hospital. Earlier test data was preserved. This reproduces the application's five-hospital case without accumulated test context. Provider quota and external connectivity remain operational limits.

The primary AI service was explicitly restarted on port 8000 with current code, and the backend development process reloaded its changes. Existing application accounts, credentials, hospital statuses and model artifacts were not changed. The actual database snapshot check was read-only; browser-created accounts and conversations were confined to the isolated schema.

## Earlier assistant purpose follow-up — 10 November 2026

The reported sequence now passes in the browser: “how many hospitals are registered in this system” receives a cited response, followed by “ok what is your purpose in this system” receiving a normal explanation without a red error. Both replies persist after reload.

**Root cause:** a live diagnostic reproduced HTTP 503 with five retrieved synthetic hospital profiles, a nonempty Groq answer and `source_ids: []`. The precise rejection was `Provider omitted citations for retrieved information`. The validator demanded a hospital citation whenever retrieval found any profile, even though the question could be answered from the system's application description. This was an application grounding/routing mismatch.

**Fix:** complete questions about the assistant's identity, purpose, capabilities and limitations now use the system description without hospital retrieval. Groq still generates the answer. Conservative full-question matching supports conversational prefixes and common paraphrases; compound or unmatched questions and all attachments retain normal retrieval. Provider output cannot enable the exemption. Hospital answers with retrieved context still require citations, and invented citation IDs remain invalid. The help prompt distinguishes explaining application workflows from executing administrative actions. Validation failures now log an application-defined reason without provider answer content or credentials.

The first browser run also exposed a stalled Windows reload: the old worker kept serving after the reloader announced a change. The identified primary AI process and its worker were explicitly stopped, then the current service was started on port 8000 without automatic reload. Startup instructions now describe explicit restarts and verification of the affected request.

| Verification in this follow-up | Result |
|---|---|
| Regression before the fix | Reproduced the reported 503 in both a live diagnostic and an automated test |
| Assistant/integration and transport suite | **39 passed**: 29 integration tests and 10 transport tests |
| New regression coverage | Exact follow-up with history, 12 help paraphrases, hospital/mixed questions still requiring citations, fabricated citation rejection and preserved media routing |
| Focused live browser regression | **Passed** in 18.9 seconds overall; both HTTP 200 replies, expected citation behavior, no error alert, persistence after reload |
| Browser test TypeScript check | **Passed** |

A longer live conversation passed the purpose question but later hit Groq HTTP 429. That extended run is not counted as passing. After the quota window recovered, the focused two-turn regression passed against the repaired primary service. External quota exhaustion remains a separate provider limitation. This follow-up does not claim to solve network-wide hospital counting from a retrieved subset.

Changed files: `ai-service/corecare/integration.py`, `ai-service/tests/test_integration.py`, `frontend/tests/assistant-live.spec.ts`, `README.md`, `ai-service/README.md`, `ai-service/docs/platform-integration.md`, `docs/deployment.md`, `docs/testing.md`, and this report. Database-writing browser tests used synthetic accounts and knowledge in `coecare_test` on port 55433. Existing application accounts, credentials, permissions and model artifacts were not changed. Main frontend/backend services and the repaired AI service remain running.

## Earlier assistant transport repair — 10 November 2026

The running application assistant now completes a real four-message Gemini/Groq conversation, including approved-source citations, follow-up context, a short greeting and persistence after browser reload. The final Playwright run passed all four workflows against the repaired primary AI service at `http://127.0.0.1:8000`. These results supersede the earlier incomplete live checks recorded below.

### Confirmed causes

1. **Outdated running service:** the backend targeted port 8000, where a Python process started before the current assistant implementation was still serving the old `CoeCare-Health AI` API. The reported “Gemini and the configured language provider are unavailable” wording belonged to that old implementation. A newer service on another port did not change the backend's target. The stale process was replaced; port 8000 now reports `RefHealth AI` and the current chat contract.
2. **Fragile provider transport:** fresh connections, a short embedding timeout and no transient-error retry made intermittent Gemini/Groq connection failures immediately fail chat. Live checks reproduced transport failures. The replacement transport pools HTTPS connections, keeps certificate verification enabled, retries only temporary failures up to three attempts, respects provider retry delays and applies a shared 80-second provider budget. Authentication/configuration errors are not retried.
3. **Repeated embedding load:** every turn re-embedded all supplied documents. A live multi-turn check reached Gemini HTTP 429 after two successful answers. Unchanged document vectors now use a bounded, 15-minute in-memory cache scoped to the requesting hospital and provider configuration. Content changes invalidate entries; only documents authorized for the current request can be retrieved. Queries remain fresh. Missing document vectors and the query are batched in groups of at most 100.
4. **Additional contract and timeout defects:** the UI silently discarded two-character greetings, and both APIs required three characters. Trimmed nonempty messages are now accepted throughout. Simple greetings still use Groq but avoid unnecessary retrieval. Assistant-specific deadlines now align: 80 seconds for provider work, 90 seconds in Fastify by default, and 100 seconds in the browser and Nginx assistant route. Failed browser requests retain the draft for retry. Audio is transcribed before one retrieval pass.

### Changed files

| Area | Files and purpose |
|---|---|
| Provider transport and retrieval | `ai-service/corecare/provider_http.py` (new), `corecare/embedding_cache.py` (new), `corecare/integration.py`; pooled transport, bounded retries, authorized vector reuse and short-message handling |
| Runtime dependencies and API schema | `ai-service/requirements.txt`, `requirements-dev.txt`, `openapi.json`; HTTPX is a serving dependency and the generated schema accepts short messages |
| Backend | `backend/src/config.ts`, `src/gateway.ts`, `src/intelligence.ts`, `.env.example`, `docs/openapi.json`; assistant deadline, accurate timeout error and matching validation |
| Frontend/proxy | `frontend/src/pages.tsx`, `frontend/nginx.conf`; short-message submission and sufficient assistant response time |
| Regression coverage | `ai-service/tests/test_provider_http.py` (new), `tests/test_integration.py`, `frontend/src/assistant.test.tsx` (new), `frontend/tests/assistant-live.spec.ts` |
| Operating instructions | `README.md`, `ai-service/README.md`, `ai-service/docs/platform-integration.md`, `docs/deployment.md`, `docs/testing.md`, this report; restart guidance, transport behavior and reproducible verification |

### Final results

| Check | Result |
|---|---|
| Complete Python suite | **72 passed**: 38 original model tests, 24 integration tests, 10 transport tests |
| Backend suite with isolated PostgreSQL | **12 passed** |
| Frontend unit/component tests | **3 passed**, including short greetings and draft-preserving retry |
| Backend and frontend production builds | **Both passed** |
| Generated API schemas | Regenerated; running backend and primary AI both expose minimum question length 1 |
| Final browser suite | **4 passed in 1.3 minutes**: administration, referrals, assistant rendering, and the real four-message provider conversation |
| Live conversation assertions | HTTP 200 replies, expected approved source, correct synthetic information, history lengths 0/2/4/6, persisted replies after reload |

Database-writing tests used only `coecare_test` at port 55433 and synthetic accounts/knowledge. The final browser stack used ports 5175/3001 and the actual repaired AI service on port 8000. Main database inspection was read-only and still found 12 users, 11 memberships and five hospitals. No existing account was reset, activated, deleted or reassigned by this repair; provider credentials and authentication/authorization rules were preserved. The original three prediction components and model artifacts were retained.

An intermediate live run still exhausted retries during an external network failure; a subsequent complete run and the final deployed-service browser run passed. Bounded retries cannot guarantee availability during provider outages or exhausted quota. Those cases remain explicit errors rather than fabricated answers. Live image/audio provider calls and the Nginx container were not exercised; media contracts were covered by automated tests. See [test instructions](testing.md#optional-live-assistant-verification) for reproducing the opt-in live check.

## Resumed verification before the assistant repair — historical, 10 November 2026

The existing Groq/Gemini implementation was inspected and tested without replacing the application or changing prediction logic. React sends authenticated requests through Fastify; Fastify obtains authorized PostgreSQL knowledge and hospital profiles, forwards that context to FastAPI, and persists the resulting private conversation. Gemini embeds the query and documents for cosine-similarity retrieval; Groq generates the final answer, whose citation IDs are checked against retrieved sources.

Verification results at that earlier stage:

| Check | Result |
|---|---|
| Python AI regression and provider contract tests | 58 passed |
| Backend tests with real isolated PostgreSQL and AI HTTP service | 12 passed, including the parent workflow test |
| Frontend validation test | 1 passed |
| Backend TypeScript build | Passed |
| Frontend TypeScript and production build | Passed |
| PostgreSQL migration check | Both existing migrations applied; none pending |
| Existing Playwright workflows | 3 passed: administration/responsiveness, cross-hospital referral, mocked assistant rendering |
| Direct live Gemini → retrieval → Groq check | Passed with synthetic source citation and correct opening hours |
| Live running AI HTTP service | HTTP 200 with embedding retrieval and the expected synthetic source |
| New opt-in multi-turn live browser test | Incomplete: initial cited answers succeeded on two attempts, but subsequent provider requests failed; no full passing run |

The backend and browser checks used `coecare_test` on the existing isolated PostgreSQL instance at port 55433. Test frontend/backend/AI ports were 5175/3001/8003. AI test storage was placed under ignored `.local/ai-resume*`. The application database on port 5432 and pre-existing application servers were not modified by these checks.

Provider keys were found in the server-side configuration and were used only with synthetic hospital information. The direct live checks establish that both configured providers can work together. They do **not** establish reliable repeated operation: three attempts at the new browser test encountered provider/network failures. Two returned a Groq network-or-timeout error; a diagnostic run identified a Gemini connection `URLError` caused by `TimeoutError` after approximately 9.7 seconds. The diagnostic wrapper logged only host, elapsed time and exception types, and did not alter provider requests or application source. Provider failures surfaced as HTTP 503. Live multi-turn verification remains outstanding until connectivity is stable.

The new test covers explanations of all three AI components, approved private knowledge, citations, forwarding of conversation history, and persistence after reload. Its final history/persistence assertions were not reached in the failed live runs. Existing mocked contract tests cover history forwarding and the existing database suite verifies private conversation persistence. The opt-in test is skipped by default to keep ordinary test runs independent of paid providers; see [test setup](testing.md#optional-live-assistant-verification).

Files changed in this resumed pass:

- Added `frontend/tests/assistant-live.spec.ts` for the opt-in live workflow.
- Updated `README.md` so the AI startup command, backend example and documentation consistently use port 8000, with instructions for selecting another matching port.
- Updated `frontend/README.md` and `docs/testing.md` with live-test setup and boundaries.
- Updated `docs/deployment.md` to describe the implemented provider configuration and explicit 503 behavior.
- Updated this report with the current evidence and remaining live-network limitation.

Required provider variables remain `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY` and `EMBEDDING_MODEL` in the AI service. The backend needs a matching `AI_SERVICE_KEY`/AI `CORECARE_API_KEY`, `AI_SERVICE_URL`, its PostgreSQL `DATABASE_URL` and `JWT_SECRET`. The existing example uses `AI_TIMEOUT_MS=60000`; optional media still requires separate `LLM_VISION_MODEL` and `LLM_AUDIO_MODEL`. Credentials were not printed or copied into frontend files.

The original historical HTTP 422 still cannot be attributed without its request/log. The earlier history-length contract correction is retained and covered by the passing backend suite; successful live browser chat requests also demonstrate the current text contract accepts normal messages. Current observed live failures were 503 provider/network failures, not 422 validation errors.

The original delay, recommendation and workload implementations and model artifacts were preserved. Their synthetic regression tests passed; this does not approve them for real clinical use. A branding search found remaining old names only in compatibility identifiers (database names, `COECARE_BACKEND_URL`, `CORECARE_*`), the actual workspace path in `prompt.md`, the old-name mapping in `update.md`, historical reports and documentation explaining those exceptions.

The sections below retain the earlier implementation history. Their original test counts and unavailable-provider statements describe those earlier runs; the assistant repair section at the top is the current verification record.

## Follow-up — RefHealth AI branding and assistant provider alignment

The project identity is now RefHealth AI and the assistant identity is RefHealth AI Assistant in the active frontend, AI API metadata and assistant prompt. Historical/internal database names and existing environment variable prefixes were retained to avoid breaking integrations.

Text chat now requires Groq configuration and uses Groq for final responses. Gemini is used only for authorized query/document embeddings; query and document vector dimensions are checked before similarity ranking. If Gemini is not configured, lexical retrieval is labeled; if configured Gemini retrieval fails, the request returns an explicit unavailable error instead of silently switching methods. If Groq is not configured or fails, no retrieval-only response is presented as a completed assistant answer. Optional media processing uses separately configured Groq vision/transcription models.

AI-service configuration examples, Compose forwarding, frontend assistant privacy text and integration/deployment guidance were aligned. Automated provider tests use test doubles; no live Groq/Gemini connectivity or production deployment is claimed. The original HTTP 422 could not be reproduced because its request/log is unavailable. Contract inspection found that a long assistant reply could exceed the backend's shorter history limit; the backend now accepts the supported reply length and bounds each forwarded history turn to the AI service's 4,000-character contract. This closes that verified contract mismatch, but does not prove it caused the historical 422.

Follow-up verification: all 57 AI-service tests passed; the frontend's 1 test and production build passed; the backend TypeScript build and OpenAPI generation passed; and the backend workflow test source type-check passed. The PostgreSQL-backed backend suite and browser workflows were not run because the configured backend `.env` targets the non-test `coecare` database rather than the required isolated test database. Live provider requests were not made; provider behavior was validated with test doubles.

The legacy development prompts now use the current brand. Remaining old-name text is limited to the explicit old-to-new mapping in [`update.md`](../update.md), read-only dated reports in `ai-service/reports/`, and internal database/environment identifiers (`coecare`, `coecare_test`, and `CORECARE_*`) retained for compatibility.

## Scope and starting state

All 1,239 lines of `full-prompt.md` were read. Its four phases request backend, frontend, extension of the existing AI service, and integration/deployment preparation. `backend/` and `frontend/` were initially empty. The existing Python service already contained working models, a V6 feature audit, training/evaluation code, feedback storage, monitoring, model approval/rollback, and 38 regression tests.

The older `prompt.md` and archived AI results describe an earlier AI-only task. The current full-system instruction was applied without deleting or replacing those working AI components. No model or dataset was deleted, regenerated or promoted. The original AI database was not used for integration-test writes.

## Delivered backend

- Fastify/TypeScript REST service with PostgreSQL/Prisma, normalized schema, two SQL migrations, configurable environments, administrator seed, production build and generated Swagger/OpenAPI.
- Scrypt password hashes, JWT access and refresh tokens, rotating hash-tracked refresh sessions, HttpOnly/Secure production cookies, logout, revocation, activation/recovery tokens, and operator-mediated recovery.
- Platform-only hospital registration/approval/rejection/suspension, account controls, settings, health monitoring and aggregate AI statistics. Platform administrators cannot access patient or operational routes.
- Hospital memberships with receiving/review permissions; hospital profiles, coordinates, departments, specialties, availability-aware services/equipment, capacity, operating hours, staffing, announcements and immutable operational observations.
- Hospital-owned patient registration and draft referrals; explicit human destination selection; validated services/specialties; submission, acceptance, rejection with reasons, in-progress, completion, cancellation, history, notifications and verified outcomes.
- Optimistic referral versions and atomic history writes prevent conflicting concurrent state changes. Patient and referral access is checked in the backend, including receiving membership permission and lifecycle visibility.
- Authenticated AI gateway with timeouts, safe errors and validated ranking/model metadata; persisted prediction IDs, model versions, feedback and actual-versus-predicted summaries with insufficient-data indicators.
- Private author-scoped conversations, hospital knowledge proposals, explicit approval/rejection, source attribution, timestamps, sharing visibility and review dates. No patient identity or clinical summary enters the shared AI context.
- External source registration, explicit permitted-public-access collection, persistent jobs, SSRF restrictions, HTTPS/time/size/content-type controls and unverified source proposals. Social URLs remain unauthorized.
- Patient-free service-authenticated export of verified daily observations and referrals with prospective feature snapshots for the existing learning workflow.
- Zod request validation, exact-origin CORS/CSRF protection, rate limits, security headers, no-store responses, safe logging, audit events and paginated list APIs.

## Delivered frontend

- React/Vite/TypeScript/Tailwind workspace using Axios, React Router, TanStack Query, React Hook Form/Zod and Recharts.
- Responsive desktop/mobile layouts, common typography/components, role-specific navigation, protected access, field validation, loading, empty and actionable failure states.
- Login, hospital registration, activation/recovery, unauthorized access, platform administration, hospital overview, profile/catalog, capacity/operations, daily observations, team permissions and source collection screens.
- Patient/referral creation, AI review, ranked comparisons with reasons/timestamps/limitations, explicit destination submission, receiving decisions, history, completion, outcome entry and verification.
- Hospital directory filters; AI observations/predictions and feedback; model catalog; private assistant history with retrieved sources; knowledge proposal/review screens.
- Real backend statistics throughout. Access tokens stay in memory, refresh uses the HttpOnly cookie, and logout clears the query cache. Production bundles are split into framework/forms/charts/application chunks.

## Existing AI preserved and extended

- Original prediction APIs, three model components, leakage-safe feature generation, training scripts, model artifacts, synthetic datasets, verification, monitoring and deployment gates remain available.
- A separate `/integration/*` bridge accepts authorized registered-hospital context from PostgreSQL through Node. It does not depend on the legacy five-hospital demonstration CSV.
- Network ranking considers essential service/specialty eligibility, shared capacity, current workload, distance, queue length, observed acceptance/processing history and freshness. Approved delay/workload predictions can adjust ranking when their evidence requirements are met.
- Workload serving requires a supported hospital, verified historical inputs and an approved real-data model. It does not silently substitute an unapproved candidate.
- Retrieval uses approved context and returns source IDs/timestamps. Gemini supports semantic retrieval and Groq generates responses. Missing Gemini credentials produce labeled lexical retrieval; missing Groq credentials or configured-provider failures return an explicit 503. Invalid provider citations are rejected.
- Conversational extraction creates private unverified proposals, never confirmed facts. Hospitals explicitly approve shared facts.
- A controlled importer validates/deduplicates verified PostgreSQL observations into the existing learning store. Training still produces candidates; evaluation, approval and rollback remain explicit.

## Integration verified

The browser calls the Node backend through `/api`; Node calls the running Python service with a service credential and reads/writes real isolated PostgreSQL records. The tests exercised:

1. Hospital registration, platform approval and hospital login.
2. Hospital profile/catalog/capacity updates reflected in directory and retrieval.
3. Patient ownership and draft privacy.
4. AI eligibility/ranking across registered hospitals, with missing model predictions clearly unavailable.
5. Human destination selection and submission to a second hospital.
6. Authorized acceptance, in-progress, completion and outcome verification.
7. Feedback ownership and duplicate protection.
8. Knowledge proposal visibility, approval and immediate cross-hospital authorized retrieval.
9. Private conversation isolation, service outage behavior and preserved referral records.
10. JWT rotation, logout, suspended access, one-time recovery and authenticated learning export.

## Initial tests executed — 8 November 2026

| Check | Result |
|---|---|
| Existing AI baseline before integration | 38 passed |
| Final Python regression + bridge suite | 48 passed |
| Backend unit/database/AI workflow suite | 12 reported tests passed, including the parent workflow test |
| Frontend form-validation test | 1 passed |
| Playwright browser workflows | 2 passed: administration/responsiveness and cross-hospital referral completion |
| Prisma schema/client | Validation and generation passed |
| PostgreSQL migrations | Both migrations applied successfully to the isolated test database |
| Backend TypeScript build | Passed |
| Frontend TypeScript + production build | Passed; bundle-size warning resolved by splitting bundles |
| Swagger generation | Generated from registered backend routes |
| Desktop/mobile review | Browser screenshots inspected; mobile horizontal overflow check passed |

The backend tests use real PostgreSQL and a running AI HTTP service. Browser tests use actual UI actions and database persistence. Language/embedding provider tests use test-only responses; they do not claim successful live provider calls. Public-source restriction tests do not claim an authorized external hospital connection.

Verification found and corrected decimal-coordinate HTML validation, a refresh-cookie path mismatch through the `/api` proxy, and a desktop sidebar overflow. The first browser attempt reached an unrelated IPv6 localhost service; tests now target the project explicitly at `127.0.0.1`. A later API test used a stale Python process after its contract changed; restarting the owned test process resolved it. These failures were investigated rather than counted as passes.

## Remaining limitations and acceptance dependencies

The implementation is **not a claim that every production acceptance criterion is already satisfied**. The following remain explicit:

1. **Real prediction readiness:** no approved real-data delay/workload models were supplied. The V6 candidate's documented macro F1 gain over persistence is only 0.0034 and its High-class recall is worse; its gate remains failed. The 15-row synthetic delay dataset is not representative validation. Real-platform predictions therefore remain unavailable until representative verified data, evaluation and professional approval exist. Operational referral coordination and transparent ranking still work.
2. **Live provider reliability:** text, image and voice-input browser workflows passed against the repaired primary AI service. Intermediate runs also encountered connection failures and rate limits; pooling, bounded retries and document-vector reuse cannot eliminate external outages or exhausted quota. Cloud speech output requires the Groq organization administrator to accept Orpheus model terms before live synthesis can be verified. Physical microphone/speaker and deployment-specific load/availability acceptance remain outstanding.
3. **Social integrations:** Facebook/Telegram OAuth, token lifecycle and provider-specific collection adapters are not implemented. Their URLs are stored as registered/not-authorized, with no fake connection. Explicitly permitted public website/feed collection is implemented.
4. **Retrieval scale:** query embeddings remain per-request; unchanged authorized document vectors use a bounded process-local cache. A persistent pgvector index is not implemented. Assistant input is bounded to 300 approved knowledge rows plus hospital profiles, and operational lists are paginated. Large-network relevance, cost and latency require evaluation before scaling.
5. **Assistant orchestration:** users request recommendations in the referral workflow and provide a referral ID to discuss saved results. The assistant does not autonomously initiate clinical referrals or perform unrestricted natural-language tool execution.
6. **Monitoring scope:** original AI performance/drift monitoring remains available; the application adds bounded 90-day verified delay comparisons and workload observations. Comprehensive network workload forecast comparisons depend on approved models and populated verified histories.
7. **External collection:** public-source parsing produces bounded text excerpts for human review; IPv6-only hosts and automatic redirects are unsupported. Hospital permission/ownership is explicitly attested by its administrator, not independently certified by the software.
8. **Recovery delivery:** identity verification and account-token delivery are operator-mediated; email/SMS transport is not configured.
9. **Operational validation:** container builds, Vercel/Render deployment, TLS/backup restoration, load testing, independent security review, real institutional privacy governance and production model/provider acceptance were not performed. Hosting credentials and professional acceptance are required for those steps.
10. **Environment:** the existing Starlette/httpx test transport emits a deprecation notice. Tests passed, but a future dependency upgrade should revalidate model compatibility and transport behavior.

No unverified model was activated to make the UI appear complete. No external hospital site or social account was represented as connected without authorized collection. No production deployment was claimed.

## Handover

- Setup: [`../README.md`](../README.md).
- API schemas: [`../backend/docs/openapi.json`](../backend/docs/openapi.json) and each service's `/docs`.
- Test commands: [`testing.md`](testing.md).
- Deployment and troubleshooting: [`deployment.md`](deployment.md).
- AI integration/learning: [`../ai-service/docs/platform-integration.md`](../ai-service/docs/platform-integration.md).

The isolated test files/data live under ignored `.local/` and `frontend/test-results/`. Existing models/datasets and the user's PostgreSQL instance on port 5432 were preserved. No external hosting resources or OS schedules were created.
