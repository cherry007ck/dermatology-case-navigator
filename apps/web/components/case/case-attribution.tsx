import { ExternalLink } from "lucide-react";

import { FICTIONAL_CASE_LABEL } from "@/components/mode-banner";
import { ModuleLabel, StatusChip } from "@/components/status";
import { buttonVariants } from "@/components/ui/button";
import type { CaseAttribution as CaseAttributionData, CaseCard, Collection } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** `CaseCard.attribution` from the generated contract (null on synthetic cards). */
export type PlannedCaseAttribution = CaseAttributionData;

export type CaseAttributionProps = {
  card: Pick<CaseCard, "source_kind" | "title" | "article_url">;
  /**
   * `undefined`: the API does not deliver attribution yet (today's contract).
   * `null`: the API says there is none (synthetic cards).
   */
  attribution?: PlannedCaseAttribution | null;
  /** `card` = full source module under a case card; `compact` = inside the source drawer. */
  variant?: "card" | "compact";
};

export type CaseReviewLabelsProps = Omit<CaseAttributionProps, "variant"> & {
  /** Collection-level review flags, used when the card itself carries none. */
  collection?: Pick<Collection, "clinical_reviewed">;
};

/** Only http(s) URLs are ever rendered as links. Anything else is shown as text or dropped. */
function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

// Identifier resolver links are built only from well-formed identifiers.
function pmcidUrl(pmcid: string) {
  return /^PMC\d+$/.test(pmcid) ? `https://pmc.ncbi.nlm.nih.gov/articles/${pmcid}/` : null;
}
function pmidUrl(pmid: string) {
  return /^\d+$/.test(pmid) ? `https://pubmed.ncbi.nlm.nih.gov/${pmid}/` : null;
}
function doiUrl(doi: string) {
  return /^10\.\d{4,9}\/\S+$/.test(doi) ? `https://doi.org/${encodeURI(doi)}` : null;
}

function formatAuthors(authors: string[]): string {
  if (authors.length === 0) return "Authors not listed";
  if (authors.length <= 3) return authors.join(", ");
  return `${authors.slice(0, 3).join(", ")} et al.`;
}

function ExternalAnchor({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) {
  return (
    <a className={cn("text-primary underline underline-offset-2 break-all", className)} href={href} target="_blank" rel="noreferrer noopener">
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/**
 * Honest review labels for a case. Developer source review and clinical review are
 * separate claims and are never merged; "reviewed" is shown only when the data says so.
 */
export function CaseReviewLabels({ card, attribution, collection }: CaseReviewLabelsProps) {
  const synthetic = card.source_kind === "synthetic";
  const clinical = attribution?.clinical_reviewed ?? collection?.clinical_reviewed;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Source and review status" data-testid="case-review-labels">
      <li>
        {synthetic ? (
          <StatusChip tone="warning">Synthetic · fictional</StatusChip>
        ) : (
          <StatusChip tone="info">Published case report</StatusChip>
        )}
      </li>
      <li>
        {synthetic ? (
          <StatusChip tone="neutral">Fixture consistency check only</StatusChip>
        ) : attribution?.source_review_status === "reviewed" ? (
          <StatusChip tone="info">Developer source-reviewed</StatusChip>
        ) : (
          <StatusChip tone="neutral">Source review status not on this card</StatusChip>
        )}
      </li>
      <li>
        {clinical === true ? (
          <StatusChip tone="ok">Clinically reviewed</StatusChip>
        ) : clinical === false ? (
          <StatusChip tone="neutral">Not clinically reviewed</StatusChip>
        ) : (
          <StatusChip tone="neutral">Clinical review status unknown</StatusChip>
        )}
      </li>
    </ul>
  );
}

/**
 * Source and attribution for one case. Synthetic cases never show article metadata
 * or links. Published cases show the original article link and, once the API supplies
 * it, the citation, identifiers and licence. Nothing is inferred or filled in locally.
 */
export function CaseAttribution({ card, attribution, variant = "card" }: CaseAttributionProps) {
  const synthetic = card.source_kind === "synthetic";
  const articleUrl = synthetic ? null : safeHttpUrl(card.article_url);
  const compact = variant === "compact";

  if (synthetic) {
    return (
      <section className={cn("space-y-2", !compact && "border-t bg-muted/40 px-4 py-3")} aria-label="Source" data-testid="case-attribution">
        {!compact && <ModuleLabel>Source</ModuleLabel>}
        {!compact && <p className="font-medium">{FICTIONAL_CASE_LABEL}</p>}
        <p className="text-sm text-muted-foreground">
          Team-authored fictional fixture. It has no article, authors, journal, identifiers or external link.
        </p>
      </section>
    );
  }

  const a = attribution ?? null;
  const licenseUrl = safeHttpUrl(a?.license_url);
  const identifiers = a
    ? [
        { label: "PMCID", value: a.pmcid, href: pmcidUrl(a.pmcid) },
        ...(a.pmid ? [{ label: "PMID", value: a.pmid, href: pmidUrl(a.pmid) }] : []),
        ...(a.doi ? [{ label: "DOI", value: a.doi, href: doiUrl(a.doi) }] : []),
      ]
    : [];

  return (
    <section className={cn("space-y-3", !compact && "border-t bg-muted/40 px-4 py-3")} aria-label="Source" data-testid="case-attribution">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {!compact && <ModuleLabel>Source</ModuleLabel>}
        {articleUrl ? (
          <a
            href={articleUrl}
            target="_blank"
            rel="noreferrer noopener"
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-10 px-3 text-sm")}
          >
            Open original article
            <ExternalLink aria-hidden="true" />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        ) : (
          <StatusChip tone="warning">Original article link missing</StatusChip>
        )}
      </div>

      {a ? (
        <>
          <p className="text-sm" data-testid="case-citation">
            {formatAuthors(a.authors)}. {card.title}. <cite className="not-italic font-medium">{a.journal}</cite>. {a.year}.
          </p>
          <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
            {identifiers.map((id) => (
              <div key={id.label} className="contents">
                <dt className="font-mono text-xs leading-5 text-muted-foreground uppercase">{id.label}</dt>
                <dd className="min-w-0 break-all">{id.href ? <ExternalAnchor href={id.href}>{id.value}</ExternalAnchor> : id.value}</dd>
              </div>
            ))}
            <dt className="font-mono text-xs leading-5 text-muted-foreground uppercase">Licence</dt>
            <dd className="min-w-0">{licenseUrl ? <ExternalAnchor href={licenseUrl}>{a.license_name}</ExternalAnchor> : a.license_name}</dd>
          </dl>
        </>
      ) : (
        <p className="text-sm text-muted-foreground" data-testid="attribution-pending">
          Authors, journal, year, identifiers and licence are not yet supplied for this card. Use the original article for the full
          citation.
        </p>
      )}
    </section>
  );
}
