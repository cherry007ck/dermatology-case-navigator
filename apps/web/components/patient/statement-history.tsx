"use client";

import { useRef, useState } from "react";

import { Panel, StatusChip } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { SessionSnapshot, Turn } from "@/lib/api/types";
import { QUESTION_STATUS_LABEL, statementHistory } from "@/lib/session/history";

function originLabel(turn: Turn): string {
  if (turn.origin === "correction") return "Your correction";
  if (turn.origin === "voice_transcript") return "Voice transcript — please review";
  return "Typed";
}

type Props = {
  snapshot: SessionSnapshot;
  busy: boolean;
  /** Corrections are allowed until confirmation and after it (a correction re-opens review). */
  onCorrect: (turn: Turn, replacementText: string) => Promise<boolean>;
};

/** Patient's own statements only: current versions, visible correction history, open questions. */
export function StatementHistory({ snapshot, busy, onCorrect }: Props) {
  const entries = statementHistory(snapshot);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const editButtons = useRef(new Map<string, HTMLButtonElement>());

  function startEdit(turn: Turn) {
    setEditing(turn.turn_id);
    setDraft(turn.text);
  }

  function cancelEdit(turnId: string) {
    setEditing(null);
    requestAnimationFrame(() => editButtons.current.get(turnId)?.focus());
  }

  async function save(turn: Turn) {
    const text = draft.trim();
    if (!text || text === turn.text) return;
    if (await onCorrect(turn, text)) setEditing(null);
  }

  const questions = snapshot.questions;

  return (
    <Panel title="Your story so far" testId="story-panel">
      {entries.length === 0 ? (
        <p className="text-muted-foreground">Nothing yet.</p>
      ) : (
        <ol className="space-y-3" data-testid="story-turns">
          {entries.map(({ current, replaced }) => (
            <li key={current.turn_id} className="rounded-xl border bg-background p-3" data-testid="statement">
              {editing === current.turn_id ? (
                <form
                  className="space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void save(current);
                  }}
                  onKeyDown={(e) => e.key === "Escape" && cancelEdit(current.turn_id)}
                >
                  <Label htmlFor={`correct-${current.turn_id}`}>Correct what you said</Label>
                  <Textarea
                    id={`correct-${current.turn_id}`}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={3}
                    className="text-base"
                    autoFocus
                    disabled={busy}
                  />
                  <p className="text-sm text-muted-foreground">Your original words stay in the record, marked as replaced.</p>
                  <div className="flex flex-wrap gap-2">
                    <Button type="submit" size="lg" className="h-11 text-base" disabled={busy || !draft.trim() || draft.trim() === current.text}>
                      Save correction
                    </Button>
                    <Button type="button" variant="ghost" size="lg" className="h-11 text-base" onClick={() => cancelEdit(current.turn_id)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <>
                  <p>{current.text}</p>
                  <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm text-muted-foreground">{originLabel(current)}</span>
                    <Button
                      ref={(el) => {
                        if (el) editButtons.current.set(current.turn_id, el);
                      }}
                      variant="outline"
                      size="sm"
                      className="h-9"
                      onClick={() => startEdit(current)}
                      disabled={busy}
                      aria-label={`Correct: ${current.text.slice(0, 60)}`}
                    >
                      Correct
                    </Button>
                  </div>
                </>
              )}
              {replaced.length > 0 && (
                <details className="mt-2 text-sm" data-testid="replaced-history">
                  <summary className="cursor-pointer text-muted-foreground">
                    Earlier version{replaced.length > 1 ? "s" : ""} ({replaced.length}) — replaced
                  </summary>
                  <ul className="mt-1 space-y-1">
                    {replaced.map((t) => (
                      <li key={t.turn_id} className="text-muted-foreground line-through decoration-1">
                        {t.text}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ol>
      )}

      {questions.length > 0 && (
        <div className="mt-4" data-testid="question-list">
          <h3 className="font-semibold">Clarifications</h3>
          <ul className="mt-1 space-y-2">
            {questions.map((q) => (
              <li key={q.question_id}>
                <p>{q.text}</p>
                <StatusChip tone={q.status === "asked" ? "info" : q.status === "answered" ? "ok" : "neutral"}>
                  {QUESTION_STATUS_LABEL[q.status]}
                </StatusChip>
              </li>
            ))}
          </ul>
        </div>
      )}

      {snapshot.brief && snapshot.brief.patient_revision === snapshot.revision && snapshot.brief.unresolved_items.length > 0 && (
        <div className="mt-4" data-testid="missing-details">
          <h3 className="font-semibold">Details still open</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-muted-foreground">
            {snapshot.brief.unresolved_items.map((item, i) => (
              <li key={`${item.text}-${i}`}>{item.text}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-3">
        <StatusChip tone="neutral">Revision {snapshot.revision}</StatusChip>
      </div>
    </Panel>
  );
}
