# Luffy status

> ## REQUIRED DEMONSTRATION MILESTONE: reviewed published collection
> Published-case evidence navigation is the product's central selling point. The synthetic
> collection was a development fallback only. The product is **not** demo-ready until a small
> (4–8 case), source-reviewed **published** collection is loaded into Exasol and a fictional
> encounter retrieves real published case cards with clickable, correct passages, plus an honest
> no-match path. Model or unit tests alone never mark the product complete.
>
> ### Remaining release checklist (open items)
> - [ ] **Published collection:** acquire candidates from original sources; human source review; import into Exasol; live retrieval with correct passages; no-match path. *(in progress: 2 pending candidates at the first source-review checkpoint, see `docs/data/published-review.md`; 2–6 more to follow)*
> - [ ] Real backend Skip and Correct (currently `STUB_NOT_IMPLEMENTED`).
> - [ ] Patient-visible review of the extracted summary before confirmation (today the patient sees their own statements and unresolved items only).
> - [ ] Combined deployment (Render API + Vercel web, Exasol egress, CORS, secrets).
> - [ ] Full ElevenLabs clarification loop (`advance_intake` tool, real prompt, live voice round trip).
> - [ ] Final rehearsal of the three-minute demo from reset encounters, with actual mode labels.
>
> Provider note: the Meta `-contributor` model mode permits training use of inputs; `store=False`
> does not prevent that. Encounters must stay fictional.

## Backend takeover (13 Nov 2026) — milestone 1: local Exasol persistence

Luffy now implements both lanes in this single session (authorized; recorded in `AGENTS.md`).

- Branch `integration/local-backend` = S3 tip `3a75027` + `origin/zoro/s1-exasol-api` (`510e44a`, `f1e2385`) via a normal merge (`325c605`). No conflicts.
  - Frozen `IntakeService` seam, DTOs and OpenAPI unchanged.
  - Voice adapter and S3 UI unchanged.
  - Sprint branches `luffy/s2-voice-evidence` and `luffy/s3-review-reliability` untouched.
- Added `tests/test_voice_encounter_service.py`. It shows the voice adapter running against Zoro's `EncounterService` (memory repository): full loop, no second question for a repeated tool call, the agent turn not bumping the revision, and the real service rejecting `DUPLICATE_TURN_ID`.
- Dependency change: `pyexasol==4.0.0` plus its locked dependencies from Zoro's `requirements.txt`, nothing else.
- Checks: `pytest` 83 passed, 4 skipped (live Exasol tests skipped: no credentials). `export_openapi --check` no drift. `validate_pack.py` PASS.
- Local `services/api/.env` created (gitignored):
  - `DATA_BACKEND=exasol`; `SESSION_TOKEN_SECRET` and `VOICE_TOOL_SECRET` generated locally, never printed.
  - Exasol credentials entered by Luffy directly in the file.
  - With them blank, Exasol mode had failed closed: `init_db` refused memory and readiness returned 503 `STORAGE_NOT_CONFIGURED`. The web `.env.local` is untouched.
- Connectivity:
  - The first attempts timed out at TCP on port 8563 (DNS OK; outside port 443 and 8563 reachable).
  - Cause: this laptop's network rotates its outbound IPv4 within `131.246.202.x`.
  - Fixed by allowlisting both the specific address and the observed range in Exasol SaaS.
  - TLS certificate verification stayed on throughout.

### Live Exasol results (13 Nov 2026, this laptop)

- `scripts.init_db`: PASS. Schema `DERMA_NAV`, all 8 tables already present, nothing created or altered.
- `scripts.seed --collection synthetic-demo-v1`: PASS twice. Unchanged; read back 3 cases and 6 passages (version `858f8867b3cd…`). Repeatable.
- `tests/test_exasol_live.py` (`DCN_LIVE_EXASOL=1`, schema `DERMA_NAV_TEST`): **4 passed**.
  - case round-trip with integrity hash
  - encounter persistence across connections (turns, search history, brief, facts, clinician note; idempotent append replay)
  - stale write-version rejection
  - UTC timestamps
