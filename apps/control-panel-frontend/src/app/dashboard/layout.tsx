'use client';

import { DashboardNav } from '@/components/layout/dashboard-nav';
import { DashboardHeader } from '@/components/layout/dashboard-header';
import { AuthGuard } from '@/components/auth/auth-guard';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { UpdateBanner } from '@/components/system/UpdateBanner';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <ErrorBoundary>
        <div className="min-h-screen bg-background">
          <DashboardHeader />
          <div className="flex">
            <DashboardNav />
            <main className="flex-1 p-6">
              <UpdateBanner />
              <ErrorBoundary>
                {children}
              </ErrorBoundary>
            </main>
          </div>
        </div>
      </ErrorBoundary>
    </AuthGuard>
  );
}