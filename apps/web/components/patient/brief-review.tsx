"use client";

import { Panel, StatusChip } from "@/components/status";
import type { BriefItem, SessionSnapshot } from "@/lib/api/types";

type Section = { title: string; items: BriefItem[]; empty: string };

/**
 * The AI-prepared summary the doctor will receive, shown to the patient before confirmation.
 * It shows patient-derived brief sections only, each line with the patient's own quoted words.
 * Case content, case IDs, doctor clarifications and clinician notes are deliberately absent.
 */
export function BriefReview({ snapshot }: { snapshot: SessionSnapshot }) {
  const brief = snapshot.brief;
  const current = brief !== null && brief.patient_revision === snapshot.revision;

  if (!brief) {
    return (
      <Panel title="Summary for your doctor" testId="brief-review">
        <p className="text-muted-foreground">The summary appears after your first statement is processed.</p>
      </Panel>
    );
  }

  const sections: Section[] = [
    { title: "What you described", items: brief.summary_items, empty: "Nothing captured yet." },
    { title: "Timing and products you mentioned", items: brief.timeline_items, empty: "Nothing captured." },
    { title: "Treatment you mentioned", items: brief.prior_treatment_items, empty: "Nothing captured." },
    { title: "Still open", items: brief.unresolved_items, empty: "Nothing open." },
  ];

  return (
    <Panel title="Summary for your doctor" testId="brief-review">
      <p className="mb-3 text-sm text-muted-foreground">
        Prepared automatically from your own words below and checked against them. It is not a diagnosis. If a
        line is wrong, correct your statement; the summary is rebuilt from your corrected words.
      </p>
      {!current && (
        <p role="status" className="mb-3" data-testid="brief-review-stale">
          <StatusChip tone="warning">Updating</StatusChip> The summary is being rebuilt for your latest statement.
        </p>
      )}
      <div className={current ? "space-y-4" : "space-y-4 opacity-60"} aria-busy={!current}>
        {sections.map((s) => (
          <section key={s.title} aria-label={s.title}>
            <h3 className="font-semibold">{s.title}</h3>
            {s.items.length === 0 ? (
              <p className="text-muted-foreground">{s.empty}</p>
            ) : (
              <ul className="mt-1 space-y-2">
                {s.items.map((item, i) => (
                  <li key={`${s.title}-${i}`} data-testid="brief-review-item">
                    <p>
                      {item.text}
                      {item.status === "conflicting" && (
                        <>
                          {" "}
                          <StatusChip tone="warning">Conflicting</StatusChip>
                        </>
                      )}
                    </p>
                    {item.evidence.length > 0 && (
                      <p className="text-sm text-muted-foreground">
                        Your words:{" "}
                        {item.evidence
                          .filter((e) => e.source_type === "patient_turn")
                          .map((e) => `“${e.quote}”`)
                          .join(", ")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
      {current && (
        <div className="mt-3">
          <StatusChip tone="neutral">Summary for revision {brief.patient_revision}</StatusChip>
        </div>
      )}
    </Panel>
  );
}
