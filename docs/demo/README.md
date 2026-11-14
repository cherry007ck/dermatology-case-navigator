# Demo handoff: Dermatology Case Navigator (fictional encounters only)

Branch `integration/local-backend`. Every result below was produced by the actual local application:
- Next.js web in live mode;
- FastAPI with Exasol storage and Meta extraction (`muse-spark-1.3-contributor`);
- the published collection `published-derm-v1`.

Patients are fictional. The two published case reports are source-reviewed by Luffy and **not clinically reviewed**.

## 1. Start locally (exact commands, PowerShell)

The API needs the explicit modes. One restart came up in memory mode from an inherited environment, so always set them:

```powershell
cd services/api
$env:EXASOL_TELEMETRY_DISABLE='1'; $env:DATA_BACKEND='exasol'; $env:EXTRACTOR_MODE='meta'; $env:COLLECTION_MODE='published'
$env:CORS_ORIGINS='http://localhost:3000'
.\.venv\Scripts\python.exe -W ignore -m uvicorn app.main:app --port 8000
```

In a second terminal:

```powershell
cd apps/web
npx next dev --port 3000       # .env.local: NEXT_PUBLIC_API_MODE=live, NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Check before presenting:
- `GET http://localhost:8000/v1/readiness` with header `X-Demo-Access-Code` must return `storage exasol, extractor meta, collection_mode published, loaded_cases 2, ready true`.
- If Exasol times out, the laptop's public IP may have rotated. Add it to the Exasol SaaS allowlist.
- Optional automated rehearsal: `node scripts/live-demo-check.mjs http://localhost:3000 <screenshot-dir>` in `apps/web`. It must print `29/29 checks passed`.

## 2. Three-minute demo script

1. **Start** (`/intake`): enter the demo access code, then **Load collections**. Only "Published — source-reviewed cases" is offered. Click **Start intake**. The banner reads: Live API · Published collection, developer source-reviewed, not clinically reviewed · Stored in Exasol · Meta model extraction.
2. **Patient statement:** "My scalp has been itching for several days. I used minoxidil foam around the time it started."
   - **Summary for your doctor** shows "Patient reports itching on the scalp.", "Patient describes the duration as days." and "Patient mentions using minoxidil foam.", each with the patient's own words.
   - The product is listed as context. It is not shown as a treatment or as a cause.
   - The patient pane shows no case content.
3. **Confirm and open doctor brief.** The workspace shows "Patient confirmed revision 1".
   - The patient brief includes the product.
   - **Comparable cases:** one published case report, *A Case of Contact Allergic Dermatitis to Topical Minoxidil*. Its shared feature is "symptom at the same site: itching on the scalp", with the patient quote and the case quote "itchiness over the scalp".
   - Click the case quote. The **source drawer** shows the exact original passage, the PMC7861115 locator and the review status. Escape closes it.
   - The **Source** block shows: BinJadeed H, Almudimeegh AM, Alomran SA et al. · Cureus 2021 · PMCID, PMID and DOI links · licence CC BY 3.0 · Open original article.
4. **Clinician note:** add a note. It is stored separately, against revision 1, and never appears in the patient view.
5. **Correction:** go back, click **Correct** and change "several days" to "about two weeks".
   - The original stays, marked replaced.
   - The earlier confirmation is shown as no longer valid.
   - The summary is rebuilt (weeks).
   - Confirm again. The doctor now sees revision 2.
6. **Honest no-match** (new encounter, or the 390 px phone layout): "My face is itchy."
   - The clarification "How long have you had this?" appears. Click **Skip**: it is recorded as skipped, not as a "no".
   - Confirm. The doctor sees **No qualifying case**: no case documents the same symptom at the same body site. The minoxidil case's scalp itching and facial swelling are not combined into a facial-itching match.
7. **Persistence (optional):** restart the API and reload the doctor page. The encounter is read back from Exasol.

