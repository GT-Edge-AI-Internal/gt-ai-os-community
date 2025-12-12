/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disable trailing slash redirects so our API routes can handle them
  skipTrailingSlashRedirect: true,

  // Ignore ESLint errors during production build
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Ignore TypeScript errors during production build (for speed)
  typescript: {
    ignoreBuildErrors: true,
  },

  // Remove console logs in production builds
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production' ? {
      exclude: ['error'],
    } : false,
  },

  // NOTE: Server-side environment variables (TENANT_BACKEND_URL, etc.) are NOT defined here
  // to prevent Next.js from inlining them at build time. They are read from process.env at
  // runtime, allowing Docker containers to inject the correct URLs via environment variables.
  // This enables flexible deployment without rebuilding when backend URLs change.

  // Rewrites disabled for /api - using API routes at src/app/api/v1/[...path]/route.ts for server-side proxying
  // This ensures proper handling of redirects and Docker internal networking
  async rewrites() {
    return [
      {
        source: '/ws/:path*',
        destination: `${process.env.INTERNAL_BACKEND_URL || 'http://tenant-backend:8000'}/ws/:path*`,
      },
      {
        source: '/socket.io/:path*',
        destination: `${process.env.INTERNAL_BACKEND_URL || 'http://tenant-backend:8000'}/socket.io/:path*`,
      },
    ];
  },
  webpack: (config) => {
    config.resolve.fallback = {
      fs: false,
      net: false,
      tls: false,
    };
    return config;
  },
};

module.exports = nextConfig;