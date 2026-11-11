# Deployment and operation

Deployment artifacts are prepared; no hosted resources were created and Docker images were not built during this implementation. The tested environment was local Windows, Node 25, PostgreSQL 18 and the existing Python 3.14 environment. Revalidate the container dependencies on your target before accepting a release.

## Production configuration

| Component | Required configuration |
|---|---|
| Backend | `DATABASE_URL`, random 32+ character `JWT_SECRET`, `CORS_ORIGIN`, `AI_SERVICE_URL`, `AI_SERVICE_KEY`, `HOST=0.0.0.0`, `NODE_ENV=production`, hosting `PORT` |
| Frontend | `VITE_API_URL=/api`; same-origin reverse proxy to backend |
| AI | `CORECARE_API_KEY` matching backend, separate `CORECARE_ADMIN_TOKEN`, persistent `CORECARE_DATABASE`, persistent `CORECARE_MODEL_DIR` |
| Assistant response generation | `LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_API_KEY`, `LLM_MODEL=openai/gpt-oss-20b` |
| Assistant semantic retrieval | `EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL=gemini-embedding-001` |
| Optional assistant media | `LLM_VISION_MODEL`, `LLM_AUDIO_MODEL`, `LLM_SPEECH_MODEL`, `LLM_SPEECH_VOICE` |
| Learning importer | `PLATFORM_BACKEND_URL` and service key |

Set credentials in hosting secret settings. Never put them in `VITE_*`, repository files, URLs, screenshots or test reports. Database passwords in connection URLs must be URL encoded. Use TLS for database connections and disk encryption/backups for both database and persistent AI storage. Restrict the AI service and `/internal/*` endpoints at the network boundary in addition to service authentication.

`CORS_ORIGIN` is the primary trusted browser origin. Optional `CORS_ADDITIONAL_ORIGINS` is a comma-separated list of additional exact HTTP(S) origins; it defaults to empty. CORS responses and the mutation-origin guard share this allowlist. Origins must contain only scheme, hostname and optional port, with no path, trailing slash, credentials or wildcard. Configure only the frontend origins you operate.

## Render + Vercel

1. Provision PostgreSQL and create a least-privilege application account. Use a separate migration credential if your deployment policy requires it.
2. Deploy `ai-service/` using its Dockerfile or a Python runtime compatible with the pinned model environment. Attach persistent storage, configure the service/operator keys, and preserve versioned artifacts. Run `python -m uvicorn main:app --host 0.0.0.0 --port "$PORT"`.
3. Deploy `backend/` using its Dockerfile, or build with `npm ci && npm run generate && npm run build`. Run migrations as a release step: `npm run migrate`. Start with `npm start` and `HOST=0.0.0.0`.
4. Set the frontend root to `frontend`, build command `npm ci && npm run build`, output `dist`. Configure a Vercel rewrite for `/api/:path*` to your actual Render backend URL, then an SPA fallback to `/index.html`. The API rewrite must precede the SPA fallback.
5. Set backend `CORS_ORIGIN` to the exact HTTPS frontend origin. Production refresh cookies are Secure/HttpOnly/SameSite Strict; the same-origin API proxy avoids cross-site cookie failures.
6. Run the seed script with a one-time administrator email and strong password. It does not overwrite existing users. Rotate bootstrap credentials after handover.
7. Run registration, approval, two-hospital referral and session-reload smoke tests against the deployed application. Do not load synthetic test patients into a live clinical database.

`GET /health` on the backend verifies PostgreSQL. The AI health route requires the service key and distinguishes unavailable models from process availability. For an infrastructure probe that cannot send headers, use TCP/process monitoring and an authenticated application-level readiness probe. A degraded AI model status does not make referral coordination unavailable.

## Containers

`compose.yaml` includes PostgreSQL, backend, AI with persistent volumes, and an Nginx frontend proxy. Supply `POSTGRES_PASSWORD`, `JWT_SECRET`, `AI_SERVICE_KEY`, `AI_ADMIN_TOKEN` and `APP_ORIGIN` through the process environment or an ignored root `.env`.

```bash
docker compose build
docker compose up -d
docker compose exec backend npx prisma migrate status
```

Compose binds its frontend to `127.0.0.1:8080`. Set Groq and Gemini keys in the host environment to enable the complete assistant; without a Gemini key, text retrieval is explicitly lexical, and without the Groq key assistant requests return an explicit unavailable response. Put a TLS reverse proxy in front and set `APP_ORIGIN` to the resulting HTTPS origin. With production Secure cookies, plain HTTP is not a production login configuration. Local development instructions use the separate Node/Vite servers instead.

Do not delete volumes to resolve migration problems. Back up PostgreSQL, AI learning data and model artifacts together. Test restoration and rollback before storing real patient records.

## Workers

The backend polls a persistent PostgreSQL queue for permitted public-source imports. Jobs atomically claim ownership, time out, and produce unverified private knowledge proposals. Redirects, private IPv4 ranges, non-HTTPS sources, alternate ports and responses over 1 MB are refused. IPv6-only sources are not supported. Failed/interrupted jobs remain visible for review; an operator can explicitly enqueue another attempt. Facebook and Telegram require future provider-authorized connectors and are not fetched by the public collector.

Schedule the following sequentially, with one importer/learning worker per database:

```bash
python -m training.import_platform_observations
python -m training.learning_cycle
```

