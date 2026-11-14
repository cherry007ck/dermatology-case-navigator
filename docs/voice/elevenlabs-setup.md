# ElevenLabs setup — Luffy (S1)

Sources: [React SDK](https://elevenlabs.io/docs/eleven-agents/libraries/react),
[Agent authentication](https://elevenlabs.io/docs/eleven-agents/customization/authentication),
[Webhook tools](https://elevenlabs.io/docs/eleven-agents/customization/tools/webhook-tools)
(all listed in `docs/08-resources.md`), plus ElevenLabs'
[API keys](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys) page for key restrictions.
Checked 13 Nov 2026 against `@elevenlabs/react` 1.22.0 / `@elevenlabs/client` 1.36.0.

Never paste the API key into chat, git, screenshots, issues or this file. It goes only in
`apps/web/.env.local` (gitignored) and later in Vercel's server-side environment settings.

## Actual configuration (S1, verified 13 Nov 2026 by Luffy)

| Setting | S1 state |
|---|---|
| Agent | Private ElevenAgents agent; ID stored only in `apps/web/.env.local` |
| Authentication | Enabled (conversations start only from a server-issued signed URL) |
| File attachments | Disabled |
| Client events | User transcript and agent response enabled |
| Prompt | **Temporary connection-test prompt**, not the intake prompt. First message asks for a fictional skin concern in one or two sentences |
| Tools | None. `advance_intake` webhook is S2 |
| Origin allowlist | Not recorded in S1. Confirm `localhost:3000` (and the Vercel domain in S4) before relying on it |
| API key | User key with **ElevenAgents Write** permission only (`convai_write`; the signed-URL endpoint returns `missing_permissions` without it), small quota, expiry set. First key disabled and replaced |
| Conversation LLM / voice | Not recorded yet; add names (no IDs) to `docs/toolchain.md` |

S2 replaces the temporary prompt with `prompts/06-elevenlabs-system.md` and adds the tool.

## 1. Private agent (dashboard, human)

1. Sign in at <https://elevenlabs.io/app/agents> and create a **blank** agent, e.g. `dcn-fictional-intake`.
2. **S1:** a short connection-test prompt and first message that ask only for a fictional skin
   concern. **S2:** switch to the first message and system prompt in `prompts/06-elevenlabs-system.md`.
3. **Security tab:** turn on authentication so the agent is private. Add allowlist hostname
   `localhost:3000`; the Vercel domain is added in S4.
4. Disable file attachments; this prototype never accepts uploads or images.
5. **Client events (Advanced tab):** enable user transcript and agent response events.
6. Do **not** add the `advance_intake` tool yet. That is S2.
7. Copy the agent ID (starts with `agent_`) straight into `.env.local`.

## 2. API key (dashboard, human)

1. Open <https://elevenlabs.io/app/settings/api-keys> and create a key named e.g. `dcn-local-luffy`.
2. Restrict it:
   - **Permission:** ElevenAgents **Write** only. Read access is not enough: the signed-URL
     endpoint answers HTTP 401 `missing_permissions` (`convai_write`). Enable nothing else.
   - **Credit quota:** a small limit for the event.
   - **Expire after:** a preset that covers the hackathon (e.g. 7 days).
3. The key is shown once. Paste it straight into `apps/web/.env.local`, **never** `.env.example`
   (tracked by git). If a key is ever shown in a terminal, chat or screenshot, disable it and
   create a new one.

## 3. Local environment — `apps/web/.env.local`

Copy `apps/web/.env.example` to `apps/web/.env.local` and fill in:

| Field | Value | Secret? |
|---|---|---|
| `NEXT_PUBLIC_API_MODE` | `live` | no |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | no |
| `API_INTERNAL_BASE_URL` | `http://localhost:8000` | no |
| `ELEVENLABS_API_KEY` | the key from step 2 | **yes** |
| `ELEVENLABS_AGENT_ID` | `agent_...` from step 1 | no, keep server-side |
| `VOICE_ALLOWED_ORIGINS` | leave blank locally | no |

No ElevenLabs value may ever start with `NEXT_PUBLIC_`.

## 4. Verify configuration (no secrets printed)

```powershell
cd apps/web
npm run check:voice
```

Every line must read `PASS`. The script requests one signed URL exactly like the server route
and reports only HTTP status and URL scheme.

## 5. Verify the browser connection

```powershell
# terminal 1 (services/api)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# terminal 2 (apps/web) — restart after editing .env.local
npm run dev
```

Open <http://localhost:3000>, demo code `local-demo`, **Start intake**, then **Start voice**,
and allow the microphone. Expected:

1. The banner shows `Voice connected — listening`. The agent speaks the first message, which
   appears in **Voice transcript — please review** as "Assistant".
2. Say: "My hands have been itchy for weeks." Your finalized words appear as
   "You (transcribed)", exactly as recognised (fillers and restarts included).
3. **Stop voice** ends the session; the panel shows "Voice stopped".

A close before the connection opens is shown as an error with its numeric close code.

**Result on 13 Nov 2026 (Luffy, Windows, local dev):** connection opened, agent first message and
finalized user transcript captured, Stop ended the session normally.

S1 scope: transcripts are captured and shown, **not saved** to the encounter. The webhook
question loop and transcript persistence are S2.

## Variables and headers used by the app

- Connection: `startSession({ signedUrl, connectionType: "websocket", dynamicVariables: { secret__voice_binding } })`.
  Signed URLs are WebSocket URLs, valid for 15 minutes to start a conversation.
- `secret__voice_binding`: the scoped binding from `POST /v1/sessions/{id}/voice-binding`. The
  `secret__` prefix keeps it out of the LLM; it is usable only in tool headers. In S2 the
  `advance_intake` tool sends `X-Voice-Binding: {{secret__voice_binding}}` plus a static
  `X-Tool-Secret` stored as a secret header (same value as the API's `VOICE_TOOL_SECRET`).
