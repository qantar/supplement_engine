import type { Metadata } from "next";
// Self-hosted variable fonts — hermetic builds, no Google Fonts network
// dependency at build time (Docker-safe, offline-safe).
import "@fontsource-variable/inter";
import "@fontsource-variable/newsreader";
import "@fontsource-variable/newsreader/wght-italic.css";
import "@fontsource-variable/inconsolata";
import "./globals.css";

export const metadata: Metadata = {
  title: "Supplement Engine — Evidence-ranked recommendations",
  description:
    "Evidence-ranked nutraceutical recommendations with a deterministic safety gate.",
};

const themeScript = `(function(){try{var t=localStorage.getItem('theme');var d=t||(window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');document.documentElement.dataset.theme=d;}catch(e){document.documentElement.dataset.theme='light';}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
