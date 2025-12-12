'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  Building2,
  Users,
  Braces,
  Settings,
  Key,
  Cpu
} from 'lucide-react';

const navigation = [
  {
    name: 'Tenant',
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

  return (
    <nav className="gt-sidebar w-64 min-h-screen p-4">
      <div className="space-y-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href);
          
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

      {/* Version display */}
      <div className="mt-4 text-center">
        <p className="text-xs text-muted-foreground">
          GT AI OS Community | v2.0.33
        </p>
      </div>
    </nav>
  );
}