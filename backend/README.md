# Backend

Fastify 5, TypeScript, Prisma 6 and PostgreSQL. No Express or MongoDB. Run all commands from this directory in Git Bash.

The RefHealth AI Assistant route forwards only authorized hospital context to the AI service. Groq generates final responses; Gemini embeddings are used for semantic retrieval when configured.

```bash
cp .env.example .env
npm ci
npm run generate
npm run migrate
npm run seed
npm run dev
```

`seed` creates only the configured platform administrator and never resets an existing password. `npm run build` compiles to `dist`; `npm start` serves the build. `npm run docs` regenerates `docs/openapi.json` from the live route schemas without requiring AI requests. `/docs` serves Swagger UI.

Prisma generates the client into `generated/prisma/`; application and seed imports use that directory. It is generated build output and is excluded from version control. Run `npm run generate` before building and include `generated/` alongside `dist/` in packaged deployments (the Dockerfile generates it inside the image). Stop processes using the generated client before regenerating it on Windows if its engine DLL is locked.

Migration `202611110001_chat_threads` adds private `ChatThread` rows and ordered thread associations to existing `Conversation` rows without replacing message IDs, text, sources or knowledge links. It collects each existing user/hospital history into a thread named **Earlier conversations**, ordered by timestamp and ID; it does not infer historical topic boundaries. Apply the migration before serving the new backend.

`GET /assistant/threads` provides a cursor-paginated list ordered by recent activity. `GET /assistant/threads/:id` provides messages in chronological sequence, with `nextBefore` for older pages. Chat requests may include `threadId`, `expectedVersion` and a UUID `clientRequestId`; omitting `threadId` starts a new chat on successful completion. The backend reads its last eight persisted pairs rather than trusting the deprecated `history` input. Atomic version checks prevent parallel requests from saving against stale context; matching retries reuse their saved result instead of duplicating it. Ownership is checked for reads/writes and enforced by the conversation/thread composite foreign key. The legacy flat `/assistant/conversations` endpoint remains available.

## Modules and boundaries

| Module | Responsibility |
|---|---|
| `app.ts` | Fastify, access-token/session verification, hospital status checks, secure errors, schema registration |
| `auth.ts` | Scrypt passwords, JWT access/refresh, refresh rotation, revocation, activation/recovery tokens |
| `hospitals.ts` | Platform registration controls and hospital-scoped profile/catalog/operations/members |
| `referrals.ts` | Patient ownership, receiving permissions, optimistic concurrency, lifecycle and verified outcomes |
| `intelligence.ts` | Authorized context, AI gateway results, knowledge review, conversations, feedback and training export |
| `sources.ts` | Explicitly permitted public HTTPS collection, IP restrictions, size/time limits, persistent jobs |

System administrators cannot query hospital operations or patient referrals. Every protected request rechecks the session, user status, membership and hospital approval in PostgreSQL. Incoming referrals require hospital-admin role or `REFERRAL_RECEIVE`; receiving access begins only after submission. Rejected/cancelled referrals retain their authorized history. `KNOWLEDGE_REVIEW` delegates review within the user's hospital.

Patient identifiers are unique per hospital; other hospitals see a patient's referral-specific record only in an authorized incoming referral. AI requests never include patient names, identifiers or clinical summaries. Capacity is private until explicitly shared. Audit records contain action and resource IDs, not patient contents or credentials.

JWT access lasts 15 minutes and is kept in frontend memory. JWT refresh lasts seven days, is stored in an HttpOnly/SameSite Strict cookie, and is hash-tracked in PostgreSQL. Refresh rotates and revokes the prior session. Logout, password recovery and user deactivation revoke sessions. Account tokens are random, hash-stored, expiring and single-use. Recovery requests are logged; a platform operator verifies identity and securely delivers a token. Email delivery is not configured.

List routes accept `page` and `limit` (default 30, maximum 100). The private training export uses a cursor. API mutations have Zod validation; Swagger schemas derive from the same contracts. Lists currently return a bounded page rather than total counts. Do not use an unaudited public database connection or cache patient responses.

## API families

| Routes | Scope |
|---|---|
| `/auth/*`, `/hospitals/register` | Authentication, activation/recovery and registration |
| `/admin/*` | Platform administrator only; hospital registrations, access, settings, aggregate AI counts |
| `/workspace*` | Own approved hospital; elevated mutations require hospital admin |
| `/hospitals` | Approved directory, filtered by name/location/service/specialty |
| `/patients`, `/referrals*` | Hospital ownership and explicit referral participants |
| `/intelligence`, `/predictions/:id/feedback` | Own hospital predictions and unverified feedback |
| `/knowledge*`, `/assistant/*` | Approved shared knowledge, private conversations and review |
| `/internal/learning-export` | Service key only; verified patient-free training observations |

Full request schemas: [`docs/openapi.json`](docs/openapi.json).

## Tests

