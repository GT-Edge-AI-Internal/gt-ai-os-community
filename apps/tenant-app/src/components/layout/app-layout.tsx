'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/auth-store';
import { Sidebar } from '@/components/layout/sidebar';
import { LoadingScreen } from '@/components/ui/loading-screen';
import { cn } from '@/lib/utils';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    // Load saved state from localStorage on initial render
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('gt-sidebar-collapsed');
      return saved ? JSON.parse(saved) : false;
    }
    return false;
  });

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Initialize WebSocket connection globally for real-time sidebar updates across all pages
  useEffect(() => {
    if (isAuthenticated) {
      const { connect } = require('@/stores/chat-store').useChatStore.getState();
      console.log('🔌 Initializing global WebSocket connection from AppLayout...');
      connect(queryClient);
      // Don't disconnect on cleanup - keep connection alive across page navigation
    }
  }, [isAuthenticated, queryClient]);

  // Redirect to login page if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Show loading screen while checking authentication
  if (isLoading) {
    return <LoadingScreen />;
  }

  // Show loading screen while redirecting to login
  if (!isAuthenticated) {
    return <LoadingScreen />;
  }

  return (
    <div className="h-screen flex bg-gt-gray-50">
      {/* Sidebar */}
      <Sidebar 
        user={user}
        onCollapseChange={setSidebarCollapsed}
        onSelectConversation={(conversationId) => {
          // If we're on chat page, trigger conversation loading
          if (window.location.pathname === '/chat') {
            window.dispatchEvent(new CustomEvent('loadConversation', { detail: { conversationId } }));
          } else {
            // Navigate to chat page with conversation
            window.location.href = `/chat?conversation=${conversationId}`;
          }
        }}
      />


      {/* Main Content */}
      <div className="flex-1 transition-all duration-700 ease-out">
        {/* Page Content */}
        <main className="h-full bg-gt-white overflow-auto">
          {children}
        </main>
      </div>

    </div>
  );
}