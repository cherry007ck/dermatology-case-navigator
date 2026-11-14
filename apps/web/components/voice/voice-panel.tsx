"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import type { VoiceIndicator } from "@/components/mode-banner";
import { Notice } from "@/components/status";
import { Button } from "@/components/ui/button";
import { ApiRequestError } from "@/lib/api/transport";
import { fetchVoiceAvailability, requestMicrophone, requestVoiceSession } from "@/lib/voice/start";
import { appendUnique, type CapturedTurn, normalizeMessage } from "@/lib/voice/transcript";

import type { ConversationEvent, VoiceControls } from "./voice-conversation";

// The SDK (and its LiveKit dependency) loads only in the browser, and only when voice is available.
const VoiceEngine = dynamic(() => import("./voice-conversation"), { ssr: false });

export type VoiceState =
  | { kind: "checking" }
  | { kind: "unavailable" }
  | { kind: "idle" }
  | { kind: "requesting_mic" }
  | { kind: "mic_denied" }
  | { kind: "no_mic" }
  | { kind: "starting" }
  | { kind: "connecting" }
  | { kind: "connected"; speaking: boolean }
  | { kind: "ended" }
  | { kind: "error"; message: string };

export function voiceIndicator(state: VoiceState): VoiceIndicator {
  switch (state.kind) {
    case "connected":
      return { label: state.speaking ? "Voice connected — assistant speaking" : "Voice connected — listening", tone: "ok" };
    case "connecting":
    case "starting":
    case "requesting_mic":
      return { label: "Voice connecting…", tone: "info" };
    case "mic_denied":
      return { label: "Microphone denied — typed intake", tone: "warning" };
    case "error":
      return { label: "Voice error — typed intake", tone: "error" };
    case "unavailable":
      return { label: "Voice not configured — typed intake", tone: "neutral" };
    default:
      return { label: "Voice off — typed intake", tone: "neutral" };
  }
}

type Props = {
  sessionId: string;
  token: string;
  revision: number;
  onStateChange: (state: VoiceState) => void;
  /** Persists one finalized transcript turn through the serialized session writer. */
  persistTurn: (turn: CapturedTurn) => Promise<void>;
  /**
   * False during review/confirmation: any live session is ended and Start is disabled.
   * The panel stays mounted, so late finalized events from the closing session are still
   * persisted (and invalidate the review) instead of being silently dropped.
   */
  captureAllowed?: boolean;
  /** Reports unsaved transcript lines so review can block confirmation until they are saved. */
  onSyncChange?: (sync: { saving: boolean; failed: boolean }) => void;
};

type SyncStatus = "saving" | "saved" | "failed";

/**
 * Private voice connection. Each finalized transcript event (user and agent) is
 * persisted once through POST /turns via the session writer, with its stable
 * event-derived turn ID. The agent's advance_intake webhook then advances the
 * session server-side; the intake view polls for the resulting question.
 *
 * The SDK provider stays mounted for the panel's lifetime and sessions start from
 * the user's click. `captureAllowed={false}` (review) ends the session; unmounting does too.
 */
