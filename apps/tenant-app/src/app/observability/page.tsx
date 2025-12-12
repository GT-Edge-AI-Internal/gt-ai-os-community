'use client';

import { AppLayout } from '@/components/layout/app-layout';
import { AuthGuard } from '@/components/auth/auth-guard';
import { usePageTitle } from '@/hooks/use-page-title';
import { ObservabilityDashboard } from '@/components/observability/observability-dashboard';

/**
 * Observability Dashboard Page
 * Available to all authenticated users with role-based data filtering:
 * - Admins/Developers: See all platform activity with user filtering
 * - Analysts/Students: See only their personal activity
 *
 * Features:
 * - Overview metrics (conversations, messages, tokens, users)
 * - Time series charts for usage trends
 * - Breakdown by user, agent, and model
 * - Full conversation browser with content viewing
 * - CSV/JSON export functionality
 */
export default function ObservabilityPage() {
  usePageTitle('Observability');

  return (
    <AuthGuard>
      <AppLayout>
        <ObservabilityDashboard />
      </AppLayout>
    </AuthGuard>
  );
}
