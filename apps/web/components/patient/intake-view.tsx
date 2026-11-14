"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FictionalDemoNotice, ModeBanner } from "@/components/mode-banner";
import { BriefReview } from "@/components/patient/brief-review";
import { StatementHistory } from "@/components/patient/statement-history";
import { Notice, Panel } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { voiceIndicator, VoicePanel, type VoiceState } from "@/components/voice/voice-panel";
import { ApiRequestError, getApiClient, newRequestId } from "@/lib/api/client";
import type { SessionSnapshot, Turn } from "@/lib/api/types";
import { isConfirmedCurrent } from "@/lib/session/history";
import { SessionWriter } from "@/lib/session/writer";
import { rememberConfirmedRevision, useLastConfirmedRevision, useSessionToken } from "@/lib/session-store";
import { useOnline } from "@/lib/use-online";
import type { CapturedTurn } from "@/lib/voice/transcript";
import { pendingQuestionId, toTurnInput } from "@/lib/voice/sync";

type Failure = { message: string; retry: (() => void) | null };

const POLL_MS = 750;

function failureMessage(e: unknown, fallback: string): string {
  if (!(e instanceof ApiRequestError)) return fallback;
  if (e.code === "REVISION_CONFLICT") return "This encounter changed in the meantime. It has been reloaded; please check it again.";
  if (e.code === "NETWORK_UNAVAILABLE") return "The service could not be reached. Nothing new was saved. Check your connection and retry.";
  if (e.status === 503) return `${e.message} Anything already shown as saved is kept.`;
  return e.message;
}

