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
