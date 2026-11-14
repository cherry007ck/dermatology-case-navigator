# Hackathon completion: design (grounded in existing code)

## Backend (`services/api`)
- **`product_use` fact key** (`app/extraction/vocabulary.py`, `rules.py`, `meta.py`, `evidence/validate.py`):
  - multi-value, negatable and raw-valued;
  - the quote must contain a use verb (used, using, applied, tried, started, take, took and similar);
  - the value must contain a non-generic word, so "cream" or "new hand soap" do not count;
  - it is rendered in the brief timeline as "Patient mentions using …" and does not affect ranking.
- **Correction** (`service.correct_turn`):
  - appends `Turn(origin="correction", supersedes_turn_id=…)`, inheriting the original's `reply_to_question_id`;
  - the server derives the turn ID from `request_id`;
  - the revision increments, `confirmed_revision` is cleared, and the state becomes `intake`;
  - the operation is stored for replay;
  - errors: unknown turn gives 404 `TURN_NOT_FOUND`; an agent turn or already-superseded turn gives 409 `TURN_NOT_CORRECTABLE`.
- **Skip** (`service.skip_question`):
  - the question must have status `asked`, otherwise 409 `QUESTION_NOT_PENDING`;
  - it becomes `skipped`, the revision increments and confirmation is cleared;
  - the pipeline already keeps skipped questions and never re-asks them;
  - the brief lists skipped questions as `missing`.
- **No storage change:** `TURNS.SUPERSEDES_TURN_ID` and question JSON already exist.

## Web (`apps/web`)
- **Patient review:** `components/patient/brief-review.tsx` shows the brief summary, timeline, product-use and prior-treatment items, and the unresolved items, all with quotes. It renders only when `brief.patient_revision === revision`, and never shows case IDs, cards or clinician notes.
- **Zoro's merge:** `zoro/s4-case-ui-attribution` brings the case card, attribution, drawer and home page. After the merge, fix the wording: "same site" no-match text, "None captured" for empty sections, and published-mode note text.

## Deployment
Use the existing Render and Vercel projects, verified first. If no access exists, use the documented `docs/voice/s2-handoff.md` settings with one worker.

## Voice
Use the existing private agent, signed URL route and `/v1/voice/advance` webhook (X-Tool-Secret plus `secret__voice_binding`). Configuring the agent tool needs the public backend URL.