/** Patient flow: linear, no case content, diagnoses, actions or rankings ever shown here. */
export function IntakeView() {
  const { session_id: rawId } = useParams<{ session_id: string }>();
  const sessionId = decodeURIComponent(rawId);
  const router = useRouter();
  const api = getApiClient();
  const token = useSessionToken(sessionId);
  const online = useOnline();
  const lastConfirmed = useLastConfirmedRevision(sessionId);
  const writer = useMemo(() => (token ? new SessionWriter(api, sessionId, token, newRequestId) : null), [api, sessionId, token]);
  const [snapshot, setSnapshot] = useState<SessionSnapshot | null>(null);
  const [pendingWrites, setPendingWrites] = useState(0);
  const [voiceSync, setVoiceSync] = useState({ saving: false, failed: false });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>({ kind: "checking" });
  const reviewHeading = useRef<HTMLHeadingElement>(null);

  const load = useCallback(() => {
    if (!writer) return;
    writer.refresh().then(
      () => setFailure(null),
      (e) => setFailure({ message: failureMessage(e, "Could not load the encounter."), retry: load }),
    );
  }, [writer]);

  useEffect(() => {
    if (!writer) return;
    const unsubscribe = writer.subscribe(setSnapshot);
    const unsubscribePending = writer.subscribePending(setPendingWrites);
    load();
    return () => {
      unsubscribe();
      unsubscribePending();
    };
  }, [writer, load]);

  // Poll only while voice is active: the agent's webhook advances the session server-side.
  const voiceLive = voiceState.kind === "connected" || voiceState.kind === "connecting";
  useEffect(() => {
    if (!writer || !voiceLive) return;
    const timer = setInterval(() => void writer.refresh().catch(() => undefined), POLL_MS);
    return () => clearInterval(timer);
  }, [writer, voiceLive]);

  const question = useMemo(() => {
    const id = pendingQuestionId(snapshot);
    return snapshot?.questions.find((q) => q.question_id === id) ?? null;
  }, [snapshot]);

  const ready = snapshot?.state === "ready_to_confirm";
  const confirmed = snapshot ? isConfirmedCurrent(snapshot) : false;

  useEffect(() => {
    if (ready) reviewHeading.current?.focus(); // move keyboard/screen-reader focus to the review step
  }, [ready]);

  const persistVoiceTurn = useCallback(
    async (turn: CapturedTurn) => {
      if (!writer) throw new Error("no session");
      await writer.appendTurns([toTurnInput(turn, writer.snapshot)]);
    },
    [writer],
  );

  async function guarded(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    try {
      await work();
    } finally {
      setBusy(false);
    }
  }

  async function runAdvance() {
    if (!writer) return;
    try {
      await writer.advance();
      setFailure(null);
    } catch (e) {
      setFailure({
        message: `Your words were saved, but processing failed: ${failureMessage(e, "unknown error")}`,
        retry: () => void guarded(runAdvance),
      });
    }
  }

  function submit(answerText: string) {
    if (!writer || !answerText.trim()) return;
    // One stable turn ID per submit: a retry can never store the same answer twice.
    const turn = {
      turn_id: newRequestId(),
      role: "patient" as const,
      origin: "typed" as const,
      text: answerText.trim(),
      reply_to_question_id: question?.question_id ?? null,
    };
    const attempt = () =>
      void guarded(async () => {
        try {
          await writer.appendTurns([turn]);
          setText("");
          await runAdvance();
        } catch (e) {
          if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT") await writer.refresh().catch(() => undefined);
          const retryable = !(e instanceof ApiRequestError) || e.retryable || e.code === "NETWORK_UNAVAILABLE";
          setFailure({ message: failureMessage(e, "Could not save."), retry: retryable ? attempt : null });
        }
      });
    attempt();
  }

  function skip() {
    if (!writer || !question || !token) return;
    const questionId = question.question_id;
    void guarded(async () => {
      try {
        await writer.write((base) => api.skip(sessionId, token, { request_id: newRequestId(), expected_revision: base.revision, question_id: questionId }));
        setNotice("Question skipped. That is recorded as skipped, not as a “no”.");
        await runAdvance();
      } catch (e) {
        setFailure({ message: failureMessage(e, "Could not skip."), retry: null });
      }
    });
  }

  async function correct(turn: Turn, replacementText: string): Promise<boolean> {
    if (!writer || !token) return false;
    let ok = false;
    await guarded(async () => {
      try {
        await writer.write((base) =>
          api.correct(sessionId, token, {
            request_id: newRequestId(),
            expected_revision: base.revision,
            replaces_turn_id: turn.turn_id,
            replacement_text: replacementText,
          }),
        );
        ok = true;
        setNotice("Correction saved. Your original words are kept and marked as replaced. The summary is being updated.");
        await runAdvance(); // recompute at the new revision; stale comparisons stay labelled until then
      } catch (e) {
        if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT") await writer.refresh().catch(() => undefined);
        setFailure({ message: failureMessage(e, "Could not save the correction."), retry: null });
      }
    });
    return ok;
  }

  function confirm() {
    if (!writer || !token || !snapshot) return;
    const reviewedRevision = snapshot.revision;
    void guarded(async () => {
      try {
        // Voice is already stopped (review disables capture). Flush every queued write,
        // then re-read: confirm only the exact revision the patient just reviewed.
        await writer.flush();
        const latest = await writer.refresh();
        if (latest.revision !== reviewedRevision || latest.state !== "ready_to_confirm") {
          setFailure({ message: "Your statement changed while you were reviewing (for example, late voice words arrived). Please review it again.", retry: null });
          return;
        }
        const result = await writer.write((base) => api.confirm(sessionId, token, { request_id: newRequestId(), expected_revision: base.revision }));
        if (result.confirmed_revision !== null) rememberConfirmedRevision(sessionId, result.confirmed_revision);
        router.push(`/doctor/${encodeURIComponent(sessionId)}`);
      } catch (e) {
        if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT") await writer.refresh().catch(() => undefined);
        setFailure({ message: failureMessage(e, "Could not confirm."), retry: null });
      }
    });
  }

  if (token === null) {
    return (
      <Notice tone="error">
        This tab has no access to that encounter. Sessions are tied to the tab that created them.{" "}
        <Link className="underline" href="/">
          Start a new fictional encounter
        </Link>
        .
      </Notice>
    );
  }

  const unsavedVoice = voiceSync.saving || voiceSync.failed;
  const confirmBlockers = [
    voiceLive && "voice is still stopping",
    pendingWrites > 0 && "your last words are still saving",
    unsavedVoice && "some voice words are not saved yet",
    !online && "you are offline",
    snapshot?.brief?.patient_revision !== snapshot?.revision && "the summary has been updated for your latest words",
  ].filter(Boolean) as string[];
  const invalidated = lastConfirmed !== null && snapshot !== null && !confirmed;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold">Patient intake</h1>
        <ModeBanner apiMode={api.mode} snapshot={snapshot} voice={voiceIndicator(voiceState)} />
      </header>
      <FictionalDemoNotice />

      {!online && (
        <Notice tone="warning">
          You are offline. What you type stays in the box; nothing new is sent until you are back online and retry.
        </Notice>
      )}
      {invalidated && (
        <Notice tone="warning">
          <span data-testid="confirmation-invalidated">
            Your confirmation of revision {lastConfirmed} no longer applies because your statement changed after it. Please review and confirm
            again.
          </span>
        </Notice>
      )}
      {!snapshot && !failure && <p role="status">Loading encounter…</p>}
      {failure && (
        <Notice tone="error">
          <p>{failure.message}</p>
          {failure.retry && (
            <Button variant="outline" size="lg" className="mt-2" onClick={failure.retry} disabled={busy || !online}>
              Retry
            </Button>
          )}
        </Notice>
      )}
      {notice && !failure && <Notice tone="info">{notice}</Notice>}

      {snapshot && (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-7">
            {!confirmed && token && (
              <VoicePanel
                sessionId={sessionId}
                token={token}
                revision={snapshot.revision}
                onStateChange={setVoiceState}
                persistTurn={persistVoiceTurn}
                captureAllowed={!ready}
                onSyncChange={setVoiceSync}
              />
            )}
            {!ready && !confirmed && (
              <Panel title={question ? "One clarification" : "Tell us about your concern"}>
                {question && (
                  <p className="mb-3 text-lg" data-testid="current-question">
                    {question.text}
                  </p>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    submit(text);
                  }}
                  className="space-y-3"
                >
                  <Label htmlFor="patient-text" className="text-base">
                    {question ? "Your answer" : "In your own words"}
                  </Label>
                  <Textarea
                    id="patient-text"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    rows={4}
                    className="text-base"
                    disabled={busy}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button type="submit" size="lg" className="h-11 px-5 text-base" disabled={busy || !text.trim() || !online}>
                      {question ? "Send answer" : "Send"}
                    </Button>
                    {question && (
                      <>
                        <Button type="button" variant="outline" size="lg" className="h-11 text-base" disabled={busy || !online} onClick={() => submit("I don't know.")}>
                          I don&apos;t know
                        </Button>
                        <Button type="button" variant="ghost" size="lg" className="h-11 text-base" disabled={busy || !online} onClick={skip}>
                          Skip
                        </Button>
                      </>
                    )}
                  </div>
                  {busy && <p role="status">Saving and processing…</p>}
                </form>
              </Panel>
            )}

            {ready && (
              <section className="rounded-2xl border bg-card p-4 sm:p-6" data-testid="review-panel" aria-labelledby="review-heading">
                <h2 id="review-heading" ref={reviewHeading} tabIndex={-1} className="mb-3 text-lg font-semibold outline-none">
                  Review your statement
                </h2>
                <p className="mb-3 text-muted-foreground">
                  Check the summary below and every line in “Your story so far”. Use Correct to fix anything. You confirm exactly what
                  you reviewed at revision {snapshot.revision}; the doctor sees the summary built only from these words.
                </p>
                {confirmBlockers.length > 0 && (
                  <p role="status" className="mb-3" data-testid="confirm-blocked">
                    Confirm is available once {confirmBlockers.join(", ")}.
                  </p>
                )}
                <Button size="lg" className="h-11 px-5 text-base" onClick={confirm} disabled={busy || confirmBlockers.length > 0}>
                  Confirm and open doctor brief
                </Button>
              </section>
            )}

            <BriefReview snapshot={snapshot} />

            {confirmed && (
              <Notice tone="ok">
                Confirmed at revision {snapshot.confirmed_revision}.{" "}
                <Link className="underline" href={`/doctor/${encodeURIComponent(sessionId)}`}>
                  Open the doctor brief
                </Link>
                . If something is wrong, use Correct; you will be asked to confirm again.
              </Notice>
            )}
          </div>

          <div className="lg:col-span-5">
            <StatementHistory snapshot={snapshot} busy={busy || !online} onCorrect={correct} />
          </div>
        </div>
      )}
    </div>
  );
}
