# Zoro's implementation prompts

Copy the prompt for the current sprint only. Start a new chat with `01-start-session.md`.

## S0 — setup while Luffy creates boilerplate (1.5 hours)

```text
I am Zoro. Execute only the parallel setup tasks for S0; Luffy is the sole application bootstrap owner. Read START-HERE.md and docs/01-setup-and-github.md, 03-api-contract.md and 04-data-and-evidence.md.

Help me provision Exasol through event access or SaaS, store credentials locally/server-side, verify TLS SELECT 1 and a tiny write/read test, and record endpoint readiness without exposing secrets. Help me create Render and Gemini access as needed; humans complete account verification/payment decisions. Spend at most sixty focused minutes finding a small real dermatology source subset through official PMC-Patients links. If no usable source collection exists, choose the supplied labelled synthetic mode, not fabricated published citations.

Review the API/domain contract and give Luffy any minimal required changes before S0 freeze. Do not create apps/web, duplicate FastAPI boilerplate, edit Luffy's work or start a second repository. Keep temporary setup notes outside conflicting app files until bootstrap merges, then update docs/status/zoro.md and docs/data source notes in my own branch. Never paste secrets into chat, git or source notes.

Review Luffy's S0 PR: confirm DTO/fixture consistency, stable IntakeService seam, registered voice stub, run commands and CI. Then pull merged main to start S1.
```

## S1 — Exasol-backed API and contract (2.5 hours)

```text
I am Zoro. Implement S1 on zoro/s1-exasol-api from merged S0. Read AGENTS.md and docs/02-product-and-architecture.md, 03-api-contract.md and 04-data-and-evidence.md. Do not edit apps/web or app/voice.

Implement the frozen Pydantic DTOs/service facade, session token authentication, demo access-code gate, exact CORS origins, body/rate limits, typed-turn append, active revision and idempotent operations. Supply memory repository for tests and real Exasol repository for live mode. Build schema initialization and repeatable seed scripts without destructive resets. Persist the small case collection, immutable passages and encounter snapshots; use queryable IDs and validated serialized JSON where that saves time.

Seed supplied synthetic cases only after internal quote/reference consistency checks. Real data remains a separate collection with actual reviewed provenance. Expose actual counts and source/storage/extractor modes. Use a deterministic fixture extractor for the documented phrases as the temporary provider; label it. No hardcoded scenario-result shortcuts.

Export OpenAPI and serialized shared examples. Provide Luffy exact health/session/turn responses and the service injection/import path. Deploy a stub/working API to Render early and verify Exasol connectivity from that host; do not assume laptop access proves hosted access.

Run focused repository/auth/turn/revision/idempotency/schema tests and a live Exasol write/read check if available. Update docs/status/zoro.md with what worked, actual data count and integration handoff. Prepare PR and stop for S1 integration.
```

## S2 — validated facts, question policy and evidence (3 hours)

```text
I am Zoro. Implement S2 on zoro/s2-evidence-pipeline from integrated main. Read the exact extraction/question/ranking rules in docs/04-data-and-evidence.md. Use app/intake_service.py as the only facade for Luffy's voice adapter. Do not edit their webhook or React state.

Create the Gemini structured-output candidate extractor from prompts/07-extraction-and-source-prompts.md, select and record an available supported model ID, validate through Pydantic, and bind every quote to an active patient turn. Use only approved normalization aliases and preserve negation, unknowns and conflicts. A quote substring is necessary but not proof of meaning. Render briefs from validated facts/templates, not a second unrestricted summary model.

Implement deterministic structured-v1 ranking from Exasol-reviewed features: eligible shared symptom AND site, explicit conflict gates, documented weights/ties, maximum three cards. Snapshot complete inputs, collection/case versions, score components, exclusions and actual before/after changes. Filter unsupported case statements and validate passage ownership.

Implement at most two neutral questions, one intake gap and one eligible case difference. Record asked/answer/unknown/skipped states and reason/evidence. In published mode do not use a clinically unreviewed case-difference question; synthetic mode can demonstrate the mechanics with visible labels. No useful case still yields a brief. Use no diagnosis/treatment selection logic.

Give Luffy fixture outputs for ask, ready, no-match, conflicting detail, provider failure and invalid evidence, plus the stable advance service. Test synthetic ranking before and after a new-soap answer without branching on scenario IDs. Run pipeline tests, update status and PR; stop for G1 integration.
```

## S3 — correctness and persistence (3 hours)

```text
I am Zoro. Implement S3 on zoro/s3-correctness. Focus on acceptance A03–A10, A12–A13, A15–A17, A19–A20 in docs/06-ui-and-demo.md. Do not expand infrastructure or retrieval scope.

Finish correction/supersedes behavior, current-revision confirmation, skip/idk semantics and separate clinician-note storage. Any new patient content invalidates confirmation and stale comparisons. Serialize per-session operations; enforce expected_revision and persisted request-id/input-hash results. Do not assume the database silently enforces all concurrent uniqueness behavior for us. Persist a coherent snapshot only after validation; keep slow provider calls outside database transactions.

Test a real quote assigned to the wrong case, missing passage, unsupported cream normalization, duplicate callback, old revision, explicit conflict, unmentioned-versus-denied feature, synthetic/published isolation, late content after confirmation and no-match reason. Never treat a provider timeout as a successful empty clinical extraction.

Verify encounter/search read-back after API restart using Exasol, and deterministic replay of an immutable search version. Work with Luffy to test webhook-before-transcript while keeping their module owned by them. Regenerate OpenAPI only for agreed contract corrections; surface any necessary change explicitly.

Run focused tests and live smoke where available. Update only my status and PR; give Luffy an exact integration handoff and stop for S3 merge.
```

## S4 — final backend/data deployment (2.5 hours)

```text
I am Zoro. Execute S4 on zoro/s4-release-api. Release the integrated API to Render following docs/07-release-and-recovery.md. Verify one worker, health, TLS, Exasol egress/network access, final frontend CORS, shared voice-tool secret and correct environment modes. Initialize/seed using a trusted script, never a public admin endpoint. Do not expose provider errors or raw transcripts in logs.

Freeze the actual reviewed collection and record version/hash and loaded counts. Have Luffy independently inspect all real-source claims shown on screen; remove unverified statements. If real data is unavailable, keep synthetic labels and ensure published mode honestly has no evidence. No last-minute bulk ingest.

Run release smoke, revision guards, source validation, saved search replay and backend-restart checks. Supply local fallback run commands and explain what breaks/reconnects when memory voice bindings expire. Update README with actual tests/limitations, status and release PR. Stop for joint release review.
```

## S5 — release verification and demo support (2.5 hours)

```text
I am Zoro. Execute S5 with new features frozen. Run prompts/04-integration-and-release.md against the exact integrated commit. Prepare resettable fictional demo encounters and a safe validation-rejection example. Ensure there is no seed/admin action exposed publicly. Support Luffy's three-minute rehearsal with actual mode, provenance and Exasol-history checks.

Fix only release blockers inside my ownership; report tests actually run. Keep a known-good local fallback and record collection/model/ranking versions. Review Luffy's release PR, coordinate the hackathon-demo-v1 tag after both approvals and smoke checks, and record final limitations. Do not claim clinical validation, real patient testing or measured time savings.
```
