# PulseDebug AI — Frontend Dockerfile
# File: frontend/Dockerfile
# Purpose:
#   Multi-stage production build for the Next.js frontend.
#   Stage 1 builds the application.
#   Stage 2 runs the optimized production server.
#   This keeps the final image small by discarding build tools.

# ── Stage 1: Build ──────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files for dependency caching
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --prefer-offline

# Copy source code
COPY . .

# Accept build-time environment variable
# This is needed because Next.js bakes NEXT_PUBLIC_ vars at build time
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build the Next.js application
RUN npm run build

# ── Stage 2: Production runner ───────────────────────────────
FROM node:18-alpine AS runner

WORKDIR /app

# Set production environment
ENV NODE_ENV=production

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Copy only what is needed to run the app
COPY --from=builder /app/public          ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static    ./.next/static

# Set correct ownership
RUN chown -R nextjs:nodejs /app

USER nextjs

# Expose frontend port
EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]