- `scripts.restart_check write` → API process stopped (port free) → fresh process → `verify`: **PASS**. The encounter, its turns, the search history and the create-session idempotency record survived. Storage `exasol`.
- Extra full-snapshot restart check (temporary local script, deleted): **PASS**.
  - Write: 1 turn, advance, 1 clinician note.
  - After a real process restart, the complete snapshot JSON was byte-identical (SHA-256 match): revision 1, `awaiting_answer`, 4 facts, 1 question, 1 search version, brief present, 1 note, storage `exasol`.
- An earlier restart-check attempt ran its steps out of order (tool batching). It was discarded and the sequence repeated step by step; only the step-by-step results are reported.
- Unit suite after the live runs: `pytest` 83 passed, 4 skipped (live tests skip by default); `export_openapi --check` no drift.

### Manual browser test against Exasol (Luffy, 13 Nov 2026): PASS

Next.js in live API mode against the Exasol-backed API (fixture extractor). Three typed demo statements produced two clarification questions; confirmation opened the doctor workspace at revision 3; the cream name stayed unknown; the comparison showed SYN-B removed after the new-soap answer; storage stayed Exasol and the synthetic/demo labels were visible.

## Backend S2 (13 Nov 2026) — validated extraction and computed ranking

Commit `445e428` on `integration/local-backend`. Same `IntakeService` seam, DTOs and OpenAPI (`export_openapi --check` clean).

- **Pipeline** (`app/pipeline.py`):
  - active patient turns only (agent and superseded turns never become evidence; pure acknowledgements skipped)
  - candidate provider
  - server validation (`app/evidence/validate.py`)
  - fact assembly preserving unknown, negated and conflicting
  - `structured-v1` ranking over the cases loaded from storage (`app/retrieval/structured_v1.py`)
  - two-question policy (`app/questions.py`)
  - template brief (`app/evidence/brief.py`)
- **Providers:**
  - `gemini` (`app/extraction/gemini.py`): google-genai 3.3.0, JSON response schema, temperature 0, 20 s timeout. Turns are sent as data. Any failure becomes `ExtractionUnavailable`, with no provider text.
  - `fixture` (`app/extraction/rules.py`): deterministic keyword rules over any wording, labelled "Demo extraction".
  - The exact-phrase replay extractor (`app/extraction/fixture.py`) is deleted; nothing selects canned snapshots any more.
- **Validation rules:**
  - Exact quote from an active patient turn.
  - Value must come from the reviewed alias map applied to words inside the quote, or be the patient's verbatim words for raw-value keys.
  - Negation needs a cue. Unknown needs "don't know"-type words about that field, or an answer to a question about it.
  - Treatment durations and responses only within a treatment clause.
  - Generic words (cream, lotion, steroid…) are never a product name.
- **Search versions:** IDs reproducible from session, revision, algorithm, collection version and facts. A new version only when inputs change. Changes are computed from the actual old and new ranks and scores, with case-passage evidence.
- **Repeat calls:** a repeat `advance` at an already-processed revision returns the stored result, with no new question or search.
- **Errors:** provider failure is a 503 `EXTRACTION_UNAVAILABLE` (retryable); the turns stay saved.
- **Gemini mode:** a missing key or model gives readiness `ready=false` and never falls back.

Checks actually run:

- `pytest` **103 passed, 7 skipped**. The skips are the opt-in live Exasol and Gemini tests.
- New `tests/test_pipeline_s2.py` (20 tests) covers:
  - an unseen hesitant paraphrase
  - acknowledgements
  - a bare "No" to the exposure question
  - "not sure" is unknown, not no
  - denial plus a duration conflict
  - no-match
  - agent speech never becoming evidence
  - checklist question
  - stop request
  - repeat advance
  - ranking computed from a modified stored collection (a 4th case appears, a 9-point score)
  - reproducible search
  - validator rejecting cream→steroid, weeks→three weeks, "didn't help"→treatment-resistant, wrong turn, invented quote, agent quote and diagnosis key
  - scripted model output filtered before ranking
  - provider failure and retry
  - Gemini provider with a fake client (schema, failures, unconfigured)
  - Gemini readiness
