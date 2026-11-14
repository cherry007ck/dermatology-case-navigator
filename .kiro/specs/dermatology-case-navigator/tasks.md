# Tasks

Both lanes are tracked here; each developer executes only their own lane for the current sprint.
Mark a box only when its acceptance evidence exists (checks actually run). Sprint prompts:
`prompts/00-bootstrap.md`, `prompts/02-luffy-sprints.md`, `prompts/03-zoro-sprints.md`.

## S0 — shared foundation

### Luffy (bootstrap)
- [x] Git repo connected to `exasol-sh/dermatology-case-navigator`; planning commit on `main`; branch `luffy/s0-bootstrap`
- [x] Root `.gitignore` / `.gitattributes`; env examples with blank secrets
- [x] `apps/web`: Next.js 16 + TS + Tailwind + shadcn/ui; landing, patient and doctor route shells; mode banners; typed intake against fixtures
- [x] `services/api`: FastAPI `/health`, `/docs`, Pydantic DTOs, memory stub repository, frozen `IntakeService` seam
- [x] Registered voice router stub in `app/voice` (no ElevenLabs call)
- [x] `contracts/openapi.json`, generated TS types, shared HTTP examples, `contracts/DECISIONS.md`
- [x] CI: `web-checks`, `api-checks` (to verify on GitHub after push)
- [x] README run commands, `docs/toolchain.md`, `docs/team.md` (usernames TODO)
- [ ] CODEOWNERS — blocked on confirmed GitHub usernames
- [ ] S0 PR reviewed by Zoro and merged

### Zoro (parallel, no app code)
- [ ] Exasol provisioned, TLS `SELECT 1` and tiny write/read verified (or blocker recorded)
- [ ] Render account ready; Gemini access attempted
- [ ] Bounded real-source search (≤ 60 min) or synthetic-only decision
- [ ] Review `contracts/DECISIONS.md` and the S0 PR

## S1 — independent vertical slices
### Luffy
- [x] Responsive patient/doctor UI, source drawer foundation, typed client against the local API stub
- [x] Private ElevenLabs agent; Next.js `/api/voice-session` signed-URL route; finalized transcript capture (live browser test passed; persistence is S2)
- [ ] S1 PR reviewed by Zoro and merged
### Zoro
- [ ] Exasol repositories, session auth, turn append/revision/idempotency, collections, fixture extractor, seed, hosted backend

## S2 — core behaviour
### Luffy
- [x] Transcript normalization/dedup/serialized queue persisted via `/turns` (live persistence test passed)
- [x] Voice bindings + authenticated `/v1/voice/advance` adapter (mocked/stub tests only)
- [x] Source drawer; before/after comparison UI from stored search versions
- [ ] Full live voice loop with `advance_intake` tool and real prompt — blocked on Render-hosted combined backend and real extractor
### Zoro
- [ ] Gemini extraction + validation; structured-v1 ranking; question policy; versioned search and brief

## G1 — integration (record known-good commit before sleep)

## S3 — reliability
### Luffy
- [x] Confirmation (stop voice, flush, current-revision check), correction/history UI, invalidation states
- [x] Unknown/skipped/conflict/retry/offline/reconnect states; separate clinician-note panel
- [x] Playwright: review, late words, correction, skip, retry, offline, notes, keyboard, 390px (skip/correction via labelled mock)
- [ ] S3 PR after S2 merge; backend skip/correction/recompute verified live (Zoro dependency)
### Zoro
- [ ] Correction invalidation, current-revision confirmation, idempotency, no-match, evidence rejection, notes, restart read-back

## S4 — deployment and polish
- [ ] Luffy: Vercel release, origin allowlists, source review, demo flow
- [ ] Zoro: Render release, Exasol connectivity, seed freeze, recovery checks

## S5 — freeze and rehearse
- [ ] Both: smoke checks, rehearsal, `hackathon-demo-v1` tag
