// Verify local ElevenLabs configuration WITHOUT printing any secret or ID.
//   npm run check:voice
// Reads apps/web/.env.local, checks required fields, then asks ElevenLabs for a
// signed URL exactly like the /api/voice-session route does. Prints only
// pass/fail facts (HTTP status, URL scheme), never the key, agent ID or URL.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const envPath = join(dirname(fileURLToPath(import.meta.url)), "..", ".env.local");

function loadEnv(path) {
  if (!existsSync(path)) return null;
  const env = {};
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!match) continue;
    env[match[1]] = match[2].replace(/^["']|["']$/g, "").trim();
  }
  return env;
}

const env = loadEnv(envPath);
if (!env) {
  console.error("FAIL  apps/web/.env.local not found. Copy .env.example to .env.local first.");
  process.exit(1);
}

let ok = true;
const report = (pass, message) => {
  console.log(`${pass ? "PASS" : "FAIL"}  ${message}`);
  ok &&= pass;
};

const key = env.ELEVENLABS_API_KEY ?? "";
const agent = env.ELEVENLABS_AGENT_ID ?? "";
report(key.length >= 20, `ELEVENLABS_API_KEY is set (${key ? `${key.length} characters` : "empty"})`);
report(/^agent_[A-Za-z0-9]+$/.test(agent), `ELEVENLABS_AGENT_ID looks like an agent ID (${agent ? "set" : "empty"})`);
report(/^https?:\/\//.test(env.API_INTERNAL_BASE_URL ?? ""), "API_INTERNAL_BASE_URL is an http(s) URL");
report(env.NEXT_PUBLIC_API_MODE === "live", `NEXT_PUBLIC_API_MODE is "live" (voice needs the real API for session bindings)`);
for (const name of Object.keys(env)) {
  if (name.startsWith("NEXT_PUBLIC_") && /KEY|SECRET|TOKEN/.test(name)) report(false, `${name} would expose a secret to the browser`);
}

if (key && agent) {
  const url = new URL("https://api.elevenlabs.io/v1/convai/conversation/get-signed-url");
  url.searchParams.set("agent_id", agent);
  try {
    const res = await fetch(url, { headers: { "xi-api-key": key } });
    const hint = { 401: "key rejected or expired", 403: "key lacks permission for this endpoint/agent, or IP not allowlisted", 404: "agent not found for this key's workspace", 422: "agent ID malformed" }[res.status];
    let reason = "";
    if (!res.ok) {
      // Report only the provider's machine-readable status code (e.g. invalid_api_key,
      // missing_permissions), never the message, which may echo request details.
      const detail = await res.clone().json().catch(() => null);
      const code = detail?.detail?.status ?? detail?.detail?.code;
      if (typeof code === "string" && /^[a-z_]{3,60}$/.test(code)) reason = `, provider status "${code}"`;
    }
    report(res.ok, `ElevenLabs signed-URL request: HTTP ${res.status}${hint ? ` (${hint})` : ""}${reason}`);
    if (res.ok) {
      const body = await res.json();
      const signed = typeof body.signed_url === "string" ? body.signed_url : "";
      report(signed.startsWith("wss://"), "Signed URL is a WebSocket (wss://) URL, matching connectionType \"websocket\"");
      report(signed.includes("conversation_signature="), "Signed URL carries a conversation signature (private agent flow)");
    }
  } catch {
    report(false, "Could not reach api.elevenlabs.io from this machine");
  }
}

console.log(ok ? "\nVoice configuration check passed. Values were not printed." : "\nVoice configuration check failed. Fix the FAIL lines above.");
process.exit(ok ? 0 : 1);
