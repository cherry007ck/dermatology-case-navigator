import { Suspense } from "react";

import { IntakeView } from "@/components/patient/intake-view";

export default function IntakePage() {
  return (
    <main className="workflow-page">
      <Suspense fallback={<p role="status">Loading encounter…</p>}>
        <IntakeView />
      </Suspense>
    </main>
  );
}