Model approval and rollback remain explicit operator commands documented in `ai-service/README.md`. No OS schedule was installed by this implementation.

## Troubleshooting

- **Registration cannot sign in:** approve the hospital and ensure user/membership are active.
- **Login returns 403 with “Untrusted request origin”:** match the browser's scheme, host and port to `CORS_ORIGIN` or an entry in `CORS_ADDITIONAL_ORIGINS`, then restart the backend. For local Vite on 5174, explicitly add `http://127.0.0.1:5174`; Vite may select that port when 5173 is occupied. This rejection happens before password validation.
- **Refresh fails after reload:** check `/api` proxy routing, cookie path, HTTPS and exact origin. Avoid mixing `localhost` and `127.0.0.1`.
- **Referral cannot be submitted:** receiving hospital must be approved and list the required available service and specialty. Reload after a version conflict.
- **AI 503 or missing predictions:** inspect service reachability/key, model approval and verified history. Do not activate a failing candidate to hide the error.
- **No assistant generation:** configure Groq's `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in the AI service. Missing or failed generation returns an explicit 503. Set the Gemini embedding variables to enable semantic retrieval; configured Gemini failures also return an explicit 503.
- **Old assistant errors after updating files:** check the process at the backend's exact `AI_SERVICE_URL`, including its port. Restart that AI process with `--env-file .env`; a second newer process on another port does not update the one serving the backend. In a noninteractive Windows session, use an explicit restart without `--reload` if reload stalls. Verify `Application startup complete` and the affected request; a RefHealth AI `/docs` title alone does not prove every code change is loaded.
- **Purpose question returns “invalid or ungrounded answer”:** earlier validation required a hospital citation whenever semantic retrieval found any hospital profile. General assistant-purpose questions now use the system's application description without hospital retrieval. Restart the AI process to load the fix. For hospital-specific questions, inspect the safe validation-reason log; citation checks remain enabled.
- **Active-hospital question returns “invalid or ungrounded answer”:** older requests used JSON-object mode without enforcing citation/proposal field types, and hospital profiles omitted approval status. Current code uses strict response schemas for supported Groq models, safely discards malformed optional proposals, and supplies the complete approved-hospital directory. Update/restart both backend and AI services. An unknown citation or invalid answer is still rejected; the directory defines active as `APPROVED` in the system, not currently open or accepting referrals.
- **Image/voice input fails:** configure `LLM_VISION_MODEL` and `LLM_AUDIO_MODEL` in the AI service and restart it. Microphone capture needs HTTPS/localhost and browser permission; audio-file upload is also available. Keep the assistant proxy body limit at least 6 MB for a 4 MB base64 attachment. Current frontend/backend/AI code accepts browser MP4 audio and persists the transcription as private text; deploy all layers together. Provider connection/quota failures still return explicit errors and retain unsent media for retry.
- **Listen fails:** check browser voices and audio output. On browser speech failure, the application requests WAV segments from the configured provider using only the signed-in user's own saved reply. Groq defaults to `canopylabs/orpheus-v1-english` / `troy`; override with `LLM_SPEECH_MODEL` / `LLM_SPEECH_VOICE` if needed. The Groq organization administrator must accept the model terms in its console before generation works. The November 10 diagnostic returned `model_terms_required`; no terms were accepted automatically. Keep `/api/assistant/speech` proxy timeout at 100 seconds. No audio or provider keys are stored in the browser persistently.
- **Assistant timeout or provider rate limit:** the AI service has an 80-second budget with pooled connections and bounded retries. `AI_ASSISTANT_TIMEOUT_MS` defaults to 90,000; keep a reverse proxy timeout of at least 100 seconds on the chat route. Document-vector caching reduces repeated Gemini calls. Sustained provider quota exhaustion still requires waiting for quota recovery or changing the provider account quota; the service does not fabricate a fallback answer.
- **Source fetch fails:** verify permitted access, the final HTTPS URL, public IPv4 DNS, content type and size. Register a final redirected URL explicitly.
- **Assistant does not know workspace activity:** deploy the current `assistant-context.ts` backend and restart the AI service together. Hospital chat now receives fresh role-filtered referral, capacity, review, team and model summaries; no database migration is required. Exact summary sources bypass semantic ranking and are selected by topic to avoid unnecessary provider tokens. Workers without receiving permission do not receive incoming referral data; system administrators remain outside hospital chat. Current model metadata is checked with a five-second internal-service deadline; unavailable metadata must be described as unknown.
- **Database error:** verify credentials, migrations and connection limits. The application returns a safe error; investigate by request ID without logging patient payloads.
- **Saved chat history / missing thread table:** apply `202611110001_chat_threads`, generate the Prisma client into `backend/generated/prisma`, build and restart the backend, then refresh the frontend. The migration preserves existing messages in per-user/per-hospital **Earlier conversations** threads. Package `generated/` together with `dist/`. Stop the server before regenerating a Windows client whose engine DLL is in use; never delete the database to fix a client or migration error.
- **npm certificate errors on this Windows host:** `NODE_OPTIONS=--use-system-ca npm ci` used the installed trusted system certificates. Do not disable TLS verification.

Reference implementation guidance: [Fastify testing](https://fastify.dev/docs/latest/Guides/Testing/) and [Prisma 6 migration workflow](https://www.prisma.io/docs/orm/v6/prisma-migrate/getting-started).
