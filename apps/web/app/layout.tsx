import type { Metadata, Viewport } from "next";
import { AppHeader } from "@/components/app-header";
import "./globals.css";

export const metadata: Metadata = {
  title: "Exasol.sh — Every story deserves a closer look",
  description:
    "Share your skin concern, review your story, and prepare for a more informed consultation. A dermatology consultation-preparation prototype, not a diagnostic service.",
};
export const viewport: Viewport = {
  themeColor: "#f7f8fa",
  colorScheme: "light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body>
        <div className="app-frame">
          <AppHeader />
          <div className="app-content">{children}</div>
        </div>
        <footer className="app-footer">
          <span>
            Consultation preparation. Clinical decisions stay with the doctor.
          </span>
          <span>Fictional encounters only · Not an Exasol product</span>
        </footer>
      </body>
    </html>
  );
}