Use a disposable PostgreSQL database whose URL contains `coecare_test`. Start the AI service with an isolated `CORECARE_DATABASE` and `CORECARE_MODEL_DIR`, then run:

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/coecare_test'
export JWT_SECRET='use-an-isolated-test-secret-at-least-32-characters'
export AI_SERVICE_KEY='same-as-the-isolated-ai-service-key'
export NODE_ENV=test
npm run migrate
npm test
```

Tests create uniquely named synthetic hospitals and patients and retain them in the disposable database for inspection. They never delete or reset a database. Do not point these tests at production. The application has a global per-process rate limit; scale behind an appropriate shared ingress rate limiter.


## Incoming referral queue

Migration `202611110002_incoming_queue` adds separate UTC `submittedAt`, `receivedAt`, and `acknowledgedAt` fields, clinical observations, recommendation/confirmation metadata, a hospital queue policy, and immutable-by-API queue audit events. `receivedAt` is generated from the database server clock after submission is written and before the atomic destination-delivery transaction commits. Failed deliveries roll back both events. It represents delivery into the receiving workspace in this single-database architecture, not patient arrival at the hospital. Receipt and submission timestamps cannot be rewritten after being set (database trigger). Historical receipt times remain NULL rather than being inferred from creation/submission. Historical submission/acceptance/rejection events provide the only timestamp backfill evidence.

The queue uses **confirmed priority only**: Critical, High, Medium, Low, then unassigned; earliest `receivedAt` and then referral ID break ties. Unassigned referrals remain explicitly flagged, with a dedicated review count/filter. Unknown historical receipt times sort last within their priority. Alternative arrival/wait views are explicitly labeled. AI suggestions never change queue order until a clinician confirms a priority.

Hospital administrators and workers with `REFERRAL_RECEIVE` can open the queue, acknowledge and inspect its audit events. **All clinical reviewers, including administrators, additionally require `REFERRAL_TRIAGE`.** Administrators grant it to authorized colleagues through Team & permissions; existing permissions and the prohibition on changing one's own membership are preserved. Workers need both permissions. Configuration remains hospital-administrator-only. System administrators have no patient-queue access.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/incoming` | Paginated receiving-hospital queue, server time, review count, filter choices, own workload forecast and selected-destination delay predictions |
| GET | `/incoming/policy` | Hospital timezone, deadlines, emergency procedure, clinical protocol status |
| POST | `/incoming/policy` | Replace policy using its current `version`; retain an audited revision |
| POST | `/incoming/:id/acknowledge` | `{version}`; acknowledge independently of acceptance; repeated acknowledgement is idempotent |
| POST | `/incoming/:id/priority` | `{version, priority, reason}`; confirm/override with a nonblank reason of at least five characters |
| POST | `/incoming/:id/recommendation` | `{version}`; future approved-protocol assessment, requiring clinical-review permission |
| GET | `/incoming/:id/events` | Authorized, paginated arrival/priority/acknowledgement/escalation/status evidence |

`GET /incoming` accepts `page`, `limit` (1?100), `priority` (CRITICAL/HIGH/MEDIUM/LOW/REVIEW_REQUIRED), `review=true`, `originId`, `service`, `status` (active by default, or a status/ALL), `acknowledged=yes|no`, `overdue=true`, `arrivedFrom`, `arrivedTo` (ISO timestamps with offset), `minWaitingMinutes`, and `sort=priority|arrival|waiting`. Waiting sort/minimum-wait filters apply to unacknowledged SUBMITTED referrals. Default ordering is applied before pagination. Completed/rejected/cancelled referrals are removed from the active queue but retain their timestamps and audit trail.

Policies contain `timezone` (IANA name; initial workspace convention Africa/Nairobi), `deadlines`, `emergencyProcedure`, `protocol` (null by default), and `version`. `deadlines` maps selected priority names or REVIEW_REQUIRED to `{minutes, warningMinutes}`. The warning lead cannot exceed the deadline. No universal deadlines are seeded. A policy snapshot is retained at receipt, so changing a policy affects future arrivals. Clinical priority changes recalculate the deadline from the original receipt using that snapshot, never restarting the waiting clock. Unknown receipt/no configured deadline means no invented deadline.

The server checks acknowledgement deadlines every five seconds independently of optional AI processing, emits at most one approaching and one overdue notification per referral, and records the reason/policy/deadline in queue events. Overdue supersedes an unissued approaching warning. Acknowledged or closed referrals stop escalation. Alerts never change clinical priority. Browser queries refresh every ten seconds without a page reload; counters use backend time and hospital-local display. Notifications are filtered by actual referral access.

### Clinical recommendation boundary

**No approved and clinically validated protocol was provided. Automatic clinical recommendations are disabled in existing hospitals.** No clinical rules, thresholds, model, or operational deadlines were invented or installed. Clinicians assign priorities now. Patient urgency and free-text summaries remain visible for human review.

The future FastAPI `/integration/clinical-priority` adapter is service-authenticated and stateless. It executes a hospital-supplied deterministic protocol, not an LLM. A protocol requires name, version, reference, approval authority/date, `approvalAttested: true`, `clinicalValidationReference`, required structured fields, and rules. Each rule has an ID, priority, explanation and a conjunction of typed conditions. Fields are urgency, service, specialty, structured symptoms/risk indicators, or named vitals with explicit units. Operators are categorical equality/list membership or numeric equality/gte/lte. No natural-language symptom parsing or arbitrary executable expressions are supported. All referenced fields must be present and units must match; missing information/no matched rule returns clinical-review-required, never a default LOW. The highest matching recommendation is explained and saved separately from confirmation. **Approval metadata is evidence supplied by the institution, not software certification of clinical validity.** Clinical governance must validate the protocol and its implementation before configuring it for real care.

Optional referral creation field `clinicalObservations` contains `symptoms: string[]`, `riskIndicators: string[]`, and `vitals: {name: {value: number, unit: string}}`. The local rules service receives these minimized observations/service/urgency and the approved protocol; no patient name, identifier or free-text clinical narrative is sent to it or any LLM. An AI timeout/invalid response leaves the referral saved and explicitly requiring review, preserves any confirmed priority, and records failure evidence. An authorized reviewer can retry later. Restarted workers pick up pending recommendations; a five-second service timeout cannot block acknowledgement monitoring. No existing delay/workload model is repurposed as a clinical urgency model.

Operational delay estimates and workload forecasts are displayed separately, with timestamps/unavailability. The learning export uses actual acknowledgement time, including acknowledgement before acceptance, while preserving historical evidence. The assistant receives only permission-scoped aggregate queue counts and capabilities, not patient details or clinical audit narratives.
