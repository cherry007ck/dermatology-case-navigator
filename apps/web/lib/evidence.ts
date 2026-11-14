// Resolve an EvidenceRef against the snapshot it came from. The UI never shows a
// citation it cannot resolve: unresolved or non-matching quotes become explicit
// "withheld" states instead of decorative badges.
import type { CaseCard, EvidenceRef, Passage, SessionSnapshot, Turn } from "@/lib/api/types";

export type { Passage };

export type ResolvedSource =
  | {
      status: "ok";
      kind: "patient_turn";
      ref: EvidenceRef;
      turn: Turn;
      quoteStart: number;
    }
  | {
      status: "ok";
      kind: "case_passage";
      ref: EvidenceRef;
      passage: Passage;
      card: CaseCard;
      quoteStart: number;
    }
  | { status: "missing_source" | "quote_mismatch" | "agent_turn"; ref: EvidenceRef };

export function resolveEvidence(ref: EvidenceRef, snapshot: SessionSnapshot, scope?: CaseCard): ResolvedSource {
  if (ref.source_type === "patient_turn") {
    const turn = snapshot.turns.find((t) => t.turn_id === ref.source_id);
    if (!turn) return { status: "missing_source", ref };
    if (turn.role !== "patient") return { status: "agent_turn", ref }; // agent turns are never evidence
    const quoteStart = turn.text.indexOf(ref.quote);
    return quoteStart < 0 ? { status: "quote_mismatch", ref } : { status: "ok", kind: "patient_turn", ref, turn, quoteStart };
  }
  // Case passages resolve only within the owning card: a quote from another case is not support.
  const cards = scope ? [scope] : snapshot.search_history.flatMap((s) => s.cards);
  for (const card of cards) {
    const passage = card.passages.find((p) => p.passage_id === ref.source_id && p.case_id === card.case_id);
    if (!passage) continue;
    const quoteStart = passage.text.indexOf(ref.quote);
    return quoteStart < 0
      ? { status: "quote_mismatch", ref }
      : { status: "ok", kind: "case_passage", ref, passage, card, quoteStart };
  }
  return { status: "missing_source", ref };
}
