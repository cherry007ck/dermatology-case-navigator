"use client";

import { useOpenSource } from "@/components/source-drawer";
import type { CaseCard, EvidenceRef } from "@/lib/api/types";

/**
 * Exact quotes for a claim. Inside a SourceDrawerProvider each quote is a button
 * that opens the source drawer (exact passage, origin, review status).
 * `scope` restricts case-passage resolution to the owning card.
 */
export function EvidenceQuotes({ evidence, scope }: { evidence: EvidenceRef[]; scope?: CaseCard }) {
  const open = useOpenSource();
  if (!evidence.length) return null;
  return (
    <ul className="mt-1 flex flex-wrap gap-2">
      {evidence.map((ref, i) => {
        const label = ref.source_type === "patient_turn" ? "Patient quote" : "Case passage quote";
        const content = (
          <>
            <span className="sr-only">{label}: </span>“{ref.quote}”
          </>
        );
        return (
          <li key={`${ref.source_id}-${i}`}>
            {open ? (
              <button
                type="button"
                data-testid="evidence-chip"
                onClick={(e) => open(ref, e.currentTarget, scope)}
                className="rounded-sm border border-primary/25 bg-card px-2 py-0.5 text-left text-sm break-words text-secondary-foreground underline-offset-2 hover:border-primary hover:bg-secondary hover:underline"
                aria-label={`${label}: “${ref.quote}”. Open source`}
              >
                {content}
              </button>
            ) : (
              <span className="rounded-sm border bg-muted px-2 py-0.5 text-sm break-words text-muted-foreground">{content}</span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
