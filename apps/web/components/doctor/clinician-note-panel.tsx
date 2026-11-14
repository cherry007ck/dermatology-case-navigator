"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { useState } from "react";
import { Notice } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiRequestError,
  type ApiTransport,
  newRequestId,
} from "@/lib/api/client";
import type { ClinicianNote, SessionSnapshot } from "@/lib/api/types";
import { statementHistory } from "@/lib/session/history";

type Props = {
  api: ApiTransport;
  sessionId: string;
  token: string;
  snapshot: SessionSnapshot;
  onSaved: (note: ClinicianNote) => void;
  onBack?: () => void;
};

/** Clinician notes are separate author-labelled records, never patient facts. */
export function ClinicianNotePanel({
  api,
  sessionId,
  token,
  snapshot,
  onSaved,
  onBack,
}: Props) {
  const [author, setAuthor] = useState("");
  const [assessment, setAssessment] = useState("");
  const [nextSteps, setNextSteps] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<ClinicianNote | null>(null);
  const [requestId, setRequestId] = useState(newRequestId);
  const story = statementHistory(snapshot).find(
    ({ current }) => !current.reply_to_question_id,
  )?.current.text;
  const unsaved = assessment.trim().length > 0 || nextSteps.trim().length > 0;

  async function save() {
    if (saving || !assessment.trim() || !author.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const note = await api.addClinicianNote(sessionId, token, {
        request_id: requestId,
        expected_revision: snapshot.revision,
        note_text: `Assessment\n${assessment.trim()}\n\nNext steps\n${nextSteps.trim() || "Not recorded."}`,
        author_label: author.trim(),
      });
      onSaved(note);
      setSaved(note);
      setRequestId(newRequestId());
    } catch (e) {
      const err = e instanceof ApiRequestError ? e : null;
      setError(
        err?.code === "REVISION_CONFLICT"
          ? "The patient's statement changed. Return to the brief and refresh before saving."
          : "The assessment could not be saved. Your text is still here; please retry.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section data-testid="clinician-notes">
      <div className="px-7 py-3">
        <button className="text-action" onClick={onBack}>
          <ArrowLeft aria-hidden="true" />
          Consultation brief
        </button>
      </div>
      <div className="doctor-heading">
        <h1 className="flex items-center gap-3">
          {saved && <Check className="text-primary" aria-hidden="true" />}
          {saved ? "Assessment saved" : "Record assessment"}
        </h1>
        <span className="font-mono text-xs">Intake {sessionId.slice(-8)}</span>
      </div>
      <div className="assessment-layout">
        <form
          id="assessment-form"
          className="dcn-clipboard assessment-clipboard"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
          aria-label="Record clinician assessment"
        >
          <div>
            <h2>Clinician assessment</h2>
            {saved && (
              <p className="text-sm text-muted-foreground">
                Recorded by {saved.author_label}
              </p>
            )}
          </div>
          {saved ? (
            <>
              <section className="saved-assessment-section">
                <h3>Assessment</h3>
                <p className="whitespace-pre-wrap">{assessment}</p>
              </section>
              <section className="saved-assessment-section">
                <h3>Next steps</h3>
                <p className="whitespace-pre-wrap">
                  {nextSteps || "Not recorded."}
                </p>
              </section>
            </>
          ) : (
            <>
              <fieldset>
                <label htmlFor="note-author">Clinician name</label>
                <Input
                  id="note-author"
                  value={author}
                  onChange={(event) => {
                    setAuthor(event.target.value);
                    setRequestId(newRequestId());
                  }}
                  placeholder="Name for this assessment"
                  maxLength={100}
                  required
                  disabled={saving}
                />
              </fieldset>
              <fieldset>
                <label htmlFor="note-text">Assessment</label>
                <Textarea
                  id="note-text"
                  value={assessment}
                  onChange={(event) => {
                    setAssessment(event.target.value);
                    setRequestId(newRequestId());
                  }}
                  rows={4}
                  placeholder="Write your clinical assessment"
                  maxLength={6000}
                  required
                  disabled={saving}
                />
              </fieldset>
              <fieldset>
                <label htmlFor="note-next-steps">Next steps</label>
                <Textarea
                  id="note-next-steps"
                  value={nextSteps}
                  onChange={(event) => {
                    setNextSteps(event.target.value);
                    setRequestId(newRequestId());
                  }}
                  rows={3}
                  placeholder="Record your plan or follow-up"
                  maxLength={3000}
                  disabled={saving}
                />
              </fieldset>
            </>
          )}
        </form>
        <aside className="patient-context">
          <h2>Patient context</h2>
          <blockquote>{story ?? "No patient statement."}</blockquote>
          <h3>To clarify</h3>
          {snapshot.brief?.doctor_clarifications.length ? (
            snapshot.brief.doctor_clarifications.map((item, i) => (
              <p key={i} className="mb-3">
                {item.text}
              </p>
            ))
          ) : (
            <p>No additional clarifications recorded.</p>
          )}
          <p className="mt-8 text-xs text-muted-foreground">
            This assessment is kept separate from the patient&apos;s words and
            is linked to revision {snapshot.revision}.
          </p>
        </aside>
      </div>
      {error && (
        <div className="feedback-area">
          <Notice tone="error">{error}</Notice>
        </div>
      )}
      <div className="workflow-actions">
        <p className="text-xs text-muted-foreground" role="status">
          {saved
            ? "Assessment saved to this encounter."
            : unsaved
              ? "Unsaved changes. Save your assessment before leaving."
              : "Only the clinician records the assessment."}
        </p>
        {saved ? (
          <Link className="action-link primary-action" href="/doctor">
            Back to patient intakes <ArrowRight aria-hidden="true" />
          </Link>
        ) : (
          <Button
            type="submit"
            form="assessment-form"
            size="lg"
            disabled={saving || !assessment.trim() || !author.trim()}
          >
            {saving ? "Saving…" : "Save assessment"}
            <ArrowRight data-icon="inline-end" />
          </Button>
        )}
      </div>
    </section>
  );
}
