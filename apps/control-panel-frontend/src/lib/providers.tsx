'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { SessionMonitor } from '@/providers/session-monitor';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000, // 5 minutes
            gcTime: 10 * 60 * 1000, // 10 minutes (renamed from cacheTime in v5)
            retry: (failureCount, error: any) => {
              // Don't retry on 401 (unauthorized) or 403 (forbidden)
              if (error?.response?.status === 401 || error?.response?.status === 403) {
                return false;
              }
              return failureCount < 2;
            },
          },
          mutations: {
            retry: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <SessionMonitor>
        {children}
      </SessionMonitor>
    </QueryClientProvider>
  );
}