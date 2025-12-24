'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { getUserRole, UserRole } from '@/lib/permissions';
import { Shield } from 'lucide-react';

interface AdminGuardProps {
  children: React.ReactNode;
  fallbackPath?: string;
}

const ADMIN_ROLES: UserRole[] = ['admin', 'developer'];

/**
 * AdminGuard - Ensures only admin or developer roles can access the wrapped content
 * This should be used inside AuthGuard for pages requiring admin privileges
 */
export function AdminGuard({
  children,
  fallbackPath = '/home'
}: AdminGuardProps) {
  const router = useRouter();
  const userRole = getUserRole();

  // Check if user has admin privileges
  const isAdmin = userRole && ADMIN_ROLES.includes(userRole);

  if (!isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gt-gray-50">
        <div className="max-w-md w-full mx-auto p-6">
          <div className="bg-gt-white rounded-lg shadow-lg p-8 text-center">
            <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Shield className="w-8 h-8 text-amber-600" />
            </div>
            <h2 className="text-xl font-semibold text-gt-gray-900 mb-2">
              Admin Access Required
            </h2>
            <p className="text-gt-gray-600 mb-2">
              This page is only accessible to tenant administrators.
            </p>
            <p className="text-sm text-gt-gray-500 mb-6">
              Current role: <span className="font-medium">{userRole || 'Unknown'}</span>
            </p>
            <button
              onClick={() => router.push(fallbackPath)}
              className="bg-gt-green text-white px-6 py-2 rounded-lg hover:bg-gt-green-dark transition-colors"
            >
              Go to Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  // User is admin - render protected content
  return <>{children}</>;
}

export default AdminGuard;
