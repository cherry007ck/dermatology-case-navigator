# Requirements — Dermatology Case Navigator

Derived from `docs/02-product-and-architecture.md`, `docs/04-data-and-evidence.md` and
`docs/06-ui-and-demo.md`. Acceptance IDs (A01–A20) refer to the matrix in `docs/06-ui-and-demo.md`.

## Scope boundary

Consultation preparation and evidence navigation for fictional encounters only. The system never
diagnoses, recommends treatment, analyses images, tells the patient what published clinicians tried,
or claims clinical review that did not happen.

## R1 Patient intake (voice and text)
- R1.1 WHEN a fictional patient types or speaks THEN the system SHALL store the exact text as a patient turn and increment the patient revision once. (A03)
- R1.2 Voice text SHALL be labelled "Voice transcript — please review"; partial ASR events SHALL NOT create turns. (A11)
- R1.3 The patient view SHALL NOT show case content, diagnoses, actions or rankings.

## R2 Supported facts
- R2.1 Every patient fact SHALL cite an exact quote from an active patient turn. (A03)
- R2.2 Unknown, negated, conflicting and unmentioned SHALL stay distinct; "cream" SHALL NOT become a named drug. (A04)

## R3 Clarifications
- R3.1 The system SHALL ask at most two neutral questions: one intake gap, one supported case difference. (A05)
- R3.2 "I don't know" SHALL record unknown; Skip SHALL record skipped; neither is a negative fact.

## R4 Comparison
- R4.1 Ranking SHALL be deterministic `structured-v1` over one collection kind; synthetic and published never mix. (A15, A20)
- R4.2 Each search SHALL be an immutable version with inputs, scores, exclusions and real before/after changes. (A06)
- R4.3 With no qualifying case the brief SHALL still be useful and the explanation collection-limited. (A07)
- R4.4 Case statements without valid same-case passage evidence SHALL be withheld or flagged. (A08)

## R5 Confirmation and handoff
- R5.1 The doctor workspace SHALL show the brief only when `state=confirmed` and `confirmed_revision=revision`.
- R5.2 New patient content or a correction SHALL invalidate confirmation and stale comparisons. (A09, A11)
- R5.3 Stale-revision writes SHALL be rejected with 409; repeated request IDs SHALL not duplicate. (A10)

## R6 Doctor workspace
- R6.1 Modular grid: brief, up to three cards or no-match, changes, clarifications, separate clinician note. (A17, A18)
- R6.2 Clicking a supported claim SHALL open a source drawer with exact quote and origin; Escape returns focus. (A18)
- R6.3 Synthetic cards SHALL say "Fictional demonstration case — not published evidence" and have no fabricated citation.

## R7 Modes, security and failure honesty
- R7.1 Storage, extractor, collection and API/voice modes SHALL be visible and report actual behaviour.
- R7.2 Session bearer tokens SHALL be unpredictable, stored hashed, tab-scoped; voice webhooks require tool secret AND binding. (A13)
- R7.3 No provider keys in browser bundles, logs, screenshots or git. (A14)
- R7.4 Provider/DB failures SHALL show honest, retryable errors, never a success-shaped empty brief. (A19)
- R7.5 Persistence SHALL be Exasol in live mode; history reloads after restart. (A16)
