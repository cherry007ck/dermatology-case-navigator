"use client";

import { useState } from "react";

import { EvidenceQuotes } from "@/components/evidence";
import { StatusChip } from "@/components/status";
import type { CaseChange, PatientFact, SearchVersion, SessionSnapshot } from "@/lib/api/types";

// Before/after view built only from stored, immutable search versions in the snapshot.
// Nothing here recomputes a ranking: order, exclusions and reasons are the backend's.

const EXCLUSION_LABEL: Record<SearchVersion["excluded_cases"][number]["reason"], string> = {
  site_conflict: "Different explicitly documented body site",
  exposure_conflict: "Explicitly contradictory product/exposure history",
  no_shared_symptom: "No explicitly shared symptom at the same site",
  no_shared_site: "No explicitly shared site",
  unreviewed_source: "Source not reviewed",
  source_mode_mismatch: "Different collection kind",
  invalid_evidence: "Evidence failed validation",
};

const CHANGE_TONE: Record<CaseChange["change"], "info" | "error" | "neutral" | "warning"> = {
  appeared: "info",
  removed: "error",
  moved: "warning",
  unchanged: "neutral",
};

function titleFor(snapshot: SessionSnapshot, caseId: string): string {
  for (const search of snapshot.search_history) {
    const card = search.cards.find((c) => c.case_id === caseId);
    if (card) return card.title;
  }
  return caseId;
}

function factLabel(f: PatientFact): string {
  if (f.key === "symptom_site" && f.value?.includes("@")) {
    const [symptom, site] = f.value.split("@");
    const pair = `${symptom.replaceAll("_", " ")} on the ${site.replaceAll("_", " ")}`;
    return `symptom at site: ${pair}${f.status === "negated" ? " (denied)" : ""}`;
  }
  const value = f.value ?? (f.status === "unknown" ? "unknown" : "not given");
  return `${f.key.replaceAll("_", " ")}: ${value.replaceAll("_", " ")}${f.status === "negated" ? " (denied)" : ""}${f.status === "conflicting" ? " (conflicting)" : ""}`;
}

function RankList({ snapshot, search, label }: { snapshot: SessionSnapshot; search: SearchVersion | null; label: string }) {
  return (
    <div className="min-w-0 flex-1 overflow-hidden rounded-sm border">
      <h3 className="dcn-band">
        {label}
        {search && <span className="ml-2 text-sm font-normal text-muted-foreground">patient revision {search.patient_revision}</span>}
      </h3>
      <div className="space-y-2 px-3 py-2">
      {!search ? (
        <p className="text-muted-foreground">No earlier comparison.</p>
      ) : search.ranked_case_ids.length === 0 ? (
        <p className="text-muted-foreground">No qualifying case.</p>
      ) : (
        <ol className="list-decimal space-y-1 pl-5">
          {search.ranked_case_ids.map((id) => (
            <li key={id}>{titleFor(snapshot, id)}</li>
          ))}
        </ol>
      )}
      {search && search.excluded_cases.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">Excluded ({search.excluded_cases.length})</summary>
          <ul className="mt-1 space-y-1">
            {search.excluded_cases.map((x) => (
              <li key={x.case_id}>
                {titleFor(snapshot, x.case_id)} — {EXCLUSION_LABEL[x.reason]}
                <EvidenceQuotes evidence={x.evidence} />
              </li>
            ))}
          </ul>
        </details>
      )}
      </div>
    </div>
  );
}

export function ComparisonHistory({ snapshot }: { snapshot: SessionSnapshot }) {
  const history = snapshot.search_history;
  const [index, setIndex] = useState(history.length - 1);
  if (history.length === 0) return <p className="text-muted-foreground">No comparison has been run.</p>;

  const safeIndex = Math.min(Math.max(index, 0), history.length - 1);
  const after = history[safeIndex];
  const before = safeIndex > 0 ? history[safeIndex - 1] : null;
  const stale = after.patient_revision !== snapshot.revision;
  const newFactIds = new Set(after.input_fact_ids.filter((id) => !before?.input_fact_ids.includes(id)));
  const newFacts = snapshot.facts.filter((f) => newFactIds.has(f.fact_id));
  const meaningful = after.changes.filter((c) => c.change !== "unchanged");

  return (
    <div className="space-y-4" data-testid="comparison-history">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="search-version" className="text-sm text-muted-foreground">
          Comparison step
        </label>
        <select
          id="search-version"
          className="h-9 max-w-full min-w-0 rounded-sm border border-input bg-card px-2"
          value={safeIndex}
          onChange={(e) => setIndex(Number(e.target.value))}
        >
          {history.map((s, i) => (
            <option key={s.search_id} value={i}>
              {i + 1} of {history.length} — after patient revision {s.patient_revision}
            </option>
          ))}
        </select>
        {stale && <StatusChip tone="warning">Earlier step — not the current revision</StatusChip>}
      </div>

      {newFacts.length > 0 && (
        <div className="space-y-2">
          <h3 className="dcn-label">New patient details at this step</h3>
          <ul className="space-y-1">
            {newFacts.map((f) => (
              <li key={f.fact_id}>
                {factLabel(f)}
                <EvidenceQuotes evidence={f.evidence} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-col gap-4 sm:flex-row">
        <RankList snapshot={snapshot} search={before} label="Before" />
        <RankList snapshot={snapshot} search={after} label="After" />
      </div>

      <div className="space-y-2">
        <h3 className="dcn-label">Why it changed</h3>
        {meaningful.length === 0 ? (
          <p className="text-muted-foreground">
            {before ? "The order did not change at this step." : "First comparison for this encounter."}
          </p>
        ) : null}
        <ul className="space-y-3">
          {(meaningful.length ? meaningful : before ? [] : after.changes).map((c) => (
            <li key={c.case_id} data-testid="case-change" className="space-y-1 rounded-sm border px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{titleFor(snapshot, c.case_id)}</span>
                <StatusChip tone={CHANGE_TONE[c.change]}>
                  {c.change}
                  {c.from_rank || c.to_rank ? ` · rank ${c.from_rank ?? "—"} → ${c.to_rank ?? "—"}` : ""}
                </StatusChip>
              </div>
              <p>{c.reason}</p>
              <EvidenceQuotes evidence={c.evidence} />
            </li>
          ))}
        </ul>
      </div>
      <p className="border-t pt-2 font-mono text-xs break-all text-muted-foreground">
        Algorithm {after.algorithm_version} · collection version {after.collection_version.slice(0, 12)}… · stored search {after.search_id}
      </p>
    </div>
  );
}
