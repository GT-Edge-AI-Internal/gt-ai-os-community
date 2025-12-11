'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, ReactNode, useEffect } from 'react';
import { isTokenValid } from '@/services/auth';
import { useChatStore } from '@/stores/chat-store';
import { SessionMonitor } from '@/providers/session-monitor';

interface ProvidersProps {
  children: ReactNode;
}

// Network status hook for offline resilience
function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(true);
  const [isServerReachable, setIsServerReachable] = useState(true);

  useEffect(() => {
    // Check server connectivity
    const checkServer = async () => {
      try {
        const response = await fetch('/api/v1/health', {
          method: 'GET'
        });
        setIsServerReachable(response.ok);
      } catch {
        setIsServerReachable(false);
      }
    };

    // When browser comes back online, immediately check server
    const handleOnline = () => {
      setIsOnline(true);
      // Immediately check if server is reachable when network comes back
      checkServer();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    const serverCheck = setInterval(checkServer, 60000); // Check every 60 seconds
    checkServer(); // Initial check

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(serverCheck);
    };
  }, []);

  return { isOnline, isServerReachable };
}

export function Providers({ children }: ProvidersProps) {
  const { isOnline, isServerReachable } = useNetworkStatus();

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // With SSR, we usually want to set some default staleTime
            // above 0 to avoid refetching immediately on the client
            staleTime: 60 * 1000, // 1 minute
            retry: (failureCount, error: any) => {
              // GT 2.0: Don't retry on auth errors - they need user intervention
              if (error?.status === 401 || error?.status === 403) {
                // Use centralized logout from auth store
                if (typeof window !== 'undefined') {
                  import('@/stores/auth-store').then(({ useAuthStore }) => {
                    useAuthStore.getState().logout('unauthorized');
                  });
                }
                return false;
              }
              // GT 2.0: Retry network and server errors for resilience
              if (error?.status >= 500 || !error?.status) {
                return failureCount < 3; // More retries for server issues
              }
              // Retry once for other client errors
              return failureCount < 1;
            },
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
          },
          mutations: {
            retry: false,
          },
        },
      })
  );

  // Initialize WebSocket connection with QueryClient for real-time updates
  useEffect(() => {
    const token = localStorage.getItem('gt2_token');
    if (token && isTokenValid()) {  // isTokenValid() checks token internally
      console.log('🔌 Initializing WebSocket connection from Providers');
      useChatStore.getState().connect(queryClient);
    }

    // No cleanup needed - WebSocket should stay alive throughout app lifecycle
    // Socket will naturally disconnect when browser tab closes
  }, [queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      {/* Session Monitor - server-authoritative session management (Issue #264) */}
      <SessionMonitor>
        {/* Network Status Indicator */}
        {(!isOnline || !isServerReachable) && (
          <div className="fixed top-0 left-0 right-0 bg-yellow-500 text-white text-center py-2 text-sm z-50">
            {!isOnline ? '📡 No internet connection - working offline' : '⚠️ Server unreachable - showing cached data'}
          </div>
        )}
        <div className={(!isOnline || !isServerReachable) ? 'pt-10' : ''}>
          {children}
        </div>
      </SessionMonitor>
    </QueryClientProvider>
  );
}