import "server-only";

// Server-only voice configuration. ELEVENLABS_API_KEY never leaves this module:
// it is not logged, not returned and not referenced from client components.

export type VoiceServerConfig = {
  apiKey: string;
  agentId: string;
  apiInternalBaseUrl: string;
  allowedOrigins: string[];
};

export function readVoiceConfig(): VoiceServerConfig | null {
  const apiKey = process.env.ELEVENLABS_API_KEY?.trim() ?? "";
  const agentId = process.env.ELEVENLABS_AGENT_ID?.trim() ?? "";
  const apiInternalBaseUrl = (process.env.API_INTERNAL_BASE_URL?.trim() ?? "").replace(/\/$/, "");
  if (!apiKey || !agentId || !apiInternalBaseUrl) return null;
  return {
    apiKey,
    agentId,
    apiInternalBaseUrl,
    allowedOrigins: (process.env.VOICE_ALLOWED_ORIGINS ?? "")
      .split(",")
      .map((o) => o.trim())
      .filter(Boolean),
  };
}

export function isVoiceConfigured(): boolean {
  return readVoiceConfig() !== null;
}
