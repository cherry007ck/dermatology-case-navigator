"use client";

// Session bearer tokens live in this tab's sessionStorage only (docs/03-api-contract.md).
// Never put tokens in URLs, localStorage, logs or snapshot JSON.
import { useSyncExternalStore } from "react";

const key = (sessionId: string) => `dcn.session-token.${sessionId}`;
const confirmedKey = (sessionId: string) => `dcn.last-confirmed.${sessionId}`;
const CHANGE_EVENT = "dcn-session-store";

export function saveSessionToken(sessionId: string, token: string): void {
  sessionStorage.setItem(key(sessionId), token);
}

const noopSubscribe = () => () => {};

/** `undefined` while server-rendering, `null` when this tab holds no token for the session. */
export function useSessionToken(sessionId: string): string | null | undefined {
  return useSyncExternalStore(
    noopSubscribe,
    () => sessionStorage.getItem(key(sessionId)),
    () => undefined,
  );
}

function subscribeChanges(callback: () => void) {
  window.addEventListener(CHANGE_EVENT, callback);
  return () => window.removeEventListener(CHANGE_EVENT, callback);
}

/**
 * The last revision this tab saw confirmed. UI memory only (not authoritative): used to
 * tell the patient and doctor that an earlier confirmation no longer applies.
 */
export function rememberConfirmedRevision(sessionId: string, revision: number): void {
  sessionStorage.setItem(confirmedKey(sessionId), String(revision));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function useLastConfirmedRevision(sessionId: string): number | null {
  const raw = useSyncExternalStore(
    subscribeChanges,
    () => sessionStorage.getItem(confirmedKey(sessionId)),
    () => null,
  );
  return raw === null ? null : Number(raw);
}
