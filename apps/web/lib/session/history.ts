// Read-only views over snapshot turns. Corrections never overwrite: a correction is a
// new patient turn whose supersedes_turn_id points at the turn it replaces.
import type { Question, SessionSnapshot, Turn } from "@/lib/api/types";

export type StatementEntry = {
  /** The version in effect now (the last correction, or the original). */
  current: Turn;
  /** Earlier versions, oldest first. Kept for the record; never used as evidence. */
  replaced: Turn[];
};

export function statementHistory(snapshot: SessionSnapshot): StatementEntry[] {
  const patient = snapshot.turns.filter((t) => t.role === "patient").sort((a, b) => a.sequence - b.sequence);
  const replacedBy = new Map<string, Turn>();
  for (const t of patient) if (t.supersedes_turn_id) replacedBy.set(t.supersedes_turn_id, t);
  return patient
    .filter((t) => !t.supersedes_turn_id) // chains start at an original statement
    .map((original) => {
      const replaced: Turn[] = [];
      let current = original;
      while (replacedBy.has(current.turn_id)) {
        replaced.push(current);
        current = replacedBy.get(current.turn_id)!;
      }
      return { current, replaced };
    });
}

export function isConfirmedCurrent(snapshot: SessionSnapshot): boolean {
  return snapshot.state === "confirmed" && snapshot.confirmed_revision === snapshot.revision;
}

export const QUESTION_STATUS_LABEL: Record<Question["status"], string> = {
  asked: "Waiting for your answer",
  answered: "Answered",
  unknown: "You said you don't know",
  skipped: "Skipped",
};

/** Doctor-facing wording: unknown and skipped are never negative findings. */
export const QUESTION_STATUS_DOCTOR: Record<Question["status"], string> = {
  asked: "Asked — no answer yet",
  answered: "Answered",
  unknown: "Patient does not know (not a negative finding)",
  skipped: "Skipped by patient (not a negative finding)",
};