- Live Exasol (`DCN_LIVE_EXASOL=1`, `DERMA_NAV_TEST`): **5 passed**, including the new S2 smoke. Hesitant 4-turn speech persisted 4 unique search versions and was re-read through a fresh connection: SYN-A removed, SYN-B moved to rank 1.
- HTTP smoke against the running Exasol-backed API (temporary script, deleted). Unseen wording ("itching like crazy… three weeks… some lotion, didn't do much / no idea what it was called… a couple of days / switched to a new dish soap") gave cream question, exposure question, then ready. Searches `[A,B]`, `[A,B]`, `[A]`, with SYN-B removed for an explicit exposure conflict. Storage `exasol`.
- Not run: the live Gemini tests (`tests/test_gemini_live.py`). `GEMINI_API_KEY` and `GEMINI_MODEL` are blank in `services/api/.env`.

Known limits:

- The keyword rules cover only the alias vocabulary.
- Re-extraction runs over all active patient turns on each advance (Gemini temperature 0, no per-turn cache).
- Skip and correction are still stubs.
- In live mode, the web e2e test "unrecognised text shows an honest processing error" no longer applies: the backend now returns an insufficient-information brief. The mock-mode test is unchanged.

## Provider change: Meta Model API (13 Nov 2026) — verified locally

Gemini is replaced by the Meta Model API. Only the provider changed; validation, ranking, questions, briefs and Exasol persistence are unchanged.

- **Provider** (`app/extraction/meta.py`):
  - `openai` 3.50.0 with an explicit `base_url` (`MODEL_BASE_URL`, https only) and `MODEL_API_KEY`.
  - Calls `client.responses.create(model=MODEL_NAME, instructions=…, input=<JSON of patient turns>, text={"format": {"type": "json_schema", "strict": true, …}}, reasoning={"effort": "minimal"}, store=False)`.
  - The output is parsed into the existing `Candidate` schema, then the unchanged evidence validator.
  - Sends alias names, active patient turns and the text of the question each turn answers. It never sends agent speech, credentials, database settings or the case collection.
  - **Retention correction:** `store=False` only stops the Responses API from storing the response for retrieval or chaining. It does **not** guarantee that the provider keeps no data or does not train on it. The `muse-spark-1.3-contributor` mode **permits training use of inputs**. This is acceptable only because every encounter is fictional; real patient data must never go through this provider.
  - Timeout 45 s, one SDK retry. Failures raise `ExtractionUnavailable` (retryable 503, turns kept), with no fallback to the keyword rules.
- **Contract:** `Modes.extractor` and `ReadinessResponse.extractor` are now `fixture | meta` (recorded in `contracts/DECISIONS.md`). OpenAPI and web types are regenerated; the UI label is "Meta model extraction". `google-genai` is removed from the clean-venv lock; `openai` 3.50.0 and `jiter` were added.
- **Config:** `services/api/.env` now has `EXTRACTOR_MODE=meta`, `MODEL_BASE_URL` and `MODEL_NAME`. `MODEL_API_KEY` was already present and untouched, and the old Gemini lines are left unused. `.env.example` has a blank key. `python -m scripts.check_model` checks model access and prints availability only.
- **Fixes found by live runs:**
  - "No clue" / "not a clue" now count as don't-know words.
  - An unknown onset ("don't know when it began") counts as duration covered, so the checklist no longer re-asks "How long have you had this?".

Checks actually run:

- `check_model`: host `api.meta.ai`; the key lists 10 models; `muse-spark-1.3-contributor` is **available** (0.64 s).
- `pytest` **107 passed, 8 skipped** (opt-in live tests). Meta provider tests with a fake client cover:
  - the strict structured-output request, `store=False`, and payload contents (no agent turn, key or DB/case data)
  - strict-subset schema
  - failures: bad JSON, schema mismatch, incomplete status, timeout; no secret text leaks
  - unconfigured, and http base URL refused
  - client pinned to the Meta base URL with 1 retry and a 45 s timeout
  - readiness false without a key
