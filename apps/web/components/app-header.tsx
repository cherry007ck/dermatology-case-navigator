import Link from "next/link";
import { Stethoscope } from "lucide-react";

export function AppHeader() {
  return (
    <header className="app-header">
      <Link href="/" className="brand" aria-label="Exasol.sh home">
        <Stethoscope aria-hidden="true" strokeWidth={1.5} />
        <span>Exasol.sh</span>
      </Link>
      <p>Exasol hackathon project</p>
    </header>
  );
}
