# Hackathon completion: tasks and checklist

Resume from this file and the actual git state (`git log`, `git status`). The branch is `integration/local-backend`.

Legend: [x] done and verified · [~] in progress · [ ] open · [!] blocked (see note)

## M0 State check (00:40 Berlin)
- [x] The baseline `ada412e` is pushed and the working tree is clean.
- [x] Zoro's branch `origin/zoro/s4-case-ui-attribution` exists, 5 commits on base `7af9925`.

## M1 Patient information and review (done 01:40, `49b67eb`)
- [x] 1.1 `product_use` key: rules, Meta prompt, validator (use verb in the quote or just before it in the same sentence) and brief timeline.
- [x] 1.2 Backend correction: supersession, recompute, invalidated confirmation, idempotent replay, budget kept.
- [x] 1.3 Backend skip: recorded as `skipped`, not a negative, not re-asked, idempotent, listed as missing in the brief.
- [x] 1.4 Patient "Summary for your doctor" panel. Confirm is blocked while the summary is stale.
- [x] 1.5 Live browser verification (Exasol, Meta, published).

## M2 UI integration (done 02:05, `cecd9d0` merge and `5d181b4`)
- [x] 2.1 Merged `zoro/s4-case-ui-attribution` with no conflicts and no force push.
- [x] 2.2 Attribution wired from the generated type; same-site wording; "None captured" empty states; `symptom_site` label.
- [x] 2.3 Typecheck, lint and build pass. Mock e2e: 58 passed, 17 skipped. Live browser check: 29/29, including the 390 px flow and keyboard Escape.

## M3 Deployment
- [x] 3.1 Access inspected: no Render, Vercel or GitHub CLI and no deploy token. Render `dcn-api-ujrd` serves old `main` code (memory, fixture, no `CaseAttribution`). No Vercel URL known.
- [!] 3.2 **BLOCKED (human):** account access, plus a PR merge to `main` or a Render branch switch, plus env vars. Exact steps are in `docs/deploy/runbook.md`.

## M4 Voice loop
- [x] 4.1 Agent inspected read-only (`apps/web/scripts/inspect-voice-agent.mjs`): private agent, connection-test prompt, no tools.
- [x] 4.1b Backend leg verified live (`services/api/scripts/voice_webhook_check.py`, 10/10). A local `VOICE_TOOL_SECRET` was generated into `.env` (it had been empty).
- [!] 4.2 **BLOCKED on 3.2:** `apps/web/scripts/configure-voice-agent.mjs` is ready (dry run by default, refuses unless the public webhook returns 401). The spoken loop is not verified.

## M5 Final verification and handoff
- [x] 5.1 Live checks 1–8 pass (see `docs/demo/README.md` §3). Check 9 (spoken voice) and check 10 (deployed flow) are blocked.
- [x] 5.2 Screenshots, demo script, start instructions, verified features and limitations, recording steps (`docs/demo/`).

## Blockers and next action
- Next action (human): deploy per `docs/deploy/runbook.md`. Then (Luffy) run the runbook verification and `configure-voice-agent.mjs --apply`, then the spoken check.
- Feature freeze 09:30. Unresolved at freeze: deployment, spoken voice loop.
