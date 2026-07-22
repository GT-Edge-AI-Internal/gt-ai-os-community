'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { isTokenValid, getUser, getUserCapabilities } from '@/services/auth';
import { useHasHydrated, useAuthStore } from '@/stores/auth-store';
import { LoadingScreen } from '@/components/ui/loading-screen';

interface AuthGuardProps {
  children: React.ReactNode;
  requiredCapabilities?: string[];
  fallbackPath?: string;
}

export function AuthGuard({
  children,
  requiredCapabilities = [],
  fallbackPath = '/login'
}: AuthGuardProps) {
  const router = useRouter();
  const hasHydrated = useHasHydrated();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const logout = useAuthStore((state) => state.logout);
  const [isAuthorized, setIsAuthorized] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const checkingRef = useRef<boolean>(false);

  // Subscribe to authentication state changes
  useEffect(() => {
    if (!hasHydrated) {
      return;
    }

    // If user becomes unauthenticated while on protected page, redirect
    if (!isAuthenticated && isAuthorized !== null) {
      console.log('AuthGuard: Authentication lost, redirecting to login');
      setIsAuthorized(false);
      router.replace(fallbackPath);
    }
  }, [isAuthenticated, hasHydrated, isAuthorized, router, fallbackPath]);

  useEffect(() => {
    // Wait for Zustand persist hydration to complete before checking auth
    if (!hasHydrated) {
      return;
    }

    const checkAuthentication = async () => {
      // Prevent multiple simultaneous auth checks
      if (checkingRef.current) {
        return;
      }

      checkingRef.current = true;

      try {
        // Check if we just completed TFA verification
        const tfaVerified = sessionStorage.getItem('gt2_tfa_verified');
        if (tfaVerified) {
          sessionStorage.removeItem('gt2_tfa_verified');

          // Trust the auth state from TFA flow, skip full validation
          if (isTokenValid() && getUser()) {
            console.log('AuthGuard: TFA verification complete, skipping full auth check');
            setIsAuthorized(true);
            setError(null);
            checkingRef.current = false;
            return;
          }
        }

        // GT 2.0: Validate token and capabilities
        if (!isTokenValid()) {
          console.log('AuthGuard: Invalid or missing token, logging out');
          logout('expired');
          return;
        }

        const user = getUser();
        if (!user) {
          console.log('AuthGuard: No user data found, logging out');
          logout('unauthorized');
          return;
        }

        // Check required capabilities if specified
        if (requiredCapabilities.length > 0) {
          const userCapabilities = getUserCapabilities();
          const hasAllCapabilities = requiredCapabilities.every(cap => 
            userCapabilities.includes(cap)
          );

          if (!hasAllCapabilities) {
            console.log('AuthGuard: Insufficient capabilities:', {
              required: requiredCapabilities,
              user: userCapabilities
            });
            logout('unauthorized');
            return;
          }
        }

        // All checks passed
        console.log('AuthGuard: Authentication successful');
        setIsAuthorized(true);
        setError(null);

      } catch (error) {
        console.error('AuthGuard: Authentication check failed:', error);
        setError('Authentication check failed. Please try logging in again.');
        logout('unauthorized');
      } finally {
        checkingRef.current = false;
      }
    };

    checkAuthentication();
  }, [hasHydrated, router, fallbackPath, requiredCapabilities]);

  // Show loading while Zustand is hydrating from localStorage
  if (!hasHydrated) {
    return <LoadingScreen message="Loading..." />;
  }

  // Show loading while checking authentication
  if (isAuthorized === null) {
    return <LoadingScreen message="Verifying authentication..." />;
  }

  // Show error if authorization failed but not redirecting
  if (isAuthorized === false && error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gt-gray-50">
        <div className="max-w-md w-full mx-auto p-6">
          <div className="bg-gt-white rounded-lg shadow-lg p-8 text-center">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg 
                className="w-8 h-8 text-red-600" 
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path 
                  strokeLinecap="round" 
                  strokeLinejoin="round" 
                  strokeWidth={2} 
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" 
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gt-gray-900 mb-2">Access Denied</h2>
            <p className="text-gt-gray-600 mb-6">{error}</p>
            <button
              onClick={() => router.push(fallbackPath)}
              className="bg-gt-green text-white px-6 py-2 rounded-lg hover:bg-gt-green-dark transition-colors"
            >
              Go to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render protected content if authorized
  if (isAuthorized) {
    return <>{children}</>;
  }

  // Fallback: show loading (should not reach here)
  return <LoadingScreen message="Loading..." />;
}

export default AuthGuard;