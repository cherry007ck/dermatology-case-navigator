# Hackathon completion: requirements

Deck due Sat 14 Nov 2026, 12:00 Europe/Berlin. Feature freeze 09:30. The baseline is `integration/local-backend` at `ada412e`; it is verified, not rebuilt.

## Product boundary

- **Purpose:** consultation preparation and published-evidence navigation only.
- **Not included:** diagnosis, treatment recommendation, image analysis, and any TK-Doc or medical-record integration claim.
- **Data:** fictional patients only.
- **Published cases:** `published-derm-v1` holds 2 cases, source-reviewed by Luffy, not clinically reviewed.

## R1 Patient information and review
1. **Product use.** Named product or medication use the patient reports is kept as supported context (`product_use`).
   - It stays separate from categorical product-change history (`exposure`).
   - It is never treated as treatment for the complaint unless the patient states that purpose.
   - Several products and explicit denial are supported.
   - Cause, dose, timing and response are never inferred.
2. **Correction.** The correction endpoint appends a superseding turn and keeps the original.
   - The revision increments, confirmation is cleared, and facts are recomputed from active turns only.
   - Requests are idempotent and the question budget is not reset.
3. **Skip.** The skip endpoint marks the pending question `skipped`, never a negative fact. It increments the revision, clears confirmation and stays idempotent.
4. **Patient review.** Before confirmation the patient sees the current supported brief with quotes, next to their original statements and correction controls. Confirmation applies to exactly the reviewed revision. Case content and clinician notes never appear in the patient view.

## R2 UI integration
1. **Zoro's work.** Zoro's `zoro/s4-case-ui-attribution` is merged normally (no force, no overwrite).
2. **Doctor workspace.** It shows:
   - visible attribution and licence;
   - "same site" comparison wording;
   - empty sections that never imply denial;
   - distinct labels for fictional and published cases;
   - loading, retry, no-match and failure states.
3. **Accessibility.** The UI works by keyboard and at desktop and 390 px widths.

## R3 Deployment
1. **Reuse.** Use the existing Render service and Vercel project, and verify the deployed commit.
2. **Configuration.** Secrets stay server-side, CORS and TLS are set correctly, and demo access is required.
3. **Explicit modes.** Exasol and Meta modes are explicit, with no silent fallback.
4. **Blocked access.** If account access is missing, the item is recorded as blocked.

## R4 Voice loop
The ElevenLabs `advance_intake` webhook runs against the verified public backend, and this chain is proven: speech, stored turn, backend advance, approved question spoken, stored answer, updated review. Transcript capture alone does not count.

## R5 Final verification and handoff
Verify the ten demo checks from the task brief against the real application. Provide screenshots, a demo script, start instructions, a verified-features and limitations note, and backup recording steps.
