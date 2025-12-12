import Image from 'next/image';
import { LoginPageClient } from './login-page-client';

// Force dynamic rendering - this page needs runtime data
export const dynamic = 'force-dynamic';

/**
 * Server Component - Fetches tenant name before rendering
 * This eliminates the flash/delay when displaying tenant name
 */
async function getTenantName(): Promise<string> {
  try {
    const controlPanelUrl = process.env.CONTROL_PANEL_URL || 'http://control-panel-backend:8000';
    const tenantDomain = process.env.TENANT_DOMAIN || 'test-company';

    const response = await fetch(
      `${controlPanelUrl}/api/v1/tenant-info?tenant_domain=${tenantDomain}`,
      {
        cache: 'no-store',
        signal: AbortSignal.timeout(5000),
      }
    );

    if (response.ok) {
      const data = await response.json();
      return data.name || '';
    }
  } catch (error) {
    console.error('Failed to fetch tenant name on server:', error);
  }
  return '';
}

export default async function LoginPage() {
  // Fetch tenant name on server before rendering
  const tenantName = await getTenantName();

  return (
    <div className="min-h-screen bg-gradient-to-br from-gt-gray-50 to-gt-gray-100 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-grid-pattern opacity-5"></div>
      <div className="relative z-10">
        <LoginPageClient tenantName={tenantName} />

        <div className="text-center mt-8 text-sm text-gt-gray-500 space-y-2">
          <p className="text-xs">GT AI OS Community | v2.0.33</p>
          <p>© 2025 GT Edge AI. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
}