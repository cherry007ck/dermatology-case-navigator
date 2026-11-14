"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ClinicianNotePanel } from "@/components/doctor/clinician-note-panel";
import { ComparisonHistory } from "@/components/doctor/comparison-history";
import { CaseCardView } from "@/components/case/case-card";
import { EvidenceQuotes } from "@/components/evidence";
import { ModeBanner, SnapshotWarnings } from "@/components/mode-banner";
import { SourceDrawerProvider } from "@/components/source-drawer";
import { ModuleLabel, Notice, Panel, StatusChip } from "@/components/status";
import { Button } from "@/components/ui/button";
import { ApiRequestError, getApiClient } from "@/lib/api/client";
import type { BriefItem, ClinicianNote, SearchVersion, SessionSnapshot } from "@/lib/api/types";
import { isConfirmedCurrent, QUESTION_STATUS_DOCTOR } from "@/lib/session/history";
import { useLastConfirmedRevision, useSessionToken } from "@/lib/session-store";
import { cn } from "@/lib/utils";

const NO_MATCH_TEXT: Record<NonNullable<SearchVersion["no_match_reason"]>, string> = {
  insufficient_information: "Not enough explicitly reported detail to compare: a symptom needs to be stated together with its body site.",
  conflicting_details: "Conflicting details prevent a fair comparison with cases in this collection.",
  no_comparable_cases: "No case in this collection documents the same symptom at the same body site that the patient reported.",
};

