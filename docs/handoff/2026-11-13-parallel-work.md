# Parallel-work handoff (13 Nov 2026)

## Starting point

- **Branch:** `integration/local-backend` on GitHub. `main` does not have the backend yet, so start from this branch.
- **Starting commit:** recorded at the end of this file. The code checkpoint is `acf1266`. The handoff commit adds only documentation on top of it.
- **This branch contains:**
  - Exasol persistence;
  - the S2 extraction and ranking pipeline;
  - the Meta Model API extractor (`ce2a5d3`);
  - the two pending published candidates, the review table and the review-gated importer (`acf1266`);
  - all S0–S3 frontend work.
- **Zoro's branch:** create `zoro/s4-case-ui-attribution` from the starting commit and open PRs back into `integration/local-backend`. Don't self-approve.
- **Run the UI without a backend:** in `apps/web`, run `npm ci` and set `NEXT_PUBLIC_API_MODE=mock` in your own `.env.local`. Mock mode uses the shared fixtures and labels itself in the UI. Checks: `npm run lint`, `npm run typecheck`, `npm run test:e2e`.
- **Credentials:** none are needed for the UI lane. Never commit `.env*` files except `.env.example`.

## Ownership (see `AGENTS.md`)

**Luffy:** the backend (`services/api/**`), source records and the published import (`data/**`, `docs/data/**`), contracts and generated types (`contracts/**`, `apps/web/lib/api/**`), voice and session integration, GitHub, ElevenLabs, Exasol and Render.

**Zoro:** presentational doctor, case and source-drawer components, styling, frontend QA and Vercel preview preparation.

### Files Zoro may edit

- `apps/web/components/source-drawer.tsx`: the drawer's presentation. Keep `resolveEvidence` usage and the provider/context API unchanged.
- `apps/web/components/evidence.tsx`
- `apps/web/components/status.tsx`
- `apps/web/components/doctor/comparison-history.tsx`
- `apps/web/components/doctor/clinician-note-panel.tsx`: markup and styling only. The save, request-ID and error-handling logic stays as it is.
- New presentational files under `apps/web/components/doctor/` and `apps/web/components/case/`, for example `case-card.tsx` and `case-attribution.tsx`. They take typed props only, with no data fetching and no session store.
- `apps/web/components/ui/**`
- `apps/web/app/globals.css`
- New e2e specs `apps/web/tests/e2e/ui-*.spec.ts`
- `docs/status/zoro.md`
- Vercel preview preparation notes in `docs/status/zoro.md`. Project creation and environment values need the human account holder.

### Shared files: agree in the PR before editing

- **`apps/web/components/doctor/doctor-workspace.tsx`:** this file mixes data loading with layout. Zoro may change the JSX and class names that render the brief and the cards, or move a card into a new presentational component. Leave `load()`, token handling, the confirmed-revision guard and the API calls unchanged.
- **`apps/web/components/mode-banner.tsx`:** you may restyle it. The required text, including "Fictional demonstration case — not published evidence", and the mode logic stay as they are.
- `apps/web/package.json`, `package-lock.json`, `next.config.ts`, `playwright.config.ts`, and the existing e2e specs.

### Not in Zoro's lane

These are Luffy's:
- `apps/web/lib/**`, including the generated types: never edit `lib/api/generated.ts` or `types.ts` by hand;
- `apps/web/mocks/**`;
- `apps/web/app/api/**` and the page data wiring;
- `components/voice/**`, `components/patient/**`, `components/start-form.tsx`;
- `services/**`, `data/**`, `contracts/**`.

Ask Luffy for any field you need instead of inventing a response shape.

## Product rules that the UI must keep

These rules are in `AGENTS.md` and `docs/06-ui-and-demo.md`:
- no diagnosis, treatment recommendation or image interpretation;
- no scores or probabilities;
- synthetic cards always show the fictional label and no article link;
- published cards link to the original article and show only reviewed passages;
- missing information, no-match, conflict, offline, loading and validation-failure states stay explicit;
- keep keyboard access and a readable 390 px phone layout.

