// Normalizes ElevenLabs SDK transcript callbacks into one shape (verified against
// @elevenlabs/client 1.36.0, via @elevenlabs/react 1.22.0):
//   onMessage({ message, event_id, role: "user" | "agent", source })
// The SDK emits role "user" only for `user_transcription_event` (finalized ASR;
// tentative user transcripts are not delivered to onMessage) and role "agent" for
// `agent_response`. Agent truncations after interruption arrive separately via
// onAgentResponseCorrection and are not captured in S1.
//
// S1 captures and displays these; S2 persists finalized patient turns through
// POST /v1/sessions/{id}/turns with these stable IDs and a serialized queue.
import type { MessagePayload } from "@elevenlabs/react";

export type CapturedTurn = {
  /** Stable, event-derived ID: identical SDK events dedupe to one turn. */
  turnId: string;
  role: "patient" | "agent";
  text: string;
  eventId: number;
  capturedAt: string;
};

export function normalizeMessage(conversationId: string, payload: MessagePayload): CapturedTurn | null {
  const text = payload.message?.trim();
  if (!text) return null;
  const role = payload.role === "user" ? "patient" : "agent";
  return {
    turnId: `voice-${conversationId}-${role}-${payload.event_id}`,
    role,
    text: payload.message, // exact ASR/agent text; never rewritten
    eventId: payload.event_id,
    capturedAt: new Date().toISOString(),
  };
}

/** Append if new; returns the same array when the turn ID was already captured. */
export function appendUnique(turns: CapturedTurn[], next: CapturedTurn): CapturedTurn[] {
  return turns.some((t) => t.turnId === next.turnId) ? turns : [...turns, next];
}
