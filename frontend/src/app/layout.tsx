/**
 * PulseDebug AI — Root Layout
 * File: frontend/src/app/layout.tsx
 * Purpose:
 *   Next.js root layout. Sets document metadata and renders the ambient
 *   scan-line animation overlay that appears on every page.
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="grid-bg min-h-screen antialiased">
        <div className="scan-line" aria-hidden="true" />
        {children}
      </body>
    </html>
  );
}