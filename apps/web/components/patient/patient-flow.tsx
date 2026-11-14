"use client";

import Link from "next/link";
import { ArrowLeft, ArrowRight, Check, Volume2, Pause } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { IntakeSteps } from "@/components/patient/intake-steps";
import { PatientReview } from "@/components/patient/patient-review";
import { PhotoStatus } from "@/components/patient/photo-status";
import { ModeBanner } from "@/components/mode-banner";
import { Waveform } from "@/components/voice/waveform";
import { Notice } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { statementHistory } from "@/lib/session/history";
import type { ApiMode } from "@/lib/api/client";
import type { Question, SessionSnapshot, Turn } from "@/lib/api/types";

type Props = {
  apiMode: ApiMode;
  snapshot: SessionSnapshot | null;
  question: Question | null;
  text: string;
  setText: (text: string) => void;
  busy: boolean;
  online: boolean;
  ready: boolean;
  confirmed: boolean;
  invalidated: boolean;
  blockers: string[];
  onSubmit: (text: string) => void;
  onSkip: () => void;
  onConfirm: () => void;
  onCorrect: (turn: Turn, text: string) => Promise<boolean>;
  failure: { message: string; retry: (() => void) | null } | null;
  notice: string | null;
  voice: ReactNode;
};

export function PatientFlow(props: Props) {
  const {
    snapshot,
    question,
    text,
    setText,
    busy,
    online,
    ready,
    confirmed,
    onSubmit,
    onSkip,
    onCorrect,
    onConfirm,
    failure,
    voice,
  } = props;
  const [speaking, setSpeaking] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  useEffect(
    () => () => {
      window.speechSynthesis?.cancel();
    },
    [question?.question_id],
  );
  function readQuestion() {
    if (!question) return;
    if (!("speechSynthesis" in window)) {
      setSpeechError(
        "Question narration is unavailable in this browser. You can read and answer below.",
      );
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(question.text);
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => {
      setSpeaking(false);
      setSpeechError(
        "Question narration could not play. You can read and answer below.",
      );
    };
    window.speechSynthesis.speak(utterance);
  }
  const step = ready || confirmed ? 2 : question ? 1 : 0;
  const initial = snapshot
    ? statementHistory(snapshot).find(
        ({ current }) => !current.reply_to_question_id,
      )?.current.text
    : null;
  const input = (
    <form
      id="patient-answer-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(text);
      }}
      className="flex flex-col gap-3"
    >
      <label htmlFor="patient-text">
        {question ? "Your answer" : "Your words"}
      </label>
      <Textarea
        id="patient-text"
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={question ? 3 : 6}
        maxLength={8000}
        disabled={busy}
        placeholder={
          question
            ? "Type your answer here…"
            : "Tell us what has been happening…"
        }
      />
      {question && (
        <Button
          type="button"
          variant="ghost"
          onClick={() => onSubmit("I don't know.")}
          disabled={busy || !online}
        >
          I don&apos;t know
        </Button>
      )}
    </form>
  );
  return (
    <>
      <IntakeSteps step={step} complete={confirmed} />
      {!confirmed && (
        <div className="page-heading">
          <h1 tabIndex={-1}>
            {ready
              ? "Review before sharing"
              : question
                ? "Follow-up questions"
                : "Tell us about your skin concern"}
          </h1>
          <p>
            {ready
              ? "Check what your doctor will receive. You can edit anything before sharing."
              : question
                ? "A little more detail helps your doctor understand your story."
                : "Describe what you noticed, when it started, and anything you've tried."}
          </p>
        </div>
      )}
      {!online && (
        <div className="feedback-area">
          <Notice tone="warning">
            You are offline. Your typed words stay in the box until you
            reconnect.
          </Notice>
        </div>
      )}
      {props.invalidated && (
        <div className="feedback-area">
          <Notice tone="warning">
            <span data-testid="confirmation-invalidated">
              Your earlier confirmation no longer applies. Review and share your
              updated story.
            </span>
          </Notice>
        </div>
      )}
      {failure && (
        <div className="feedback-area">
          <Notice tone="error">
            <p>{failure.message}</p>
            {failure.retry && (
              <Button
                variant="outline"
                onClick={failure.retry}
                disabled={busy || !online}
                className="mt-3"
              >
                Retry
              </Button>
            )}
          </Notice>
        </div>
      )}
      {props.notice && !failure && (
        <div className="feedback-area">
          <Notice>{props.notice}</Notice>
        </div>
      )}
      {!snapshot && !failure && (
        <p className="p-8" role="status">
          Loading your intake…
        </p>
      )}
      {snapshot && confirmed ? (
        <section className="sharing-success">
          <div className="success-check">
            <Check aria-hidden="true" />
          </div>
          <h1>Your intake has been shared.</h1>
          <p>Your doctor can now review your story and follow-up answers.</p>
          <Link href="/" className="action-link primary-action">
            Back to home
          </Link>
          <Link className="text-action" href="/doctor">
            Open doctor workspace <ArrowRight aria-hidden="true" />
          </Link>
        </section>
      ) : (
        snapshot && (
          <>
            {/* Keep the voice engine mounted through review to drain late transcript writes. */}
            <div hidden={ready || (!!question && !showVoice)}>
              <div className="story-entry corner-marks">
                {voice}
                <section className="story-text">
                  {!ready && !question ? (
                    <>
                      {input}
                      <PhotoStatus />
                    </>
                  ) : (
                    <p>
                      Voice transcripts are saved to your story. Stop recording
                      before reviewing your intake.
                    </p>
                  )}
                </section>
              </div>
            </div>
            {question && !ready && (
              <div className="followup-grid corner-marks">
                <aside className="story-aside">
                  <h2>Your story</h2>
                  <blockquote>{initial}</blockquote>
                </aside>
                <section className="question-panel">
                  <p className="voice-caption">
                    {speaking
                      ? "Reading the question aloud"
                      : "One question at a time"}
                  </p>
                  <Waveform active={speaking} />
                  <h2 data-testid="current-question">{question.text}</h2>
                  <div className="question-tools">
                    <Button variant="secondary" onClick={readQuestion}>
                      <Volume2 data-icon="inline-start" />
                      Read question aloud
                    </Button>
                    {speaking && (
                      <Button
                        variant="outline"
                        onClick={() => {
                          window.speechSynthesis.cancel();
                          setSpeaking(false);
                        }}
                      >
                        <Pause data-icon="inline-start" />
                        Stop narration
                      </Button>
                    )}
                    <button
                      className="text-action"
                      onClick={() =>
                        document.getElementById("patient-text")?.focus()
                      }
                    >
                      Type instead
                    </button>
                  </div>
                  {speechError && (
                    <p role="status" className="text-sm">
                      {speechError}
                    </p>
                  )}
                  {input}
                  <Button
                    variant="ghost"
                    onClick={() => setShowVoice(!showVoice)}
                  >
                    {showVoice ? "Hide voice controls" : "Answer with voice"}
                  </Button>
                </section>
              </div>
            )}
            {ready && (
              <section data-testid="review-panel">
                <PatientReview
                  snapshot={snapshot}
                  busy={busy || !online}
                  onCorrect={onCorrect}
                />
                {props.blockers.length > 0 && (
                  <p
                    className="px-7 pb-4 text-sm"
                    role="status"
                    data-testid="confirm-blocked"
                  >
                    Sharing is paused because {props.blockers.join(", ")}.
                  </p>
                )}
              </section>
            )}
            {!ready && failure && initial && (
              <details className="m-6 border p-4">
                <summary className="cursor-pointer">Your saved words</summary>
                <PatientReview
                  snapshot={snapshot}
                  busy={busy}
                  onCorrect={onCorrect}
                />
              </details>
            )}
            <div className="workflow-actions corner-marks">
              <Link href="/" className="text-action">
                <ArrowLeft aria-hidden="true" />
                Back to home
              </Link>
              <div className="flex flex-wrap items-center gap-4">
                {question && !ready && (
                  <Button
                    variant="ghost"
                    onClick={onSkip}
                    disabled={busy || !online}
                  >
                    Skip question
                  </Button>
                )}
                {ready ? (
                  <Button
                    size="lg"
                    onClick={onConfirm}
                    disabled={busy || props.blockers.length > 0}
                  >
                    {busy ? "Sharing…" : "Confirm and share"}
                    <ArrowRight data-icon="inline-end" />
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    form="patient-answer-form"
                    size="lg"
                    disabled={busy || !text.trim() || !online}
                  >
                    {busy ? "Saving and processing…" : "Continue"}
                    <ArrowRight data-icon="inline-end" />
                  </Button>
                )}
              </div>
            </div>
          </>
        )
      )}
      <div className="service-status">
        <ModeBanner apiMode={props.apiMode} snapshot={snapshot} />
      </div>
    </>
  );
}
