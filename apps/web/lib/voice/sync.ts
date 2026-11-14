// Maps captured voice transcript events to contract TurnInputs.
// Only finalized SDK events reach here (see transcript.ts). Agent turns are stored
// for context but never support patient facts (backend rule). A patient turn is
// linked to the question currently pending in the latest snapshot, if any; the
// backend may also link a later turn to the pending question by sequence.
import type { SessionSnapshot, TurnInput } from "@/lib/api/types";

import type { CapturedTurn } from "./transcript";

export const MAX_TURN_CHARS = 4_000;

export function pendingQuestionId(snapshot: SessionSnapshot | null): string | null {
  if (!snapshot || snapshot.state !== "awaiting_answer") return null;
  return snapshot.questions.find((q) => q.status === "asked")?.question_id ?? null;
}

export function toTurnInput(turn: CapturedTurn, snapshot: SessionSnapshot | null): TurnInput {
  return {
    turn_id: turn.turnId,
    role: turn.role,
    origin: "voice_transcript",
    text: turn.text.slice(0, MAX_TURN_CHARS),
    reply_to_question_id: turn.role === "patient" ? pendingQuestionId(snapshot) : null,
  };
}