function BriefList({ title, items, empty, className }: { title: string; items: BriefItem[]; empty: string; className?: string }) {
  return (
    <section className={cn("min-w-0 overflow-hidden rounded-sm border", className)}>
      <h3 className="dcn-band">{title}</h3>
      {items.length === 0 ? (
        <p className="px-3 py-2 text-muted-foreground">{empty}</p>
      ) : (
        <ul className="space-y-3 px-3 py-2">
          {items.map((item, i) => (
            <li key={`${item.text}-${i}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span>{item.text}</span>
                {item.status === "missing" && <StatusChip tone="warning">Missing</StatusChip>}
                {item.status === "conflicting" && <StatusChip tone="error">Conflicting</StatusChip>}
              </div>
              <EvidenceQuotes evidence={item.evidence} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function DoctorWorkspace() {
  const { session_id: rawId } = useParams<{ session_id: string }>();
  const sessionId = decodeURIComponent(rawId);
  const api = getApiClient();
  const token = useSessionToken(sessionId);
  const lastConfirmed = useLastConfirmedRevision(sessionId);
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [error, setError] = useState<{ message: string; retryable: boolean } | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!token) return;
    api.getSession(sessionId, token).then(
      (snap) => {
        setSnapshot(snap);
        setError(null);
        setLoadedAt(new Date().toLocaleTimeString());
      },
      (e) =>
        setError({
          message: e instanceof ApiRequestError ? e.message : "Could not load the session.",
          retryable: !(e instanceof ApiRequestError) || e.retryable || e.code === "NETWORK_UNAVAILABLE",
        }),
    );
  }, [api, sessionId, token]);

  useEffect(load, [load]);

  const addNote = useCallback(
    (note: ClinicianNote) => setSnapshot((prev) => (prev ? { ...prev, clinician_notes: [...prev.clinician_notes, note] } : prev)),
    [],
  );

  if (token === null) {
    return (
      <Notice tone="error">
        This tab has no access to that encounter.{" "}
        <Link className="underline" href="/">
          Start a new fictional encounter
        </Link>
        .
      </Notice>
    );
  }
  if (!snapshot && error) {
    return (
      <Notice tone="error">
        {error.message}
        {error.retryable && (
          <Button variant="outline" size="sm" className="ml-2" onClick={load}>
            Retry
          </Button>
        )}
      </Notice>
    );
  }
  if (!snapshot) return <p role="status">Loading doctor workspace…</p>;

  const confirmed = isConfirmedCurrent(snapshot);
  const header = (
    <header className="dcn-module rounded-md border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
          <ModuleLabel>Consultation brief</ModuleLabel>
          <h1 className="text-2xl font-semibold">Doctor workspace</h1>
        </div>
        <Button variant="outline" size="lg" className="h-10 px-4" onClick={load}>
          Refresh
        </Button>
      </div>
      <div className="space-y-3 px-4 py-3 sm:px-6">
        <ModeBanner apiMode={api.mode} snapshot={snapshot} />
        <div className="flex flex-wrap gap-2 text-sm">
          <StatusChip tone={confirmed ? "ok" : "warning"}>
            {confirmed ? `Patient confirmed revision ${snapshot.confirmed_revision}` : "Awaiting patient confirmation"}
          </StatusChip>
          <StatusChip tone="neutral">Collection {snapshot.collection.collection_id}</StatusChip>
          {loadedAt && <StatusChip tone="neutral">Loaded {loadedAt}</StatusChip>}
        </div>
        {error && <Notice tone="error">{error.message} The view below may be out of date.</Notice>}
      </div>
    </header>
  );

  if (!confirmed) {
    const invalidated = lastConfirmed !== null;
    return (
      <div className="space-y-6">
        {header}
        <Notice tone="warning">
          <span data-testid="doctor-awaiting">
            {invalidated
              ? `The patient changed their statement after confirming revision ${lastConfirmed}. That brief and comparison are no longer current. `
              : ""}
            The brief opens only after the patient confirms the current revision ({snapshot.revision}).{" "}
          </span>
          <Link className="underline" href={`/intake/${encodeURIComponent(sessionId)}`}>
            Return to patient review
          </Link>
        </Notice>
      </div>
    );
  }

  const brief = snapshot.brief;
  const latest = snapshot.search_history.at(-1) ?? null;
  const current = latest && latest.patient_revision === snapshot.revision ? latest : null;

  return (
    <SourceDrawerProvider snapshot={snapshot}>
    <div className="space-y-6">
      {header}
      <SnapshotWarnings snapshot={snapshot} />
      <div className="grid gap-6 lg:grid-cols-12">
        <Panel title="Patient brief" className="lg:col-span-7" testId="brief-panel">
          {!brief || brief.patient_revision !== snapshot.revision ? (
            <Notice tone="warning">No brief for the current revision.</Notice>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <BriefList title="Summary" items={brief.summary_items} empty="Nothing captured from the patient's words yet." className="sm:col-span-2" />
              <BriefList title="Timeline" items={brief.timeline_items} empty="No timing or product details captured." />
              <BriefList title="Reported prior treatment" items={brief.prior_treatment_items} empty="None captured (not the same as none used)." />
              <BriefList title="Unresolved details" items={brief.unresolved_items} empty="No open items recorded." className="sm:col-span-2" />
            </div>
          )}
        </Panel>

        <Panel
          title="Comparable cases"
          className="lg:col-span-5"
          testId="cases-panel"
          action={
            current && current.cards.length > 0 ? (
              <span className="text-sm text-muted-foreground">
                {current.cards.length} {current.cards.length === 1 ? "case" : "cases"} ·{" "}
                {snapshot.collection.mode === "synthetic" ? "fictional demonstration" : "published case reports"}
              </span>
            ) : undefined
          }
        >
          {!current ? (
            <Notice tone="warning">Comparison is stale or missing for this revision.</Notice>
          ) : current.cards.length === 0 ? (
            <div className="space-y-2" data-testid="no-match">
              <StatusChip tone="neutral">No qualifying case</StatusChip>
              <p>{current.no_match_reason ? NO_MATCH_TEXT[current.no_match_reason] : "No case qualified."}</p>
              <p className="text-sm text-muted-foreground">
                No match in this collection does not mean no medical evidence exists.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {current.cards.map((card) => (
                <CaseCardView key={card.case_id} card={card} collection={snapshot.collection} attribution={card.attribution ?? null} />
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Before and after: what changed the comparison" className="lg:col-span-7" testId="changes-panel">
          <ComparisonHistory snapshot={snapshot} />
        </Panel>

        <Panel title="For the doctor to clarify" className="lg:col-span-5" testId="clarify-panel">
          {!brief || brief.doctor_clarifications.length === 0 ? (
            <p className="text-muted-foreground">Nothing flagged.</p>
          ) : (
            <ul className="divide-y overflow-hidden rounded-sm border">
              {brief.doctor_clarifications.map((d, i) => (
                <li key={`${d.text}-${i}`} className="px-3 py-2">
                  {d.text}
                </li>
              ))}
            </ul>
          )}
          {snapshot.questions.length > 0 && (
            <div className="mt-4 space-y-2" data-testid="doctor-questions">
              <h3 className="dcn-label">Clarifications asked during intake</h3>
              <ul className="divide-y overflow-hidden rounded-sm border">
                {snapshot.questions.map((q) => (
                  <li key={q.question_id} className="space-y-1 px-3 py-2">
                    <p>{q.text}</p>
                    <StatusChip tone={q.status === "answered" ? "ok" : q.status === "asked" ? "warning" : "neutral"}>
                      {QUESTION_STATUS_DOCTOR[q.status]}
                    </StatusChip>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        {token && <ClinicianNotePanel api={api} sessionId={sessionId} token={token} snapshot={snapshot} onSaved={addNote} />}
      </div>
    </div>
    </SourceDrawerProvider>
  );
}
