# Contract decisions at S0 freeze

Proposed by Luffy during bootstrap. **Zoro must review and agree in the S0 PR**; after merge, Zoro owns
`contracts/**` and changes follow `docs/09-contract-change-template.md`.

Sources reconciled: `docs/03-api-contract.md` (prose), `contracts/domain.schema.json` (machine schema),
`contracts/examples/*.json` (serialized snapshots).

## Discrepancies resolved

| # | Topic | Prose said | Resolution |
|---|---|---|---|
| 1 | Case-difference question metadata | "two case IDs and supported contrasting features in its reason metadata" | Use the schema's `Question.comparison_basis {case_ids, contrasting_feature, evidence}`; `reason` stays a plain string. |
| 2 | Endpoint DTOs | Listed inline in the route table only | Defined in `services/api/app/models.py`: `CreateSessionRequest/Response`, `AppendTurnsRequest`, `AdvanceRequest`, `SkipQuestionRequest`, `ConfirmRequest`, `CorrectionRequest`, `ClinicianNoteRequest`, `VoiceBindingRequest/Response`, `ReadinessResponse`, `CollectionsResponse`, `HealthResponse`, `ApiErrorResponse`. All forbid unknown fields. |
| 3 | `GET /v1/collections` shape | "Available collection ID/mode/version/review count" | `{collections: Collection[]}`, reusing the domain `Collection`. Published mode with no reviewed data returns an empty list. |
| 4 | `GET /v1/readiness` | `{storage, extractor, collection_mode, loaded_cases, ready}` | Same fields; `collection_mode` is `published|synthetic`; `storage`/`extractor` report what the implementation actually does, not configuration. |
| 5 | Error `request_id` | Always present | Nullable: 422 validation errors and auth failures before body parsing have no request ID. Validation errors never echo submitted content. |
| 6 | Service helpers | Eight frozen methods | Eight methods unchanged. Added read-only `readiness()` and `list_collections()` to `IntakeService` so both system routes also go through the seam. |
| 7 | `SearchVersion.score_components` | Not in prose | Present in schema and examples; kept. The UI must not render scores as percentages or probabilities. |
| 8 | `article_url` format | Schema `format: uri` | Pydantic uses plain `str`; URI validation is left to Zoro's importer (published cases only). The alignment test ignores `format: uri`. |
| 9 | Shared HTTP examples | Only snapshot examples existed | Added `contracts/examples/http/*.json` (create-session, collections, readiness, clinician-note, two error envelopes). Kept in a subfolder so `validate_pack.py` (domain-only glob) still passes. Backend tests round-trip each through its DTO; the web mock imports synced copies. |
| 10 | OpenAPI components | — | Exported with `separate_input_output_schemas=False` so generated TS names match domain names. `HTTPValidationError` still appears as a FastAPI artifact; runtime 422s use `ApiErrorResponse`. |

## Error codes used so far

`UNAUTHORIZED` 401, `BAD_DEMO_CODE` 403, `SESSION_NOT_FOUND` 404 (also for a wrong token: no existence
oracle), `COLLECTION_NOT_FOUND` 404, `REVISION_CONFLICT` 409, `IDEMPOTENCY_MISMATCH` 409,
`DUPLICATE_TURN_ID` 409, `NOT_READY_TO_CONFIRM` 409, `VALIDATION_ERROR` 422,
`DEMO_ACCESS_NOT_CONFIGURED` 503, `EXTRACTION_UNAVAILABLE` 503, `STUB_NOT_IMPLEMENTED` 503,
`VOICE_NOT_IMPLEMENTED` 503. Rate limiting (429) is not implemented yet (Zoro, S1).

## Left for Zoro to decide (not changed by Luffy)