- Live Meta (`DCN_LIVE_META=1`, `tests/test_meta_live.py`): **3 passed** on unseen, hesitant fictional speech.
  - A hesitant main story ends with SYN-A only, the cream name unknown and no drug inferred.
  - A denial story: "not itchy exactly, more like they burn" gives itching negated and burning reported.
  - A no-match paraphrase passes.
  - All quotes are exact substrings of patient turns.
  - Latency at effort `minimal`: **5.0–8.5 s per extraction** (`low` measured 8–15 s with identical validated facts).
- Exasol + Meta HTTP workflow, temporary script deleted. Readiness `exasol/meta/ready`; new wording ("lotion… couple of days… new dish soap").
  - 4 advances at 6.2–7.6 s; questions cream then exposure.
  - Searches `[A,B] ×3 → [A]`, SYN-B removed, SYN-A score 9.
  - Repeat advance at the same revision took 1.1 s and created no new search.
  - Confirmed at revision 4.
  - All quotes exact; the brief includes treatment duration and exposure.
- Web: typecheck and lint pass.
  - Playwright mock mode: 43 passed, 9 skipped.
  - Live mode `typed-intake.spec.ts` against Exasol + Meta: **8 passed, 2 skipped** (mock-only test). It includes the new live test: unfamiliar wording gives the neutral site question, then "I don't know", then an insufficient-information no-match brief with no processing error.
  - The first live run had 2 failures (an unknown-onset re-ask); fixed and re-run.
  - Playwright live mode now uses 180 s test and 30 s expect timeouts.

Not run in live mode this round: the other web suites (voice, review-reliability). They were unchanged and pass in mock mode.

### Not done (by instruction)

- No Render deployment.
- No ElevenLabs prompt or tool change.
- No new UI feature.
- `integration/local-backend` not pushed.

- Current sprint: S3 — checkpoint reached; branch `luffy/s3-review-reliability` (from S2 tip `f2ee90c`)
- S2: PR from `luffy/s2-voice-evidence` under review (branch unchanged since push). S3 commits stay off that branch.
- Reconcile with `main` (normal merge, no force push) after the S2 PR merges, before opening the S3 PR.
- Full voice loop remains **unverified** (see S2 notes below).

## Implemented (S3, Luffy lane only)

- **Final review and confirmation**:
  - On `ready_to_confirm`, the review heading takes focus and the voice panel stops capture (`captureAllowed={false}`). The panel stays mounted, so late finalized words are still saved, not dropped.
  - Confirm stays disabled while voice is live, writes are queued, voice lines are unsaved or failed, or the browser is offline. The page shows why.
  - On click: flush the write queue, re-read, and confirm only if the revision equals the one reviewed. Otherwise show "Your statement changed while you were reviewing" and do not confirm.
- **Correction and history** (`components/patient/statement-history.tsx`, `lib/session/history.ts`):
  - Each current statement has a keyboard-accessible Correct button. Escape cancels and returns focus.
  - A correction is a new `origin="correction"` turn superseding the original. Replaced versions are listed struck-through under "Earlier version — replaced". Nothing is overwritten.
  - Corrections are available after confirmation too. Afterwards the patient view says the earlier confirmation no longer applies, and the doctor view refuses the brief and explains why.
  - The comparison stays labelled stale until a recompute at the new revision.
- **Unknown, skipped, conflict, retry and reconnect states**:
  - Clarification list with Answered, You said you don't know, Skipped and Waiting chips.
  - Doctor-side wording: "not a negative finding" for unknown and skipped.
  - The skip notice says it is recorded as skipped, not as a "no".
  - Revision conflicts re-read the session and explain. 503 failures keep already-saved words and offer Retry.
  - An offline banner disables sending while keeping the typed text.
  - The doctor view has Refresh, a load-time chip and a retryable load error. Voice reconnect is from S1/S2.
- **Clinician note** (`components/doctor/clinician-note-panel.tsx`):
  - Author label plus note, saved through `POST /clinician-notes` with one request ID per draft (safe retry).
  - Unsaved and saved states. The list shows author and patient revision, and marks notes written against an earlier revision.
  - The note never changes the brief and is never shown in the patient view.
