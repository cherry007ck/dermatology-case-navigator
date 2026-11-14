import { Suspense } from "react";

import { DoctorWorkspace } from "@/components/doctor/doctor-workspace";

export default function DoctorPage() {
  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8">
      <Suspense fallback={<p role="status">Loading doctor workspace…</p>}>
        <DoctorWorkspace />
      </Suspense>
    </main>
  );
}
