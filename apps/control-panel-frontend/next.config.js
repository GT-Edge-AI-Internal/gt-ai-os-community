/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    // Skip type checking during build (types are checked in dev)
    ignoreBuildErrors: true
  },
  eslint: {
    // Skip ESLint during build
    ignoreDuringBuilds: true
  },
  compiler: {
    // Strip console.* calls in production builds (keep console.error for debugging)
    removeConsole: process.env.NODE_ENV === 'production' ? {
      exclude: ['error']
    } : false
  },
  // NOTE: Server-side environment variables (INTERNAL_API_URL, etc.) are NOT defined here
  // to prevent Next.js from inlining them at build time. They are read from process.env at
  // runtime, allowing Docker containers to inject the correct URLs via environment variables.
  // This enables flexible deployment without rebuilding when backend URLs change.

  async rewrites() {
    // Use INTERNAL_API_URL for server-side requests (Docker networking)
    // Fall back to Docker hostname - this is evaluated at build time so localhost won't work
    const apiUrl = process.env.INTERNAL_API_URL || 'http://control-panel-backend:8000';

    return [
      {
        source: '/api/v1/models',
        destination: `${apiUrl}/api/v1/models/`,
      },
      {
        source: '/api/v1/models/:path*',
        destination: `${apiUrl}/api/v1/models/:path*`,
      },
      {
        source: '/api/v1/tenants',
        destination: `${apiUrl}/api/v1/tenants/`,
      },
      {
        source: '/api/v1/users',
        destination: `${apiUrl}/api/v1/users/`,
      },
      {
        source: '/api/v1/resources',
        destination: `${apiUrl}/api/v1/resources/`,
      },
      {
        source: '/api/v1/system/:path*',
        destination: `${apiUrl}/api/v1/system/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;