- **Labelled mocks** (`mocks/mock-transport.ts`, mock mode only):
  - MOCK-ONLY contract-shaped `skip` and `corrections`, each adding a visible snapshot warning: "Mock skip…" / "Mock correction… not implemented yet".
  - Duplicate-turn rejection, matching the backend.
  - A `dcn.mock-fail` sessionStorage hook for failure tests.
  - The mock cannot recompute after a skip or correction; the UI shows an honest "processing failed".

No backend, contract, DTO or ElevenLabs change in S3.

## Checks actually run (Windows, local; S3 branch before merging main)

- Backend unchanged: `validate_pack.py` PASS, `export_openapi --check` no drift, `pytest` 70 passed.
- Web: fixture and type drift clean, `typecheck`, `lint`, `build` pass.
- Playwright, mock mode, `CI=true`: **43 passed, 7 skipped**. Skips are by design: logic and layout tests run on one project only.
- New S3 tests (`tests/e2e/review-reliability.spec.ts`), mock mode:
  - review focus and confirm at revision 3
  - late words during review block the stale confirmation (A11)
  - keyboard correction after confirmation: original kept, confirmation invalidated, revision 4, doctor view refuses the old brief (A09)
  - skip recorded as skipped (A05)
  - injected 503 keeps saved words and recovers with Retry (A19)
  - offline disables Send and keeps the text
  - clinician note saved separately, brief unchanged, persists after reload, not shown to the patient (A17)
  - 390px: no horizontal overflow on intake, review and doctor; source drawer full-width (A18)
- Playwright, live mode against the local FastAPI S0 stub: **35 passed, 15 skipped**.
  - Skipped: the 7 single-project checks, plus the 4 mock-only tests (late words, correction, skip, injected failure) on both projects. The stub returns `STUB_NOT_IMPLEMENTED` for skip and correction.
  - In live mode this covers review/confirm, clinician note persistence through the real `/clinician-notes` route, offline, 390px layout, and all S1/S2 suites.
  - An earlier live run showed 21 failures because the API process was not running; re-run with the API up.
- **No live voice or ElevenLabs test in S3.** Agent configuration unchanged (connection-test prompt, no tools).

## Remaining backend dependencies (Zoro)

1. `POST /v1/sessions/{id}/skip`: records `skipped` (never a negative fact), bumps the revision once, and `advance` then continues without re-asking.
2. `POST /v1/sessions/{id}/corrections`:
   - appends `origin="correction"` with `supersedes_turn_id`, bumps the revision
   - clears `confirmed_revision`, and resets answer links where relevant
   - `advance` recomputes from active turns only, with no new question budget
   - an already-replaced turn gives a clear 409
3. A late patient turn after confirmation clears `confirmed_revision` (already true in the S0 stub).
4. Clinician notes stay in a separate store and are returned in `clinician_notes`; persisted in Exasol mode.
5. Readable 503 messages (e.g. storage unavailable) with `retryable` set correctly.
6. From S2: the real extractor must handle ordinary spoken text, and the combined backend must be on Render, before the full voice loop can be verified.

## S2 notes kept for reference

- Live: voice transcript persistence PASS (patient and assistant turns saved, patient-only story, revision 3 for three patient utterances). The "agent did not acknowledge" report was diagnosed as Stop interrupting the reply.
- Unverified: full loop speech → stored turn → `advance_intake` → spoken backend question → answer → changed snapshot. Handoff: `docs/voice/s2-handoff.md`.

## Next action

- Zoro: review the S2 PR; implement skip, corrections and recompute in the real service.
- Luffy: after the S2 merge, merge `main` into the S3 branch, re-run checks and open the S3 PR. After the Render backend is ready, verify the webhook, then configure the tool and prompt.

## Published collection: first source-review checkpoint (13 Nov 2026)

