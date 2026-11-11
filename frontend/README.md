# Hospital workspace

React, Vite, TypeScript, Tailwind, Axios, TanStack Query, React Router, React Hook Form, Zod and Recharts. All dashboard counts and records come from the backend. No production mock dataset exists.

```bash
cp .env.example .env
npm ci
npm run dev
npm run build
npm test
```

Open `http://127.0.0.1:5173`; the dev proxy maps `/api` to `http://127.0.0.1:3000`. Set `VITE_API_URL` only to a backend URL, never the AI service or a secret. Prefer a same-origin proxy in production.

`main.tsx` provides authentication and role-specific navigation. `pages.tsx` contains hospital operations, platform administration, directory, assistant, knowledge and analytics. `referrals.tsx` handles patient registration, human destination selection, receiving decisions and outcomes. `ui.tsx` provides shared forms, loading/errors, actions and layouts. `api.ts` keeps access tokens in memory and refreshes through the HttpOnly cookie. Signing out clears the query cache.

The frontend displays unavailable AI information explicitly and continues to support referral coordination. Source registration does not fabricate a social connection. Account recovery uses a token issued after platform-operator identity verification.

## Assistant images and voice

**New chat** starts a separate conversation. The left-hand **Chat history** lists your saved chats by most recent activity, titled from the first message. Select a chat to reopen or continue it; its URL preserves the selection after reload. **Load more chats** and **Load earlier messages** keep older history accessible. On narrow screens the history panel appears above the conversation. Earlier unthreaded messages are preserved in **Earlier conversations**; their original topic boundaries were not recorded.

Only the signed-in user's chats for the current hospital are listed or readable. Messages stay in sequence within their chat. The backend builds model context from the last eight saved question/reply pairs in that chat; client-supplied history cannot mix separate chats. All older messages remain saved. New empty drafts are not saved until a reply succeeds; failed requests preserve the current draft for retry. Switching chats stops media capture/playback; switching is disabled during capture/preparation or an active send.

The assistant is available only in hospital workspaces. Ask about current capacity, approved hospital services, visible referral totals, today's activity, role permissions, saved forecasts and model status. Hospital administrators can also ask about aggregate team access, review queues and source collection. Select the optional Referral ID for patient-free details about an authorized referral. Replies cite current authorized sources; private patient fields, credentials and other hospitals' private records are excluded. Chat explains workflows and cannot edit records. Unknown or stale information should be stated explicitly.

Use **Attach image** to choose a JPEG, PNG or WebP, wait for its preview, then send it with an optional question. Images are resized and compressed before upload. Use **Record voice message**, allow microphone access, then **Stop recording** and **Send**. Recording stops automatically after 30 seconds. **Attach audio** accepts WAV, MP3, MP4/M4A, MPEG, OGG, FLAC, WebM and Opus files; audio uploads are limited to 4 MB. Recording requires HTTPS or localhost and a supported browser.

Voice transcripts appear as the user message, persist in private history and are included in later turns. Raw images and audio are not stored. **Listen** reads a reply using a browser voice, falling back to authenticated cloud speech when local speech fails; **Stop** cancels it. The fallback reads only your own saved reply. For Groq, the organization administrator must accept [Orpheus model terms](https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english); otherwise the UI explains the setup requirement. `assistant-media.ts` manages preparation, microphone/preview cleanup and playback; sending stays disabled while capture or preparation is in progress.

## Browser test

Start backend, AI and frontend against an isolated test database. Seed `browser-admin@test.org` with the test-only password in `tests/workflow.spec.ts`. Never use that account in production.

```bash
# Windows Chrome is used by default; override on another machine.
export CHROME_PATH='C:/Program Files/Google/Chrome/Application/chrome.exe'
npx playwright test
```

The browser test registers a hospital, signs in as the platform administrator, approves it, signs in as its administrator, updates profile and capacity, reloads the persisted session and checks mobile navigation/layout. Screenshots are written to ignored `test-results/`.

The opt-in `tests/assistant-live.spec.ts` verifies real Gemini retrieval and Groq responses through the browser, with citations, history and saved replies. It is skipped by default. See [live assistant test setup](../docs/testing.md#optional-live-assistant-verification) for the required isolated stack and environment variables.

`tests/assistant-media-live.spec.ts` separately checks real image interpretation, visual follow-ups, audio uploads, Chrome microphone capture from a public speech fixture, transcript persistence and browser playback controls. See [live media verification](../docs/testing.md#optional-live-media-verification).
