"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import useSWR from "swr";
import { Notice } from "@/components/status";
import { PatientFlow } from "@/components/patient/patient-flow";
import { getIntakeDraft, clearIntakeDraft } from "@/components/start-form";
import { VoicePanel, type VoiceState } from "@/components/voice/voice-panel";
import { ApiRequestError, getApiClient, newRequestId } from "@/lib/api/client";
import type { Turn } from "@/lib/api/types";
import { isConfirmedCurrent } from "@/lib/session/history";
import { SessionWriter } from "@/lib/session/writer";
import {
  rememberConfirmedRevision,
  useLastConfirmedRevision,
  useSessionToken,
} from "@/lib/session-store";
import { useOnline } from "@/lib/use-online";
import type { CapturedTurn } from "@/lib/voice/transcript";
import { pendingQuestionId, toTurnInput } from "@/lib/voice/sync";

type Failure = { message: string; retry: (() => void) | null };
const noopSubscribe = () => () => {};

function failureMessage(e: unknown, fallback: string): string {
  if (!(e instanceof ApiRequestError)) return fallback;
  if (e.code === "REVISION_CONFLICT")
    return "This encounter changed. Please review the latest version before continuing.";
  if (e.code === "NETWORK_UNAVAILABLE")
    return "The service could not be reached. Your text is still here. Check your connection and retry.";
  return e.message;
}

