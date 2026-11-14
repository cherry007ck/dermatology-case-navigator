import { Suspense } from "react";

import { IntakeView } from "@/components/patient/intake-view";

export default function IntakePage() {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8">
      <Suspense fallback={<p role="status">Loading encounter…</p>}>
        <IntakeView />
      </Suspense>
    </main>
  );
}
