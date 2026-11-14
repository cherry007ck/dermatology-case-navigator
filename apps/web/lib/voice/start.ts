// Browser-side steps before the SDK connects. No secrets pass through here:
// the signed URL and binding token are short-lived and scoped to one session.
import { ApiRequestError } from "@/lib/api/transport";
import type { ApiErrorResponse } from "@/lib/api/types";

export type MicResult = "granted" | "denied" | "no_device" | "unsupported" | "error";

/** Ask for microphone access after the user pressed Start; release it immediately (the SDK opens its own). */
export async function requestMicrophone(): Promise<MicResult> {
  if (!navigator.mediaDevices?.getUserMedia) return "unsupported";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return "granted";
  } catch (e) {
    const name = e instanceof DOMException ? e.name : "";
    if (name === "NotAllowedError" || name === "SecurityError") return "denied";
    if (name === "NotFoundError" || name === "OverconstrainedError") return "no_device";
    return "error";
  }
}

export async function fetchVoiceAvailability(): Promise<boolean> {
  try {
    const res = await fetch("/api/voice-status", { cache: "no-store" });
    if (!res.ok) return false;
    const data = (await res.json()) as { configured?: unknown };
    return data.configured === true;
  } catch {
    return false;
  }
}

export type VoiceSessionGrant = { signed_url: string; binding_token: string; expires_at: string };

export async function requestVoiceSession(
  sessionId: string,
  token: string,
  expectedRevision: number,
): Promise<VoiceSessionGrant> {
  let res: Response;
  try {
    res = await fetch("/api/voice-session", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ session_id: sessionId, expected_revision: expectedRevision, request_id: crypto.randomUUID() }),
      cache: "no-store",
    });
  } catch {
    throw new ApiRequestError(0, "NETWORK_UNAVAILABLE", "Could not reach the voice service.", true);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (data && typeof data === "object" && "error" in data) throw ApiRequestError.fromBody(res.status, data as ApiErrorResponse);
    throw new ApiRequestError(res.status, "VOICE_START_FAILED", "Voice could not start.", res.status >= 500);
  }
  return data as VoiceSessionGrant;
}
