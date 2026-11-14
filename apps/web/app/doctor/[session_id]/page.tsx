import { Suspense } from "react";

import { DoctorWorkspace } from "@/components/doctor/doctor-workspace";

export default function DoctorPage() {
  return (
    <main className="workflow-page">
      <Suspense fallback={<p role="status">Loading doctor workspace…</p>}>
        <DoctorWorkspace />
      </Suspense>
    </main>
  );
}
