# ==============================================================================
# ORBIT Frontend Dockerfile
# Multi-stage Next.js production build using Node 20 Alpine
# ==============================================================================

# Base image is configurable so builds can use a registry mirror when Docker Hub is
# unreachable: --build-arg NODE_IMAGE=mirror.gcr.io/library/node:20-alpine
ARG NODE_IMAGE=node:20-alpine

# Stage 1: Install dependencies
FROM ${NODE_IMAGE} AS deps
WORKDIR /app

RUN apk add --no-cache libc6-compat
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: Build the application
FROM ${NODE_IMAGE} AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values are inlined into the browser bundle at build time, so the
# API URL must be supplied here as a build argument, not as a runtime variable.
ARG NEXT_PUBLIC_API_URL=http://localhost:8001/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

# Stage 3: Production runner
FROM ${NODE_IMAGE} AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built public and build output
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

RUN chown -R nextjs:nodejs /app/.next
USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
