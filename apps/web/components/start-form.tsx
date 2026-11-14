"use client";

import { ArrowLeft, ArrowRight, Mic } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { IntakeSteps } from "@/components/patient/intake-steps";
import { PhotoStatus } from "@/components/patient/photo-status";
import { Waveform } from "@/components/voice/waveform";
import { ModeBanner } from "@/components/mode-banner";
import { Notice } from "@/components/status";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, getApiClient, newRequestId } from "@/lib/api/client";
import type { CreateSessionResponse } from "@/lib/api/types";
import { saveSessionToken } from "@/lib/session-store";

export function StartForm() {
  const router = useRouter();
  const api = getApiClient();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const created = useRef<CreateSessionResponse | null>(null);
  const requestId = useRef<string | null>(null);

  async function start() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (!created.current) {
        requestId.current ??= newRequestId();
        if (api.mode === "mock") {
          const { collections } = await api.listCollections("fixture-preview");
          const collection =
            collections.find((item) => item.mode === "published") ??
            collections[0];
          if (!collection) throw new Error("No case collection is available.");
          created.current = await api.createSession("fixture-preview", {
            request_id: requestId.current,
            collection_id: collection.collection_id,
          });
        } else {
          const response = await fetch("/api/intake-start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ request_id: requestId.current }),
          });
          const data = await response.json();
          if (!response.ok)
            throw new Error(
              data.error?.message ??
                "Could not start intake. Please try again.",
            );
          created.current = data as CreateSessionResponse;
        }
      }
      const session = created.current;
      saveSessionToken(session.session_id, session.session_token);
      // Pass only a transient draft through the router's in-memory handoff, never a URL or storage.
      setIntakeDraft(session.session_id, text);
      router.push(`/intake/${encodeURIComponent(session.session_id)}`);
    } catch (e) {
      setError(
        e instanceof ApiRequestError || e instanceof Error
          ? e.message
          : "Could not start the intake.",
      );
      setBusy(false);
    }
  }

  return (
    <>
      <IntakeSteps step={0} />
      <div className="page-heading">
        <h1>Tell us about your skin concern</h1>
        <p>
          Describe what you noticed, when it started, and anything you&apos;ve
          tried.
        </p>
      </div>
      <div className="story-entry corner-marks">
        <section className="voice-intro" aria-label="Voice intake">
          <Mic
            className="microphone-icon"
            strokeWidth={1.3}
            aria-hidden="true"
          />
          <Waveform />
          <p className="voice-caption">Your story. In your own words.</p>
          <Button size="lg" variant="secondary" onClick={start} disabled={busy}>
            Start voice intake
          </Button>
          <button
            className="text-action"
            onClick={() => document.getElementById("initial-story")?.focus()}
          >
            Type instead
          </button>
          <p className="voice-help">
            Microphone access is requested only when voice is available and you
            choose to record.
          </p>
        </section>
        <section className="story-text">
          <label htmlFor="initial-story">Your words</label>
          <Textarea
            id="initial-story"
            placeholder="Tell us what has been happening…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={8000}
            rows={6}
            disabled={busy}
          />
          <PhotoStatus />
        </section>
      </div>
      {error && (
        <div className="feedback-area">
          <Notice tone="error">{error}</Notice>
        </div>
      )}
      <div className="workflow-actions corner-marks">
        <Link href="/" className="text-action">
          <ArrowLeft aria-hidden="true" /> Back
        </Link>
        <Button size="lg" onClick={start} disabled={busy}>
          {busy ? "Opening intake…" : "Continue"}
          <ArrowRight data-icon="inline-end" />
        </Button>
      </div>
      <div className="service-status">
        <ModeBanner apiMode={api.mode} />
      </div>
    </>
  );
}

const drafts = new Map<string, string>();
function setIntakeDraft(sessionId: string, text: string) {
  drafts.set(sessionId, text);
}
export function getIntakeDraft(sessionId: string) {
  return drafts.get(sessionId) ?? "";
}
export function clearIntakeDraft(sessionId: string) {
  drafts.delete(sessionId);
}
