# Toolchain (recorded at S0, 13 Nov 2026)

Versions below are what was actually installed and verified on Luffy's Windows laptop. CI uses the
same lockfiles. Do not upgrade during the event without agreement (S5 forbids upgrades).

## Runtimes

| Tool | Local version | CI |
|---|---|---|
| Node.js | 22.17.0 | `actions/setup-node@v7`, `node-version: 22` |
| npm | 10.9.2 | bundled with Node 22 |
| Python | 3.12.7 | `actions/setup-python@v7`, `3.12` |
| Git | 2.49.0 | — |

Next.js 16.4.6 requires Node >= 20.9 (`engines` in its package.json).

## Web (`apps/web/package.json`, locked by `package-lock.json`, exact pins)

| Package | Version | Note |
|---|---|---|
| next | 16.4.6 | Scaffolded with `create-next-app@16.4.6`; `cacheComponents` + `partialPrefetching` on (scaffold default) |
| react / react-dom | 19.3.0 | |
| typescript | 5.9.3 | |
| tailwindcss / @tailwindcss/turbopack | 4.3.3 | |
| eslint / eslint-config-next | 9.39.5 / 16.4.6 | Flat config, `npm run lint` = `eslint`. npm flags eslint 9 as no longer supported upstream; kept because `eslint-config-next@16.4.6` targets it |
| shadcn (CLI + `shadcn/tailwind.css`) | 4.23.0 | `components.json` style `base-nova`, Base UI primitives |
| @base-ui/react | 1.9.0 | shadcn primitives |
| cn | 0.5.2 | shadcn's class merger (publisher shadcn, repo shadcn-ui/cn, no install scripts) |
| class-variance-authority | 0.7.1 | |
| lucide-react | 1.72.0 | |
| tw-animate-css | 1.4.0 | |
| openapi-typescript | 7.13.0 | `npm run generate:api` |
| @playwright/test | 1.65.0 | Chromium headless shell build 1254 |

`npm audit` reported 8 moderate advisories in the scaffold's dependency tree at install time; not
triaged in S0.

## API (`services/api/requirements.txt`, full `pip freeze` lock; direct deps in `requirements.in`)

| Package | Version |
|---|---|
| fastapi | 0.162.5 |
| starlette | 1.10.0 |
| pydantic / pydantic_core | 2.14.3 / 2.50.4 |
| uvicorn (+ httptools, watchfiles, websockets) | 0.54.0 |
| python-dotenv | 1.2.4 |
| httpx | 0.28.1 |
| pytest | 9.2.0 |
| jsonschema | 4.26.0 |

Starlette warns that using `httpx` with its TestClient is deprecated in favour of `httpx2`; tests
still pass. Revisit only if it breaks.

## Not chosen yet (owners record these when integrated)

| Item | Owner | Sprint |
|---|---|---|
| PyExasol version, Exasol SaaS region/endpoint (no secrets here) | Zoro | S1 |
| Extraction provider: Meta Model API, `openai` 3.50.0 Python SDK (`base_url=https://api.meta.ai/v1`), Responses API with `text.format` JSON Schema (strict), model `muse-spark-1.3-contributor`, reasoning effort `minimal`, timeout 45 s, 1 retry. Gemini / `google-genai` removed | Luffy (backend takeover) | S2 |
| PyExasol 4.0.0 (locked by Zoro, S1) | — | done |
| `@elevenlabs/react` SDK version, connection type, agent model | Luffy | S1/S2 |
| Render Python version / plan, Vercel project settings | Zoro / Luffy | S1/S4 |
