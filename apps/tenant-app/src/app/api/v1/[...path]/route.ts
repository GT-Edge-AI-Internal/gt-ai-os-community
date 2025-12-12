/**
 * Next.js API Route Proxy
 *
 * Proxies all /api/v1/* requests from browser to tenant-backend via Docker network.
 * This is required because Next.js rewrites don't work for client-side fetch() calls.
 *
 * Flow:
 * 1. Browser → fetch('/api/v1/models')
 * 2. Next.js catches via this route (server-side)
 * 3. Proxy → http://tenant-backend:8000/api/v1/models (Docker network)
 * 4. Response → Return to browser
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || 'http://tenant-backend:8000';

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

/**
 * Proxy request to tenant-backend via Docker network
 */
async function proxyRequest(
  request: NextRequest,
  method: string,
  path: string
): Promise<NextResponse> {
  try {
    const url = `${BACKEND_URL}/api/v1/${path}`;

    console.log(`[API Proxy] ${method} /api/v1/${path} → ${url}`);

    // Forward body for POST/PUT/PATCH
    let body: string | FormData | undefined;
    const contentType = request.headers.get('content-type');
    const isMultipart = contentType?.includes('multipart/form-data');

    if (['POST', 'PUT', 'PATCH'].includes(method)) {
      if (isMultipart) {
        body = await request.formData();
      } else {
        body = await request.text();
      }
    }

    // Forward headers (auth, tenant domain, content-type)
    const headers = new Headers();
    request.headers.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      // Don't forward host-related headers
      // Don't forward content-length or content-type for multipart/form-data
      // (fetch will generate new headers with correct boundary)
      if (!lowerKey.startsWith('host') &&
          !lowerKey.startsWith('connection') &&
          !(isMultipart && lowerKey === 'content-length') &&
          !(isMultipart && lowerKey === 'content-type')) {
        headers.set(key, value);
      }
    });

    // Forward query parameters
    const searchParams = request.nextUrl.searchParams.toString();
    const finalUrl = searchParams ? `${url}?${searchParams}` : url;

    // Make server-side request to backend via Docker network
    // Follow redirects automatically (FastAPI trailing slash redirects)
    const response = await fetch(finalUrl, {
      method,
      headers,
      body,
      redirect: 'follow',
    });

    console.log(`[API Proxy] Response: ${response.status} ${response.statusText}`);

    // Forward response headers
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      responseHeaders.set(key, value);
    });

    // Return response to browser
    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error(`[API Proxy] Error:`, error);
    return NextResponse.json(
      {
        error: 'Proxy error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 502 }
    );
  }
}

// HTTP Method Handlers
export async function GET(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  let path = params.path.join('/');
  // Preserve trailing slash from original URL
  if (request.nextUrl.pathname.endsWith('/')) {
    path = path + '/';
  }
  return proxyRequest(request, 'GET', path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  let path = params.path.join('/');
  if (request.nextUrl.pathname.endsWith('/')) {
    path = path + '/';
  }
  return proxyRequest(request, 'POST', path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  let path = params.path.join('/');
  if (request.nextUrl.pathname.endsWith('/')) {
    path = path + '/';
  }
  return proxyRequest(request, 'PUT', path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  let path = params.path.join('/');
  if (request.nextUrl.pathname.endsWith('/')) {
    path = path + '/';
  }
  return proxyRequest(request, 'DELETE', path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  let path = params.path.join('/');
  if (request.nextUrl.pathname.endsWith('/')) {
    path = path + '/';
  }
  return proxyRequest(request, 'PATCH', path);
}
