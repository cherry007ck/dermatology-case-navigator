import { FictionalDemoNotice } from "@/components/mode-banner";
import { StartForm } from "@/components/start-form";
import { StatusChip } from "@/components/status";
import { getApiMode } from "@/lib/api/client";

// First step of the patient intake flow. This is the setup block that used to sit on
// the homepage (mode label, fictional-demo notice, access code and collection),
// moved unchanged. StartForm creates the session and opens /intake/[session_id].
export default function IntakeStartPage() {
  const apiMode = getApiMode();
  return (
    <main className="mx-auto w-full max-w-2xl space-y-6 px-4 py-10">
      <header className="space-y-3">
        <p className="text-sm font-medium tracking-wide text-primary uppercase">Patient intake</p>
        <h1 className="text-3xl font-semibold">Start patient intake</h1>
        <p className="text-muted-foreground">
          Dermatology Case Navigator: a fictional patient&apos;s own words become a reviewable, source-linked brief for the
          doctor, with optional comparison to documented cases from one clearly labelled collection.
        </p>
        <div>
          {apiMode === "mock" ? (
            <StatusChip tone="warning">Mock API — shared fixture responses, no backend</StatusChip>
          ) : (
            <StatusChip tone="info">Live API</StatusChip>
          )}
        </div>
      </header>
      <FictionalDemoNotice />
      <StartForm />
    </main>
  );
}