/** Patient flow never displays case content, diagnoses, actions or rankings. */
export function IntakeView() {
  const { session_id: rawId } = useParams<{ session_id: string }>();
  const sessionId = decodeURIComponent(rawId);
  const api = getApiClient();
  const token = useSessionToken(sessionId);
  const online = useOnline();
  const lastConfirmed = useLastConfirmedRevision(sessionId);
  const writer = useMemo(
    () =>
      token ? new SessionWriter(api, sessionId, token, newRequestId) : null,
    [api, sessionId, token],
  );
  const [text, setText] = useState(() => getIntakeDraft(sessionId));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>({
    kind: "checking",
  });
  const [voiceSync, setVoiceSync] = useState({ saving: false, failed: false });
  const snapshot = useSyncExternalStore(
    useCallback(
      (cb) => (writer ? writer.subscribe(cb) : noopSubscribe()),
      [writer],
    ),
    () => writer?.snapshot ?? null,
    () => null,
  );
  const pendingWrites = useSyncExternalStore(
    useCallback(
      (cb) => (writer ? writer.subscribePending(cb) : noopSubscribe()),
      [writer],
    ),
    () => writer?.pendingWrites ?? 0,
    () => 0,
  );
  const voiceLive = [
    "connected",
    "connecting",
    "starting",
    "requesting_mic",
  ].includes(voiceState.kind);
  const { error: loadError, mutate } = useSWR(
    writer ? ["intake", sessionId, token] : null,
    () => writer!.refresh(),
    {
      refreshInterval: voiceLive ? 750 : 0,
      revalidateOnFocus: true,
      shouldRetryOnError: false,
    },
  );
  const question =
    snapshot?.questions.find(
      (q) => q.question_id === pendingQuestionId(snapshot),
    ) ?? null;
  const ready = snapshot?.state === "ready_to_confirm";
  const confirmed = snapshot ? isConfirmedCurrent(snapshot) : false;

  useEffect(() => () => clearIntakeDraft(sessionId), [sessionId]);

  const persistVoiceTurn = useCallback(
    async (turn: CapturedTurn) => {
      if (!writer) throw new Error("Session unavailable");
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
        message: `Your words were saved, but processing failed: ${failureMessage(e, "Please retry.")}`,
        retry: () => void guarded(runAdvance),
      });
    }
  }

  function submit(answerText: string) {
    if (!writer || !answerText.trim() || !online) return;
    // Stable turn ID across retries prevents duplicate patient statements.
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
          clearIntakeDraft(sessionId);
          await runAdvance();
        } catch (e) {
          if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT")
            await writer.refresh().catch(() => undefined);
          setFailure({
            message: failureMessage(e, "Could not save your words."),
            retry:
              !(e instanceof ApiRequestError) || e.retryable ? attempt : null,
          });
        }
      });
    attempt();
  }

  function skip() {
    if (!writer || !question || !token) return;
    const questionId = question.question_id;
    void guarded(async () => {
      try {
        await writer.write((base) =>
          api.skip(sessionId, token, {
            request_id: newRequestId(),
            expected_revision: base.revision,
            question_id: questionId,
          }),
        );
        setText("");
        setNotice("Question skipped. This is not recorded as a ‘no’.");
        await runAdvance();
      } catch (e) {
        setFailure({
          message: failureMessage(e, "Could not skip the question."),
          retry: null,
        });
      }
    });
  }

  async function correct(
    turn: Turn,
    replacementText: string,
  ): Promise<boolean> {
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
        setNotice(
          "Correction saved. Your original words remain in the record.",
        );
        await runAdvance();
      } catch (e) {
        if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT")
          await writer.refresh().catch(() => undefined);
        setFailure({
          message: failureMessage(e, "Could not save the correction."),
          retry: null,
        });
      }
    });
    return ok;
  }

  function confirm() {
    if (!writer || !token || !snapshot) return;
    const reviewedRevision = snapshot.revision;
    void guarded(async () => {
      try {
        // Drain late voice writes, then confirm only the exact revision the patient reviewed.
        await writer.flush();
        const latest = await writer.refresh();
        if (
          latest.revision !== reviewedRevision ||
          latest.state !== "ready_to_confirm"
        ) {
          setFailure({
            message:
              "Your words changed while you were reviewing. Please review the latest version before sharing.",
            retry: null,
          });
          return;
        }
        const result = await writer.write((base) =>
          api.confirm(sessionId, token, {
            request_id: newRequestId(),
            expected_revision: base.revision,
          }),
        );
        if (result.confirmed_revision !== null)
          rememberConfirmedRevision(sessionId, result.confirmed_revision);
        setNotice(null);
        setFailure(null);
      } catch (e) {
        if (e instanceof ApiRequestError && e.code === "REVISION_CONFLICT")
          await writer.refresh().catch(() => undefined);
        setFailure({
          message: failureMessage(e, "Could not share the intake."),
          retry: null,
        });
      }
    });
  }

  if (token === null)
    return (
      <div className="feedback-area">
        <Notice tone="error">
          This tab has no access to that encounter.{" "}
          <Link className="underline" href="/intake">
            Start a new intake
          </Link>
          .
        </Notice>
      </div>
    );
  const blockers = [
    voiceLive && "voice is still stopping",
    pendingWrites > 0 && "your words are still saving",
    (voiceSync.saving || voiceSync.failed) &&
      "voice words have not all been saved",
    !online && "you are offline",
    snapshot?.brief?.patient_revision !== snapshot?.revision &&
      "the summary needs to be updated",
  ].filter(Boolean) as string[];
  return (
    <PatientFlow
      apiMode={api.mode}
      snapshot={snapshot}
      question={question}
      text={text}
      setText={setText}
      busy={busy}
      online={online}
      ready={ready}
      confirmed={confirmed}
      blockers={blockers}
      onSubmit={submit}
      onSkip={skip}
      onCorrect={correct}
      onConfirm={confirm}
      failure={
        failure ??
        (loadError
          ? {
              message: failureMessage(loadError, "Could not load intake."),
              retry: () => void mutate(),
            }
          : null)
      }
      notice={notice}
      invalidated={lastConfirmed !== null && !!snapshot && !confirmed}
      voice={
        snapshot && token ? (
          <VoicePanel
            sessionId={sessionId}
            token={token}
            revision={snapshot.revision}
            onStateChange={setVoiceState}
            persistTurn={persistVoiceTurn}
            captureAllowed={!ready && !confirmed}
            onSyncChange={setVoiceSync}
          />
        ) : null
      }
    />
  );
}
