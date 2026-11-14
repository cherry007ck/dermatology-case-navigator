---
inclusion: always
---

# Engineering steering

Respect ownership in `AGENTS.md`. Implement only the identified developer's current sprint. Next.js/TypeScript frontend in `apps/web`, FastAPI/Python backend in `services/api`, Exasol for persisted evidence and encounter records. Freeze DTOs before parallel work; use `docs/03-api-contract.md` and `contracts/domain.schema.json`. Frontend HTTP mocks share the same serialized examples as backend tests. No independently designed response shapes, no giant end-of-hackathon merge. Use deterministic ranking, stable IDs, revision checks, idempotency and explicit mock/live modes. Read `docs/05-sprints-and-ownership.md` for gates. Finish with verified behavior and a teammate handoff.
