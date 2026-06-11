import type { Metadata } from "next";
import "./globals.css";

// Fonts are wired via @font-face in globals.css with robust system fallbacks,
// so the build never depends on a network fetch at compile time. To use the
// Inter / IBM Plex Mono webfonts, drop the .woff2 files into /public/fonts
// (the @font-face rules already point at them) or swap in next/font/google.

export const metadata: Metadata = {
  title: "Supplement Engine — Clinician Console",
  description:
    "Evidence-ranked nutraceutical recommendations with a deterministic safety gate.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ground bg-grid">{children}</body>
    </html>
  );
}
