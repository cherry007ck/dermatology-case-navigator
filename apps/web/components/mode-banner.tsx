import type { ApiMode } from "@/lib/api/client";
import type { SessionSnapshot } from "@/lib/api/types";

import { type ChipTone, StatusChip } from "./status";

export const FICTIONAL_CASE_LABEL =
  "Fictional demonstration case — not published evidence";

/** Always-visible actual modes. Reports what the API returned, never what we hope is configured. */
export type VoiceIndicator = { label: string; tone: ChipTone };

export function ModeBanner({
  apiMode,
  snapshot,
  voice,
}: {
  apiMode: ApiMode;
  snapshot?: SessionSnapshot | null;
  /** Actual voice state; omitted where voice is not part of the view. */
  voice?: VoiceIndicator;
}) {
  const collection = snapshot?.collection;
  const modes = snapshot?.modes;
  return (
    <div
      className="mode-banner"
      aria-label="Current data and service modes"
      data-testid="mode-banner"
    >
      {apiMode === "mock" ? (
        <StatusChip tone="warning">
          Preview data · fixture responses only · not connected to a backend
        </StatusChip>
      ) : (
        <StatusChip tone="info">Live API</StatusChip>
      )}
      {collection &&
        (collection.mode === "synthetic" ? (
          <StatusChip tone="warning">
            Synthetic collection — fictional cases
          </StatusChip>
        ) : (
          <StatusChip tone="info">
            Published collection · {collection.source_review_count} developer
            source-reviewed
            {collection.clinical_reviewed ? "" : " · not clinically reviewed"}
          </StatusChip>
        ))}
      {modes &&
        (modes.storage === "memory" ? (
          <StatusChip tone="warning">
            Development storage — not Exasol
          </StatusChip>
        ) : (
          <StatusChip tone="ok">Stored in Exasol</StatusChip>
        ))}
      {modes &&
        (modes.extractor === "fixture" ? (
          <StatusChip tone="warning">Demo extraction</StatusChip>
        ) : (
          <StatusChip tone="info">Meta model extraction</StatusChip>
        ))}
      {voice && <StatusChip tone={voice.tone}>{voice.label}</StatusChip>}
    </div>
  );
}

export function FictionalDemoNotice() {
  return (
    <p className="rounded-xl border border-warning/40 bg-warning-surface px-4 py-3 text-warning-foreground">
      Fictional demonstration only. Do not enter real patient information. This
      prototype prepares a consultation brief; it does not diagnose, recommend
      treatment or assess urgent concerns. For urgent help, contact appropriate
      medical services.
    </p>
  );
}

export function SnapshotWarnings({ snapshot }: { snapshot: SessionSnapshot }) {
  if (!snapshot.warnings.length) return null;
  return (
    <ul
      className="space-y-1 text-sm text-muted-foreground"
      aria-label="Service warnings"
    >
      {snapshot.warnings.map((w) => (
        <li key={w}>• {w}</li>
      ))}
    </ul>
  );
}
