"use client";

import { Pencil } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PhotoStatus } from "@/components/patient/photo-status";
import { statementHistory, QUESTION_STATUS_LABEL } from "@/lib/session/history";
import type { SessionSnapshot, Turn } from "@/lib/api/types";

type Props = {
  snapshot: SessionSnapshot;
  busy: boolean;
  onCorrect: (turn: Turn, text: string) => Promise<boolean>;
};

function ReviewStatement({
  turn,
  busy,
  onCorrect,
}: { turn: Turn } & Pick<Props, "busy" | "onCorrect">) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(turn.text);
  return editing ? (
    <form
      className="review-edit"
      onSubmit={async (event) => {
        event.preventDefault();
        if (await onCorrect(turn, draft.trim())) setEditing(false);
      }}
    >
      <label htmlFor={`edit-${turn.turn_id}`}>Correct what you said</label>
      <Textarea
        id={`edit-${turn.turn_id}`}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        rows={4}
        maxLength={8000}
        autoFocus
        disabled={busy}
      />
      <p className="text-xs text-muted-foreground">
        Your original words stay in the record, marked as replaced.
      </p>
      <div className="flex gap-2">
        <Button
          type="submit"
          disabled={busy || !draft.trim() || draft.trim() === turn.text}
        >
          Save correction
        </Button>
        <Button variant="ghost" type="button" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </form>
  ) : (
    <div className="review-answer">
      <p className="whitespace-pre-wrap">{turn.text}</p>
      <Button
        variant="outline"
        size="icon"
        aria-label={`Correct: ${turn.text.slice(0, 60)}`}
        onClick={() => {
          setDraft(turn.text);
          setEditing(true);
        }}
        disabled={busy}
      >
        <Pencil />
      </Button>
    </div>
  );
}

export function PatientReview({ snapshot, busy, onCorrect }: Props) {
  const entries = statementHistory(snapshot);
  const initial = entries.filter(
    ({ current }) => !current.reply_to_question_id,
  );
  return (
    <div className="review-grid corner-marks" data-testid="story-panel">
      <section className="review-story">
        <h2>Your story</h2>
        <ol className="flex flex-col gap-5" data-testid="story-turns">
          {initial.map(({ current, replaced }) => (
            <li key={current.turn_id} data-testid="statement">
              <ReviewStatement
                turn={current}
                busy={busy}
                onCorrect={onCorrect}
              />
              {replaced.length > 0 && (
                <details
                  className="mt-3 text-xs text-muted-foreground"
                  data-testid="replaced-history"
                >
                  <summary>Earlier versions — replaced</summary>
                  {replaced.map((turn) => (
                    <p key={turn.turn_id} className="mt-2 line-through">
                      {turn.text}
                    </p>
                  ))}
                </details>
              )}
            </li>
          ))}
        </ol>
        <div className="mt-8">
          <PhotoStatus />
        </div>
      </section>
      <section className="review-answers">
        <div className="flex items-baseline justify-between gap-4">
          <h2>Follow-up answers</h2>
          <span className="text-sm">{snapshot.questions.length} questions</span>
        </div>
        {snapshot.questions.length === 0 && (
          <p className="text-muted-foreground">
            No follow-up questions were needed.
          </p>
        )}
        {snapshot.questions.map((question) => {
          const answers = entries.filter(
            ({ current }) =>
              current.reply_to_question_id === question.question_id ||
              question.answer_turn_ids.includes(current.turn_id),
          );
          return (
            <details key={question.question_id} className="review-item" open>
              <summary>{question.text}</summary>
              <div>
                {answers.length ? (
                  answers.map(({ current, replaced }) => (
                    <div key={current.turn_id} className="mb-2">
                      <ReviewStatement
                        turn={current}
                        busy={busy}
                        onCorrect={onCorrect}
                      />
                      {replaced.length > 0 && (
                        <details className="mt-2 text-xs text-muted-foreground">
                          <summary>Earlier versions — replaced</summary>
                          {replaced.map((turn) => (
                            <p key={turn.turn_id}>{turn.text}</p>
                          ))}
                        </details>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-muted-foreground">
                    {QUESTION_STATUS_LABEL[question.status]}
                  </p>
                )}
              </div>
            </details>
          );
        })}
      </section>
    </div>
  );
}
