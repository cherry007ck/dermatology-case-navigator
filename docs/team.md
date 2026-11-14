# Team

| Nickname | GitHub username | Owns |
|---|---|---|
| Luffy | TODO — confirm actual username | `apps/web/**`, `services/api/app/voice/**`, `services/api/tests/test_voice*`, `docs/voice/**`, `docs/status/luffy.md`, UI/browser tests, GitHub/Vercel, ElevenLabs |
| Zoro | TODO — confirm actual username | Other `services/api/**`, `data/**`, `docs/data/**`, `contracts/**` (after S0), `docs/status/zoro.md`, Exasol, Python CI, Render |

- Organization: `exasol-sh`
- Repository: <https://github.com/exasol-sh/dermatology-case-navigator>

`.github/CODEOWNERS` is added only once both usernames are confirmed (nicknames are not valid owners).
When added: Luffy for `apps/web/` and `services/api/app/voice/`; Zoro for `services/api/`, `data/`,
`contracts/`; the voice rule goes after the general backend rule. One teammate approval is enough; do
not require a sole author's own code-owner approval.

## Branch and review convention

- Branch from current `main`: `<developer>/s<index>-<feature>`, e.g. `luffy/s1-interface-voice`, `zoro/s1-exasol-api`.
- One reviewed PR per developer per sprint; the other developer approves. No self-approval, no force pushes.
- Required checks once they have run on `main`: `web-checks`, `api-checks`.
- Squash merge after approval and green checks. Merge backend first when a frontend PR depends on it.
- Contract changes after S0 need the short record in `docs/09-contract-change-template.md`, agreed by both.
- Branch protection: enable on `main` if the plan supports it for this repository's visibility; otherwise follow the same rules by convention.
