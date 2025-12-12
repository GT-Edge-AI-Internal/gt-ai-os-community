# Tenant App Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Accept build args for Docker internal URLs
ARG INTERNAL_BACKEND_URL
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ARG NEXT_PUBLIC_TENANT_DOMAIN

# Set as env vars so next.config.js can use them during build
ENV INTERNAL_BACKEND_URL=$INTERNAL_BACKEND_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_TENANT_DOMAIN=$NEXT_PUBLIC_TENANT_DOMAIN

# Copy package files
COPY package*.json ./

# Install ALL dependencies (including devDependencies needed for build)
# Using npm ci for deterministic, faster installs from lockfile
RUN npm ci

# Copy application code
COPY . .

# Set NODE_ENV to production AFTER install, BEFORE build
# This enables Next.js production optimizations without breaking npm install
ENV NODE_ENV=production

# Build the application (next.config.js will use env vars above)
RUN npm run build

# Prune dev dependencies after build (avoids second npm install in prod stage)
RUN npm prune --omit=dev

# Production stage
FROM node:18-alpine

WORKDIR /app

# Set environment to production
ENV NODE_ENV=production
ENV PORT=3001

# Copy built application and pruned node_modules from builder
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/node_modules ./node_modules

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001 && \
    chown -R nextjs:nodejs /app

USER nextjs

# Expose port
EXPOSE 3001

# Run the application with npm start (uses PORT env var)
CMD ["npm", "start"]