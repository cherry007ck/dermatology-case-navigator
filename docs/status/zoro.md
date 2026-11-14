# Zoro status

## S4 — case UI and attribution, milestone 1 (13 Nov 2026)

- Developer: Zoro (confirmed in chat). Lane: presentational UI and frontend QA under the revised ownership in `AGENTS.md` and `docs/handoff/2026-11-13-parallel-work.md`. Zoro acknowledges that ownership with this PR.
- Branch: `zoro/s4-case-ui-attribution` from `7af9925` (handoff commit on `integration/local-backend`). PR targets `integration/local-backend`.

### Changed behaviour (presentation only)

- **Grid/modular theme** (`app/globals.css`, `components/status.tsx`, `components/ui/{button,input,textarea}.tsx`). It follows the reference mock-ups: a faint static page grid, white modules with thin borders and navy corner markers, mono uppercase module labels, light-blue section bands, light-blue primary buttons with a navy border, small corner radii, and a static clipboard frame for the case record and the assessment form. Tokens change globally, so the patient pages pick up the theme without any edits to their components. The accent changed from teal `#0F766E` to navy `#1F4E8C` at the user's request. `docs/06-ui-and-demo.md` still says teal and should be updated by agreement.
- **Case card** (`components/case/case-card.tsx`, new, typed props only). Sections: comparison with this intake (shared features, important differences), case record (documented or fictional actions and outcomes) and a source footer. The card lays itself out from its container width: one column in the 5-column cases panel and at 390 px, two columns at 42 rem or wider. A statement without evidence is still withheld. The card shows no scores, percentages or "match" values.
- **Attribution** (`components/case/case-attribution.tsx`, new). `CaseAttribution` and `CaseReviewLabels` are built against a local `PlannedCaseAttribution` type that uses the planned handoff field names.
  - Synthetic: the fictional label and "no article, authors, journal, identifiers or external link". No links.
  - Published, attribution supplied: citation (authors, journal, year), PMCID/PMID/DOI resolver links (only for well-formed IDs), the licence link (http(s) only) and "Open original article".
  - Published, attribution not supplied (today's contract): "Open original article" plus "Authors, journal, year, identifiers and licence are not yet supplied for this card." Nothing is inferred from the URL.
  - Review labels are separate: "Developer source-reviewed" appears only when `source_review_status === "reviewed"`, otherwise "Source review status not on this card". Clinical review comes from the attribution, falling back to the collection: "Clinically reviewed" / "Not clinically reviewed" / "Clinical review status unknown". Synthetic shows "Fixture consistency check only".
- **Source drawer** (`components/source-drawer.tsx`, presentation only; `resolveEvidence`, the provider and the context API are unchanged). Shows the exact quote, the full passage or turn with the quote highlighted in place, a details table (section, locator, passage ID, SHA-256 prefix, review), the review labels and the compact attribution with the article link for published cards only. Escape and focus return are unchanged.
- **Doctor workspace** (shared file, JSX and classes only). Header module, brief as banded sub-modules, the case card moved into `CaseCardView`, case count in the cases panel heading, and restyled clarification lists. `load()`, token handling, the confirmed-revision guard and API calls are untouched.
- **Comparison history / clinician note panel**: markup and classes only. The note form sits in a clipboard module next to "Saved assessments". The save logic, request-ID handling, errors and Retry are unchanged.

### Deliberately not implemented from the reference images

- "90% case match" / "Demo score": product rules forbid scores and match percentages.
- Patient photos and sex badges: these fields are not in the contract, and photo review is out of scope (no image interpretation).
- The "Exasol.sh / EXASOL HACKATHON PROJECT" header: `app/layout.tsx` is not in Zoro's allowed files, and the branding could imply Exasol owns the product.
- Patient-side step tabs, waveform, follow-up and success screens, intake list, separate case-detail and assessment routes: these are Luffy's patient/session components and page wiring. Theme tokens already apply there. Structural changes need Luffy.

### Checks actually run (Windows, mock mode)

- `npm run typecheck`: pass. `npm run lint`: pass (0 problems). `npm run build`: pass.
- Playwright, `CI=true`, mock mode, desktop + phone-390: **48 passed, 10 skipped** (skips are by design: single-project and live-only tests). This includes all existing specs unchanged and the new `tests/e2e/ui-case-attribution.spec.ts`:
  - card headings, review labels, fictional source, no links, no identifiers, no scores/percentages;
  - drawer exact quote equals the clicked quote, highlight, locator, hash, no link, Escape returns focus;
  - 390 px: no horizontal overflow, and the card, brief, comparison and note form fit the viewport.
- Screenshots were taken with `UI_SCREENSHOT_DIR` (desktop and 390 px: workspace, case card, case and patient drawer). They stay outside the repo and are attached to the PR.
- Not run: live mode, and the published attribution path in a browser (no published example exists yet).

### Integration dependency (Luffy)

1. Add `CaseCard.attribution` (nullable; `null` for synthetic) with the planned fields: `authors`, `journal`, `year`, `doi`, `pmid`, `pmcid`, `license_name`, `license_url`, `source_review_status`, `clinical_reviewed`. Then regenerate `contracts/openapi.json` and `apps/web/lib/api/generated.ts`.
2. Add a published card example to `contracts/examples/` and `apps/web/mocks/`.
3. Then Zoro will replace `PlannedCaseAttribution` with the generated type, pass `attribution={card.attribution}` at the two marked call sites (`doctor-workspace.tsx` cases panel, `source-drawer.tsx` case passage), and add a published-card UI test.

### Shared-file agreement requested in the PR

- `components/doctor/doctor-workspace.tsx`: JSX and classes only, within the scope the handoff describes. Kept in its own commit so it can be reviewed or dropped separately.
- `components/mode-banner.tsx`: not edited. It is restyled indirectly through `StatusChip`.

## S4 — homepage (13 Nov 2026)

- **Agreement:** Luffy agreed to the homepage changes in Luffy's lane (relayed by Zoro in chat, 13 Nov 2026). Luffy should confirm this in the PR. The agreement covers:
  - `app/page.tsx`: the new homepage;
  - the new `app/intake/page.tsx`: the intake setup step;
  - the new `components/home/home-entry-actions.tsx`;
  - the one-line `page.goto("/intake")` change in the four existing e2e specs.
- **Homepage** (`952911e`, `0c2ae02`):
  - **Layout:** the four-column grid at 72 rem and wider (Patient | stethoscope across two columns | Doctor). Between 48 and 72 rem the stethoscope sits in its own row with Patient | Doctor below it, and below 48 rem everything stacks. There are no fixed heights, the text wraps, and nothing restricts zoom. All styling is local to the page, and the homepage ends after the two entry sections.
  - **Patient button:** "Start patient intake" opens `/intake`. That page holds the mode label, fictional-demo notice, access code and collection choice, moved there unchanged from the homepage. It then opens `/intake/[session_id]` as before.
  - **Doctor button:** "Open doctor workspace" opens `/doctor/[session_id]` for an encounter started in this tab. Without one, it is `aria-disabled` and shows "Share a patient intake first to review it here." The doctor route's confirmation guard is unchanged.
- **Hero image:** the drawn `public/home/stethoscope.svg` is a placeholder. The corrected PNG has not been received yet. To swap it in, set `HERO_SRC`, `HERO_WIDTH` and `HERO_HEIGHT` in `app/page.tsx`.
- **Checks:** typecheck and lint pass.
  - `tests/e2e/ui-home.spec.ts` checks 320, 390, 768 and 1280 px, plus emulated 80%, 125% and 200% zoom. At each size it checks for no sideways scrolling, no overlap and no clipped text, that the image keeps its aspect ratio, and that the setup block is gone. It also checks both button routes. All pass.
  - Full Playwright suite: 54 passed, 17 skipped, 1 flaky. The flaky test (`review-reliability` "skip is recorded as skipped" at 390 px) passed on retry and then 8 more times in a row.
- **Follow-up for Luffy:** add a "latest session in this tab" helper to `lib/session-store.ts`. The homepage currently reads the token key prefix directly.

> **Takeover note (13 Nov 2026):** Luffy now owns this backend lane too (see `AGENTS.md`). Zoro's
> `zoro/s1-exasol-api` (`510e44a`, `f1e2385`) is merged unchanged into `integration/local-backend`.
> Progress after the takeover is recorded in `docs/status/luffy.md` under "Backend takeover".

- Current sprint: S1 — Exasol-backed encounter service (code complete; live Exasol checks pending)
- Branch: `zoro/s1-exasol-api` from `main` at `3744a70` (S0 PR #1)

## S0 setup (done)

- Exasol SaaS: database running. From Zoro's laptop: TLS with certificate verification, `SELECT 1`,
  and write/read in `DERMA_NAV.S0_PROBE` passed (13 Nov 2026). PyExasol 4.0.0. The SaaS PAT works only
  as `password=`; `access_token=` was rejected. Laptop IP and Render outbound ranges are allow-listed.
- Render: `https://dcn-api-ujrd.onrender.com` live from `main` in memory/fixture mode; `/health` 200
  over HTTPS; demo code enforced. Render-to-Exasol connectivity not yet tested (needs this sprint).
- Source mode: synthetic only (3 fictional cases). No reviewed published cases; source search not done.
- Gemini: not yet set up (S2).

## Implemented (S1)

- `app/service.py` `EncounterService`: the frozen `IntakeService` over an `EncounterRepository`.
  Session tokens HMAC-derived and stored hashed; 24 h session expiry; per-session lock plus optimistic
  `write_version` commit; revisions, stale-write 409, request-ID idempotency persisted with the
  encounter (create-session retry returns the original snapshot and re-derives the same token; the raw
  bearer is never stored); confirmation only at the current processed revision; notes kept separate.
  Storage failures are 503 `STORAGE_UNAVAILABLE` (retryable, no driver text).
- `get_intake_service()` selects by `DATA_BACKEND`: `memory` or `exasol`. Exasol mode never falls back
  to memory: missing configuration is 503 `STORAGE_NOT_CONFIGURED`; Exasol mode also refuses to start
  without a stable `SESSION_TOKEN_SECRET`.
- `app/repositories/exasol.py`: tables COLLECTIONS, CASES, PASSAGES, SESSIONS, TURNS, OPERATIONS,
  SEARCH_VERSIONS, CLINICIAN_NOTES. Queryable IDs/revisions; validated JSON for current facts,
  questions and brief; append-only turns, search versions and notes; case JSON integrity hash checked on
  read. One connection, all access serialized, idle connections re-checked, TLS verification on.
  PyExasol telemetry disabled by default (`EXASOL_TELEMETRY_DISABLE=1`).
- `app/extraction/fixture.py`: labelled fixture extractor (`extractor = "fixture"`), moved out of the
  stub. It replays the documented demo phrases only; any other text is 503 `EXTRACTION_UNAVAILABLE`.
  `advance` refuses results that reference cases missing from storage.
- `scripts.init_db` (create missing tables only) and `scripts.seed --collection synthetic-demo-v1`
  (validate, insert once, read back; refuses a changed version under the same ID) are now real.
- `scripts.restart_check write|verify`: proves an encounter survives an API restart via the live API.
- `pyexasol==4.0.0` and its dependencies locked in `requirements.txt`.

## Not implemented / stubbed

- Natural-language extraction, ranking and question selection: S2. Natural speech does not work yet.
- Skip and correction: still `STUB_NOT_IMPLEMENTED` (S3).
- Field-level caps (utterance length, turns per request) and exact CORS for Vercel: not done.
- `app/stub_service.py` kept only because Luffy's voice tests construct it directly.

## Checks actually run

- `pytest`: 68 passed, 4 skipped. The 57 S0 tests now run against `EncounterService` + memory
  repository. 11 new S1 tests cover restart persistence across service instances, original idempotent
  create response, concurrent modification, storage-failure 503, readiness when storage is down,
  missing stored cases, expiry, published-mode isolation, no memory fallback in Exasol mode.
- The 4 skipped tests are `tests/test_exasol_live.py` (live Exasol). Not run: no local `services/api/.env`.
- All Exasol SQL formatted through PyExasol's `ExaFormatter` with a fake connection (27 statements:
  schema, seed, create, append/advance commit). Not executed against Exasol.
- `scripts.export_openapi --check`: no drift (no DTO or route change).
- Not run: `init_db`, `seed`, live tests, restart check against Exasol, Render deployment of this branch.

## Handoff for Luffy

- No contract change. Same routes and DTOs. New error codes: `STORAGE_UNAVAILABLE` (503, retryable),
  `STORAGE_NOT_CONFIGURED` (503), `COLLECTION_UNAVAILABLE` (503, retryable).
- Snapshot warnings now say "Demo extraction…" and, in memory mode, "Development storage — not Exasol…".
- The voice route keeps working: `get_intake_service()` and `IntakeService.get_session/advance` unchanged.

## Next action

Create `services/api/.env` with `DATA_BACKEND=exasol`, the `EXASOL_*` values and `SESSION_TOKEN_SECRET`,
then run `init_db`, `seed`, the live tests and the restart check.
