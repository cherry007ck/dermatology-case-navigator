# Dermatology Case Navigator

Hackathon prototype for **fictional** encounters. A patient's own words become a reviewable,
source-linked brief for the doctor, with optional comparison to documented cases from one clearly
labelled collection. It does not diagnose, recommend treatment, analyse images or assess urgent
concerns. All data in this repository is fictional.

**Current state: Sprint 0 foundation.** The API is a labelled stub (memory storage, replay of shared
contract examples). No Exasol connection, Gemini extraction or voice exists yet. See
`docs/status/luffy.md` and `docs/status/zoro.md` for what has actually been verified.

| Path | Owner | What |
|---|---|---|
| `apps/web` | Luffy | Next.js 16 App Router, TypeScript, Tailwind 4, shadcn/ui |
| `services/api` | Zoro (except `app/voice`, `tests/test_voice*` = Luffy) | FastAPI, Pydantic, Python 3.12 |
| `contracts/` | Zoro after S0 | Domain schema, exported OpenAPI, shared serialized examples |
| `data/synthetic` | Zoro | Fictional fixture cases — never published evidence |

Planning pack: start at `START-HERE.md`; rules in `AGENTS.md`; versions in `docs/toolchain.md`;
contract decisions in `contracts/DECISIONS.md`.

## Prerequisites

Git, Node.js 22 LTS (>= 20.9), npm, Python 3.12. No provider accounts are needed for local mock or
stub mode.

## Run locally

### Backend (`services/api`)

Windows (PowerShell):

```powershell
cd services/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env        # optional; defaults work for local development
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

macOS/Linux:

```bash
cd services/api
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env               # optional
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000/health> and <http://localhost:8000/docs>. With `APP_ENV=development` and a
blank `DEMO_ACCESS_CODE`, the API accepts the local demo code `local-demo`. Any other environment
requires an explicit code and `SESSION_TOKEN_SECRET`.

Backend scripts (separate terminal, same folder; Unix: replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`):

```powershell
.\.venv\Scripts\python.exe -m pytest                     # contract alignment, fixtures, stub API, voice stub
.\.venv\Scripts\python.exe -m scripts.export_openapi     # regenerate contracts/openapi.json (--check in CI)
.\.venv\Scripts\python.exe -m scripts.smoke              # API_URL / DEMO_ACCESS_CODE env; never prints tokens
.\.venv\Scripts\python.exe -m scripts.init_db            # NOT YET LIVE: exits 3, no Exasol connection (S1)
.\.venv\Scripts\python.exe -m scripts.seed --collection synthetic-demo-v1   # NOT YET LIVE: validates locally, exits 3
```

### Frontend (`apps/web`)

```bash
cd apps/web
npm ci
npm run dev                         # http://localhost:3000
```

Modes are explicit. Copy `.env.example` to `.env.local`:

- `NEXT_PUBLIC_API_MODE=mock` (default when unset): replays the shared contract examples in the
  browser, no backend. The UI shows **"Mock API — shared fixture responses, no backend"**. Any demo
  code is accepted.
- `NEXT_PUBLIC_API_MODE=live` + `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`: calls the FastAPI
  backend. Use demo code `local-demo` against a development API.

Demo phrases the S0 stub/mock recognise (other text returns an honest "processing failed" error):

1. `My hands have been itchy for weeks. I tried a cream, but it didn't help.`
2. `I don't remember the name. I used it for a few days.`
3. `I started using a new hand soap before this began.`
4. No-match encounter: `My scalp feels uncomfortable. I don't know when it began.`

Web scripts:

```bash
npm run build          # production build
npm run typecheck      # tsc --noEmit
npm run lint           # eslint (flat config; `next lint` no longer exists)
npm run test:e2e       # Playwright, mock mode, desktop + 390px (first run: npx playwright install chromium)
npm run generate:api   # contracts/openapi.json -> lib/api/generated.ts (committed)
npm run sync:fixtures  # contracts/examples -> mocks/fixtures (committed)
```

Run the same browser suite against a running local API (allow the test origin in CORS):

```powershell
# API terminal
$env:CORS_ORIGINS="http://localhost:3000,http://localhost:3200"; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# web terminal
$env:E2E_API_MODE="live"; npm run test:e2e
```

## CI

`.github/workflows/web.yml` (job `web-checks`): fixture sync drift, generated-type drift, typecheck,
lint, build, Playwright (mock). `.github/workflows/api.yml` (job `api-checks`): `validate_pack.py`,
OpenAPI drift, pytest. CI uses memory storage and fixture data only; no provider keys.

## Limitations (S0)

- Memory storage only; nothing survives an API restart. UI shows "Development storage — not Exasol".
- No extraction or ranking: the stub replays contract examples for the documented phrases.
- Skip and correction return `STUB_NOT_IMPLEMENTED`; voice routes return `VOICE_NOT_IMPLEMENTED`.
- Synthetic collection only. Nothing has been clinically reviewed.
