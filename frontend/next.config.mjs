/**
 * PulseDebug AI — Next.js Configuration
 * File: frontend/next.config.mjs
 * Purpose:
 *   Configures the Next.js build. Rewrites /api/backend/* to the FastAPI
 *   backend so the frontend can proxy requests without exposing the Render
 *   URL to the browser.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;