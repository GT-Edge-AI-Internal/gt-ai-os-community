'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore, useHasHydrated } from '@/stores/auth-store';
import { verifyTFALogin, getTFASessionData, getTFAQRCodeBlob } from '@/services/tfa';
import { parseCapabilities, setAuthToken, setUser, parseTokenPayload, mapControlPanelRoleToTenantRole } from '@/services/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export default function VerifyTFAPage() {
  const router = useRouter();
  const hasHydrated = useHasHydrated();
  const {
    requiresTfa,
    tfaConfigured,
    logout,
  } = useAuthStore();

  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingSession, setIsFetchingSession] = useState(true);
  const [attempts, setAttempts] = useState(0);

  // Session data fetched from server
  const [qrCodeBlobUrl, setQrCodeBlobUrl] = useState<string | null>(null);
  const [manualEntryKey, setManualEntryKey] = useState<string | null>(null);

  useEffect(() => {
    // Wait for hydration before checking TFA state
    if (!hasHydrated) {
      return;
    }

    // Fetch TFA session data from server using HTTP-only cookie
    const fetchSessionData = async () => {
      if (!requiresTfa) {
        // User doesn't need TFA, redirect to login
        router.push('/login');
        return;
      }

      try {
        setIsFetchingSession(true);

        // Fetch session metadata
        const sessionData = await getTFASessionData();

        if (sessionData.manual_entry_key) {
          setManualEntryKey(sessionData.manual_entry_key);
        }

        // Fetch QR code as secure blob (if needed for setup)
        if (!sessionData.tfa_configured) {
          const blobUrl = await getTFAQRCodeBlob();
          setQrCodeBlobUrl(blobUrl);
        }
      } catch (err: any) {
        console.error('Failed to fetch TFA session data:', err);
        setError('Session expired. Please login again.');
        setTimeout(() => {
          router.push('/login');
        }, 2000);
      } finally {
        setIsFetchingSession(false);
      }
    };

    fetchSessionData();

    // Cleanup: revoke blob URL on unmount
    return () => {
      if (qrCodeBlobUrl) {
        URL.revokeObjectURL(qrCodeBlobUrl);
      }
    };
  }, [hasHydrated, requiresTfa, router]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate code format (6 digits)
    if (!/^\d{6}$/.test(code)) {
      setError('Please enter a valid 6-digit code');
      return;
    }

    setIsLoading(true);

    try {
      // Session cookie automatically sent with request
      const result = await verifyTFALogin(code);

      if (result.success && result.access_token) {
        // Save token
        setAuthToken(result.access_token);

        // Decode JWT to extract user data
        const payload = parseTokenPayload(result.access_token);

        if (!payload) {
          throw new Error('Failed to decode token');
        }

        // Construct user object from JWT claims
        const user = {
          id: parseInt(payload.sub),
          email: payload.email,
          full_name: payload.current_tenant?.display_name || payload.email,
          role: mapControlPanelRoleToTenantRole(payload.user_type),
          user_type: payload.user_type,
          tenant_id: payload.current_tenant?.id ? parseInt(payload.current_tenant.id) : null,
          is_active: true,
          available_tenants: payload.available_tenants || []
        };

        // Parse capabilities from JWT
        const capabilityStrings = parseCapabilities(result.access_token);

        // Save user to localStorage
        setUser(user);

        // Update auth store
        useAuthStore.setState({
          token: result.access_token,
          user: user,
          capabilities: capabilityStrings,
          isAuthenticated: true,
          requiresTfa: false,
          tfaConfigured: false,
          isLoading: false,
        });

        // Small delay ensures localStorage writes complete before navigation
        await new Promise(resolve => setTimeout(resolve, 50));

        // Signal that TFA was just completed (prevents login page flash)
        sessionStorage.setItem('gt2_tfa_verified', 'true');

        // Use replace to skip login page in browser history
        router.replace('/agents');
      } else {
        throw new Error(result.message || 'Verification failed');
      }
    } catch (err: any) {
      const newAttempts = attempts + 1;
      setAttempts(newAttempts);

      if (newAttempts >= 5) {
        setError('Too many attempts. Please wait 60 seconds and try again.');
      } else {
        setError(err.message || 'Invalid verification code. Please try again.');
      }

      setCode('');
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    // Only show cancel if NOT mandatory (tfa_configured=true means optional)
    logout();
    router.push('/login');
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  // Show loading while hydrating or fetching session data
  if (!hasHydrated || isFetchingSession) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gt-gray-50 to-gt-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto w-16 h-16 bg-gt-green rounded-full flex items-center justify-center mb-4">
            <svg className="animate-spin h-8 w-8 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          <p className="text-gt-gray-600">Loading TFA setup...</p>
        </div>
      </div>
    );
  }

  if (!requiresTfa) {
    return null; // Will redirect via useEffect
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gt-gray-50 to-gt-gray-100 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-grid-pattern opacity-5"></div>

      <div className="relative z-10 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="mx-auto w-16 h-16 bg-gt-green rounded-full flex items-center justify-center mb-4">
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gt-gray-900 mb-2">
            {tfaConfigured ? 'Two-Factor Authentication' : 'Setup Two-Factor Authentication'}
          </h1>
          <p className="text-gt-gray-600">
            {tfaConfigured
              ? 'Enter the 6-digit code from your authenticator app'
              : 'Your administrator requires 2FA for your account'}
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-8 border border-gt-gray-200">
          {/* Mode A: Setup (tfa_configured=false) */}
          {!tfaConfigured && qrCodeBlobUrl && (
            <div className="mb-6">
              <h2 className="text-lg font-semibold text-gt-gray-900 mb-4">
                Scan QR Code
              </h2>

              {/* QR Code Display (secure blob URL - TOTP secret never in JavaScript) */}
              <div className="bg-white p-4 rounded-lg border-2 border-gt-gray-200 mb-4 flex justify-center">
                <img
                  src={qrCodeBlobUrl}
                  alt="QR Code"
                  className="w-48 h-48"
                />
              </div>

              {/* Manual Entry Key */}
              {manualEntryKey && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gt-gray-700 mb-2">
                    Manual Entry Key
                  </label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 px-3 py-2 bg-gt-gray-50 border border-gt-gray-200 rounded-lg text-sm font-mono">
                      {manualEntryKey}
                    </code>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => copyToClipboard(manualEntryKey.replace(/\s/g, ''))}
                    >
                      Copy
                    </Button>
                  </div>
                </div>
              )}

              <div className="bg-gt-blue-50 border border-gt-blue-200 rounded-lg p-4 mb-4">
                <p className="text-sm text-gt-blue-900">
                  <strong>Instructions:</strong>
                </p>
                <ol className="text-sm text-gt-blue-800 mt-2 ml-4 list-decimal space-y-1">
                  <li>Download Google Authenticator or any TOTP app</li>
                  <li>Scan the QR code or enter the manual key as shown above</li>
                  <li>Enter the 6-digit code below to complete setup</li>
                </ol>
              </div>
            </div>
          )}

          {/* Code Input (both modes) */}
          <form onSubmit={handleVerify} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gt-gray-700 mb-2">
                6-Digit Code
              </label>
              <Input
                type="text"
                value={code}
                onChange={(value) => setCode(value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                maxLength={6}
                autoFocus
                disabled={isLoading || attempts >= 5}
                className="text-center text-2xl tracking-widest font-mono"
              />
            </div>

            {error && (
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
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              </div>
            )}

            {attempts > 0 && attempts < 5 && (
              <p className="text-sm text-gt-gray-600 text-center">
                Attempts remaining: {5 - attempts}
              </p>
            )}

            <div className="flex gap-3">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={isLoading}
                disabled={isLoading || code.length !== 6 || attempts >= 5}
                className="flex-1"
              >
                {isLoading ? 'Verifying...' : tfaConfigured ? 'Verify' : 'Verify and Complete Setup'}
              </Button>

              {/* Only show cancel if TFA is already configured (optional flow) */}
              {tfaConfigured && (
                <Button
                  type="button"
                  variant="secondary"
                  size="lg"
                  onClick={handleCancel}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
              )}
            </div>
          </form>

          {/* No cancel button for mandatory setup (Mode A) */}
          {!tfaConfigured && (
            <div className="mt-4 text-center">
              <p className="text-xs text-gt-gray-500">
                2FA is required for your account. Contact your administrator if you need assistance.
              </p>
            </div>
          )}
        </div>

        {/* Security Info */}
        <div className="mt-6 text-center text-sm text-gt-gray-500">
          <p>Secured by GT Edge AI • Enterprise Grade Security</p>
        </div>
      </div>
    </div>
  );
}
