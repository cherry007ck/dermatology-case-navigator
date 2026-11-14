# Sixteen-hour execution plan

Work estimates are timeboxes, not a promise that AI removes account, integration or review work. Both developers work concurrently. Total capacity is 32 person-hours; the timetable allocates 16 hours per person including reviews and rehearsal.

## Clock

| Stage | Active hours | Example elapsed hours | Luffy | Zoro | Required gate |
|---|---:|---:|---|---|---|
| S0 — shared foundation | 0–1.5 | 0–1.5 | Organization, repo, bootstrap, stub web/API, web CI | Exasol access, data search, backend-host signup, review contract | Both can run same skeleton; DTOs frozen |
| S1 — independent vertical slices | 1.5–4 | 1.5–4 | Patient/doctor UI on fixtures, ElevenLabs private-agent connection | Live Exasol schema/seed, real session API, typed intake, hosted health | UI text path reaches backend; DB write/read verified |
| S2 — core behavior | 4–7 | 4–7 | Voice transcript sync + secure webhook adapter; source drawer and comparison UI | Validated extraction, ranking, question policy, versioned search and brief | One answer changes a comparison with traceable reasons |
| G1 — integration | 7–8 | 7–8 | Test real voice from browser; review on-screen sources | Test hosted backend/DB; fix service contract defects | Combined main works; save known-good commit |
| Sleep | — | 8–16 | Sleep | Sleep | Eight hours reserved |
| S3 — reliability | 8–11 | 16–19 | Confirmation, correction UI, retry/skip/offline states, keyboard/mobile, browser checks | Confirmation/version guards, idempotency, no-match, evidence rejection tests, separate note | Main and no-match scenarios pass end to end |
| S4 — deployment and polish | 11–13.5 | 19–21.5 | Vercel release, v0 polish if safe, source review, demo flow | Render release, Exasol connectivity, seed freeze, reproducibility and recovery checks | Deployed combined build works; local fallback ready |
| S5 — freeze and rehearse | 13.5–16 | 21.5–24 | Present patient/doctor story, record backup, screenshots/submission | Run smoke checks, reset demo, verify actual mode labels, README limitations | Tag release; rehearsed three-minute demo |

Sleep can move to suit the event schedule, but keep the eight-hour allowance and a working integration before it. No new feature starts after active hour 13.5. A blocker exceeding 30 focused minutes triggers the recovery plan, not unbounded debugging.

## S0 completion checklist

- Organization and repository exist, both developers can push feature branches.
- Planning files and steering rules are in repo root; each Kiro chat asks identity.
- Luffy creates Next.js/TypeScript app under `apps/web` and FastAPI scaffold under `services/api`; **Zoro does not duplicate this**.
- Bootstrap registers a voice router stub and a stable `IntakeService`; both sides have documented import paths.
- Domain fixture loads and schema validates; mock snapshots use same DTOs as backend.
- Typed UI demo runs without provider accounts; `/health` and `/docs` work.
- Web and API check workflows execute; selected versions and run commands recorded.
- Contract changes are discussed now, then frozen. S0 PR reviewed by Zoro and merged.

Zoro's parallel non-code checklist: database provisioned or explicit blocker recorded; Render account ready; Gemini access attempted; source search timeboxed; candidate metadata saved for later import. If provisioning is slow, that does not delay Luffy's mock UI.

## S1 completion checklist

Luffy: modular patient and doctor layouts; source drawer placeholder; typed input; visible mode banners; connect/disconnect private voice agent using signed server route. No fabricated “live” response from fixture mode.

Zoro: Exasol repositories; session bearer verification; turn append, revision and idempotency foundation; collection list; deterministic fixture extractor; seed/import script; first hosted backend deployment; exported OpenAPI and mock responses. Map fixture data through real endpoints rather than embedding scenario-specific responses in production logic.

Integrate after S1: replace the UI's mock base URL with the real API. Create a synthetic encounter, append typed text, reload it from Exasol. Connect ElevenLabs independently even if its next-question webhook is still stubbed. Confirm callback/transcript shapes before S2.

## S2 completion checklist

Luffy: raw SDK events normalized through one adapter; finalized-turn queue and deduplication; private voice connection; voice bindings and authenticated webhook routes; agent speaks only backend-approved questions; brief/cards poll; clickable source drawer; before/after change UI.

Zoro: Gemini candidate extraction plus strict validation; deterministic ranking; question templates/budget; provenance checks; stored search snapshots; fact-derived brief; actual eligible case cards; explicit no-match reasons. Supply fixtures and service tests for Luffy's voice routes.

G1 acceptance: start from an empty session, hear the first question, answer, see the new facts and comparison change, then stop voice and review the final statement. If live voice is blocked, typed intake must still pass. Merge both PRs and record the known-good commit before sleep. A missing webhook is a visible incomplete feature, not a reason to claim the full voice loop works.

## S3 completion checklist

Luffy: confirm screen; immutable original/correction history view; skip and unknown paths; microphone denied; API retry; reconnect; no-match and conflict states; clinician note panel; 390px patient view and readable desktop doctor grid.

Zoro: correction invalidation, current-revision confirmation, duplicate operation handling, stale-write rejection, late voice-turn handling, no unsupported quote/cross-case reference, notes kept separate, read-back persisted snapshots after restart. Backend binds every source reference to its correct patient session or case.

Integrate S3: live or labelled-fallback end-to-end run for main, no-match, correction and validation rejection. No production provider credentials are required for CI; a separately run authenticated live smoke check verifies real integrations.

## S4 completion checklist

Both: deploy exact same `main` commit; validate domains/CORS/agent allowlist; rehearse a second synthetic patient; check Exasol-backed history after API restart; freeze data and model/config versions. Luffy checks real-source cards if any; Zoro records actual loaded counts. Remove placeholders that imply real medical evidence.

## S5 completion checklist

No redesign, provider switch, package upgrade, native app or dataset expansion. Both rehearse from a reset encounter. Submit working link/repo as required, actual capability list, source attribution and limitations. Tag `hackathon-demo-v1` after smoke checks. Keep credentials out of presentation materials.

## File ownership rules that avoid conflicts

> **Superseded on 13 Nov 2026** by the revised ownership in `AGENTS.md` and `docs/handoff/2026-11-13-parallel-work.md`. Luffy now owns the backend, source records and import, contracts and generated types, voice/session integration and Render. Zoro owns the presentational doctor/case/source-drawer UI, styling, frontend QA and Vercel preview preparation. The table below is the original plan.

| Area | Owner | Other developer's approach |
|---|---|---|
| All React/UI, web dependencies and Vercel | Luffy | Request needed response fields via contract issue |
| ElevenLabs agent and `app/voice` Python adapter | Luffy | Supply service methods; do not rewrite adapter |
| API facade/models/routes outside voice, Exasol, extraction, ranking | Zoro | Call frozen service and typed HTTP client |
| Contract files and generated OpenAPI | Zoro | Regenerate frontend types after a reviewed change |
| Fixture/case imports and source metadata | Zoro | Luffy reviews quoted passages; passes notes to Zoro |
| `docs/status/luffy.md` / `zoro.md` | Each their own | Read but do not overwrite |
| Root docs, CI registration, shared config | Frozen after S0 | Agree owner for a small change before editing |

Do not keep one enormous Luffy branch and one enormous Zoro branch for the entire event. Every sprint starts from integrated `main`. Mocks make coding independent; checkpoint merges make the product coherent.
