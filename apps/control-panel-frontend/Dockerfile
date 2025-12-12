# Control Panel Frontend Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Accept build args for Docker internal URLs
ARG INTERNAL_API_URL
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL

# Set as env vars so next.config.js can use them during build
ENV INTERNAL_API_URL=$INTERNAL_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

# Copy package files
COPY package*.json ./

# Install dependencies (including devDependencies needed for build)
RUN npm install

# Copy application code
COPY . .

# Set NODE_ENV to production AFTER install, BEFORE build
# This enables Next.js production optimizations without breaking npm install
ENV NODE_ENV=production

# Build the application (next.config.js will use env vars above)
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Set environment to production
ENV NODE_ENV=production
ENV PORT=3000

# Copy built application
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/next.config.js ./
# Copy public directory if it exists
RUN mkdir -p ./public

# Install production dependencies only
RUN npm install --only=production

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001 && \
    chown -R nextjs:nodejs /app

USER nextjs

# Expose port
EXPOSE 3000

# Run the application with npm start (uses PORT env var)
CMD ["npm", "start"]