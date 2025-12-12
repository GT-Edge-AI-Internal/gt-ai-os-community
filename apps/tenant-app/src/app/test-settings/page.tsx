'use client';

import { TestLayout } from '@/components/layout/test-layout';
import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  User, Bell, Shield, Palette, Globe, Database,
  CreditCard, HelpCircle, ChevronRight, Save, Moon, Sun
} from 'lucide-react';

export default function TestSettingsPage() {
  const [theme, setTheme] = useState('system');
  const [notifications, setNotifications] = useState({
    email: true,
    push: true,
    sms: false,
    mentions: true,
    updates: false,
  });
  const [privacy, setPrivacy] = useState({
    analytics: true,
    progressSharing: false,
    peerComparison: false,
  });

  const settingsSections = [
    {
      title: 'Profile',
      icon: User,
      items: [
        { label: 'Name', value: 'Jane User' },
        { label: 'Email', value: 'jane@test-company.com' },
        { label: 'Role', value: 'Tenant User', badge: true },
        { label: 'Department', value: 'Research & Development' },
      ]
    },
    {
      title: 'Appearance',
      icon: Palette,
      items: [
        { label: 'Theme', component: 'theme-selector' },
        { label: 'UI Density', value: 'Comfortable' },
        { label: 'Accent Color', value: '#00d084', color: true },
        { label: 'Font Size', value: 'Medium' },
      ]
    },
    {
      title: 'Notifications',
      icon: Bell,
      items: [
        { label: 'Email Notifications', toggle: 'email' },
        { label: 'Push Notifications', toggle: 'push' },
        { label: 'SMS Alerts', toggle: 'sms' },
        { label: 'Mentions', toggle: 'mentions' },
        { label: 'Product Updates', toggle: 'updates' },
      ]
    },
    {
      title: 'Privacy & Security',
      icon: Shield,
      items: [
        { label: 'Two-Factor Authentication', value: 'Enabled', badge: 'green' },
        { label: 'Session Timeout', value: '30 minutes' },
        { label: 'Usage Analytics', toggle: 'analytics' },
        { label: 'Progress Sharing', toggle: 'progressSharing' },
        { label: 'Peer Comparison', toggle: 'peerComparison' },
      ]
    },
    {
      title: 'AI Preferences',
      icon: Globe,
      items: [
        { label: 'Default Model', value: 'GPT-4' },
        { label: 'Temperature', value: '0.7' },
        { label: 'Max Tokens', value: '2000' },
        { label: 'Explanation Level', value: 'Intermediate' },
        { label: 'Auto-suggestions', value: 'Enabled', badge: 'green' },
      ]
    },
    {
      title: 'Storage & Usage',
      icon: Database,
      items: [
        { label: 'Storage Used', value: '3.6 GB / 10 GB', progress: 36 },
        { label: 'API Calls', value: '12,456 / 50,000', progress: 25 },
        { label: 'Compute Hours', value: '45 / 100', progress: 45 },
      ]
    },
    {
      title: 'Billing',
      icon: CreditCard,
      items: [
        { label: 'Current Plan', value: 'Professional', badge: 'blue' },
        { label: 'Billing Cycle', value: 'Monthly' },
        { label: 'Next Payment', value: 'Feb 1, 2024' },
        { label: 'Payment Method', value: '•••• 4242', action: true },
      ]
    },
  ];

  const handleToggle = (section: string, key: string) => {
    if (section === 'notifications') {
      setNotifications(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
    } else if (section === 'privacy') {
      setPrivacy(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
    }
  };

  const getToggleValue = (section: string, key: string) => {
    if (section === 'notifications') return notifications[key as keyof typeof notifications];
    if (section === 'privacy') return privacy[key as keyof typeof privacy];
    return false;
  };

  return (
    <TestLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
              <p className="text-gray-600 mt-1">Manage your account and preferences</p>
            </div>
            <Button className="bg-green-600 hover:bg-green-700 text-white">
              <Save className="w-4 h-4 mr-2" />
              Save Changes
            </Button>
          </div>
        </div>

        {/* Settings Sections */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {settingsSections.map((section) => {
            const Icon = section.icon;
            return (
              <Card key={section.title} className="p-6">
                <div className="flex items-center mb-4">
                  <Icon className="w-5 h-5 text-green-600 mr-2" />
                  <h2 className="text-lg font-semibold text-gray-900">{section.title}</h2>
                </div>
                
                <div className="space-y-4">
                  {section.items.map((item, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">{item.label}</span>
                      
                      {'component' in item && item.component === 'theme-selector' ? (
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant={theme === 'light' ? 'primary' : 'secondary'}
                            onClick={() => setTheme('light')}
                            className="h-8 px-3"
                          >
                            <Sun className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant={theme === 'dark' ? 'primary' : 'secondary'}
                            onClick={() => setTheme('dark')}
                            className="h-8 px-3"
                          >
                            <Moon className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant={theme === 'system' ? 'primary' : 'secondary'}
                            onClick={() => setTheme('system')}
                            className="h-8 px-3"
                          >
                            Auto
                          </Button>
                        </div>
                      ) : 'toggle' in item && item.toggle ? (
                        <Switch
                          checked={getToggleValue(
                            section.title.toLowerCase().includes('notification') ? 'notifications' : 
                            section.title.toLowerCase().includes('privacy') ? 'privacy' : '',
                            item.toggle
                          )}
                          onCheckedChange={() => handleToggle(
                            section.title.toLowerCase().includes('notification') ? 'notifications' : 
                            section.title.toLowerCase().includes('privacy') ? 'privacy' : '',
                            item.toggle
                          )}
                        />
                      ) : 'badge' in item && item.badge ? (
                        <Badge 
                          className={
                            item.badge === 'green' ? 'bg-green-100 text-green-700' :
                            item.badge === 'blue' ? 'bg-blue-100 text-blue-700' :
                            item.badge === true ? 'bg-gray-100 text-gray-700' : ''
                          }
                        >
                          {item.value}
                        </Badge>
                      ) : 'color' in item && item.color ? (
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-6 h-6 rounded border border-gray-300"
                            style={{ backgroundColor: item.value }}
                          />
                          <span className="text-sm font-medium">{item.value}</span>
                        </div>
                      ) : 'progress' in item && item.progress !== undefined ? (
                        <div className="flex items-center gap-3 flex-1 max-w-xs ml-4">
                          <span className="text-sm font-medium text-gray-900">{item.value}</span>
                          <div className="flex-1 bg-gray-200 rounded-full h-2">
                            <div 
                              className="bg-green-600 h-2 rounded-full"
                              style={{ width: `${item.progress}%` }}
                            />
                          </div>
                        </div>
                      ) : 'action' in item && item.action ? (
                        <Button variant="ghost" size="sm" className="h-8">
                          <span className="text-sm mr-1">{item.value}</span>
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      ) : (
                        <span className="text-sm font-medium text-gray-900">{item.value}</span>
                      )}
                    </div>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>

        {/* Help Section */}
        <Card className="mt-6 p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <HelpCircle className="w-5 h-5 text-green-600 mr-3" />
              <div>
                <h3 className="font-semibold text-gray-900">Need Help?</h3>
                <p className="text-sm text-gray-600 mt-1">
                  Access documentation, tutorials, and contact support
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary">View Documentation</Button>
              <Button className="bg-green-600 hover:bg-green-700 text-white">
                Contact Support
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </TestLayout>
  );
}