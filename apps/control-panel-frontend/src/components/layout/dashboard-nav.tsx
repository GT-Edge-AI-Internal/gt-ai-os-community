'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { tenantsApi, usersApi } from '@/lib/api';
import {
  LayoutDashboard,
  Building2,
  Users,
  Braces,
  Settings,
  Key,
  Cpu
} from 'lucide-react';

const navigation = [
  {
    name: 'Overview',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    name: 'Tenants',
    href: '/dashboard/tenants',
    icon: Building2,
  },
  {
    name: 'Users',
    href: '/dashboard/users',
    icon: Users,
  },
  {
    name: 'Models',
    href: '/dashboard/models',
    icon: Braces,
  },
  {
    name: 'API Keys',
    href: '/dashboard/api-keys',
    icon: Key,
  },
  // System menu item - Hidden until update/install process is properly architected
  // {
  //   name: 'System',
  //   href: '/dashboard/system',
  //   icon: Cpu,
  // },
  {
    name: 'Settings',
    href: '/dashboard/settings',
    icon: Settings,
  },
];

export function DashboardNav() {
  const pathname = usePathname();
  const { isAuthenticated, token } = useAuthStore();
  const [quickStats, setQuickStats] = useState({
    tenants: 0,
    users: 0
  });

  useEffect(() => {
    const fetchQuickStats = async () => {
      if (!isAuthenticated || !token) return;

      try {
        const [tenantsResponse, usersResponse] = await Promise.allSettled([
          tenantsApi.list(1, 100),
          usersApi.list(1, 100)
        ]);

        let tenants = 0;
        let users = 0;

        if (tenantsResponse.status === 'fulfilled') {
          tenants = tenantsResponse.value.data.total || 0;
        }

        if (usersResponse.status === 'fulfilled') {
          users = usersResponse.value.data.total || 0;
        }

        setQuickStats({
          tenants,
          users
        });
      } catch (error) {
        console.error('Failed to fetch quick stats:', error);
      }
    };

    fetchQuickStats();
  }, [isAuthenticated, token]);

  return (
    <nav className="gt-sidebar w-64 min-h-screen p-4">
      <div className="space-y-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/dashboard' && pathname.startsWith(item.href));
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'gt-nav-item',
                isActive ? 'gt-nav-item-active' : 'gt-nav-item-inactive'
              )}
            >
              <item.icon className="h-4 w-4" />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </div>

      <div className="mt-8 p-4 bg-muted rounded-lg">
        <h4 className="text-sm font-medium mb-2">Quick Stats</h4>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Active Tenants</span>
            <span className="font-medium">{quickStats.tenants}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total Users</span>
            <span className="font-medium">{quickStats.users}</span>
          </div>
        </div>
      </div>

      {/* Version display */}
      <div className="mt-4 text-center">
        <p className="text-xs text-muted-foreground">
          GT AI OS Community | v2.0.33
        </p>
      </div>
    </nav>
  );
}