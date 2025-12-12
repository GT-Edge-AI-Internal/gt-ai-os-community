'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isTokenValid } from '@/services/auth';
import { LoadingScreen } from '@/components/ui/loading-screen';

/**
 * Root page with authentication-aware redirect
 *
 * Checks authentication state and redirects appropriately:
 * - Authenticated users go to /agents (home page)
 * - Unauthenticated users go to /login
 *
 * This prevents the redirect loop that causes login page flickering.
 */
export default function RootPage() {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const checkAuthAndRedirect = () => {
      try {
        // Check if user is authenticated
        if (isTokenValid()) {
          // Authenticated - go to agents (home page)
          router.replace('/agents');
        } else {
          // Not authenticated - go to login
          router.replace('/login');
        }
      } catch (error) {
        console.error('Auth check failed:', error);
        // On error, redirect to login for safety
        router.replace('/login');
      } finally {
        setIsChecking(false);
      }
    };

    checkAuthAndRedirect();
  }, [router]);

  // Show loading screen while checking authentication
  if (isChecking) {
    return <LoadingScreen message="Loading GT 2.0..." />;
  }

  // Fallback - should not be visible due to redirects
  return null;
}