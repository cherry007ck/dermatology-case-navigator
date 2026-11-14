"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { ArrowLeft, ArrowRight, RefreshCw } from "lucide-react";
import { ClinicianNotePanel } from "@/components/doctor/clinician-note-panel";
import { ComparisonHistory } from "@/components/doctor/comparison-history";
import { CaseCardView } from "@/components/case/case-card";
import { EvidenceQuotes } from "@/components/evidence";
import { ModeBanner, SnapshotWarnings } from "@/components/mode-banner";
import { SourceDrawerProvider } from "@/components/source-drawer";
import { Notice } from "@/components/status";
import { Button } from "@/components/ui/button";
import { ApiRequestError, getApiClient } from "@/lib/api/client";
import type { BriefItem, ClinicianNote, SearchVersion } from "@/lib/api/types";
import {
  isConfirmedCurrent,
  QUESTION_STATUS_DOCTOR,
  statementHistory,
} from "@/lib/session/history";
import { useLastConfirmedRevision, useSessionToken } from "@/lib/session-store";

const NO_MATCH_TEXT: Record<
  NonNullable<SearchVersion["no_match_reason"]>,
  string
> = {
  insufficient_information:
    "Not enough explicitly reported detail to compare: a symptom needs to be stated together with its body site.",
  conflicting_details:
    "Conflicting details prevent a fair comparison with cases in this collection.",
  no_comparable_cases:
    "No case in this collection documents the same symptom at the same body site that the patient reported.",
};

function ClinicalLine({
  title,
  items,
  empty,
}: {
  title: string;
  items: BriefItem[];
  empty: string;
}) {
  return (
    <div>
      <strong>{title}: </strong>
      {items.length ? (
        items.map((item, index) => (
          <span key={index}>
            {item.text} <EvidenceQuotes evidence={item.evidence} />
          </span>
        ))
      ) : (
        <span className="text-muted-foreground">{empty}</span>
      )}
    </div>
  );
}