- `examples/no-match.json`: unresolved item "Onset is unknown." has `status: "reported"`, while
  `BriefItem.status` also offers `missing`. Defensible (the patient explicitly said they don't know),
  but pick one convention for S2 briefs.
- `examples/no-match.json`: excluded cases carry empty `evidence` for `site_conflict`. Allowed by the
  schema; S2 exclusions should cite both sides where possible.
- Session token derivation: the S0 stub already uses HMAC-SHA256 over
  `dcn.session-token.v1|<session_id>|<creation request_id>` and stores only a SHA-256 hash. Keep or
  replace in S1, but keep a domain-separated string.

## Change after S0 (13 Nov 2026, single-owner backend takeover by Luffy)

- Problem: the extraction provider changed from Gemini (no credentials) to the Meta Model API.
  `Modes.extractor` and `ReadinessResponse.extractor` were `fixture | gemini`, so the app could not
  truthfully report Meta extraction.
- Change: enum value `gemini` replaced by `meta` in `contracts/domain.schema.json`, `app/models.py`,
  regenerated `contracts/openapi.json` and `apps/web/lib/api/generated.ts`. `fixture` unchanged.
  No route, field or other DTO change. The UI label is "Meta model extraction".
- Compatibility: no stored snapshot or shared example used `gemini`. Agreement: Luffy holds both
  roles after the recorded takeover (`AGENTS.md`).

## Change: published-case attribution (13 Nov 2026, Luffy as contract owner)

- **Problem:** published cards must credit their CC BY source, so Zoro's UI needs authors, journal, year, identifiers and licence on the card. `CaseRecord` had nowhere to store the bibliographic metadata.
- **Change: `CaseRecord.citation`** is a new `ArticleCitation | null` with `{authors, journal, year, license_name, license_url}`. The values are captured from the source article's PMC JATS XML. The field is optional, and the API omits it when null, so all synthetic records and stored JSON serialize unchanged. The synthetic collection digest is not affected. `app.published` requires the citation on every published record, and requires `license == "<license_name> (<license_url>)"`.
- **Change: `CaseCard.attribution`** is a new `CaseAttribution | null` with:
  - `authors`, `journal` and `year`;
  - `doi` and `pmid` (nullable) and `pmcid`;
  - `license_name` and `license_url`;
  - `source_review_status` (`"reviewed"`) and `clinical_reviewed`.

  structured-v1 builds it only for reviewed published cases that have a citation, and returns `null` otherwise. API responses always include the key. The schema default only keeps search snapshots stored before this change readable.
- **Examples:** every synthetic card in `contracts/examples/*.json` now has `"attribution": null`, and the mocks have been re-synced. No published example was added, because there is no reviewed published case yet.
- **Generated artifacts:** `contracts/openapi.json` and `apps/web/lib/api/generated.ts` were regenerated, and the `CaseAttribution` alias was added to `lib/api/types.ts`.
- **Compatibility:** no route changed. The alignment test now treats a single-value Literal (`const`) as a one-value enum.

## Change: ranking `structured-v2` and the `symptom_site` key (13 Nov 2026, Luffy as contract owner)

- **Problem:** `structured-v1` intersected sites and symptoms independently. Scalp itching plus facial swelling therefore qualified as "facial itching".
- **Change:** this is a semantic change with no schema change. `PatientFact.key` and `CaseFeature.key` gain the value `symptom_site`, written `"<symptom>@<site>"`. The value is supported only by text that states the two together. New searches use `SearchVersion.algorithm_version = "structured-v2"`. `ExcludedCase.reason = "no_shared_symptom"` now also covers "no symptom at the same site in both". Its stored `CaseChange.reason` text says so. Rules: `docs/data/ranking-structured-v2.md`.
- **Unchanged:** routes, DTOs, enums, OpenAPI and generated TS types are all unchanged (`export_openapi --check` reports no drift). The examples stay `structured-v1` snapshots and still round-trip.
- **Stored data:** stored `structured-v1` searches are never recomputed. The next v2 search attributes its changes to the rule change. `synthetic-demo-v1` records and their digest are untouched.
- **Brief text:** "Patient reports X on the Y" is rendered only for stated associations. Separate mentions are rendered as "(body site not clearly linked in the patient's words)" and "(not clearly linked to a symptom in the patient's words)".
