# Deployment runbook (Render API and Vercel web)

Status on 14 Nov 2026, 02:15: **blocked on account access.** This checkout has no Render, Vercel or GitHub CLI, and no deploy token. The existing Render service `https://dcn-api-ujrd.onrender.com` serves **old `main` code**: memory storage, fixture extraction, synthetic collection, and an OpenAPI schema without `CaseAttribution`. Its `/health` returns 200. It is **not** the current application. No Vercel URL is recorded.

## Human actions needed (account holder)

1. **Get the code onto the deployed branch.** Do one of these:
   - open a PR `integration/local-backend` → `main`, get Zoro's review, and merge; or
   - point the Render service's branch at `integration/local-backend` for the demo.
2. **Render, existing service `dcn-api-ujrd`.**
   - Root directory: `services/api`.
   - Build command: `pip install -r requirements.txt`.
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`. Run one worker only: voice bindings are process-local.
   - Environment (secret values go in Render's secret settings, never in git):
     - `APP_ENV=production`, `DATA_BACKEND=exasol`, `EXTRACTOR_MODE=meta`, `COLLECTION_MODE=published`
     - `EXASOL_DSN`, `EXASOL_USER`, `EXASOL_PASSWORD`, `EXASOL_SCHEMA`: same as local `services/api/.env`
     - `EXASOL_TELEMETRY_DISABLE=1`
     - `MODEL_BASE_URL`, `MODEL_NAME`, `MODEL_API_KEY`: Meta, same as local
     - `SESSION_TOKEN_SECRET`, `VOICE_TOOL_SECRET`: long random values
     - `DEMO_ACCESS_CODE`: the demo code
     - `CORS_ORIGINS=https://<vercel-host>` (exact origin)
   - Exasol SaaS allowlist: Render's outbound IP ranges. Zoro reported these as allow-listed on 13 Nov; re-check if readiness fails.
3. **Vercel**, project rooted at `apps/web`:
   - `NEXT_PUBLIC_API_MODE=live`
   - `NEXT_PUBLIC_API_BASE_URL=https://dcn-api-ujrd.onrender.com`
   - `API_INTERNAL_BASE_URL=https://dcn-api-ujrd.onrender.com`
   - `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`: server-only, same as local `.env.local`
   - `VOICE_ALLOWED_ORIGINS=https://<vercel-host>`
4. **ElevenLabs:** add `<vercel-host>` to the agent's allowed hosts, if the allowlist is used.

## Verification (Luffy runs these after the deploy)

1. Version and modes:
   - `GET https://dcn-api-ujrd.onrender.com/openapi.json` must contain `components.schemas.CaseAttribution`.
   - `GET /v1/readiness` with `X-Demo-Access-Code` must return `{"storage":"exasol","extractor":"meta","collection_mode":"published","loaded_cases":2,"ready":true}`.
2. Voice webhook: `POST /v1/voice/advance` with no headers must return 401 `VOICE_AUTH_FAILED`.
3. Browser flow from the public frontend:
   `E2E_DEMO_CODE=<code> node apps/web/scripts/live-demo-check.mjs https://<vercel-host> <screenshot-dir>`
   It must report 29/29.
4. Voice:
   - Dry run: `node apps/web/scripts/configure-voice-agent.mjs --api-base https://dcn-api-ujrd.onrender.com`.
   - Then the same with `VOICE_TOOL_SECRET=<same value> … --apply`.
   - Then the spoken check in `docs/demo/demo-script.md`.

Do not mark deployment complete until steps 1–3 pass against the public URLs.
