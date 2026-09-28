# syntax=docker/dockerfile:1

# ==============================================================================
# Stage 1: deps — install node_modules (its own layer, cached unless
# package*.json change).
# ==============================================================================
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ==============================================================================
# Stage 2: builder — runs `next build`.
#
# IMPORTANT: NEXT_PUBLIC_* variables are baked into the client-side JS
# bundle AT BUILD TIME, not read at container start. Passing them as
# regular `environment:` values in docker-compose would have no effect
# on the browser bundle -- they have to arrive as Docker build ARGs and
# be re-exported as ENV here, before `npm run build` runs. This is the
# single most common way a Next.js container "works" but the deployed
# frontend still can't reach the backend.
# ==============================================================================
FROM node:20-slim AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_BACKEND_HOST
ARG NEXT_PUBLIC_BACKEND_PORT
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_BACKEND_HOST=${NEXT_PUBLIC_BACKEND_HOST}
ENV NEXT_PUBLIC_BACKEND_PORT=${NEXT_PUBLIC_BACKEND_PORT}

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ==============================================================================
# Stage 3: runner — standalone output (no node_modules copied!).
# ==============================================================================
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=5000
ENV HOSTNAME="0.0.0.0"

RUN useradd --create-home --shell /bin/bash appuser

# Copy only standalone build files directly with permissions (no 16-min chown)
COPY --chown=appuser:appuser --from=builder /app/public ./public
COPY --chown=appuser:appuser --from=builder /app/.next/standalone ./
COPY --chown=appuser:appuser --from=builder /app/.next/static ./.next/static

# Server-side rewrites in next.config.ts (the /api/:path* proxy) run
# inside this container, so BACKEND_HOST here should be the Docker
# service name (e.g. "backend"), NOT the same value as the
# NEXT_PUBLIC_BACKEND_HOST build arg above -- that one has to be
# reachable from the user's browser instead. See docker-compose.yaml's
# comments on the frontend service for both values set explicitly.
ENV BACKEND_HOST=backend
ENV BACKEND_PORT=8000

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD node -e "fetch('http://localhost:5000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]