- Discovery: PMC-Patients `PMC-Patients.csv` from Hugging Face (dataset licence tag `cc-by-nc-sa-4.0`), used to find candidates only. `data/tools/pmc_patients_filter.py` scanned 167,034 summaries and kept 104 keyword candidates. Raw files stay in gitignored `data/raw/`.
- Source of every passage: the original article's PMC JATS XML from E-utilities efetch (`data/tools/pmc_fetch.py`). The licence is read from the article's own `<permissions>`.
- `data/tools/build_published_candidates.py` writes `data/published/candidates/PUB-PMC7647841-1.json` and `PUB-PMC7861115-1.json`. Both are `source_review: pending` and `clinical_reviewed: false`, licensed CC BY 3.0. It refuses any excerpt that is not verbatim in its cited paragraph and any quote that falls outside its own passage.
- `docs/data/published-review.md` (generated by `data/tools/review_table.py`) holds the review table: passages, locators, claims, quotes and reviewer flags.
- The human reviewer records a review with `data/tools/record_source_review.py`, which copies the record to `data/published/reviewed/`. No agent runs it.
- `app/published.py` and `scripts/import_published.py` import only `data/published/reviewed/`, refuse pending records, refuse an ID without the `published-` prefix, and check that other collections are unchanged after the seed. A dry run against a temporary reviewed copy validated 2 cases and 10 passages. No Exasol import has run.
- `tests/test_published.py` (11 tests) covers:
  - the review gate;
  - cross-case passages;
  - edited text and quotes;
  - synthetic records excluded;
  - mode isolation;
  - a published encounter returning `PUB-PMC7647841-1` with its own passages and the article URL;
  - a published no-match.
- Checks: `pytest` 118 passed, 8 skipped (venv).
- Open: the published card shows the title and article link but has no licence or attribution field; a CC BY attribution line needs a `CaseCard` contract addition after review.

## Parallel-work handoff (13 Nov 2026)

Ownership has been revised (`AGENTS.md`). Luffy now owns the backend, source records and import, contracts and generated types, voice/session integration and Render. Zoro owns the presentational doctor/case/source-drawer UI, styling, frontend QA and Vercel preview preparation. The handoff, with allowed files and attribution fields, is in `docs/handoff/2026-11-13-parallel-work.md`. Before the push, a value-based secret scan checked tracked files and the full history. It found no keys, passwords, DSNs, tokens or demo codes, only the documented non-secret schema name, model name and model base URL.

## Attribution contract and revised candidates (13 Nov 2026)

- **Contract:** `CaseRecord.citation` (optional, omitted when null) and `CaseCard.attribution` (always serialized, `null` for synthetic) were added. Schema, OpenAPI, generated TS, the `CaseAttribution` alias, examples and mocks are all updated. Details are in `contracts/DECISIONS.md`. Zoro can consume it now; the exact types are in the handoff.
- **PMC7861115:** the duration feature was removed. "for two days" refers to the facial swelling, and a CaseFeature cannot tie a duration to one symptom or site. Exposure stays `topical_minoxidil_foam`.
- **Licence evidence** (`data/published/licence-checks.json`):
  - Both PMC XML artifacts state CC BY 3.0.
  - The Cureus publisher PDF for PMC7861115 states CC-BY 4.0.
  - The PMC7647841 publisher PDF could not be retrieved without a browser challenge, and I did not bypass it.
  - The records carry the XML licence, because every passage comes from the XML.
- **Unchanged:** passages, passage hashes and `source_version` are identical. Both records remain `pending` with `clinical_reviewed=false`. No review was recorded and nothing was imported.
- **Checks:**
  - `pytest`: 124 passed, 8 skipped.
  - Live Exasol and live Meta tests: 8 passed.
  - `export_openapi --check`: no drift.
  - `validate_pack.py`: PASS.
  - Web: `typecheck` and `lint` clean; Playwright in mock mode, 43 passed and 9 skipped.

## Symptom–site matching: structured-v2 (13 Nov 2026)

- **Bug fixed:** `structured-v1` intersected sites and symptoms independently, so scalp itching plus facial swelling qualified as facial itching.
- **Matching now:** `structured-v2` needs a shared `symptom_site` association (`"<symptom>@<site>"`), stated together on both sides with its own evidence.
  - **Patient side:** a clause-level link, or a direct answer to the site/symptom question when only one symptom or site was reported. The rules provider, Meta prompt and schema enum all carry the key, and the server validator rejects any association not stated together (`app/extraction/association.py`).
  - **Case side:** published records have explicit curated features; the importer requires them. Legacy synthetic records get passage-stated links, and their file and digest are untouched.
  - **Rules:** `docs/data/ranking-structured-v2.md`.
