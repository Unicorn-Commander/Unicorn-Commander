# Bolt.DIY Custom Dockerfile
# This Dockerfile is for building Bolt.DIY from source if needed
# By default, we use the official prebuilt image: ghcr.io/stackblitz-labs/bolt.diy:latest

# Base stage - Common setup
FROM node:22-bookworm-slim AS base

# Install pnpm globally
RUN npm install -g pnpm@latest

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Development stage
FROM base AS bolt-ai-development

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install

# Copy source code
COPY . .

# Expose development port
EXPOSE 5173

# Development command
CMD ["pnpm", "run", "dev", "--host", "0.0.0.0"]

# Build stage
FROM base AS build

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Build the application
RUN pnpm run build

# Prune development dependencies
RUN pnpm prune --prod

# Production stage
FROM base AS bolt-ai-production

# Set production environment
ENV NODE_ENV=production
ENV RUNNING_IN_DOCKER=true

# Copy built application from build stage
COPY --from=build /app /app

# Copy production node_modules
COPY --from=build /app/node_modules /app/node_modules

# Expose production port
EXPOSE 5173

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5173 || exit 1

# Start the application
CMD ["pnpm", "run", "dockerstart"]
