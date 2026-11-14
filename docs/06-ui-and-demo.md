# Interface, demonstration and acceptance

## Design direction

Use a contemporary modular/bento grid as a design choice, not a claim that a particular layout is universally trendy in 2026. Keep the patient flow calm and sequential; modular cards are most useful in the doctor workspace. Avoid a wall of equal-sized cards that hides the main task.

Visual tokens: off-white `#F7F8FA`, white cards, ink `#14232B`, teal `#0F766E`, muted slate text, amber warnings, red only for errors/conflicts. Use accessible contrast, visible focus, approximately 16px body type, 12/16/24px spacing steps, 12–16px card corners and subtle borders. Use a system sans or a locally bundled font. No animated gradients, skin-diagnosis imagery or invented medical graphs.

## Routes and grid

`/` shows product title, fixed fictional-demo notice, collection/source mode selector, demo access-code entry and “Start intake.” Team name appears in the footer; do not imply official Exasol ownership of the product.

`/intake/[session_id]`:

```text
+---------------------------------------------------------------+
| Patient intake      [Synthetic / Published] [Storage / Voice]   |
+------------------------------------+--------------------------+
| Tell us about your concern         | Your story so far        |
| [Start voice] [Stop] [Type instead] | Reviewable patient text  |
| Listening / Thinking / Disconnected| Corrections visible      |
|                                    | Missing details          |
| One clarification at a time        |                          |
| [Answer] [I don't know] [Skip]      |                          |
+------------------------------------+--------------------------+
| [Review statement] -> [Confirm and open doctor brief]          |
+---------------------------------------------------------------+
```

Never show retrieved diagnoses, past case treatments or similarity rankings in the patient pane. “I don't know” is a real user answer; Skip is a UI action. Voice transcript is editable and labelled as transcription. Confirm is disabled while transcript writes or reprocessing are pending.

`/doctor/[session_id]` on desktop uses a 12-column grid:

- Header: confirmed revision, collection kind, actual stored modes and last update.
- Left 7 columns: concise brief, patient quote anchors, timeline, reported prior treatment and unanswered details.
- Right 5 columns: up to three comparable case cards, or a full no-match explanation.
- Next row 7 columns: before/after comparison with actual appearance/removal/rank reasons.
- Next row 5 columns: a short “For the doctor to clarify” panel.
- Full-width footer panel: separately labelled clinician assessment/note and save action.

Clicking a supported claim opens a side drawer showing exact quote, originating turn or article passage, source type, review status, and original article link when real. Keyboard Escape closes; focus returns to the clicked item. On narrow screens cards stack in reading order and the drawer becomes a full-width dialog. Cases do not become swipe-only content.

Case cards show shared features, important differences, documented actions, outcomes and links. Do not use diagnosis probabilities, match percentages or green “recommended treatment” badges. Show “not reported” only when the reviewed passages lack the information. Synthetic case titles and banners remain visibly fictional even in screenshots.

## Required UI states

Idle, microphone request, listening, processing, question awaiting answer, skipped/unknown answer, no match, missing information, conflicting information, provider error with retry, Exasol unavailable, memory/mock mode, synthetic mode, transcript correction, stale comparison, awaiting confirmation, confirmed revision, late transcript invalidation, clinician note saved and unsaved. Do not bury error state inside a source drawer.

## Three-minute demonstration

Use fictional actors and statements. If only synthetic data is available, open with “These are fictional cases demonstrating the workflow; we have not validated clinical matching.” If real sources are available, distinguish their source review from clinical validation.

| Time | What to show | What to say |
|---|---|---|
| 0:00–0:20 | Product and mode labels | “A patient's story becomes a reviewable brief and a traceable case comparison.” |
| 0:20–0:55 | Speak: “My hands have been itchy for weeks. I tried a cream, but it didn't help.” | Let the agent ask the cream-name/use-duration question. Answer: “I don't remember the name. I used it for a few days.” |
| 0:55–1:25 | One eligible difference question in the synthetic workflow, or clinically approved real workflow | Answer: “I started using a new hand soap before this began.” Show which comparison changed and why. |
| 1:25–2:00 | Stop voice, review/confirm, doctor brief and source drawer | Click a fact and case statement. Show both exact sources and differences. “Actions in another case are examples for the doctor, not advice to this patient.” |
| 2:00–2:25 | Second encounter: “My scalp feels uncomfortable. I don't know when it began.” | Show a useful brief and no qualifying hand-case comparison. “No match in this collection does not mean no medical evidence exists.” |
| 2:25–2:45 | Evidence rejection | In a prepared validation panel/test output, introduce a statement referencing a missing or wrong-case passage and show rejection. Do not manipulate real patient content. |
| 2:45–3:00 | Exasol-backed history and separate clinician note | “Exasol lets us reconstruct the source, revision and search result; the doctor makes the clinical decision.” |

For speed, prepare separate resettable encounters for the main and no-match scenarios. Do not silently inject the later patient answer before the live user says it. Keep a clearly labelled recording/typed fallback if network or microphone fails.

## Acceptance matrix

| ID | Test | Required outcome | Owner |
|---|---|---|---|
| A01 | Start a new Kiro coding chat | Identity question or recognition of explicit Luffy/Zoro answer; correct scope | Both |
| A02 | Fresh checkout using README | Both apps start with documented commands and fixture mode | Both |
| A03 | Main typed story | Supported facts only; source quotes resolve | Zoro |
| A04 | “Cream” with unknown name | No inferred drug/adherence; missing name stays unknown | Zoro |
| A05 | Answer/skip/idk | At most two questions; unknown/skip is not a negative exposure | Both |
| A06 | Before/after retrieval | Real diff from stored versions; changed facts explain it | Both |
| A07 | No qualifying case | Useful brief, precise collection-limited explanation | Both |
| A08 | Bad or cross-case evidence | Withheld/flagged; no unsupported display | Zoro |
| A09 | Correction after confirmation | Original retained; confirmation/current search invalidated | Both |
| A10 | Two writes at same old revision | One conflict, no lost update; duplicate request creates no duplicate turn | Zoro |
| A11 | Late voice transcript | Flush before confirm; late event invalidates confirmed revision | Luffy |
| A12 | Voice webhook before transcript | Bounded wait/retry; no fabricated patient data or duplicate question | Both |
| A13 | Wrong session token/tool secret/expired binding | Request rejected; no other session's data exposed | Both |
| A14 | Browser inspection | No provider keys/secrets in JS/network responses except scoped session/binding tokens | Luffy |
| A15 | Synthetic versus published search | Never mixed; synthetic cards have no fake citations | Zoro |
| A16 | Backend restart in Exasol mode | Encounter/search history reloads; voice reconnects if binding lost | Zoro |
| A17 | Clinician note saved | Separate author-labelled note; no alteration of patient facts | Both |
| A18 | 390px and desktop, keyboard | Readable content; focus and controls work | Luffy |
| A19 | Provider/DB failure | Honest error, saved transcript retained when persistence succeeded, retry possible | Both |
| A20 | Reproduce a saved search | Same immutable inputs/version -> same order and reasons | Zoro |

Use pytest for backend domain/integration checks and a small Playwright browser suite for core typed flow, confirmation/correction and no-match. Do not write tests for every decorative component. CI uses fake providers and memory storage; real Exasol and voice smoke checks are separate and clearly reported. A UI screenshot is not evidence that an integration works.
