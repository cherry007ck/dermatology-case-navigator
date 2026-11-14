"use client";

// Loaded only in the browser (see voice-panel.tsx). Mounts the SDK provider once and
// hands stable controls to the panel. Sessions start from the user's click, never
// from a mount effect: React Strict Mode's simulated unmount would otherwise trigger
// the provider's cleanup and cancel the pending connection before it opens.
import {
  ConversationProvider,
  type DisconnectionDetails,
  type MessagePayload,
  useConversationControls,
  useConversationMode,
} from "@elevenlabs/react";
import { useEffect, useRef } from "react";

export type ConversationEvent =
  | { type: "connected"; conversationId: string }
  | { type: "mode"; speaking: boolean }
  | { type: "message"; conversationId: string; payload: MessagePayload }
  | { type: "disconnected"; reason: "user" | "agent" | "error"; closeCode?: number }
  | { type: "error" };

export type VoiceControls = {
  start: (signedUrl: string, bindingToken: string) => void;
  stop: () => void;
};

type Props = {
  onEvent: (event: ConversationEvent) => void;
  onControls: (controls: VoiceControls | null) => void;
};

export default function VoiceEngine({ onEvent, onControls }: Props) {
  const conversationId = useRef("");
  return (
    <ConversationProvider
      onConnect={({ conversationId: id }) => {
        conversationId.current = id;
        onEvent({ type: "connected", conversationId: id });
      }}
      onMessage={(payload) => onEvent({ type: "message", conversationId: conversationId.current, payload })}
      onDisconnect={(details: DisconnectionDetails) =>
        // Only the numeric close code is surfaced; provider close reasons are not displayed.
        onEvent({ type: "disconnected", reason: details.reason, closeCode: details.reason === "user" ? undefined : details.closeCode })
      }
      // SDK error text may contain provider detail; the panel shows a fixed message instead.
      onError={() => onEvent({ type: "error" })}
    >
      <Bridge onEvent={onEvent} onControls={onControls} />
    </ConversationProvider>
  );
}

function Bridge({ onEvent, onControls }: Props) {
  const { startSession, endSession } = useConversationControls();
  const { isSpeaking } = useConversationMode();

  useEffect(() => {
    onControls({
      start: (signedUrl, bindingToken) =>
        startSession({
          signedUrl,
          // Signed URLs are WebSocket URLs; never let the SDK infer WebRTC for them.
          connectionType: "websocket",
          // secret__ variables are only usable in tool headers and never sent to the LLM.
          dynamicVariables: { secret__voice_binding: bindingToken },
        }),
      stop: () => endSession(),
    });
    return () => onControls(null); // registration only; the provider ends sessions on real unmount
  }, [startSession, endSession, onControls]);

  useEffect(() => {
    onEvent({ type: "mode", speaking: isSpeaking });
  }, [isSpeaking, onEvent]);

  return null;
}
