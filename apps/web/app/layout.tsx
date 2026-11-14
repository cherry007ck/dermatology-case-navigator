import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dermatology Case Navigator — fictional demo",
  description:
    "Consultation preparation and evidence navigation prototype for fictional encounters. No diagnosis or treatment advice.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <div className="flex-1">{children}</div>
        <footer className="border-t bg-card px-4 py-3 text-sm text-muted-foreground">
          Double Helix team · Hackathon prototype for fictional encounters only. Not an Exasol product.
        </footer>
      </body>
    </html>
  );
}
