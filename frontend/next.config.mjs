/**
 * PulseDebug AI — Next.js Configuration
 * File: frontend/next.config.mjs
 * Purpose:
 *   Added output: 'standalone' for Docker multi-stage build.
 *   This produces a minimal self-contained server in .next/standalone
 *   which is copied into the production Docker image without node_modules.
 *   All existing rewrites and settings are preserved unchanged.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required for Docker multi-stage build
  // Produces .next/standalone with a minimal node server
  output: "standalone",

  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source:      "/api/backend/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;