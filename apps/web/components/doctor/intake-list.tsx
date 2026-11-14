"use client";

import Link from "next/link";
import { ArrowRight, RefreshCw } from "lucide-react";
import useSWR from "swr";
import { getApiClient } from "@/lib/api/client";
import type { SessionSnapshot } from "@/lib/api/types";
import { readSessionToken, useTabSessionIds } from "@/lib/session-store";
import { isConfirmedCurrent, statementHistory } from "@/lib/session/history";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/status";
import { ModeBanner } from "@/components/mode-banner";

export function IntakeList() {
  const ids = useTabSessionIds();
  const api = getApiClient();
  const { data, error, isLoading, mutate } = useSWR(
    ["doctor-intakes", ...ids],
    async () => {
      return Promise.all(
        ids.map(async (id) => {
          const token = readSessionToken(id);
          if (!token)
            throw new Error("This tab no longer has access to an intake.");
          return api.getSession(id, token);
        }),
      );
    },
    { shouldRetryOnError: false },
  );
  const shared = (data ?? []).filter(isConfirmedCurrent);
  const awaiting = shared.filter(
    (item) =>
      !item.clinician_notes.some(
        (note) => note.patient_revision === item.revision,
      ),
  );
  const reviewed = shared.filter((item) =>
    item.clinician_notes.some(
      (note) => note.patient_revision === item.revision,
    ),
  );

  function section(title: string, sessions: SessionSnapshot[]) {
    return (
      <section>
        <div className="table-band">
          <h2>{title}</h2>
          <span className="text-sm">
            {sessions.length} {sessions.length === 1 ? "intake" : "intakes"}
          </span>
        </div>
        {sessions.length ? (
          <div className="intake-table-scroll">
            <table className="intake-table">
              <thead>
                <tr>
                  <th>Intake</th>
                  <th>Patient-reported concern</th>
                  <th>Started</th>
                  <th>Status</th>
                  <th>
                    <span className="sr-only">Open intake</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((item) => {
                  const first = statementHistory(item)[0]?.current;
                  const number = ids.indexOf(item.session_id) + 1;
                  return (
                    <tr key={item.session_id}>
                      <td>
                        <span className="dcn-label">
                          Intake {String(number).padStart(2, "0")}
                        </span>
                      </td>
                      <td className="max-w-md">
                        {first?.text ?? "No patient statement recorded"}
                      </td>
                      <td className="whitespace-nowrap">
                        {first
                          ? new Date(first.created_at).toLocaleDateString(
                              undefined,
                              { month: "short", day: "numeric" },
                            )
                          : "—"}
                      </td>
                      <td>
                        {title === "Reviewed" ? "Reviewed" : "Awaiting review"}
                      </td>
                      <td>
                        <Link
                          className="action-link"
                          href={`/doctor/${encodeURIComponent(item.session_id)}`}
                        >
                          Open intake <ArrowRight aria-hidden="true" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-intakes">
            {title === "Reviewed"
              ? "No reviewed intakes yet."
              : "No shared intakes yet. Once a patient reviews and shares their story, it will appear here."}
          </div>
        )}
      </section>
    );
  }
  return (
    <>
      <div className="doctor-heading">
        <div className="flex items-center gap-5">
          <span className="eyebrow">Doctor workspace</span>
          <h1>Patient intakes</h1>
        </div>
        <Link className="text-action" href="/">
          Back to home
        </Link>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3">
        <p className="text-xs text-muted-foreground">
          Only encounters authorized in this browser tab are shown. This is not
          a clinic-wide patient directory.
        </p>
        <Button
          variant="ghost"
          onClick={() => void mutate()}
          disabled={isLoading}
        >
          <RefreshCw data-icon="inline-start" />
          Refresh
        </Button>
      </div>
      {error && (
        <div className="feedback-area">
          <Notice tone="error">
            Some intakes could not be loaded. Refresh to try again; no records
            were removed.
          </Notice>
        </div>
      )}
      {isLoading ? (
        <p role="status" className="p-6">
          Loading patient intakes…
        </p>
      ) : (
        <div className="intake-table-wrap">
          {section("Awaiting review", awaiting)}
          <div className="h-6" />
          {section("Reviewed", reviewed)}
        </div>
      )}
      {!isLoading && !error && shared.length === 0 && (
        <div className="px-6 pb-8">
          <Link className="action-link primary-action" href="/intake">
            Start patient intake <ArrowRight aria-hidden="true" />
          </Link>
        </div>
      )}
      <div className="service-status">
        <ModeBanner apiMode={api.mode} />
      </div>
    </>
  );
}