## Attribution: Luffy provides the data, Zoro builds the display

### Available today on `CaseCard`

Generated types are in `apps/web/lib/api/types.ts`.

| Field | Content |
|---|---|
| `source_kind` | `"published"` or `"synthetic"` |
| `title` | Article title (published) or fictional label title |
| `article_url` | `https://pmc.ncbi.nlm.nih.gov/articles/PMC…/` for published cards, `null` for synthetic |
| `passages[]` | `passage_id`, `text`, `section`, `locator` (PMCID, section, paragraph, character range), `sha256` |

### `CaseCard.attribution`: available now (see "Attribution commit" at the end of this file)

Import it as `import type { CaseAttribution, CaseCard } from "@/lib/api/types";`. The field is declared as `attribution?: CaseAttribution | null` in `apps/web/lib/api/generated.ts`.

- **The key is in every API response.** It is `null` on all synthetic cards. The type marks it optional (`?`) only so that search snapshots stored before this change stay readable. Treat `undefined` the same as `null`.
- **It is non-null only for a reviewed published case.** That also requires citation metadata captured from the article. Pending published cases never reach a card.

```ts
type CaseAttribution = {
  authors: string[];          // article order, "Surname Initials" (PubMed style), authors only (no editors)
  journal: string;            // e.g. "Cureus"
  year: string;               // electronic publication year, e.g. "2020"
  doi: string | null;         // e.g. "10.7759/cureus.10839" (bare DOI, no https://doi.org/ prefix)
  pmid: string | null;        // e.g. "33173645"
  pmcid: string;              // e.g. "PMC7647841"
  license_name: string;       // e.g. "CC BY 3.0"
  license_url: string;        // e.g. "https://creativecommons.org/licenses/by/3.0/"
  source_review_status: "reviewed";
  clinical_reviewed: boolean; // currently always false: show "Not clinically reviewed"
};
```

- **Where the values come from:**
  - `authors`, `journal`, `year` and the licence come from the article's PMC JATS XML: `contrib-group`, `journal-title`, `pub-date[@date-type="pub"]` and `ali:license_ref`.
  - The identifiers come from the PMC ID converter.
  - The review fields come from the stored record.
- **Licence version:** the licence is the one stated in the artifact the passages come from, the PMC XML. For PMC7861115, the publisher PDF states CC BY 4.0, while the XML states CC BY 3.0. That discrepancy is documented for review in `docs/data/published-review.md`. The UI shows `license_name` and links `license_url` exactly as given.
- **Mocks:** there is no published mock yet. All current examples are synthetic, so `attribution: null`. No reviewed published case exists, and I won't fabricate a reviewed example. A published example from a real reviewed import will follow in `contracts/examples/` and `apps/web/mocks/fixtures/`. Until then, build and test the display against the `CaseAttribution` type in an uncommitted local harness. You can use the real values of the two pending candidates in `data/published/candidates/*.json` (`citation` and `article_identifiers`), but don't commit them as a reviewed card.
- **Display suggestion:** the layout is Zoro's decision. Show the authors, title, journal, year, linked DOI/PMID/PMCID, linked licence name, and "Source-reviewed · Not clinically reviewed".

## Current state (updated 13 Nov 2026, after structured-v2)

### What Zoro needs from the structured-v2 change

There are no type changes: OpenAPI, `generated.ts` and the mocks are unchanged. Three display points are worth knowing:

- **New fact key.** Patient facts can have `key = "symptom_site"` with `value = "<symptom>@<site>"` (e.g. `itching@scalp`). `comparison-history.tsx` `factLabel` currently prints it as "symptom site: itching@scalp". Suggested label: "itching on the scalp" (split on `@`).
- **Exclusion label.** `ExcludedCase.reason = "no_shared_symptom"` now also means "no symptom reported at the same site in both". Suggested `EXCLUSION_LABEL` text: "No explicitly shared symptom at the same site".
- **Search text.**
  - New searches carry `algorithm_version = "structured-v2"`. Older stored searches stay `structured-v1`, and the mocks are v1 snapshots.
  - The shared-feature text is now "Shared reported symptom at the same site: …".
  - After a rule change, change reasons begin with "Comparison rules changed to structured-v2".

### Implementation status (checked in code, not inferred from mock tests)

| Capability | Status | Evidence |
|---|---|---|
| Typed/voice-transcript intake → validated facts → structured-v2 ranking → brief (Exasol, Meta) | Implemented, live-verified | `tests/test_exasol_live.py`, `tests/test_meta_live.py` (live runs, 13 Nov) |
| Patient confirmation of the current revision | Implemented | `EncounterService.confirm`, `intake-view.tsx` confirm guard |
| Live **corrections** | **Missing in the backend.** The UI exists, but `EncounterService.correct_turn` returns `503 STUB_NOT_IMPLEMENTED` | `services/api/app/service.py` |
| Live **skip** | **Missing in the backend** (`503 STUB_NOT_IMPLEMENTED`) | `services/api/app/service.py` |
| Patient-visible review of the extracted summary | **Missing.** The patient reviews their own statements ("Your story so far") and the brief's unresolved items. Extracted facts and the summary (including symptom–site links) are shown only in the doctor view | `statement-history.tsx`, `intake-view.tsx` |
| Deployment (Render API, Vercel web) | **Missing.** Only CI workflows exist (`.github/workflows/api.yml`, `web.yml`); there is no deploy config and nothing deployed | repository |
| Full voice loop (agent asks backend-approved questions via `advance_intake`) | **Unverified end to end.** The backend webhook `POST /v1/voice/advance` is implemented and unit-tested, and live transcript capture was verified in S1/S2. The ElevenLabs `advance_intake` tool is not configured: it needs a public backend URL | `services/api/app/voice/`, `docs/voice/s2-handoff.md` |
| Published collection | **Imported and live-verified (14 Nov).** `published-derm-v1` has 2 source-reviewed cases (not clinically reviewed) in Exasol. Live API and browser runs return the minoxidil card for scalp itching and a no-match for an itchy face | `docs/status/luffy.md` |
| Published-mode UI text (Zoro) | **Open.** Attribution is in the API response but not displayed yet. The no-match text still uses v1 wording ("shares both an explicitly reported symptom and site"). The clinician-note helper says "Fictional demo only" in published mode. An empty prior-treatment section reads "None reported", but should not suggest absence | doctor workspace, live run 14 Nov |

### Luffy's next actions

1. Wait for the human source-review result on `PUB-PMC7647841-1` and `PUB-PMC7861115-1`.
2. After approval:
   - run `record_source_review.py` (Luffy, as reviewer) and `import_published --dry-run`, then the real import into Exasol;
   - run a live published encounter, checking source links and an honest no-match;
   - add a real published example to `contracts/examples/` for Zoro.
3. Expand toward 4–8 published cases.
4. Then: backend skip and correct, a patient-visible summary review, deployment, and the `advance_intake` tool.

## Starting commit

Start from **`3d7ab9d`** ("Handoff: revised Luffy/Zoro ownership, allowed UI files and attribution fields") on `integration/local-backend`. The commit after it only adds this line. Code and contracts are identical to `acf1266`, apart from documentation.

## Attribution commit

`CaseCard.attribution` is available from **`daa20c6`** ("Contract: CaseCard.attribution and CaseRecord.citation from PMC metadata; revised pending candidates and licence evidence") on `integration/local-backend`. To consume it, rebase or merge your branch onto that commit, or onto any later tip, and then run `npm ci`. You don't need to regenerate anything: `lib/api/generated.ts`, `lib/api/types.ts` and `mocks/fixtures/` are already updated.
