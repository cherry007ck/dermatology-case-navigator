# Voice adapter handoff for Zoro (S2)

Names only. No secret values appear here or in git. Owner of everything below: Luffy.

## Files

| File | Role |
|---|---|
| `services/api/app/voice/router.py` | `POST /v1/sessions/{id}/voice-binding`, `POST /v1/voice/advance` (registered once in `app/main.py`) |
| `services/api/app/voice/bindings.py` | Scoped in-memory bindings: hashed token, 30-minute expiry, revoke-on-reissue, idempotent by request ID |
| `services/api/app/voice/advance.py` | `advance_intake` logic: bounded wait, per-turn operation key, voice-safe mapping |
| `services/api/tests/test_voice_stub.py`, `tests/test_voice_advance.py` | Adapter tests against the S0 stub |
| `apps/web/app/api/voice-session/route.ts` | Next.js server route: same-origin, rate limit, binding, ElevenLabs signed URL |
| `apps/web/lib/session/writer.ts`, `lib/voice/*`, `components/voice/*` | Browser: transcript capture, serialized `/turns` writes, polling |

No change to `app/models.py`, `app/intake_service.py`, `contracts/**` or `contracts/openapi.json`.

## Service methods the adapter calls (frozen S0 seam only)

- `IntakeService.get_session(session_id, session_token) -> SessionSnapshot`
  - binding issue: authenticates the browser's bearer
  - webhook: reads the newest persisted patient turn and revision, using the bearer held by the binding in process memory
- `IntakeService.advance(session_id, AdvanceRequest) -> AdvanceResult`, called with:
  - `request_id = "voice-" + sha256("voice-advance|<binding hash>|<turn_id>")[:32]`, stable per patient answer
  - `expected_revision` = the snapshot revision just read; one re-read and retry on `REVISION_CONFLICT`

Behaviour the real service must keep for the voice loop to work:

1. **Idempotent `advance`.** The same `request_id` with the same content returns the original result.
2. **Repeat calls at one revision.** A second `advance` at an already-processed revision, with a *different* request ID, must return the current pending question or ready state without issuing a new question. This can happen when typed and voice paths both advance the same revision.
3. **Agent turns don't bump the revision.** Agent-role turns with `origin="voice_transcript"` never increment the revision and never support facts.
4. **Answer linking.** Patient voice turns arrive with `reply_to_question_id` set to the pending question when the browser already knows it, otherwise `null`. Link a later patient turn to the pending question by sequence (contract voice step 7).
5. **Duplicate turn IDs.** A duplicate `turn_id` is rejected with `409 DUPLICATE_TURN_ID`; the browser treats it as already saved. Turn IDs look like `voice-<conversation>-<patient|agent>-<event_id>`.
6. **Session reads must not add a rate limit or side effects.** The webhook may call `get_session` up to about 11 times within its 2-second wait.
7. **Messages are spoken aloud.** Errors from `advance` are mapped to `VOICE_ADVANCE_FAILED` with a fixed spoken-safe message. Never put internal details into `ApiError.message` for `advance`, because the voice path can surface it.

## Authentication on `POST /v1/voice/advance`

| Header | Source | Check |
|---|---|---|
| `X-Tool-Secret` | Static secret header in the ElevenLabs tool configuration | Constant-time compare with `VOICE_TOOL_SECRET` |
| `X-Voice-Binding` | `{{secret__voice_binding}}`, a `secret__` dynamic variable (never sent to the LLM) | Must resolve to a live, unrevoked, unexpired binding |

Both are required. Any failure returns the same `401 VOICE_AUTH_FAILED`. An unset `VOICE_TOOL_SECRET` returns `503 VOICE_TOOL_NOT_CONFIGURED`. The request body is ignored, so the model cannot supply session IDs, transcripts or facts.

Response is only `{action, question_id, question_text, spoken_message}`. No cases, diagnoses, actions, outcomes or clinician content.

## Runtime configuration (names only)

Render API service (Zoro sets values in Render's secret settings):

- `VOICE_TOOL_SECRET`: long random value. Luffy copies the same value into the ElevenLabs tool's secret header; it is never shared in chat or git.
- `SESSION_TOKEN_SECRET`, `DEMO_ACCESS_CODE`: required outside development. The voice binding route depends on session auth.
- `CORS_ORIGINS`: exact frontend origin(s).
- Run **one worker** (`--workers 1`). Bindings, the voice advancer state and the bearer held for the webhook are process-local. A restart or second worker means "reconnect voice", not data loss.

Vercel/Next.js (Luffy, server-only):

- `ELEVENLABS_API_KEY` (ElevenAgents Write), `ELEVENLABS_AGENT_ID`
- `API_INTERNAL_BASE_URL` = the Render URL
- `NEXT_PUBLIC_API_MODE=live`, `NEXT_PUBLIC_API_BASE_URL` = the Render URL
- `VOICE_ALLOWED_ORIGINS` if needed

ElevenLabs tool (Luffy configures once the combined backend on Render passes the checks below):

- name `advance_intake`, POST `https://<render-host>/v1/voice/advance`, body `{}`
- headers `X-Tool-Secret` (secret) and `X-Voice-Binding: {{secret__voice_binding}}`
- then replace the temporary prompt with `prompts/06-elevenlabs-system.md`

Checks before the tool is configured:

1. On the Render host, `/v1/voice/advance` returns 401 without headers.
2. It returns 503 `VOICE_TOOL_NOT_CONFIGURED` if `VOICE_TOOL_SECRET` is missing.
3. It returns 200 `waiting_for_transcript` with valid headers on an empty session.

## Known gap: spoken hesitations

The S0 stub's `advance` replays contract examples only for patient text that **exactly** matches the demo phrases. Real speech ("Hi. I have a... My hands have been itchy for weeks.") never matches, so a live voice advance on the stub returns `VOICE_ADVANCE_FAILED`. The full voice loop needs your fixture/Gemini extractor working on ordinary transcribed speech. Until then the voice loop stays **unverified**.
