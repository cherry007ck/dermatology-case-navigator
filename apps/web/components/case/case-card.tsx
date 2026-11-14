import { CaseAttribution, CaseReviewLabels, type PlannedCaseAttribution } from "@/components/case/case-attribution";
import { EvidenceQuotes } from "@/components/evidence";
import { FICTIONAL_CASE_LABEL } from "@/components/mode-banner";
import { ModuleLabel, StatusChip } from "@/components/status";
import type { CaseCard, Collection, SupportedStatement } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export type CaseCardViewProps = {
  card: CaseCard;
  /** Collection-level review flags for the labels. */
  collection?: Pick<Collection, "clinical_reviewed">;
  /** `CaseCard.attribution` from the API (null for synthetic cards). */
  attribution?: PlannedCaseAttribution | null;
};

/** One group of case statements. A statement without evidence is withheld, never shown as a claim. */
function StatementGroup({
  title,
  items,
  empty,
  scope,
  className,
}: {
  title: string;
  items: SupportedStatement[];
  empty: string;
  scope: CaseCard;
  className?: string;
}) {
  return (
    <section className={cn("overflow-hidden rounded-sm border bg-card", className)}>
      <h4 className="dcn-band text-sm">{title}</h4>
      <div className="px-3 py-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="space-y-2">
            {items.map((s, i) => (
              <li key={`${s.text}-${i}`}>
                {s.evidence.length ? (
                  <>
                    <span>{s.text}</span>
                    <EvidenceQuotes evidence={s.evidence} scope={scope} />
                  </>
                ) : (
                  <StatusChip tone="error">Statement withheld — no supporting passage</StatusChip>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/**
 * Presentational case card: comparison with this intake (shared features, important
 * differences), the case record (documented actions and outcomes) and its source.
 * Typed props only; no data fetching and no session store.
 * Layout follows its container: one column in the narrow cases panel or on phones,
 * two columns when the card has room (≥ 42rem).
 */
export function CaseCardView({ card, collection, attribution }: CaseCardViewProps) {
  const synthetic = card.source_kind === "synthetic";
  const headingId = `case-${card.case_id}-title`;
  return (
    <article className="@container dcn-module min-w-0 rounded-md border bg-card" data-testid="case-card" aria-labelledby={headingId}>
      <header className="space-y-2 border-b px-4 py-3">
        <ModuleLabel>{synthetic ? "Fictional case" : "Case report"}</ModuleLabel>
        <h3 id={headingId} className="text-lg leading-snug font-semibold">
          {card.title}
        </h3>
        {synthetic && <StatusChip tone="warning">{FICTIONAL_CASE_LABEL}</StatusChip>}
        <CaseReviewLabels card={card} attribution={attribution} collection={collection} />
      </header>

      <div className="grid gap-4 p-4 @2xl:grid-cols-2">
        <div className="min-w-0 space-y-3">
          <h4 className="font-semibold">Comparison with this intake</h4>
          <StatementGroup title="Shared features" scope={card} items={card.shared_features} empty="None recorded." />
          <StatementGroup title="Important differences" scope={card} items={card.important_differences} empty="None recorded." />
        </div>

        <div className="dcn-clipboard min-w-0 space-y-3">
          <h4 className="border-b pb-2 font-semibold">{synthetic ? "Fictional case record" : "Case record"}</h4>
          <StatementGroup
            title={synthetic ? "Fictional recorded actions" : "Documented actions"}
            scope={card}
            items={card.actions}
            empty="No actions in the reviewed passages."
          />
          <StatementGroup
            title={synthetic ? "Fictional recorded outcomes" : "Documented outcomes"}
            scope={card}
            items={card.outcomes}
            empty="Outcome not reported in the reviewed passages."
          />
        </div>
      </div>

      <CaseAttribution card={card} attribution={attribution} />
      <p className="border-t px-4 py-2 text-sm text-muted-foreground">Examples for the doctor&apos;s review, not advice for this patient.</p>
    </article>
  );
}
