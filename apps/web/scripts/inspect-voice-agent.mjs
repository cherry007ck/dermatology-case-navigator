// Read-only inspection of the configured ElevenLabs agent. Prints non-secret configuration only:
// name, LLM, first lines of the system prompt, first message, tools (name, type, URL host/path,
// header NAMES only) and dynamic variable names. Never prints the API key, agent ID or header values.
//   node scripts/inspect-voice-agent.mjs
import { readFileSync } from "node:fs";

const env = Object.fromEntries(readFileSync(new URL("../.env.local", import.meta.url), "utf8").split(/\r?\n/)
  .map((l) => l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/)).filter(Boolean)
  .map((m) => [m[1], m[2].replace(/^["']|["']$/g, "").trim()]));
const headers = { "xi-api-key": env.ELEVENLABS_API_KEY };
const res = await fetch(`https://api.elevenlabs.io/v1/convai/agents/${encodeURIComponent(env.ELEVENLABS_AGENT_ID)}`, { headers });
console.log("GET agent:", res.status);
if (!res.ok) process.exit(1);
const a = await res.json();
const cfg = a.conversation_config ?? {};
const agent = cfg.agent ?? {};
const prompt = agent.prompt ?? {};
console.log("name:", a.name);
console.log("llm:", prompt.llm, "| temperature:", prompt.temperature);
console.log("first_message:", JSON.stringify(agent.first_message ?? ""));
console.log("prompt (first 600 chars):", JSON.stringify((prompt.prompt ?? "").slice(0, 600)));
console.log("prompt length:", (prompt.prompt ?? "").length);
const inline = prompt.tools ?? [];
console.log("inline tools:", inline.map((t) => ({ name: t.name, type: t.type, url: t.api_schema?.url ? new URL(t.api_schema.url).host + new URL(t.api_schema.url).pathname : undefined,
  method: t.api_schema?.method, header_names: Object.keys(t.api_schema?.request_headers ?? {}) })));
console.log("tool_ids count:", (prompt.tool_ids ?? []).length);
for (const id of prompt.tool_ids ?? []) {
  const t = await fetch(`https://api.elevenlabs.io/v1/convai/tools/${encodeURIComponent(id)}`, { headers });
  if (!t.ok) { console.log(" tool fetch:", t.status); continue; }
  const tool = (await t.json()).tool_config ?? {};
  const url = tool.api_schema?.url;
  console.log(" tool:", { name: tool.name, type: tool.type, method: tool.api_schema?.method,
    url: url ? (() => { try { const u = new URL(url); return u.host + u.pathname; } catch { return "(templated)"; } })() : undefined,
    header_names: Object.keys(tool.api_schema?.request_headers ?? {}) });
}
console.log("dynamic variable names:", Object.keys(agent.dynamic_variables?.dynamic_variable_placeholders ?? {}));
const auth = a.platform_settings?.auth ?? {};
console.log("auth enabled (private agent):", auth.enable_auth, "| allowlist hosts:", (auth.allowlist ?? []).map((h) => h.hostname));
console.log("overrides allowed:", JSON.stringify(a.platform_settings?.overrides?.conversation_config_override ?? {}));