export function DoctorWorkspace() {
  const { session_id: rawId } = useParams<{ session_id: string }>();
  const sessionId = decodeURIComponent(rawId);
  const api = getApiClient();
  const token = useSessionToken(sessionId);
  const lastConfirmed = useLastConfirmedRevision(sessionId);
  const [view, setView] = useState<"brief" | "assessment">("brief");
  const {
    data: snapshot,
    error,
    mutate,
  } = useSWR(
    token ? ["doctor-session", sessionId, token] : null,
    () => api.getSession(sessionId, token!),
    { shouldRetryOnError: false },
  );
  const addNote = (note: ClinicianNote) =>
    void mutate(
      (previous) =>
        previous
          ? {
              ...previous,
              clinician_notes: [...previous.clinician_notes, note],
            }
          : previous,
      { revalidate: false },
    );

  if (token === null)
    return (
      <div className="feedback-area">
        <Notice tone="error">
          This tab has no access to that encounter.{" "}
          <Link className="underline" href="/doctor">
            Back to patient intakes
          </Link>
          .
        </Notice>
      </div>
    );
  if (!snapshot && error)
    return (
      <div className="feedback-area">
        <Notice tone="error">
          {error instanceof ApiRequestError
            ? error.message
            : "Could not load the intake."}
          <Button
            variant="outline"
            className="ml-3"
            onClick={() => void mutate()}
          >
            Retry
          </Button>
        </Notice>
      </div>
    );
  if (!snapshot)
    return (
      <p className="p-8" role="status">
        Loading consultation brief…
      </p>
    );
  const confirmed = isConfirmedCurrent(snapshot);
  if (!confirmed)
    return (
      <div className="p-7">
        <Notice tone="warning">
          <span data-testid="doctor-awaiting">
            {lastConfirmed !== null
              ? "The patient changed their previously confirmed statement. "
              : ""}
            The brief opens only after the patient confirms the current revision
            ({snapshot.revision}).{" "}
          </span>
          <Link
            className="underline"
            href={`/intake/${encodeURIComponent(sessionId)}`}
          >
            Return to patient review
          </Link>
        </Notice>
      </div>
    );

  const brief =
    snapshot.brief?.patient_revision === snapshot.revision
      ? snapshot.brief
      : null;
  const latest = snapshot.search_history.at(-1);
  const current =
    latest?.patient_revision === snapshot.revision ? latest : null;
  const entries = statementHistory(snapshot);
  const story = entries.filter(({ current }) => !current.reply_to_question_id);

  return (
    <SourceDrawerProvider snapshot={snapshot}>
      <div hidden={view !== "brief"}>
        <div className="doctor-heading">
          <div className="flex flex-wrap items-center gap-5">
            <Link href="/doctor" className="text-action">
              <ArrowLeft aria-hidden="true" />
              Patient intakes
            </Link>
            <h1>Consultation brief</h1>
          </div>
          <Button variant="ghost" onClick={() => void mutate()}>
            <RefreshCw data-icon="inline-start" />
            Refresh
          </Button>
        </div>
        <div className="doctor-body">
          {error && (
            <Notice tone="error">
              The latest intake could not be loaded. The displayed information
              may be out of date.
            </Notice>
          )}
          <div className="consultation-summary" data-testid="brief-panel">
            <section>
              <h2>Patient story</h2>
              {story.map(({ current }) => (
                <blockquote key={current.turn_id}>{current.text}</blockquote>
              ))}
              <a
                href="#follow-up-answers"
                className="text-action mt-3 text-primary"
              >
                View follow-up answers <ArrowRight aria-hidden="true" />
              </a>
            </section>
            <section>
              <h2>Clinical summary</h2>
              {brief ? (
                <div className="clinical-lines">
                  <ClinicalLine
                    title="Summary"
                    items={brief.summary_items}
                    empty="Nothing captured yet."
                  />
                  <ClinicalLine
                    title="Onset"
                    items={brief.timeline_items}
                    empty="Not reported."
                  />
                  <ClinicalLine
                    title="Prior treatment"
                    items={brief.prior_treatment_items}
                    empty="Not reported (not the same as none used)."
                  />
                  {brief.unresolved_items.length > 0 && (
                    <ClinicalLine
                      title="Unknowns"
                      items={brief.unresolved_items}
                      empty="None recorded."
                    />
                  )}
                </div>
              ) : (
                <Notice tone="warning">
                  No brief for the current revision.
                </Notice>
              )}
            </section>
            <div className="consultation-clarify">
              <strong>To clarify: </strong>
              {brief?.doctor_clarifications
                .map((item) => item.text)
                .join(" ") || "No additional clarifications recorded."}
            </div>
          </div>
          <section className="reference-panel">
            <header>
              <h2>Patient photos</h2>
              <span className="text-xs text-muted-foreground">
                For clinician review only
              </span>
            </header>
            <p className="text-sm text-muted-foreground">
              No photos shared. Secure photo uploads are not configured for this
              application.
            </p>
          </section>
          <section className="reference-panel" data-testid="cases-panel">
            <header>
              <h2>Similar case histories</h2>
              <span className="text-xs text-muted-foreground">
                {snapshot.collection.mode === "synthetic"
                  ? "Fictional cases · not published evidence"
                  : "Published case reports · not diagnostic matches"}
              </span>
            </header>
            {!current ? (
              <Notice tone="warning">
                Comparison is stale or missing for this revision.
              </Notice>
            ) : current.cards.length === 0 ? (
              <div data-testid="no-match">
                <p>
                  {current.no_match_reason
                    ? NO_MATCH_TEXT[current.no_match_reason]
                    : "No case qualified."}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  No match in this collection does not mean no medical evidence
                  exists.
                </p>
              </div>
            ) : (
              <div className="case-grid">
                {current.cards.map((card) => (
                  <CaseCardView
                    key={card.case_id}
                    card={card}
                    collection={snapshot.collection}
                    attribution={card.attribution ?? null}
                  />
                ))}
              </div>
            )}
          </section>
          <details
            className="reference-panel"
            id="follow-up-answers"
            data-testid="doctor-questions"
          >
            <summary className="cursor-pointer font-semibold">
              Follow-up answers · {snapshot.questions.length} questions
            </summary>
            <div className="mt-4 flex flex-col gap-4">
              {snapshot.questions.map((question) => (
                <section key={question.question_id}>
                  <h3 className="font-semibold">{question.text}</h3>
                  <p className="mt-1 text-sm">
                    {entries
                      .filter(
                        ({ current }) =>
                          current.reply_to_question_id ===
                            question.question_id ||
                          question.answer_turn_ids.includes(current.turn_id),
                      )
                      .map(({ current }) => current.text)
                      .join(" ") || QUESTION_STATUS_DOCTOR[question.status]}
                  </p>
                </section>
              ))}
            </div>
          </details>
          <details className="reference-panel" data-testid="changes-panel">
            <summary className="cursor-pointer font-semibold">
              Before and after: what changed the comparison
            </summary>
            <div className="mt-4">
              <ComparisonHistory snapshot={snapshot} />
            </div>
          </details>
          {snapshot.clinician_notes.length > 0 && (
            <section className="reference-panel" data-testid="saved-notes">
              <header>
                <h2>Saved assessments</h2>
              </header>
              {snapshot.clinician_notes.map((note) => (
                <article
                  key={note.note_id}
                  className="border-b py-3 last:border-0"
                >
                  <p className="whitespace-pre-wrap">{note.note_text}</p>
                  <p className="mt-3 text-xs text-muted-foreground">
                    {note.author_label} · Patient revision{" "}
                    {note.patient_revision}
                    {note.patient_revision !== snapshot.revision
                      ? " · Earlier revision"
                      : ""}
                  </p>
                </article>
              ))}
            </section>
          )}
          <SnapshotWarnings snapshot={snapshot} />
        </div>
        <div className="workflow-actions">
          <span className="text-xs text-muted-foreground">
            Patient confirmed revision {snapshot.confirmed_revision}
          </span>
          <Button size="lg" onClick={() => setView("assessment")}>
            Record assessment <ArrowRight data-icon="inline-end" />
          </Button>
        </div>
      </div>
      <div hidden={view !== "assessment"}>
        {token && (
          <ClinicianNotePanel
            api={api}
            sessionId={sessionId}
            token={token}
            snapshot={snapshot}
            onSaved={addNote}
            onBack={() => setView("brief")}
          />
        )}
      </div>
      <div className="service-status">
        <ModeBanner apiMode={api.mode} snapshot={snapshot} />
      </div>
    </SourceDrawerProvider>
  );
}
