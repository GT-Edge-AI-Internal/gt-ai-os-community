'use client';

import { useState } from 'react';
import { Header } from '@/components/layout/header';
import { Sidebar } from '@/components/layout/sidebar';

interface TestLayoutProps {
  children: React.ReactNode;
}

export function TestLayout({ children }: TestLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // Mock user for testing
  const mockUser = {
    id: 1,
    email: 'jane@test-company.com',
    full_name: 'Jane User',
    tenant: 'Test Company',
    role: 'user',
    user_type: 'tenant_user' as const,
    avatar_url: null,
  };

  return (
    <div className="h-screen flex bg-gt-gray-50">
      {/* Sidebar */}
      <Sidebar 
        open={sidebarOpen} 
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header 
          user={mockUser}
          onMenuClick={() => setSidebarOpen(true)}
        />

        {/* Main Content Area */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}