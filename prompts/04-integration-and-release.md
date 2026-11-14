# Checkpoint prompts

## End of each sprint — paste in either developer's chat

```text
Integrate the current sprint for my confirmed developer identity. Read both status files and current main. Inspect git state without discarding anything. Summarize the two PRs, contract version and outstanding dependencies. Do not merge or overwrite the other person's code without their review.

Verify my changes against the shared contract, run my focused checks and prepare the smallest reviewable PR. Ask my teammate for any missing dependency as a concrete method/route/fixture requirement, not a vague “backend isn't ready.” Use a mock for independent progress only, with visible labels. Update my status file with branch/commit, implemented behavior, tests actually run, integration blockers and exact teammate action.

After both reviewed PRs merge, pull integrated main and execute the sprint gate from docs/05-sprints-and-ownership.md. Check a fresh fictional session, not just a previously cached happy-path session. Save the known-good commit if successful. If a check fails, identify the owning module and smallest fix; each developer implements their own fix. Do not launch the next sprint until the gate passes or we explicitly choose and document a labelled fallback.
```

## Final integration — run together after S4

```text
We are integrating Exasol Double Helix's Dermatology Case Navigator. Keep the two file ownership lanes intact. Inspect actual implementations, both status files and docs/06-ui-and-demo.md; do not assume tasks are complete because checkboxes are ticked.

Verify the exact same commit across frontend/backend. Run schema drift/fixture validation, web build/typecheck/lint, focused backend tests and core browser flows. Separately run authenticated live Exasol and ElevenLabs smoke checks; list any skipped or unverified check explicitly. Never print tokens or provider keys.

Exercise main intake, unknown/skip, no-match, correction invalidation, source drawer, separate clinician note, duplicate/stale write, webhook-before-transcript and final voice-stop/flush/confirm ordering. Validate no fabricated citation, no synthetic/published mixing, no patient diagnosis/treatment advice and no unsupported claim displayed. Reproduce one saved search from immutable inputs and reload it after backend restart.

Report one of: ready for live demo; ready with these labelled fallbacks; not ready due to these concrete blockers. Fix release blockers in the appropriate owner's lane, then rerun only affected checks. Prepare final README, known-good commit/tag, deployment/local URLs and three-minute script. Preserve eight-hour sleep and feature freeze; do not add infrastructure or redesign.
```

## PR/handoff format

```text
Developer / sprint / branch / PR:
User-visible behavior delivered:
Contract changes (or none):
Checks actually run and results:
Live integrations verified:
Mocked, skipped or blocked checks:
Known limitations:
Teammate's next exact action:
```
