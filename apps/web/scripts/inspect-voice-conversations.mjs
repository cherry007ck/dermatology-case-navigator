// Diagnose recent agent conversations WITHOUT printing transcripts, IDs or secrets.
//   npm run inspect:voice
// Prints per conversation: status, duration, turn counts by role, whether the agent
// replied after the last user turn, the provider's termination reason category, and
// whether any tool calls happened. Requires an API key that can read conversations.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const envPath = join(dirname(fileURLToPath(import.meta.url)), "..", ".env.local");
if (!existsSync(envPath)) {
  console.error("FAIL  apps/web/.env.local not found.");
  process.exit(1);
}
const env = Object.fromEntries(
  readFileSync(envPath, "utf8")
    .split(/\r?\n/)
    .map((l) => l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/))
    .filter(Boolean)
    .map((m) => [m[1], m[2].replace(/^["']|["']$/g, "")]),
);
const headers = { "xi-api-key": env.ELEVENLABS_API_KEY ?? "" };
const base = "https://api.elevenlabs.io/v1/convai";

async function get(path) {
  const res = await fetch(`${base}${path}`, { headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const code = body?.detail?.status ?? "";
    console.error(`FAIL  HTTP ${res.status}${/^[a-z_]{3,60}$/.test(code) ? ` provider status "${code}"` : ""}`);
    process.exit(1);
  }
  return res.json();
}

// Only short machine-like categories are printed; free text could echo speech.
const safe = (v) => (typeof v === "string" && /^[A-Za-z0-9 _.:-]{1,60}$/.test(v) ? v : v ? "<text omitted>" : "none");

const list = await get(`/conversations?agent_id=${encodeURIComponent(env.ELEVENLABS_AGENT_ID ?? "")}&page_size=5`);
const items = list.conversations ?? [];
console.log(`Recent conversations for the configured agent: ${items.length}`);
for (const [index, item] of items.entries()) {
  const detail = await get(`/conversations/${encodeURIComponent(item.conversation_id)}`);
  const transcript = Array.isArray(detail.transcript) ? detail.transcript : [];
  const roles = transcript.map((t) => t.role);
  const lastUser = roles.lastIndexOf("user");
  const agentAfterUser = lastUser >= 0 && roles.slice(lastUser + 1).includes("agent");
  const toolCalls = transcript.reduce((n, t) => n + (Array.isArray(t.tool_calls) ? t.tool_calls.length : 0), 0);
  const emptyAgentTurns = transcript.filter((t) => t.role === "agent" && !String(t.message ?? "").trim()).length;
  const meta = detail.metadata ?? {};
  console.log(
    [
      `#${index + 1}`,
      `status=${safe(detail.status)}`,
      `duration_s=${meta.call_duration_secs ?? "?"}`,
      `turns: user=${roles.filter((r) => r === "user").length} agent=${roles.filter((r) => r === "agent").length}`,
      `agent_replied_after_last_user=${agentAfterUser}`,
      `empty_agent_turns=${emptyAgentTurns}`,
      `tool_calls=${toolCalls}`,
      `termination=${safe(meta.termination_reason)}`,
      `error=${safe(meta.error?.code ?? meta.error?.reason ?? "")}`,
    ].join("  "),
  );
  if (process.argv.includes("--turns")) {
    for (const t of transcript) {
      const length = String(t.message ?? "").length;
      const flags = [t.interrupted ? "interrupted" : "", t.tool_calls?.length ? `tools=${t.tool_calls.length}` : ""].filter(Boolean).join(",");
      // Numeric latency metrics only (seconds), e.g. LLM time-to-first-byte; never text.
      const metrics = t.conversation_turn_metrics?.metrics ?? {};
      const numbers = Object.entries(metrics)
        .map(([name, m]) => [name, typeof m?.elapsed_time === "number" ? m.elapsed_time : null])
        .filter(([name, v]) => v !== null && /^[a-z_]{1,40}$/.test(name))
        .map(([name, v]) => `${name}=${v.toFixed(2)}s`)
        .join(" ");
      console.log(`      t=${t.time_in_call_secs ?? "?"}s  ${t.role}  chars=${length}${flags ? `  ${flags}` : ""}${numbers ? `  ${numbers}` : ""}`);
    }
  }
}
