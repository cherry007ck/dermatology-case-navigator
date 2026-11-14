# Run once — Luffy creates the common foundation

Paste the following into Kiro after copying this pack into the empty shared repository root. Organization/repository creation is described in `docs/01-setup-and-github.md`; this prompt does not assume the agent can create accounts or spend money.

```text
I am Luffy. Implement Sprint 0 of this repository's hackathon playbook. This is an implementation request: create and verify the common foundation, not another proposed plan.

Read AGENTS.md, START-HERE.md, docs/01-setup-and-github.md, docs/02-product-and-architecture.md, docs/03-api-contract.md, docs/05-sprints-and-ownership.md and contracts/domain.schema.json. Inspect the repository and preserve existing work. If the supplied files are missing, ask me to copy the playbook contents into the repo root before proceeding. Do not bootstrap a second repository elsewhere.

I own bootstrap only; Zoro is handling provider accounts and source acquisition in parallel. Work on luffy/s0-bootstrap. Use the recommended stack and verify current package/runtime requirements from official docs. Lock actual installed versions and record them in docs/toolchain.md. Use npm in apps/web and Python 3.12 with a virtual environment in services/api. Avoid extra monorepo tooling.

Create:
1. Next.js App Router/TypeScript/Tailwind web app with modular patient and doctor route shells, mode banners and typed intake running against fixtures.
2. FastAPI app with /health, /docs, Pydantic DTOs matching the contract, in-memory stub repository, and the documented IntakeService facade. It must load validated fictional fixtures, not return untyped arbitrary dicts.
3. Registered but minimal voice router in app/voice so Luffy can implement it independently without later editing main.py. Do not call ElevenLabs yet.
4. Exact ownership structure from docs/02-product-and-architecture.md; separate dependency files/locks. Environment examples with blank secrets; gitignore env files, virtualenvs, caches, generated logs, local identity hints and source downloads.
5. Exported contracts/openapi.json, generated TypeScript API types, shared serialized mock examples, and validation commands. Keep domain schema and DTOs aligned; resolve any discrepancy now before freezing the contract and document the resolution.
6. .github/workflows/web.yml and api.yml with unique web-checks/api-checks jobs. Include build/typecheck/lint, schema/fixture verification and focused backend tests; no production provider keys in CI.
7. A README with exact Windows and Unix run commands, required npm scripts and Python script entrypoints from docs/07-release-and-recovery.md. init_db/seed may be explicit not-yet-live stubs, but never report a real Exasol connection unless verified.
8. docs/team.md with actual GitHub usernames when supplied (otherwise clear TODOs), branch-review convention and CODEOWNERS only once usernames are known. Generate Kiro requirements/design/tasks docs under .kiro/specs/dermatology-case-navigator/ from this playbook; track both lanes but execute only the current identity's lane.

Run API startup/fixture checks and web build/typecheck. Demonstrate that a fresh local checkout can render a fictional brief without external accounts. If dependencies cannot be installed, report the blocker and do not claim a passing build. No actual provider keys are needed for this sprint.

Update docs/status/luffy.md with implemented behavior, exact checks, branch/commit, unresolved dependencies and Zoro's next steps. Prepare a reviewable PR summary and the contract/interface files Zoro must pull. Do not auto-merge without Zoro's review. Stop after S0; do not implement Zoro's backlog.
```
