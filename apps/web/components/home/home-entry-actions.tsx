import { ArrowRight } from "lucide-react";
import Link from "next/link";

export function PatientEntryButton() {
  return (
    <Link
      href="/intake"
      className="action-link primary-action"
      data-testid="home-patient-cta"
    >
      Start patient intake <ArrowRight aria-hidden="true" />
    </Link>
  );
}

export function DoctorEntryButton() {
  return (
    <Link href="/doctor" className="action-link" data-testid="home-doctor-cta">
      Open doctor workspace <ArrowRight aria-hidden="true" />
    </Link>
  );
}
