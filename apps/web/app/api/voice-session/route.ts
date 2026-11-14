import type { NextRequest } from "next/server";

import { allowRequest } from "@/lib/server/rate-limit";
import { readVoiceConfig } from "@/lib/server/voice-config";

// POST /api/voice-session (docs/03-api-contract.md, voice step 1).
// Request:  { session_id, expected_revision, request_id } + Authorization: Bearer <session token>
// Response: { signed_url, binding_token, expires_at }
//
// 1. same-origin, body-size, rate-limit and shape checks
// 2. backend verifies the session bearer and issues a scoped voice binding
// 3. ElevenLabs issues a signed WebSocket URL using the server-only API key
// Nothing here is logged; provider and backend bodies are never forwarded verbatim.

const MAX_BODY_BYTES = 2_048;
const RATE_LIMIT_PER_MINUTE = 10;
const NO_STORE = { "Cache-Control": "no-store" };

function error(status: number, code: string, message: string, retryable: boolean, requestId: string | null = null) {
  return Response.json({ error: { code, message, retryable }, request_id: requestId }, { status, headers: NO_STORE });
}

function sameOrigin(req: NextRequest, allowed: string[]): boolean {
  const origin = req.headers.get("origin");
  if (!origin) return false;
  const fetchSite = req.headers.get("sec-fetch-site");
  if (fetchSite && fetchSite !== "same-origin") return false;
  return origin === req.nextUrl.origin || allowed.includes(origin);
}

type Body = { session_id: string; expected_revision: number; request_id: string };

function parseBody(raw: unknown): Body | null {
  if (!raw || typeof raw !== "object") return null;
  const { session_id, expected_revision, request_id, ...rest } = raw as Record<string, unknown>;
  if (Object.keys(rest).length) return null;
  if (typeof session_id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(session_id)) return null;
  if (typeof request_id !== "string" || request_id.length < 1 || request_id.length > 64) return null;
  if (typeof expected_revision !== "number" || !Number.isInteger(expected_revision) || expected_revision < 0) return null;
  return { session_id, expected_revision, request_id };
}

export async function POST(req: NextRequest) {
  const config = readVoiceConfig();
  if (!sameOrigin(req, config?.allowedOrigins ?? [])) return error(403, "FORBIDDEN_ORIGIN", "Request origin not allowed.", false);

  const length = Number(req.headers.get("content-length") ?? "0");
  if (length > MAX_BODY_BYTES) return error(413, "BODY_TOO_LARGE", "Request body too large.", false);

  const client = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "local";
  if (!allowRequest(`voice-session:${client}`, RATE_LIMIT_PER_MINUTE)) {
    return error(429, "RATE_LIMITED", "Too many voice start attempts. Wait a minute and retry.", true);
  }

  const authorization = req.headers.get("authorization") ?? "";
  if (!/^Bearer \S+$/.test(authorization)) return error(401, "UNAUTHORIZED", "Session token required.", false);

  const text = await req.text();
  if (text.length > MAX_BODY_BYTES) return error(413, "BODY_TOO_LARGE", "Request body too large.", false);
  let raw: unknown = null;
  try {
    raw = JSON.parse(text);
  } catch {
    /* handled below */
  }
  const body = parseBody(raw);
  if (!body) return error(422, "VALIDATION_ERROR", "The request does not match the API contract.", false);

  if (!config) return error(503, "VOICE_NOT_CONFIGURED", "Voice is not configured on this server. Use typed intake.", false, body.request_id);

  // Step 2: backend authenticates the session bearer and issues the scoped binding.
  let binding: { binding_token: string; expires_at: string };
  try {
    const res = await fetch(`${config.apiInternalBaseUrl}/v1/sessions/${encodeURIComponent(body.session_id)}/voice-binding`, {
      method: "POST",
      headers: { Authorization: authorization, "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: body.request_id, expected_revision: body.expected_revision }),
      cache: "no-store",
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      // Backend errors use the shared safe envelope; pass only code/message/retryable through.
      const e = data?.error;
      if (e && typeof e.code === "string" && typeof e.message === "string") {
        return error(res.status, e.code, e.message, Boolean(e.retryable), body.request_id);
      }
      return error(502, "API_UNAVAILABLE", "The intake API did not respond as expected.", true, body.request_id);
    }
    binding = data;
  } catch {
    return error(503, "API_UNAVAILABLE", "The intake API could not be reached.", true, body.request_id);
  }

  // Step 3: signed WebSocket URL from ElevenLabs (expires ~15 minutes after issue per provider docs).
  try {
    const url = new URL("https://api.elevenlabs.io/v1/convai/conversation/get-signed-url");
    url.searchParams.set("agent_id", config.agentId);
    const res = await fetch(url, { headers: { "xi-api-key": config.apiKey }, cache: "no-store" });
    if (!res.ok) {
      return error(502, "VOICE_PROVIDER_UNAVAILABLE", "The voice service could not start a session. Use typed intake or retry.", true, body.request_id);
    }
    const data = (await res.json()) as { signed_url?: unknown };
    if (typeof data.signed_url !== "string" || !data.signed_url.startsWith("wss://")) {
      return error(502, "VOICE_PROVIDER_UNAVAILABLE", "The voice service returned an unexpected response.", true, body.request_id);
    }
    return Response.json(
      { signed_url: data.signed_url, binding_token: binding.binding_token, expires_at: binding.expires_at },
      { headers: NO_STORE },
    );
  } catch {
    return error(503, "VOICE_PROVIDER_UNAVAILABLE", "The voice service could not be reached.", true, body.request_id);
  }
}
