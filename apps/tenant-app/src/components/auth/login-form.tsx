'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { VersionDisplay } from '@/components/ui/version-display';
import { isValidEmail } from '@/lib/utils';

interface LoginFormProps {
  tenantName?: string;
}

export function LoginForm({ tenantName = '' }: LoginFormProps) {
  const { login, isLoading, error, clearError } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [validationError, setValidationError] = useState<string>('');

  const validateForm = (): boolean => {
    setValidationError('');

    if (!email.trim()) {
      setValidationError('Email is required');
      return false;
    }

    if (!isValidEmail(email)) {
      setValidationError('Please enter a valid email address');
      return false;
    }

    if (!password.trim()) {
      setValidationError('Password is required');
      return false;
    }

    if (password.length < 6) {
      setValidationError('Password must be at least 6 characters long');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    clearError();
    
    const success = await login(email.trim(), password);
    
    if (!success) {
      // Error is already set in the store
      setPassword(''); // Clear password on failed login
    }
  };

  const displayError = validationError || error;

  return (
    <div className="w-full max-w-md mx-auto space-y-4">
      {/* Logo Container */}
      <div className="bg-gt-white rounded-xl shadow-lg p-8 border border-gt-gray-200">
        <div className="text-center">
          <div className="flex items-center justify-center">
            <a href="https://gtedge.ai" target="_blank" rel="noopener noreferrer" className="block">
              <Image
                src="/gtedgeai-green-logo.jpeg"
                alt="GT Edge AI Logo"
                width={1536}
                height={462}
                className="h-32 w-auto cursor-pointer hover:opacity-80 transition-opacity"
                priority
              />
            </a>
          </div>
          {tenantName && (
            <div className="mt-4 inline-block px-6 py-3 bg-white shadow-md border border-gt-gray-200 rounded-lg">
              <p className="text-lg font-semibold text-gt-gray-900">{tenantName}</p>
            </div>
          )}
        </div>
      </div>

      {/* Sign In Form Container */}
      <div className="bg-gt-white rounded-xl shadow-lg p-8 border border-gt-gray-200">
        <div className="text-center mb-6">
          <h2 className="text-2xl font-bold text-gt-gray-900">Sign In</h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(value) => setEmail(value)}
            placeholder="Enter your email"
            required
            disabled={isLoading}
            autoComplete="email"
            autoFocus
          />

          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(value) => setPassword(value)}
            placeholder="Enter your password"
            required
            disabled={isLoading}
            autoComplete="current-password"
          />

          {displayError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <div className="flex items-center">
                <svg 
                  className="w-4 h-4 text-red-600 mr-2" 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path 
                    strokeLinecap="round" 
                    strokeLinejoin="round" 
                    strokeWidth={2} 
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" 
                  />
                </svg>
                <p className="text-sm text-red-700">
                  {displayError}
                </p>
              </div>
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={isLoading}
            disabled={isLoading}
            className="w-full"
          >
            {isLoading ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-sm text-gt-gray-500">
            Secured by GT Edge AI • Enterprise Grade Security
          </p>
        </div>
      </div>
    </div>
  );
}