'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';
import { verifyTFALogin, getTFASessionData, getTFAQRCodeBlob } from '@/services/tfa';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Lock, AlertCircle, Copy } from 'lucide-react';
import toast from 'react-hot-toast';

export default function VerifyTFAPage() {
  const router = useRouter();
  const {
    requiresTfa,
    tfaConfigured,
    completeTfaLogin,
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
    let blobUrl: string | null = null;

    // Fetch TFA session data from server using HTTP-only cookie
    const fetchSessionData = async () => {
      if (!requiresTfa) {
        router.push('/auth/login');
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
          blobUrl = await getTFAQRCodeBlob();
          setQrCodeBlobUrl(blobUrl);
        }
      } catch (err: any) {
        console.error('Failed to fetch TFA session data:', err);
        setError('Session expired. Please login again.');
        setTimeout(() => router.push('/auth/login'), 2000);
      } finally {
        setIsFetchingSession(false);
      }
    };

    fetchSessionData();

    // Cleanup: revoke blob URL on unmount using local variable
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [requiresTfa, router]);

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
        // Extract user data from response
        const user = result.user;

        // Update auth store with token and user
        completeTfaLogin(result.access_token, user);

        // Redirect to dashboard
        router.push('/dashboard');
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
    logout();
    router.push('/auth/login');
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  // Show loading while fetching session data
  if (isFetchingSession) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <Loader2 className="w-12 h-12 mx-auto mb-4 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading TFA setup...</p>
        </div>
      </div>
    );
  }

  if (!requiresTfa) {
    return null; // Will redirect via useEffect
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center space-y-1">
          <div className="w-16 h-16 bg-primary rounded-lg flex items-center justify-center mx-auto mb-4">
            <Lock className="h-8 w-8 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl font-bold">
            {tfaConfigured ? 'Two-Factor Authentication' : 'Setup Two-Factor Authentication'}
          </CardTitle>
          <CardDescription>
            {tfaConfigured
              ? 'Enter the 6-digit code from your authenticator app'
              : 'Your administrator requires 2FA for your account'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {/* Mode A: Setup (tfa_configured=false) */}
          {!tfaConfigured && qrCodeBlobUrl && (
            <div className="mb-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold mb-3">Scan QR Code</h3>

                {/* QR Code Display (secure blob URL - TOTP secret never in JavaScript) */}
                <div className="bg-white p-4 rounded-lg border-2 border-border mb-4 flex justify-center">
                  <img
                    src={qrCodeBlobUrl}
                    alt="QR Code"
                    className="w-48 h-48"
                  />
                </div>
              </div>

              {/* Manual Entry Key */}
              {manualEntryKey && (
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Manual Entry Key
                  </label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 px-3 py-2 bg-muted border border-border rounded-lg text-sm font-mono">
                      {manualEntryKey}
                    </code>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(manualEntryKey.replace(/\s/g, ''))}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}

              <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <p className="text-sm font-semibold mb-2 text-blue-900 dark:text-blue-100">
                  Instructions:
                </p>
                <ol className="text-sm text-blue-800 dark:text-blue-200 ml-4 list-decimal space-y-1">
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
              <label className="block text-sm font-medium mb-2">
                6-Digit Code
              </label>
              <Input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                maxLength={6}
                autoFocus
                disabled={isLoading || attempts >= 5}
                className="text-center text-2xl tracking-widest font-mono"
              />
            </div>

            {error && (
              <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3">
                <div className="flex items-center">
                  <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 mr-2" />
                  <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
                </div>
              </div>
            )}

            {attempts > 0 && attempts < 5 && (
              <p className="text-sm text-muted-foreground text-center">
                Attempts remaining: {5 - attempts}
              </p>
            )}

            <div className="flex gap-3">
              <Button
                type="submit"
                className="flex-1"
                disabled={isLoading || code.length !== 6 || attempts >= 5}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  tfaConfigured ? 'Verify' : 'Verify and Complete Setup'
                )}
              </Button>

              {/* Only show cancel if TFA is already configured (optional flow) */}
              {tfaConfigured && (
                <Button
                  type="button"
                  variant="outline"
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
              <p className="text-xs text-muted-foreground">
                2FA is required for your account. Contact your administrator if you need assistance.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Security Info */}
      <div className="absolute bottom-4 left-0 right-0 text-center text-sm text-muted-foreground">
        <p>GT 2.0 Control Panel • Enterprise Security</p>
      </div>
    </div>
  );
}
