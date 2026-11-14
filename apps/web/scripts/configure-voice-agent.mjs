// Configure the EXISTING private ElevenLabs agent for the backend-driven clarification loop.
//
//   node scripts/configure-voice-agent.mjs --api-base https://<public-api-host>            # dry run (default)
//   VOICE_TOOL_SECRET=... node scripts/configure-voice-agent.mjs --api-base https://... --apply
//
// Preconditions (docs/voice/s2-handoff.md): the public API at --api-base runs the current
// integration code with VOICE_TOOL_SECRET set; POST /v1/voice/advance returns 401 without headers.
// The script checks that first and refuses otherwise.
// --apply: stores VOICE_TOOL_SECRET as an ElevenLabs workspace secret, creates (or reuses) the
// `advance_intake` webhook tool (POST {api}/v1/voice/advance, empty body, headers X-Tool-Secret from
// the secret and X-Voice-Binding from the secret__voice_binding dynamic variable), then replaces the
// temporary connection-test prompt with prompts/06-elevenlabs-system.md and attaches the tool.
// Never prints the API key, agent ID, secret values or the binding.
import { readFileSync } from "node:fs";

const args = process.argv.slice(2);
const apiBase = args[args.indexOf("--api-base") + 1];
const apply = args.includes("--apply");
if (!apiBase || !/^https:\/\/[^/]+$/.test(apiBase)) throw new Error("--api-base https://<host> (no path, https only) is required");

const env = Object.fromEntries(readFileSync(new URL("../.env.local", import.meta.url), "utf8").split(/\r?\n/)
  .map((l) => l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/)).filter(Boolean)
  .map((m) => [m[1], m[2].replace(/^["']|["']$/g, "").trim()]));
const XI = "https://api.elevenlabs.io";
const headers = { "xi-api-key": env.ELEVENLABS_API_KEY, "Content-Type": "application/json" };
const agentPath = `/v1/convai/agents/${encodeURIComponent(env.ELEVENLABS_AGENT_ID)}`;

// System prompt: the text block of prompts/06-elevenlabs-system.md.
const promptDoc = readFileSync(new URL("../../../prompts/06-elevenlabs-system.md", import.meta.url), "utf8");
const systemPrompt = promptDoc.match(/```text\r?\n([\s\S]*?)```/)?.[1]?.trim();
const firstMessage = "This is a fictional consultation-preparation demo. Tell me about the skin concern you would like the doctor to review.";
if (!systemPrompt) throw new Error("system prompt block not found in prompts/06-elevenlabs-system.md");

// 1. Public backend precondition.
const probe = await fetch(`${apiBase}/v1/voice/advance`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
const probeBody = await probe.json().catch(() => ({}));
console.log(`public webhook without headers: HTTP ${probe.status} ${probeBody?.error?.code ?? ""}`);
if (probe.status !== 401) {
  console.log("REFUSED: the public API must answer 401 VOICE_AUTH_FAILED (current code with VOICE_TOOL_SECRET set).");
  process.exit(1);
}

const agentRes = await fetch(XI + agentPath, { headers });
if (!agentRes.ok) throw new Error(`agent GET ${agentRes.status}`);
const agent = await agentRes.json();
const currentPrompt = agent.conversation_config?.agent?.prompt ?? {};
console.log("agent:", agent.name, "| current tools:", (currentPrompt.tool_ids ?? []).length, "| current prompt starts:",
  JSON.stringify((currentPrompt.prompt ?? "").slice(0, 80)));

const toolConfig = (secretId) => ({
  type: "webhook",
  name: "advance_intake",
  description: "Call after the user finishes their initial statement or an answer. The application records the transcript and "
    + "returns the only question you may ask (question_text) or tells you to send the user to the review screen.",
  response_timeout_secs: 20,
  api_schema: {
    url: `${apiBase}/v1/voice/advance`,
    method: "POST",
    request_headers: {
      "X-Tool-Secret": { secret_id: secretId },
      "X-Voice-Binding": { variable_name: "secret__voice_binding" },
    },
    request_body_schema: { type: "object", description: "No parameters: the backend ignores the body.", properties: {} },
  },
});

if (!apply) {
  console.log("DRY RUN: would create/reuse workspace secret 'dcn_voice_tool_secret', create/reuse webhook tool 'advance_intake' ->",
    `${new URL(apiBase).host}/v1/voice/advance`, "with headers X-Tool-Secret (secret) and X-Voice-Binding ({{secret__voice_binding}}),",
    `replace the prompt (${systemPrompt.length} chars from prompts/06) and first message, and attach the tool. Re-run with --apply.`);
  process.exit(0);
}

const secretValue = process.env.VOICE_TOOL_SECRET;
if (!secretValue || secretValue.length < 24) throw new Error("VOICE_TOOL_SECRET (same value as the public API) must be set in the environment");

// 2. Workspace secret (reuse by name).
const secrets = await (await fetch(`${XI}/v1/convai/secrets`, { headers })).json();
let secret = (secrets.secrets ?? []).find((s) => s.name === "dcn_voice_tool_secret");
if (!secret) {
  const r = await fetch(`${XI}/v1/convai/secrets`, { method: "POST", headers, body: JSON.stringify({ type: "new", name: "dcn_voice_tool_secret", value: secretValue }) });
  if (!r.ok) throw new Error(`create secret ${r.status}`);
  secret = await r.json();
  console.log("workspace secret created");
} else {
  const r = await fetch(`${XI}/v1/convai/secrets/${encodeURIComponent(secret.secret_id)}`, { method: "PATCH", headers, body: JSON.stringify({ type: "update", name: "dcn_voice_tool_secret", value: secretValue }) });
  console.log("workspace secret updated:", r.status);
}
const secretId = secret.secret_id;

// 3. Webhook tool (reuse by name).
const tools = await (await fetch(`${XI}/v1/convai/tools`, { headers })).json();
let tool = (tools.tools ?? []).find((t) => t.tool_config?.name === "advance_intake");
if (tool) {
  const r = await fetch(`${XI}/v1/convai/tools/${encodeURIComponent(tool.id)}`, { method: "PATCH", headers, body: JSON.stringify({ tool_config: toolConfig(secretId) }) });
  if (!r.ok) throw new Error(`update tool ${r.status}: ${(await r.text()).slice(0, 300)}`);
  console.log("tool advance_intake updated");
} else {
  const r = await fetch(`${XI}/v1/convai/tools`, { method: "POST", headers, body: JSON.stringify({ tool_config: toolConfig(secretId) }) });
  if (!r.ok) throw new Error(`create tool ${r.status}: ${(await r.text()).slice(0, 300)}`);
  tool = await r.json();
  console.log("tool advance_intake created");
}

// 4. Agent prompt, first message and tool attachment.
const toolIds = [...new Set([...(currentPrompt.tool_ids ?? []), tool.id])];
const patch = { conversation_config: { agent: { first_message: firstMessage, prompt: { prompt: systemPrompt, tool_ids: toolIds } } } };
const r = await fetch(XI + agentPath, { method: "PATCH", headers, body: JSON.stringify(patch) });
if (!r.ok) throw new Error(`agent PATCH ${r.status}: ${(await r.text()).slice(0, 300)}`);
console.log("agent updated: prompt from prompts/06, first message set, tools attached:", toolIds.length);
