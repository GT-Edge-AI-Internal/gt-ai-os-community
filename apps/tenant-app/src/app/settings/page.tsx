'use client';

import { AppLayout } from '@/components/layout/app-layout';
import { AuthGuard } from '@/components/auth/auth-guard';
import { useAuthStore } from '@/stores/auth-store';
import { TFASettings } from '@/components/settings/tfa-settings';
import { User } from 'lucide-react';
import { usePageTitle } from '@/hooks/use-page-title';

export default function SettingsPage() {
  usePageTitle('Settings');
  const { user } = useAuthStore();

  return (
    <AuthGuard>
      <AppLayout>
        <div className="min-h-screen bg-gradient-to-br from-gt-gray-50 to-gt-gray-100">
          <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
            {/* Header */}
            <div>
              <h1 className="text-3xl font-bold text-gt-gray-900">Account Settings</h1>
              <p className="text-gt-gray-600 mt-2">
                Manage your account preferences and security settings
              </p>
            </div>

            {/* Profile Information */}
            <div className="bg-gt-white border border-gt-gray-200 rounded-lg p-6 space-y-4">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 bg-gt-green rounded-full flex items-center justify-center">
                  <User className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gt-gray-900">
                    {user?.full_name || 'User'}
                  </h2>
                  <p className="text-sm text-gt-gray-600">{user?.email}</p>
                  {user?.user_type && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gt-blue-100 text-gt-blue-800 mt-1">
                      {user.user_type.replace('_', ' ').toUpperCase()}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Security Section */}
            <div className="space-y-4">
              <div className="border-b border-gt-gray-200 pb-2">
                <h2 className="text-xl font-semibold text-gt-gray-900">Security</h2>
                <p className="text-sm text-gt-gray-600 mt-1">
                  Manage your account security and authentication methods
                </p>
              </div>

              {/* TFA Settings Component */}
              <TFASettings />
            </div>

            {/* Additional Settings Sections (Placeholder for future) */}
            {/*
            <div className="space-y-4">
              <div className="border-b border-gt-gray-200 pb-2">
                <h2 className="text-xl font-semibold text-gt-gray-900">Preferences</h2>
                <p className="text-sm text-gt-gray-600 mt-1">
                  Customize your GT Edge AI experience
                </p>
              </div>

              <div className="bg-gt-white border border-gt-gray-200 rounded-lg p-6">
                <p className="text-sm text-gt-gray-500">Additional preferences coming soon...</p>
              </div>
            </div>
            */}
          </div>
        </div>
      </AppLayout>
    </AuthGuard>
  );
}