- **Stored searches:** `structured-v1` searches are read as stored. The next search attributes its changes to the rule change.
- **Contract:** no schema, OpenAPI or TS change; the semantic change is recorded in `contracts/DECISIONS.md`.
- **Brief:** "X on the Y" now appears only for stated associations.
- **Candidates:** rebuilt with explicit associations.
  - PMC7647841: rash@hands, rash@forearms, rash@legs, itching@fingers.
  - PMC7861115: itching@scalp, pain@face, swelling@face.
  - Passages, locators, hashes, licence and source versions are unchanged. Both remain pending; nothing was imported.
- **Checks:**
  - `pytest`: 136 passed, 8 skipped. New `tests/test_association.py` (12 tests).
  - Live Meta: 4 passed, including the new cross-pair test. Live Exasol: 5 passed.
  - `export_openapi --check`: no drift. `validate_pack.py`: PASS.
- **Status of other capabilities:** see "Current state" in `docs/handoff/2026-11-13-parallel-work.md`.

## Published import and live verification (14 Nov 2026)

- **Review:** Luffy recorded the source review himself at 23:08 UTC on 13 Nov, for `PUB-PMC7647841-1` and `PUB-PMC7861115-1`. Both have `clinical_reviewed=false`. The committed reviewed records have the same content Luffy produced. The only difference is that git stores them with LF line endings.
- **Import:** `import_published --collection-id published-derm-v1` returned `inserted`, and a repeat returned `unchanged`. Exasol now holds 2 cases and 10 passages for `published-derm-v1`, with every passage hash correct. `synthetic-demo-v1` is unchanged: 3 cases, 6 passages, and identical version and case hashes before and after.
- **Live API run** (Exasol, Meta, `COLLECTION_MODE=published`):
  - "My scalp has been itching for several days. I used minoxidil foam…" gave the fact `itching@scalp` and exactly one card, `PUB-PMC7861115-1`. The card's evidence is the patient quote "My scalp has been itching" plus the case quote "itchiness over the scalp". Full attribution came through, and the PMC and licence links return 200.
  - "My face is itchy" gave no card (`no_comparable_cases`). The minoxidil case was excluded as `no_shared_symptom`.
- **Browser run:** a temporary, uncommitted Playwright script drove the live web app on port 3000 and showed the same results. The source drawer and "Original article" link worked. Only the published collection was listed, and no case content appeared in the patient pane.
- **Fix:** snapshots in published mode carried the warning "Fictional demonstration cases — not published evidence". The warning now depends on the collection's mode.
- **Open:**
  - The patient's "I used minoxidil foam" is not captured. `exposure` accepts only new_product/no_new_product, so the brief omits it and the UI shows "Reported prior treatment: None reported".
  - Zoro's UI does not display attribution yet, and still has v1 no-match wording and a "Fictional demo only" note in published mode.

## Hackathon completion run (14 Nov 2026, 00:40–02:30 Berlin)

The checklist is `.kiro/specs/hackathon-completion/tasks.md`, and the demo handoff is `docs/demo/README.md`.

- **M1** (`49b67eb`):
  - named `product_use` facts;
  - live correction and skip endpoints;
  - patient "Summary for your doctor" review;
  - `apps/web/scripts/live-demo-check.mjs`.
- **M2** (`cecd9d0`, `5d181b4`): merged Zoro's S4 UI normally. Attribution is wired from the generated type, with same-site and "none captured" wording.
- **Live checks** (Exasol, Meta, published):
  - the browser check passes 29/29;
  - the restart check passes;
  - the voice webhook backend leg passes 10/10.
- **Blocked:** deployment (no account access; the Render service runs old `main`), and therefore the spoken voice loop. See `docs/deploy/runbook.md`.
- **Release checklist above:**
  - Skip/Correct: done.
  - Patient summary review: done.
  - Published collection with live retrieval: done.
  - Deployment and full voice loop: still open (blocked).
  - Rehearsal: the script is ready.