export function VoicePanel({ sessionId, token, revision, onStateChange, persistTurn, captureAllowed = true, onSyncChange }: Props) {
  const [state, setState] = useState<VoiceState>({ kind: "checking" });
  const [captured, setCaptured] = useState<CapturedTurn[]>([]);
  const [sync, setSync] = useState<Record<string, SyncStatus>>({});
  const controls = useRef<VoiceControls | null>(null);
  const seen = useRef(new Set<string>()); // each event persisted at most once per panel

  useEffect(() => onStateChange(state), [state, onStateChange]);

  useEffect(() => {
    let active = true;
    fetchVoiceAvailability().then((ok) => active && setState({ kind: ok ? "idle" : "unavailable" }));
    return () => {
      active = false;
    };
  }, []);

  const onControls = useCallback((value: VoiceControls | null) => {
    controls.current = value;
  }, []);

  const liveNow = state.kind === "connecting" || state.kind === "connected";
  useEffect(() => {
    if (!captureAllowed && liveNow) controls.current?.stop();
  }, [captureAllowed, liveNow]);

  async function start() {
    setState({ kind: "requesting_mic" });
    const mic = await requestMicrophone();
    if (mic === "denied") return setState({ kind: "mic_denied" });
    if (mic !== "granted") return setState({ kind: "no_mic" });
    setState({ kind: "starting" });
    try {
      const grant = await requestVoiceSession(sessionId, token, revision);
      if (!controls.current) {
        return setState({ kind: "error", message: "Voice is still loading. Retry in a moment." });
      }
      setState({ kind: "connecting" });
      controls.current.start(grant.signed_url, grant.binding_token);
    } catch (e) {
      setState({ kind: "error", message: e instanceof ApiRequestError ? e.message : "Voice could not start." });
    }
  }

  const onEvent = useCallback((event: ConversationEvent) => {
    switch (event.type) {
      case "connected":
        setState({ kind: "connected", speaking: false });
        break;
      case "mode":
        setState((prev) => (prev.kind === "connected" ? { ...prev, speaking: event.speaking } : prev));
        break;
      case "message": {
        const turn = normalizeMessage(event.conversationId || "pending", event.payload);
        if (!turn || seen.current.has(turn.turnId)) break;
        seen.current.add(turn.turnId);
        setCaptured((prev) => appendUnique(prev, turn));
        setSync((prev) => ({ ...prev, [turn.turnId]: "saving" }));
        persistTurn(turn).then(
          () => setSync((prev) => ({ ...prev, [turn.turnId]: "saved" })),
          () => setSync((prev) => ({ ...prev, [turn.turnId]: "failed" })),
        );
        break;
      }
      case "disconnected":
        setState((prev) => {
          const code = event.closeCode ? ` (close code ${event.closeCode})` : "";
          if (prev.kind === "connecting") {
            // Closing before onConnect is never a normal stop.
            return { kind: "error", message: `The voice connection closed before it opened${code}. Reconnect or keep typing.` };
          }
          if (event.reason === "error") {
            return { kind: "error", message: `The voice connection closed unexpectedly${code}. Reconnect or keep typing.` };
          }
          return { kind: "ended" };
        });
        break;
      case "error":
        setState({ kind: "error", message: "The voice connection reported an error." });
        break;
    }
  }, [persistTurn]);

  function retryFailed() {
    for (const turn of captured) {
      if (sync[turn.turnId] !== "failed") continue;
      setSync((prev) => ({ ...prev, [turn.turnId]: "saving" }));
      persistTurn(turn).then(
        () => setSync((prev) => ({ ...prev, [turn.turnId]: "saved" })),
        () => setSync((prev) => ({ ...prev, [turn.turnId]: "failed" })),
      );
    }
  }

  const anyFailed = captured.some((t) => sync[t.turnId] === "failed");
  const anySaving = captured.some((t) => sync[t.turnId] === "saving");
  useEffect(() => onSyncChange?.({ saving: anySaving, failed: anyFailed }), [anySaving, anyFailed, onSyncChange]);
  const live = state.kind === "connecting" || state.kind === "connected";
  const busy = state.kind === "requesting_mic" || state.kind === "starting";
  const available = state.kind !== "checking" && state.kind !== "unavailable";

  return (
    <section className="space-y-3 rounded-2xl border bg-card p-4 sm:p-6" aria-labelledby="voice-heading" data-testid="voice-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="voice-heading" className="text-lg font-semibold">
          Speak instead
        </h2>
        {!live ? (
          <Button size="lg" variant="outline" className="h-11 text-base" onClick={start} disabled={busy || !available || !captureAllowed}>
            {state.kind === "ended" || state.kind === "error" || state.kind === "mic_denied" ? "Reconnect voice" : "Start voice"}
          </Button>
        ) : (
          <Button size="lg" variant="outline" className="h-11 text-base" onClick={() => controls.current?.stop()}>
            Stop voice
          </Button>
        )}
      </div>

      <p role="status" aria-live="polite" className="text-muted-foreground" data-testid="voice-status">
        {
          {
            checking: "Checking whether voice is available…",
            unavailable: "Voice is not configured on this server. Typed intake is available.",
            idle: "Voice is optional. Your browser will ask for microphone access when you start.",
            requesting_mic: "Waiting for microphone permission…",
            mic_denied: "Microphone access was denied. You can keep typing, or allow the microphone in your browser and reconnect.",
            no_mic: "No usable microphone was found. You can keep typing.",
            starting: "Starting a private voice session…",
            connecting: "Connecting…",
            connected: state.kind === "connected" && state.speaking ? "Assistant speaking" : "Listening",
            ended: "Voice stopped. You can keep typing or reconnect.",
            error: "",
          }[state.kind]
        }
      </p>
      {state.kind === "error" && <Notice tone="error">{state.message} Typed intake still works.</Notice>}
      {!captureAllowed && available && (
        <p className="text-sm text-muted-foreground" data-testid="voice-paused">
          Voice is paused while you review. Correct your statement below if anything is wrong.
        </p>
      )}

      {available && <VoiceEngine onEvent={onEvent} onControls={onControls} />}

      {captured.length > 0 && (
        <div className="space-y-2" data-testid="voice-transcript">
          <p className="text-sm font-medium">Voice transcript — please review</p>
          <p className="text-sm text-muted-foreground">
            Automatic transcription, not a recording. Your words are added to your story; check them before confirming.
          </p>
          {anyFailed && (
            <Notice tone="error">
              Some words could not be saved yet.{" "}
              <Button variant="outline" size="sm" onClick={retryFailed}>
                Retry saving
              </Button>
            </Notice>
          )}
          <ol className="space-y-2">
            {captured.map((t) => (
              <li key={t.turnId} className="rounded-xl border bg-background p-3" data-sync={sync[t.turnId]}>
                <span className="text-sm text-muted-foreground">{t.role === "patient" ? "You (transcribed)" : "Assistant"}: </span>
                {t.text}
                <span className="ml-2 text-xs text-muted-foreground">
                  {{ saving: "· saving…", saved: "· saved", failed: "· not saved" }[sync[t.turnId] ?? "saving"]}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
