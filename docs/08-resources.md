# Official resources and verification notes

Checked for this playbook on 13 November 2026. These support integration choices; they are not proof of clinical efficacy, hackathon eligibility, plan entitlements or continued pricing. Kiro should verify current SDK interfaces during implementation and record chosen versions. No third-party tutorial is required.

| Topic | Primary resource | Use |
|---|---|---|
| Kiro repository instructions | [Steering and AGENTS.md](https://kiro.dev/docs/steering/) | Persistent instructions; explicitly start each chat with the supplied identity prompt |
| GitHub organization | [Create organization](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/creating-a-new-organization-from-scratch) | Account bootstrap |
| GitHub invitations | [Invite members](https://docs.github.com/en/organizations/managing-membership-in-your-organization/inviting-users-to-join-your-organization) | Add both teammates |
| GitHub protection | [Protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | Plan availability and review/check settings |
| Next.js | [Installation](https://nextjs.org/docs/app/getting-started/installation) | Current supported runtime and App Router setup |
| ElevenLabs UI integration | [React SDK](https://elevenlabs.io/docs/eleven-agents/libraries/react) | Connection, callbacks and current package APIs |
| ElevenLabs connection security | [Agent authentication](https://elevenlabs.io/docs/eleven-agents/customization/authentication) | Server-generated signed URL |
| ElevenLabs backend tool | [Webhook tools](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools) | Authentication headers, dynamic variables and tool configuration |
| ElevenLabs UI-only tools | [Client tools](https://elevenlabs.io/docs/eleven-agents/customization/tools/client-tools) | Optional UI events; not the MVP backend integration |
| Exasol signup | [SaaS first steps](https://docs.exasol.com/db/latest/get_started/saas_first_steps.htm) | Provision event/trial database |
| Exasol Python | [Developer getting started](https://exasol.github.io/developer-documentation/main/getting_started.html) | PyExasol connection and queries |
| Exasol advanced search, optional only | [Exasol agentic engineering example](https://www.exasol.com/blog/exasol-agentic-engineering/) | Shows external vector infrastructure; not needed for this MVP |
| FastAPI | [Official tutorial](https://fastapi.tiangolo.com/tutorial/) | DTOs, validation, dependency injection and OpenAPI |
| Gemini | [API keys](https://ai.google.dev/gemini-api/docs/api-key), [structured output](https://ai.google.dev/gemini-api/docs/structured-output), [models](https://ai.google.dev/gemini-api/docs/models) | Server-only extraction provider; verify actual accessible model ID |
| Dataset | [PMC-Patients official repository](https://github.com/pmc-patients/pmc-patients) | Versioned data links and field definitions |
| PMC full text | [OAI-PMH](https://pmc.ncbi.nlm.nih.gov/tools/oai/), [legacy OA service status](https://pmc.ncbi.nlm.nih.gov/tools/oa-service/) | Current access route and article-level reuse restrictions |
| v0 | [Git import](https://v0.app/docs/git-import) | Optional frontend-only design iteration |
| Vercel | [Monorepos](https://vercel.com/docs/monorepos) | Web root and deployment setup |
| Render | [Deploy FastAPI](https://render.com/docs/deploy-fastapi) | Python web service startup |

## Claims that remain unverified until you implement

Organization name availability; hackathon rules/sponsor requirements; credits and costs; model access; Exasol provision/network access; current frontend/backend host entitlements; availability and suitability of the 988 candidate cases; clinical validity of matching/question selection; performance and time savings. Do not present these as established results.