## 3. Verified features (13–14 Nov 2026, local)

| Check | Result | How |
|---|---|---|
| Scalp/minoxidil story, including the reported product | PASS (live) | `live-demo-check.mjs` 29/29; screenshots A1, A3 |
| Correct published case, source passages, attribution and licence | PASS (live) | A2, A3 |
| Honest no-match for facial itching | PASS (live) | B2; API check |
| Correction changes active facts and invalidates the old confirmation | PASS (live) | A4, A5 |
| Skip on an encounter that actually asks a clarification | PASS (live) | B1 |
| Patient-confirmed brief matches the doctor's revision | PASS (live) | A5 ("Patient confirmed revision 2") |
| Clinician notes separate from the patient view | PASS (live) | live check |
| Encounter survives an API restart | PASS (live Exasol) | `python -m scripts.restart_check write/verify` |
| Voice webhook: binding → stored voice turn → backend advance → backend-approved question → stored answer → updated review | PASS for the **backend leg only** (live API, Exasol, Meta) | `python -m scripts.voice_webhook_check` |
| Spoken voice loop through the ElevenLabs agent | **NOT VERIFIED** (blocked) | needs a public backend URL for the webhook (see §5) |
| Public deployment | **BLOCKED** | `docs/deploy/runbook.md` |
| Backend unit and contract tests | PASS | `pytest` 145 passed, 9 skipped (live-only); OpenAPI drift check passes |
| Frontend | PASS | typecheck, lint, production build; mock-mode Playwright 58 passed, 17 skipped (live-only) |

Mock-mode browser tests use labelled fixture responses. They are not live evidence. Live evidence is the `live-demo-check.mjs` run and the API scripts above.

## 4. Limitations (say these honestly)

- **Scope:** consultation preparation and published-evidence navigation only. No diagnosis, treatment recommendation, image analysis or urgency assessment. No integration with TK-Doc or medical records.
- **Collection size:** two published case reports. The collection is source-reviewed by a developer and **not clinically reviewed**. A no-match does not mean no evidence exists.
- **Matching:** prototype `structured-v2` rules, not a validated clinical score. A symptom must be stated together with its site.
  - Pronoun-only links ("they burn") are conservatively left unlinked.
  - Sites are not mapped to regions ("fingers" is not "hands").
- **Extraction:** the Meta model proposes candidate facts, and the server keeps only those supported by the patient's exact words. The `-contributor` model mode permits training use of inputs, so encounters must stay fictional.
- **Licence:** the case records carry the licence stated in the PMC XML that the passages come from (CC BY 3.0). The publisher PDF of one article states CC BY 4.0, and this is documented.
- **Voice:** connection and transcript capture work. The agent still runs the connection-test prompt, and the spoken clarification loop is not configured (§5).

## 5. Remaining blockers (exact human actions)

1. **Deployment:** follow the Render and Vercel steps in `docs/deploy/runbook.md`. That needs account access to the existing Render service `dcn-api-ujrd` and to the Vercel project, plus a PR merge or a branch switch.
2. **Voice loop** (after step 1): run `node apps/web/scripts/configure-voice-agent.mjs --api-base https://dcn-api-ujrd.onrender.com`, which is a dry run. Then rerun it with `VOICE_TOOL_SECRET=<the Render value>` and `--apply`. Then speak the step-6 story and confirm in the browser.

## 6. Backup recording (precise steps)

1. Start both services as in §1 and check readiness.
2. Use Windows Game Bar (Win+Alt+R) or OBS to record the browser window at 1280×800. Close other tabs and hide the demo code: type it before you start recording.
3. Follow §2 steps 1–6, about 3 minutes. Pause about 2 s on the source drawer, the attribution block and the no-match panel.
4. Save as `dcn-demo-backup.mp4` outside the repository. Do not commit recordings.

Screenshots of fictional data from the final live run are in `docs/demo/screenshots/`.
