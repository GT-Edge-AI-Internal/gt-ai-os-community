'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { Loader2 } from 'lucide-react';

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const { isAuthenticated, isLoading, token, user, checkAuth } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const initializeAuth = async () => {
      await checkAuth();
      setIsInitialized(true);
    };
    
    initializeAuth();
  }, [checkAuth]);

  useEffect(() => {
    console.log('AuthGuard state:', { isInitialized, isAuthenticated, isLoading, hasToken: !!token, userType: user?.user_type });

    if (isInitialized && !isLoading) {
      // Redirect if not authenticated OR not a super_admin
      if (!isAuthenticated || (user && user.user_type !== 'super_admin')) {
        console.log('Redirecting to login from AuthGuard - not authenticated or not super_admin');
        router.replace('/auth/login');
      }
    }
  }, [isInitialized, isAuthenticated, isLoading, router, token, user]);

  if (!isInitialized || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading...</span>
        </div>
      </div>
    );
  }

  // Block access if not authenticated or not super_admin
  if (!isAuthenticated || (user && user.user_type !== 'super_admin')) {
    return null; // Will redirect to login
  }

  return <>{children}</>;
}