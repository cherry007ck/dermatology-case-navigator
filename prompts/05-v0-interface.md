# Optional v0 interface prompt — Luffy only

Use after importing the existing repository/web app into v0. Keep changes on Luffy's branch, then review in Kiro. This is optional; the product must not depend on v0 being available.

```text
Improve the presentational UI of the existing Dermatology Case Navigator in apps/web. This is a two-person hackathon project. Preserve its Next.js App Router/TypeScript/Tailwind/shadcn stack, current routes, typed API adapter, generated types, event handling and tests. Do not create a new backend, change response fields, edit services/api or contracts, expose credentials, replace package locks unnecessarily, or create a separate competing project.

Use a calm modular/bento doctor workspace with off-white background, white cards, dark ink typography and teal accent. Patient intake stays sequential and accessible. Desktop doctor grid: brief 7/12 columns, case comparison 5/12; below that, timeline/change history and doctor-clarification panels; separate full-width clinician-note area. At phone widths stack in task order with no horizontal overflow. Use clear spacing, subtle borders, restrained corners, visible focus and readable body text.

Primary interactions: start/stop voice, type instead, one question at a time, skip/idk, review/edit/confirm, click claim to inspect exact source, compare actual before/after searches, save separate clinician note. Preserve unknown, conflicting, loading, error, no-match, stale-revision and reconnect states.

Keep prominent source/storage/extractor mode labels. Synthetic cards must say “Fictional demonstration case — not published evidence” and have no fake article links. Patient view contains no retrieved diagnoses or past-case treatment advice. No diagnosis probabilities, match percentages, fabricated statistics, medical-image analysis, excessive animation or decorative charts.

Use existing fixtures only. Produce reviewable presentational changes and summarize touched files. Functional integration remains Kiro's responsibility. If the repository cannot be imported cleanly within twenty minutes, stop and return a design description rather than rebuilding the app elsewhere.
```
