# Exasol Double Helix — Kiro build playbook

**Product:** Dermatology Case Navigator  
**Developers:** Luffy and Zoro  
**Budget:** 24 elapsed hours, including 8 hours of sleep; 16 working hours each  
**Status:** planning and prompt pack, not an implemented or clinically validated application  
**Prepared:** 13 November 2026

## Start here

1. Both developers read `docs/01-setup-and-github.md` and create the organization and repository together. Suggested organization slug: `exasol-double-helix`; repository: `dermatology-case-navigator`. Availability is not checked.
2. Luffy copies the **contents** of this pack into the repository root, including `AGENTS.md` and the hidden `.kiro` directory. Do not nest the pack inside the repository. The repository should initially contain these planning files and no application code.
3. Luffy opens that repository in Kiro and pastes `prompts/00-bootstrap.md`. Luffy alone creates the shared application skeleton. Zoro sets up Exasol and assembles source candidates while this happens; Zoro does not create a second skeleton.
4. Merge and verify Sprint 0. Zoro then clones/pulls the same repository. Each person opens their own local checkout in Kiro. They do not edit the same working directory.
5. Every new Kiro coding chat starts with the prompt in `prompts/01-start-session.md`. The repository instructions also tell Kiro to ask **“Who is coding today: Luffy or Zoro?”** before implementation. This is an agent instruction, not a guaranteed IDE login prompt. Use the session-start prompt explicitly if Kiro does not ask.
6. Each developer runs their role prompt for the current sprint from `prompts/02-luffy-sprints.md` or `prompts/03-zoro-sprints.md`. Complete one sprint at a time. Use `prompts/04-integration-and-release.md` at every checkpoint.

## Fixed decisions

- Build a **responsive web application**, not native mobile. Laptop-first doctor workspace; patient intake also usable on a phone.
- Next.js App Router + TypeScript + Tailwind + shadcn/ui; Python 3.12 + FastAPI + Pydantic; Exasol via PyExasol.
- ElevenLabs React SDK for conversation; a private agent calls one authenticated backend webhook to request the next approved question.
- Gemini structured-output API is the default extraction provider; model name is configured from the available supported models during setup. No model key or subscription is assumed to exist. If access fails, use labelled deterministic demo extraction while fixing access.
- Deterministic structured-feature ranking for the MVP. No vector database, embeddings service, live PubMed crawler, image model, or fine-tuning.
- One repository, one shared API contract, small feature branches, one reviewed PR per developer per sprint, regular merges into `main`.
- Hosted target: Vercel frontend + Render Python backend + Exasol SaaS. Local laptop is the release fallback. v0 is an optional UI accelerator used only by Luffy.
- This pack creates no accounts and makes no purchases. Follow the linked setup instructions and check current access, costs, and hackathon rules yourselves.

## What success looks like

A fictional patient speaks or types. Their supported words become a source-linked brief. The system asks at most two clarification questions, updates case comparisons with visible reasons, and hands over only after patient confirmation. The doctor can inspect source passages, record a separate assessment, and see a useful brief even when no case qualifies.

**The key demo moment:** one patient answer changes the comparison, and the doctor can inspect the evidence and the reason for the change.

## Reading map

| File | Purpose |
|---|---|
| `docs/01-setup-and-github.md` | Account setup, organization, access, local prerequisites, environment variables |
| `docs/02-product-and-architecture.md` | Scope, architecture, ownership, storage, safety boundaries |
| `docs/03-api-contract.md` | Exact routes, shared DTO shapes, sequencing, authentication and failure handling |
| `contracts/domain.schema.json` | Machine-readable domain schema to use for DTOs and fixtures |
| `docs/04-data-and-evidence.md` | Real-source review, synthetic fallback, extraction and ranking rules |
| `docs/05-sprints-and-ownership.md` | Timeboxes, role responsibilities and integration gates |
| `docs/06-ui-and-demo.md` | Modular grid design, states, demo script, evaluation checklist |
| `docs/07-release-and-recovery.md` | Deployment, commands, failure recovery, cut order |
| `docs/08-resources.md` | Official sources and links |
| `prompts/` | Copy-paste coding prompts |
| `data/synthetic/` | Fictional source fixtures; never published medical evidence |

## First ten minutes

Luffy creates the GitHub organization and invites Zoro. Zoro accepts and starts Exasol signup. Both enable account security and connect their own Kiro installation. Luffy creates the repository and copies this pack in. Zoro opens the data-source links and begins the bounded source search. Do not spend the opening hour debating frameworks or adding infrastructure.

## Important change from the idea document

The earlier description mentioned 988 unreviewed candidate cases. You have now said nothing is set up, so this plan treats that collection as **unavailable until someone supplies and verifies it**. The app must not advertise 988 loaded or reviewed cases. It displays the actual collection count, source mode and review status returned by the backend.
