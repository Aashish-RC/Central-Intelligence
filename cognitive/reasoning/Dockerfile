# ==============================================================================
# Pheonix Model Gateway — Multi-Stage Production Dockerfile
# ==============================================================================

# Stage 1: Build & Compile
FROM node:22-alpine AS builder

WORKDIR /app

# Install build dependencies
COPY package.json tsconfig.json vitest.config.ts ./
RUN npm install

# Copy source code and build
COPY src ./src
COPY tests ./tests
RUN npm run build

# Stage 2: Production Minimal Runtime
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV FEATURE_CONSOLE_UI=false
ENV FEATURE_MCP=false
ENV FEATURE_TOOL_SEARCH=false
ENV FEATURE_A2A=false
ENV FEATURE_SECRETS_SYNC=false

# Install production dependencies only
COPY package.json ./
RUN npm install --omit=dev

# Copy compiled JavaScript from builder stage
COPY --from=builder /app/dist ./dist
COPY src/telemetry/pricing-data.json ./dist/telemetry/pricing-data.json

# Expose HTTP port
EXPOSE 3000 4000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health/liveness || exit 1

# Start high-performance model gateway
CMD ["node", "dist/index.js"]
