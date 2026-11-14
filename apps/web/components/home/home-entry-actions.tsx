"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";

// Homepage entry buttons. Presentation plus navigation only: no API calls.
// Patient: /intake, the first step of the existing intake flow (access code, collection,
// demo notice), which then opens /intake/[session_id].
// Doctor: /doctor/[session_id] for an encounter started in this tab, because the doctor
// route needs the session token this tab holds. That route keeps its own guard: the brief
// opens only after the patient confirms and shares the current revision.

// Mirrors the key used by lib/session-store.ts (read-only here). If Luffy adds a
// "latest session in this tab" helper to session-store, use it instead.
const TOKEN_PREFIX = "dcn.session-token.";

function readTabSessionId(): string | null {
  let found: string | null = null;
  for (let i = 0; i < sessionStorage.length; i++) {
    const key = sessionStorage.key(i);
    if (key?.startsWith(TOKEN_PREFIX)) found = key.slice(TOKEN_PREFIX.length);
  }
  return found;
}

const noopSubscribe = () => () => {};

// Labels wrap at narrow widths or high zoom; min-h keeps a comfortable target without clipping.
const base =
  "inline-flex min-h-12 max-w-full items-center justify-center gap-2 rounded-none border px-5 py-2.5 text-left text-base leading-snug font-medium whitespace-normal text-[#111418] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#1f4e8c]";

function Arrow() {
  return <ArrowRight aria-hidden="true" className="size-4 shrink-0" />;
}

export function PatientEntryButton() {
  return (
    <Link href="/intake" className={`${base} border-[#1f4e8c] bg-[#e3edf9] hover:bg-[#d3e3f6]`} data-testid="home-patient-cta">
      Start patient intake
      <Arrow />
    </Link>
  );
}

export function DoctorEntryButton() {
  const sessionId = useSyncExternalStore(noopSubscribe, readTabSessionId, () => null);
  const className = `${base} border-[#111418] bg-white`;
  if (sessionId) {
    return (
      <Link href={`/doctor/${encodeURIComponent(sessionId)}`} className={`${className} hover:bg-[#f1f3f5]`} data-testid="home-doctor-cta">
        Open doctor workspace
        <Arrow />
      </Link>
    );
  }
  // No intake in this tab: stay visible and focusable, explain, and do not navigate.
  return (
    <div className="space-y-2">
      <button
        type="button"
        aria-disabled="true"
        aria-describedby="home-doctor-hint"
        className={`${className} cursor-not-allowed text-[#4b5560]`}
        data-testid="home-doctor-cta"
      >
        Open doctor workspace
        <Arrow />
      </button>
      <p id="home-doctor-hint" className="text-sm text-[#3f4851]">
        Share a patient intake first to review it here.
      </p>
    </div>
  );
}
