import { connection } from "next/server";

import { isVoiceConfigured } from "@/lib/server/voice-config";

// Frontend-internal: tells the browser whether this server can start a voice session.
// Returns a boolean only; no IDs, URLs or keys.
export async function GET() {
  await connection(); // evaluate env at request time, never prerendered into the build
  return Response.json({ configured: isVoiceConfigured() }, { headers: { "Cache-Control": "no-store" } });
}
