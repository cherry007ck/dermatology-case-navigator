"use client";

import { useState } from "react";

import { Notice, Panel, StatusChip } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, type ApiTransport, newRequestId } from "@/lib/api/client";
import type { ClinicianNote, SessionSnapshot } from "@/lib/api/types";

type Props = {
  api: ApiTransport;
  sessionId: string;
  token: string;
  snapshot: SessionSnapshot;
  onSaved: (note: ClinicianNote) => void;
};

/**
 * Clinician assessment, stored through POST /clinician-notes as its own record with
 * an author label and the patient revision it was written against. It never edits,
 * adds to or summarises patient facts, and is never shown in the patient view.
 */
export function ClinicianNotePanel({ api, sessionId, token, snapshot, onSaved }: Props) {
  const [author, setAuthor] = useState("");
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<{ message: string; retryable: boolean } | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  // One request ID per draft: a retry after a timeout cannot save the same note twice.
  const [requestId, setRequestId] = useState(newRequestId);
  const unsaved = text.trim().length > 0;

  async function save() {
    if (!unsaved || !author.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const note = await api.addClinicianNote(sessionId, token, {
        request_id: requestId,
        expected_revision: snapshot.revision,
        note_text: text.trim(),
        author_label: author.trim(),
      });
      onSaved(note);
      setSavedId(note.note_id);
      setText("");
      setRequestId(newRequestId());
    } catch (e) {
      const err = e instanceof ApiRequestError ? e : null;
      setError({
        message:
          err?.code === "REVISION_CONFLICT"
            ? "The patient's statement changed. Reload the brief before saving a note against it."
            : `${err?.message ?? "The note could not be saved."} Your text is still here.`,
        retryable: err?.retryable ?? true,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel title="Clinician assessment (separate from patient statements)" className="lg:col-span-12" testId="clinician-notes">
      <p className="mb-4 text-sm text-muted-foreground">
        Saved as a separate, author-labelled note against patient revision {snapshot.revision}. It never changes the patient&apos;s words,
        facts or brief, and the patient does not see it. Fictional demo only.
      </p>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <form
          className="dcn-clipboard min-w-0 space-y-4"
          aria-label="Record clinician assessment"
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          <h3 className="border-b pb-2 text-lg font-semibold">Record assessment</h3>
          <div className="space-y-1">
            <Label htmlFor="note-author">Author label</Label>
            <Input id="note-author" value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="e.g. Demo clinician" className="h-11 text-base" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="note-text">Assessment note</Label>
            <Textarea
              id="note-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              placeholder="Write your clinical assessment and next steps"
              className="text-base"
            />
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-3">
            <span role="status" aria-live="polite">
              {unsaved ? <StatusChip tone="warning">Unsaved note</StatusChip> : savedId ? <StatusChip tone="ok">Note saved</StatusChip> : null}
            </span>
            <Button type="submit" size="lg" className="h-11 px-5 text-base" disabled={saving || !unsaved || !author.trim()}>
              {saving ? "Saving…" : "Save note"}
            </Button>
          </div>
          {error && (
            <Notice tone="error">
              {error.message}
              {error.retryable && (
                <Button type="submit" variant="outline" size="sm" className="ml-2">
                  Retry
                </Button>
              )}
            </Notice>
          )}
        </form>

        <section className="min-w-0 overflow-hidden rounded-sm border self-start" aria-labelledby="saved-notes-heading">
          <h3 id="saved-notes-heading" className="dcn-band">
            Saved assessments
          </h3>
          {snapshot.clinician_notes.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">No assessment saved for this encounter yet.</p>
          ) : (
            <ul className="divide-y" data-testid="saved-notes">
              {snapshot.clinician_notes.map((n) => (
                <li key={n.note_id} className="px-3 py-2">
                  <p className="whitespace-pre-wrap">{n.note_text}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {n.author_label} · patient revision {n.patient_revision} · {new Date(n.created_at).toLocaleString()}
                    {n.patient_revision !== snapshot.revision && " · written against an earlier revision"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Panel>
  );
}
