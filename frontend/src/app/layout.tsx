/**
 * PulseDebug AI — Root Layout
 * File: frontend/src/app/layout.tsx
 * Purpose:
 *   Next.js App Router root layout. Wraps every page including the new
 *   /analyze and /integrate routes. Sets metadata, loads fonts via CSS,
 *   and renders the ambient scan-line animation overlay.
 *
 *   The globals.css import is a side-effect import — it injects Tailwind
 *   base styles and custom CSS variables globally. The tsconfig.json must
 *   have moduleResolution set to "bundler" for this to resolve without error.
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PulseDebug AI — API Incident Triage",
  description:
    "AI-powered API incident triage assistant. Detect anomalies, cluster failures, correlate deployments, and get Gemini-powered debugging guidance.",
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><text y='26' font-size='28'>⚡</text></svg>",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="grid-bg min-h-screen antialiased">
        <div className="scan-line" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}