# Merging, deployment and recovery

## Local commands Kiro must make true in S0

These commands are the required interface of the generated app, not commands that work before bootstrap. Python commands avoid shell activation-policy differences on Windows.

Frontend (in `apps/web`):

```powershell
npm ci
npm run dev
```

Backend (in `services/api`, first run):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Separate terminal for database initialization and checks, after credentials are configured:

```powershell
.\.venv\Scripts\python.exe -m scripts.init_db
.\.venv\Scripts\python.exe -m scripts.seed --collection synthetic-demo-v1
.\.venv\Scripts\python.exe -m scripts.smoke
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.export_openapi
```

`init_db` and seed must be idempotent; they must not drop tables or wipe encounters. `smoke` uses an explicit API URL/demo code from environment, creates only a labelled fictional encounter and does not print tokens. For CI add explicit fixture/memory test configuration so missing production keys do not fail ordinary tests.

Web scripts required: `dev`, `build`, `lint`, `typecheck`, `test:e2e`, `generate:api`. API type generation consumes checked-in `contracts/openapi.json`; Vercel builds must not depend on connecting to a running Python server. Follow current Next.js lint tooling rather than assuming an old `next lint` command exists.

## Branch and merge routine

Start each sprint from an updated main in your own checkout:

```powershell
git status --short
git switch main
git pull --ff-only
git switch -c luffy/s1-ui
```

Zoro uses their own branch, e.g. `zoro/s1-exasol`. If there are uncommitted changes, preserve them before switching; never tell Kiro to discard everything. Commit small working steps and push the branch. Open a PR with behavior changed, actual checks, screenshots/API sample as relevant, contract changes, and teammate dependency. The other developer reviews and approves; squash merge when checks pass. Do not wait until both entire backlogs are finished to merge.

At integration use current main, not one person's private branch. Merge backend PR first if needed by a frontend PR. Frontend rebases/merges current main normally, regenerates types if the contract changed, and fixes only its owned files. Avoid force pushes; a regular merge from main is enough for the event. A conflict in someone else's code is handled with that person, not by choosing “ours” everywhere.

## Early and final deployments

Deploy stub services during S1; establish TLS, network access and microphone support early. The final release is the integrated commit after S4/S5, not the first time hosting is attempted.

### Render API — Zoro

Create a Python web service from the shared repository; root directory `services/api`. Build: `pip install -r requirements.txt`. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`. Configure Python version, production secrets, `DATA_BACKEND=exasol`, correct schema and exact frontend CORS origins. Use its HTTPS URL. Initialize/seed the database from a trusted local terminal if the hosting plan lacks a shell; do not expose a public seed endpoint. [FastAPI deployment guide](https://render.com/docs/deploy-fastapi)

Verify Exasol allows the host's actual egress network and TLS succeeds from Render. Do not assume it works because laptop access works. If hosting/network limits block access, the local API is the fallback and the frontend must also run locally for the live demo unless a verified secure tunnel is used. Plan for service startup delays; warm and test before presentation without promising a specific free-tier SLA.

### Vercel web — Luffy

Import the organization repository, choose `apps/web` as root, install with the lockfile, build with `npm run build`. Set frontend environment variables, API URL and server-only ElevenLabs credentials. Point the backend CORS allowlist and ElevenLabs origin allowlist to the final deployment domain. Use an explicit preview URL for testing instead of allowing every origin. [Monorepo setup](https://vercel.com/docs/monorepos)

If `generate:api` needs root contracts outside `apps/web`, enable the appropriate Vercel outside-root build access or generate/commit the frontend types before deploy. Keep runtime imports self-contained. The frontend cannot connect directly to Exasol, and no provider key belongs in a public environment variable.

### Optional v0 — Luffy only

Import the existing shared repository and select the web app; do not create a competing backend/repository. Use `prompts/05-v0-interface.md` for presentational changes only. Review changes in Luffy's branch; prevent v0 from replacing contracts, API adapters, lockfiles unexpectedly, or deployment settings. If integration/import consumes more than 20 minutes, skip v0. [v0 Git import](https://v0.app/docs/git-import)

## Cut order and failure recovery

| Trigger | Decision |
|---|---|
| Real cases unavailable after 60 focused minutes | Synthetic-only labelled demo; published evidence capability not claimed |
| Exasol blocked for 30 minutes | Continue memory-backed dev, show label; escalate event access and retry during S1/S2. Final presentation cannot claim real Exasol until live write/read works |
| Gemini unavailable | Fixture extractor for supplied phrases, explicit demo label; preserve pipeline and source checks |
| Live voice loop blocked after S2/G1 | Keep working typed flow; one bounded fix window in S3; optional narrated/recorded demo clearly disclosed |
| Render-to-Exasol networking blocked | Local API + local web; verified HTTPS tunnel only if needed for live voice webhook |
| Photo feature threatens core path | Omit photos from demo; no image-analysis claim |
| Doctor correction UI late | Keep patient correction/reconfirmation and clinician note; defer doctor editing |
| Behind at active hour 11 | Cut v0 refinement, larger dataset, photos and advanced UI; retain core provenance/no-match |
| Final deployed release fails | Use last known-good commit and rehearsed local setup; disclose actual mode |

Do not cut source labels, honest no-match handling, patient confirmation, evidence validation, token checks, or secret hygiene to make a demo appear complete.

## Release checklist

- Record git commit, installed versions, extraction model ID, collection version/hash, ranking version and actual integration modes.
- Run core typed flow and live voice smoke where available; state separately what passed and what is fallback.
- Verify source references, fake-source labels, no patient treatment advice, no fabricated citations, no unsupported metrics.
- Stop voice before confirmation; test one correction and one no-match encounter.
- Exasol read/write and replay work from actual runtime; no credentials in screenshots or logs.
- Prepare demo access code, warm service, reset encounters, record a labelled backup.
- README contains setup, architecture, team ownership, sources, limitations, actual deployment link and actual checks.
- Teammate review; tag known-good commit `hackathon-demo-v1`; stop adding features.
