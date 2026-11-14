# Luffy's implementation prompts

Copy the prompt for the current sprint only. Read `01-start-session.md` first in a new chat. S0 is in `00-bootstrap.md`.

## S1 — patient/doctor interface and private voice connection (2.5 hours)

```text
I am Luffy. Implement S1 only, from the verified shared main, on luffy/s1-interface-voice. Read AGENTS.md and docs/03-api-contract.md, 05-sprints-and-ownership.md and 06-ui-and-demo.md. Stay within my owned paths.

Build the responsive modular patient and doctor UI using shared fixture HTTP responses. Create one typed API adapter with configurable real/mock transport; do not scatter fixture logic through components. Provide collection/access-code entry, session creation, typed patient input, transcript view, current brief, case-card shell, no-match state and source drawer foundation. Never put case diagnoses/actions in the patient view. Display actual storage/extractor/source mode.

Configure a private ElevenLabs agent in the dashboard with my human assistance for account/key entry. Create the server-only Next.js voice-session route and backend voice-binding module using the frozen service seam. Initially demonstrate a private browser voice connection and finalized transcript callback capture; the next-question webhook may remain an explicitly reported S2 dependency. Use installed SDK types and current official docs, not assumed callback fields. Keep signed WebSocket URLs and connection mode consistent. Never expose the ElevenLabs API key.

Create frontend checks/fixtures for rendering and microphone-denied/error states. Connect typed session creation/turn persistence to Zoro's deployed or local API as soon as available. If backend is not ready, finish the UI against mocks and report the exact expected routes; do not rewrite their backend.

Pass build/typecheck/lint and the focused UI checks. Update docs/status/luffy.md, prepare a PR and integration instructions. State separately whether voice connection, transcript delivery and backend persistence have actually worked. Stop for S1 merge.
```

## S2 — live question loop and evidence interactions (3 hours)

```text
I am Luffy. Implement S2 on luffy/s2-voice-evidence from integrated main. Read the frozen voice sequence in docs/03-api-contract.md. Own apps/web and app/voice only; reuse Zoro's IntakeService.

Implement finalized transcript normalization, stable turn IDs, deduplication and a serialized write queue. Preserve exact ASR text and label it as a transcript requiring review. Register patient versus agent role correctly; partial ASR updates must not become duplicate patient turns. Test actual installed SDK event shapes.

Implement short-lived scoped voice bindings and /v1/voice/advance in the voice module. Require static tool secret AND binding token, resolve the session from the binding, bound transcript waiting/retry, and call shared advance with the newest persisted patient revision. Repeated calls cannot issue duplicate questions. Do not accept authoritative transcript text/session identity from the language model. Store binding tokens safely and handle expiry/restart as reconnect.

Configure the ElevenLabs server tool and system prompt using prompts/06-elevenlabs-system.md. It returns only the approved question or review instruction. Never send case treatments/diagnoses to the voice model. Browser polls state to render the question/brief and links later patient answers safely to the pending question. Handle webhook-before-transcript and answer-before-poll races explicitly.

Finish source drawer with exact quote and originating source, case shared/different features, actions/outcomes with correct synthetic labels, and actual before/after search changes. A missing evidence reference is an error/withheld claim, not a decorative citation badge.

Test typed flow and one real voice round trip: user speech -> stored patient turn -> backend-approved question -> spoken question -> answer -> changed snapshot. If credentials/network block live verification, keep typed path working and say exactly which link is unverified. Run focused voice-auth/race tests and web checks. Update my status and PR; stop for G1 integration.
```

## S3 — review, corrections and failure states (3 hours)

```text
I am Luffy. Implement S3 on luffy/s3-review-reliability. Read docs/06-ui-and-demo.md acceptance A05, A09, A11–A14 and A17–A19.

Implement final patient review and explicit confirmation. Stop capture and flush transcript writes, refresh/recompute the current revision, then enable Confirm. Doctor workspace may show a final brief only when confirmed_revision equals revision. A late voice turn or correction invalidates confirmation and shows a clear return-to-review action.

Implement patient correction using append/supersedes history, no destructive replacement. Show unknown versus skipped versus conflicting details. Wire separate clinician notes to their endpoint; never merge them into patient facts. Add visible microphone-denied, reconnect, transcript-sync timeout, provider error, stale comparison and DB-unavailable states with appropriate retry or typed fallback.

Use a small Playwright suite for main typed intake -> confirm -> doctor, correction invalidation and no-match. Test keyboard focus for source drawer and 390px patient layout. Reuse the contract fixtures; don't build a fake alternate API just to make tests pass. Source-review Zoro's on-screen real passages if present; otherwise verify fictional labels and no fake citations. Hand reviewed notes to Zoro instead of editing their case records silently.

Run focused browser/web/voice tests, update my status and PR. Report what passed live versus mocked. Stop for S3 integration.
```

## S4 — frontend deployment and restrained polish (2.5 hours)

```text
I am Luffy. Implement S4 on luffy/s4-deploy-polish. Deploy apps/web to Vercel from integrated main, set server-only credentials, exact backend URL and origin allowlists with Zoro. Verify private voice and backend calls from the actual HTTPS URL, not just localhost. Do not publish any real patient data or expose provider keys.

Use prompts/05-v0-interface.md only if v0 import is quick and the core product already passes. Keep the same repository and API adapter; review presentational changes in my branch. Timebox v0 setup to twenty minutes. Improve readability, spacing and responsive stacking before animation. Complete remaining source review and accurate synthetic/published labels.

Run the main and no-match demos against the deployed backend; verify a correction and saved clinician note. Check browser bundle/network for secrets. Coordinate a local fallback using the same commit and documented commands. Update deployment URL, actual check results and status. Prepare release PR and stop for joint review.
```

## S5 — presentation freeze (2.5 hours)

```text
I am Luffy. Execute S5; freeze new features. Use docs/06-ui-and-demo.md and prompts/04-integration-and-release.md. Rehearse the three-minute demo from reset fictional encounters with Zoro, verify all labels and source drawers, prepare submission screenshots and a clearly labelled backup recording if useful. Show only capabilities actually verified; a prerecorded or fixture flow must never be presented as live.

Fix only release-blocking issues inside my ownership. Re-run checks only where fixes require them. Record final frontend commit, URL, voice mode and unresolved limitations in my status. Review Zoro's release changes, then coordinate the known-good release tag and submission. Do not upgrade dependencies, redesign or add features.
```
