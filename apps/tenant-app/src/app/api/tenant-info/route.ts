import { NextResponse } from 'next/server';

/**
 * Server-side API route to fetch tenant information from Control Panel backend
 *
 * This route runs on the Next.js server, so it can communicate with the Control Panel
 * backend without CORS issues. The client fetches from this same-origin endpoint.
 *
 * Caching disabled to ensure immediate updates when tenant name changes in Control Panel.
 */

// Disable Next.js route caching (force fresh data on every request)
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export async function GET() {
  try {
    // Get configuration from server environment variables
    const tenantDomain = process.env.TENANT_DOMAIN || 'test-company';
    const controlPanelUrl = process.env.CONTROL_PANEL_URL || 'http://localhost:8001';

    // Server-to-server request (no CORS)
    // Disable caching to ensure fresh tenant data
    const response = await fetch(
      `${controlPanelUrl}/api/v1/tenant-info?tenant_domain=${tenantDomain}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-cache',
        },
        cache: 'no-store',
        // Server-side fetch with reasonable timeout
        signal: AbortSignal.timeout(5000),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));

      return NextResponse.json(
        {
          error: errorData.detail || 'Failed to fetch tenant info',
          status: response.status
        },
        { status: response.status }
      );
    }

    const data = await response.json();

    // Validate response has required fields
    if (!data.name || !data.domain) {
      return NextResponse.json(
        { error: 'Invalid tenant info response from Control Panel' },
        { status: 500 }
      );
    }

    // Return with no-cache headers to prevent browser caching
    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0',
      }
    });

  } catch (error) {
    console.error('Server-side tenant info fetch error:', error);

    // Check if it's a timeout error
    if (error instanceof Error && error.name === 'TimeoutError') {
      return NextResponse.json(
        { error: 'Control Panel backend timeout' },
        { status: 504 }
      );
    }

    return NextResponse.json(
      { error: 'Failed to fetch tenant information' },
      { status: 500 }
    );
  }
}
