"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import { CaseAttribution, CaseReviewLabels } from "@/components/case/case-attribution";
import { FICTIONAL_CASE_LABEL } from "@/components/mode-banner";
import { ModuleLabel, StatusChip } from "@/components/status";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import type { CaseCard, EvidenceRef, SessionSnapshot } from "@/lib/api/types";
import { resolveEvidence, type ResolvedSource } from "@/lib/evidence";

type OpenSource = (ref: EvidenceRef, trigger: HTMLElement, scope?: CaseCard) => void;

const SourceDrawerContext = createContext<OpenSource | null>(null);

export function useOpenSource(): OpenSource | null {
  return useContext(SourceDrawerContext);
}

/** Provides the source drawer for every evidence chip rendered inside it. */
export function SourceDrawerProvider({ snapshot, children }: { snapshot: SessionSnapshot; children: React.ReactNode }) {
  const [source, setSource] = useState<ResolvedSource | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const open = useCallback<OpenSource>(
    (ref, trigger, scope) => {
      triggerRef.current = trigger;
      setSource(resolveEvidence(ref, snapshot, scope));
    },
    [snapshot],
  );

  const value = useMemo(() => open, [open]);

  return (
    <SourceDrawerContext.Provider value={value}>
      {children}
      <Sheet open={source !== null} onOpenChange={(isOpen) => !isOpen && setSource(null)}>
        {/* Right-side panel on desktop; full-width on phones. Escape closes; focus returns to the clicked chip. */}
        <SheetContent
          side="right"
          finalFocus={triggerRef}
          className="w-full overflow-y-auto bg-background text-base data-[side=right]:w-full data-[side=right]:border-primary/40 data-[side=right]:sm:max-w-lg"
          data-testid="source-drawer"
        >
          {source && <SourceDetails source={source} snapshot={snapshot} />}
        </SheetContent>
      </Sheet>
    </SourceDrawerContext.Provider>
  );
}

/** The exact quote, then the full source text with the quote highlighted in place. */
function Highlighted({ text, start, length, sourceLabel }: { text: string; start: number; length: number; sourceLabel: string }) {
  return (
    <div className="space-y-3">
      <section className="overflow-hidden rounded-sm border" aria-label="Exact quote">
        <h3 className="dcn-band text-sm">Exact quote</h3>
        <blockquote className="px-3 py-2 text-lg leading-snug" data-testid="drawer-quote">
          “{text.slice(start, start + length)}”
        </blockquote>
      </section>
      <section className="overflow-hidden rounded-sm border" aria-label={sourceLabel}>
        <h3 className="dcn-band text-sm">{sourceLabel}</h3>
        <p className="px-3 py-2 leading-relaxed">
          {text.slice(0, start)}
          <mark className="rounded-sm bg-secondary px-0.5 text-secondary-foreground ring-1 ring-primary/40">
            {text.slice(start, start + length)}
          </mark>
          {text.slice(start + length)}
        </p>
      </section>
    </div>
  );
}

function Details({ children }: { children: React.ReactNode }) {
  return (
    <dl className="grid grid-cols-[minmax(0,8rem)_minmax(0,1fr)] gap-x-3 gap-y-2 rounded-sm border bg-card px-3 py-2 text-sm [&_dt]:font-mono [&_dt]:text-xs [&_dt]:leading-5 [&_dt]:text-muted-foreground [&_dt]:uppercase [&_dd]:min-w-0">
      {children}
    </dl>
  );
}

function SourceDetails({ source, snapshot }: { source: ResolvedSource; snapshot: SessionSnapshot }) {
  if (source.status !== "ok") {
    const reason = {
      missing_source: "The referenced source is not in this encounter.",
      quote_mismatch: "The quoted text does not appear in the referenced source.",
      agent_turn: "Agent speech is context only and never supports a patient fact.",
    }[source.status];
    return (
      <>
        <SheetHeader className="border-b pr-12">
          <ModuleLabel>Source check</ModuleLabel>
          <SheetTitle className="text-lg">Claim withheld — source could not be verified</SheetTitle>
          <SheetDescription>{reason}</SheetDescription>
        </SheetHeader>
        <div className="space-y-2 px-4 pb-4">
          <StatusChip tone="error">Unverified reference {source.ref.source_id}</StatusChip>
          <p className="text-muted-foreground">Quoted text: “{source.ref.quote}”</p>
        </div>
      </>
    );
  }

  if (source.kind === "patient_turn") {
    const { turn } = source;
    return (
      <>
        <SheetHeader className="border-b pr-12">
          <ModuleLabel>Patient source</ModuleLabel>
          <SheetTitle className="text-lg">Patient statement</SheetTitle>
          <SheetDescription>
            Exact words from the patient, turn {turn.sequence}
            {turn.origin === "voice_transcript" ? " — voice transcript, reviewed by the patient before confirmation" : ""}
            {turn.origin === "correction" ? " — patient correction" : ""}.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-3 px-4 pb-4">
          <Highlighted text={turn.text} start={source.quoteStart} length={source.ref.quote.length} sourceLabel="Full patient turn" />
          <Details>
            <dt>Source type</dt>
            <dd>Patient turn ({turn.origin === "typed" ? "typed" : turn.origin === "voice_transcript" ? "voice transcript" : "correction"})</dd>
            <dt>Turn ID</dt>
            <dd className="font-mono text-xs break-all">{turn.turn_id}</dd>
            <dt>Recorded</dt>
            <dd>{new Date(turn.created_at).toLocaleString()}</dd>
          </Details>
        </div>
      </>
    );
  }

  const { passage, card } = source;
  const synthetic = card.source_kind === "synthetic";
  const collection = snapshot.collection;
  return (
    <>
      <SheetHeader className="border-b pr-12">
        <ModuleLabel>{synthetic ? "Fictional case source" : "Case report source"}</ModuleLabel>
        <SheetTitle className="text-lg">{synthetic ? "Fictional case passage" : "Case passage"}</SheetTitle>
        <SheetDescription>{card.title}</SheetDescription>
      </SheetHeader>
      <div className="space-y-3 px-4 pb-4">
        {synthetic && <StatusChip tone="warning">{FICTIONAL_CASE_LABEL}</StatusChip>}
        <CaseReviewLabels card={card} collection={collection} attribution={card.attribution ?? null} />
        <Highlighted
          text={passage.text}
          start={source.quoteStart}
          length={source.ref.quote.length}
          sourceLabel={synthetic ? "Full fictional passage" : "Full reviewed passage"}
        />
        <Details>
          <dt>Section</dt>
          <dd>{passage.section}</dd>
          <dt>Locator</dt>
          <dd className="break-all">{passage.locator}</dd>
          <dt>Passage ID</dt>
          <dd className="font-mono text-xs break-all">{passage.passage_id}</dd>
          <dt>Passage hash</dt>
          <dd className="font-mono text-xs break-all" title={`SHA-256 ${passage.sha256}`}>
            SHA-256 {passage.sha256.slice(0, 16)}…
          </dd>
          <dt>Review</dt>
          <dd>
            {synthetic
              ? "Fixture consistency check only (quote and ID match). Not published evidence."
              : "Developer source review recorded for this collection."}{" "}
            {collection.clinical_reviewed ? "Clinically reviewed." : "Not clinically reviewed."}
          </dd>
        </Details>
        <CaseAttribution card={card} variant="compact" />
      </div>
    </>
  );
}
