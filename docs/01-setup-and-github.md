# Setup from zero

## 1. GitHub organization — together, 15 minutes

Luffy: GitHub profile -> Settings -> Organizations -> New organization. Choose a suitable plan and a name, e.g. `exasol-double-helix`. Select that it belongs to your personal/team use as appropriate; do not claim employment or official sponsorship through the name. Naming availability is unknown. [Official organization guide](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/creating-a-new-organization-from-scratch)

Invite Zoro using their actual GitHub username; Zoro accepts. Map the nicknames Luffy and Zoro to actual usernames in `docs/team.md`. Both can be organization owners for this two-person event if you agree; otherwise make Luffy owner and give Zoro repository admin access. Do not share a personal GitHub password. [Invitation guide](https://docs.github.com/en/organizations/managing-membership-in-your-organization/inviting-users-to-join-your-organization)

Create organization repository `dermatology-case-navigator`. Private is the default recommendation; follow hackathon submission rules if a public repository is required. Add a README and `.gitignore`; choose a license only when agreed. Invite both people with write access. Enable Issues, PRs and squash merge. Record actual organization/repository URL in `docs/team.md`.

Protect `main` where your plan supports it: PR required, one approval from the other person, passing unique `web-checks` and `api-checks`, no force pushes, no branch deletion. GitHub Free organization branch protection is available for public repositories; private organization repositories need a supporting paid plan. If unsupported, keep the private repository and use the same review rules as a team convention instead of losing time upgrading. Do not add required checks until they have run once. [Protection availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

After bootstrap add `.github/CODEOWNERS` with actual usernames, not Luffy/Zoro nicknames. Luffy covers `apps/web` and `services/api/app/voice`; Zoro covers other backend/data/contracts paths. Put the more specific voice rule after the general backend rule. One teammate approval is sufficient; do not require a sole author's own code-owner approval, which would deadlock a two-person team.

## 2. Local tools — both developers

Install Git, Kiro, a currently supported Node.js LTS compatible with current Next.js, and Python 3.12. Verify `git --version`, `node --version`, `npm --version`, `python --version`. Use npm for the web app and a Python virtual environment for the API. Do not install unpinned global framework tooling. Bootstrap chooses versions, verifies they work, and records them in `docs/toolchain.md`; use those versions on both laptops and in CI. [Next.js installation](https://nextjs.org/docs/app/getting-started/installation)

Use GitHub sign-in through your credential manager or an SSH key. Do not paste access tokens into prompts or repo URLs. Each developer clones the same repository into their own local folder. Do not use two independent repositories or a shared network working directory.

## 3. Accounts — split immediately

| Owner | Account/action | Proof of readiness |
|---|---|---|
| Luffy | GitHub organization, Kiro, Vercel, optional v0 | Repo access works; frontend preview URL opens |
| Luffy | ElevenLabs account and private conversational agent | Browser voice test works; signed URL issued server-side |
| Zoro | Exasol SaaS account/trial or hackathon-provided environment | TLS connection and `SELECT 1` succeed from laptop and backend host |
| Zoro | Render account | FastAPI `/health` works over HTTPS |
| Zoro | Google AI Studio/Gemini API access | One structured-output extraction returns valid schema |
| Both | Data access and source review | Small reviewed collection or explicitly synthetic-only mode |

Use event-provided credits before paid services. No free-tier availability, credits or production compliance is assumed. Human account holders complete verification, payment decisions and access approval. Set a small budget/usage limit where supported. If a setup step blocks for 30 minutes, continue with a mock and record the blocker; Exasol must still become real for the final Exasol demo claim.

### Exasol

Start at [Exasol SaaS first steps](https://docs.exasol.com/db/latest/get_started/saas_first_steps.htm). Create a database in a nearby region, record endpoint and connection instructions, and configure network access for the laptop/backend host. Prefer the smallest practical network scope and verify outbound access from the deployment host before committing to it.

Follow [Exasol Python getting started](https://exasol.github.io/developer-documentation/main/getting_started.html) for PyExasol and SaaS personal access-token authentication where applicable. Separate bootstrap/schema credentials from runtime credentials when feasible. Keep TLS verification enabled; do not “fix” connectivity by disabling certificate checks. Create schema `DERMA_NAV`; seed a tiny table and verify read/write. Do not spend hackathon time installing a local Exasol server unless SaaS/event access is unavailable and you already know the installation.

### AI extraction provider

Create a [Gemini API key](https://ai.google.dev/gemini-api/docs/api-key). Select a currently available low-latency text model that supports [structured output](https://ai.google.dev/gemini-api/docs/structured-output); record the exact ID in `GEMINI_MODEL` and `docs/toolchain.md`. Use the current `google-genai` Python SDK and server-side schema validation. Do not hardcode an assumed model ID from an old example. The voice agent's configured conversation model is separate from this backend extraction model.

### ElevenLabs

Luffy creates a private agent, stores credentials only on servers, and configures the webhook described in `docs/03-api-contract.md`. Use a signed WebSocket URL with an explicitly compatible connection type; do not combine a WebSocket signed URL with a default WebRTC token flow. Verify SDK callbacks and payload types against the installed package. [React SDK](https://elevenlabs.io/docs/eleven-agents/libraries/react), [agent authentication](https://elevenlabs.io/docs/eleven-agents/customization/authentication), [webhook tools](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools).

## 4. Environment variables

Kiro creates examples with blank placeholders only. Actual files are gitignored. No credentials belong in `NEXT_PUBLIC_*`.

`apps/web/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
API_INTERNAL_BASE_URL=http://localhost:8000
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=
```

`NEXT_PUBLIC_API_BASE_URL` is a non-secret URL; the browser needs it. `API_INTERNAL_BASE_URL` is used by the Next.js signed-URL server route when validating the session and requesting a voice binding.

`services/api/.env`:

```dotenv
APP_ENV=development
DATA_BACKEND=memory
EXASOL_DSN=
EXASOL_USER=
EXASOL_PASSWORD=
EXASOL_SCHEMA=DERMA_NAV
CORS_ORIGINS=http://localhost:3000
DEMO_ACCESS_CODE=
SESSION_TOKEN_SECRET=
VOICE_TOOL_SECRET=
EXTRACTOR_MODE=fixture
GEMINI_API_KEY=
GEMINI_MODEL=
COLLECTION_MODE=synthetic
```

Use `DATA_BACKEND=exasol` for the real demo. Memory mode is for isolated development and CI; it displays “Development storage — not Exasol.” Use `EXTRACTOR_MODE=gemini` only when verified; fixture mode supports the documented demo phrases and marks results “Demo extraction.” Generate long random secrets with a password manager. Keep `SESSION_TOKEN_SECRET` stable across backend restarts; changing it requires new encounters. Set the same `VOICE_TOOL_SECRET` in the agent's server-tool authentication header. Add provider keys directly to each host's secret settings; do not share through git. Both need non-secret IDs and shared demo access information; only the owner of each integration needs its administrative credentials.

`COLLECTION_MODE` determines available collections, not a client override that can relabel cases. A synthetic collection never becomes published by changing an environment variable; per-case validation must pass.

## 5. First shared commit

Luffy copies this pack to the repo root, commits planning files and creates branch `luffy/s0-bootstrap`. Zoro works on account setup and data notes outside application paths until that PR merges. Then:

```powershell
git clone https://github.com/ACTUAL_ORG/dermatology-case-navigator.git
cd dermatology-case-navigator
git switch main
git pull --ff-only
```

Replace `ACTUAL_ORG` before running. Subsequent sprint commands are in `docs/07-release-and-recovery.md`.
