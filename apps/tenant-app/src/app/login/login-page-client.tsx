'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { LoginForm } from '@/components/auth/login-form';
import { useAuthStore } from '@/stores/auth-store';

interface LoginPageClientProps {
  tenantName: string;
}

/**
 * Session expiration type for different messages (Issue #242)
 * - 'idle': 30-minute inactivity timeout
 * - 'absolute': 8-hour session limit reached
 */
type SessionExpiredType = 'idle' | 'absolute' | null;

/**
 * Client Component - Handles auth checks and redirects
 * Receives tenant name from Server Component (no flash)
 */
export function LoginPageClient({ tenantName }: LoginPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [sessionExpiredType, setSessionExpiredType] = useState<SessionExpiredType>(null);

  useEffect(() => {
    document.title = 'GT AI OS | Login';
  }, []);

  useEffect(() => {
    // Check for session expiration parameter (NIST/OWASP Issue #242)
    const sessionExpiredParam = searchParams.get('session_expired');
    if (sessionExpiredParam === 'true') {
      // Idle timeout (30 min inactivity)
      setSessionExpiredType('idle');
    } else if (sessionExpiredParam === 'absolute') {
      // Absolute timeout (8 hour session limit)
      setSessionExpiredType('absolute');
    }

    // Clean up the URL by removing the query parameter (after a delay to show the message)
    if (sessionExpiredParam) {
      setTimeout(() => {
        router.replace('/login');
      }, 100);
    }
  }, [searchParams, router]);

  useEffect(() => {
    // Check authentication status on mount to sync localStorage with store
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    // Don't auto-redirect if we just completed TFA (prevents race condition flash)
    if (sessionStorage.getItem('gt2_tfa_verified')) {
      return;
    }

    // Redirect to agents if already authenticated (prevents redirect loop)
    if (isAuthenticated) {
      router.push('/agents');
    }
  }, [isAuthenticated, router]);

  // Get the appropriate message based on expiration type (Issue #242)
  const getSessionExpiredMessage = (): string => {
    if (sessionExpiredType === 'absolute') {
      return 'Your session has reached the maximum duration (8 hours). Please log in again.';
    }
    return 'Your session has expired due to inactivity. Please log in again.';
  };

  return (
    <>
      {sessionExpiredType && (
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-2">
          <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-3 rounded-lg shadow-lg flex items-center gap-3">
            <svg
              className="w-5 h-5 text-red-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="font-medium">{getSessionExpiredMessage()}</span>
          </div>
        </div>
      )}
      <LoginForm tenantName={tenantName} />
    </>
  );
}
