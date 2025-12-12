'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { enableTFA, verifyTFASetup, disableTFA, getTFAStatus } from '@/services/tfa';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

interface TFAStatus {
  tfa_enabled: boolean;
  tfa_required: boolean;
  tfa_status: string; // "disabled", "enabled", "enforced"
}

export function TFASettings() {
  const { user } = useAuthStore();
  const [tfaStatus, setTfaStatus] = useState<TFAStatus>({
    tfa_enabled: false,
    tfa_required: false,
    tfa_status: 'disabled',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Enable TFA modal state
  const [showEnableModal, setShowEnableModal] = useState(false);
  const [qrCodeUri, setQrCodeUri] = useState('');
  const [manualEntryKey, setManualEntryKey] = useState('');
  const [setupCode, setSetupCode] = useState('');
  const [setupStep, setSetupStep] = useState<'qr' | 'verify'>('qr');

  // Disable TFA modal state
  const [showDisableModal, setShowDisableModal] = useState(false);
  const [disablePassword, setDisablePassword] = useState('');

  // Load TFA status on mount
  useEffect(() => {
    loadTFAStatus();
  }, []);

  const loadTFAStatus = async () => {
    try {
      const status = await getTFAStatus();
      setTfaStatus(status);
    } catch (err: any) {
      console.error('Failed to load TFA status:', err);
    }
  };

  const handleToggleChange = (checked: boolean) => {
    if (checked) {
      // Enable TFA
      handleEnableTFA();
    } else {
      // Disable TFA
      if (tfaStatus.tfa_required) {
        setError('Cannot disable 2FA - it is required by your administrator');
        setTimeout(() => setError(''), 5000);
        return;
      }
      setShowDisableModal(true);
    }
  };

  const handleEnableTFA = async () => {
    setIsLoading(true);
    setError('');

    try {
      const result = await enableTFA();
      setQrCodeUri(result.qr_code_uri);
      setManualEntryKey(result.manual_entry_key);
      setSetupStep('qr');
      setShowEnableModal(true);
    } catch (err: any) {
      setError(err.message || 'Failed to enable 2FA');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifySetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validate code format (6 digits)
    if (!/^\d{6}$/.test(setupCode)) {
      setError('Please enter a valid 6-digit code');
      return;
    }

    setIsLoading(true);

    try {
      await verifyTFASetup(setupCode);

      // Success! Close modal and refresh status
      setShowEnableModal(false);
      setSetupCode('');
      setSetupStep('qr');
      setSuccess('2FA enabled successfully!');
      setTimeout(() => setSuccess(''), 5000);

      await loadTFAStatus();
    } catch (err: any) {
      setError(err.message || 'Invalid verification code');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisableTFA = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!disablePassword) {
      setError('Password is required');
      return;
    }

    setIsLoading(true);

    try {
      await disableTFA(disablePassword);

      // Success! Close modal and refresh status
      setShowDisableModal(false);
      setDisablePassword('');
      setSuccess('2FA disabled successfully');
      setTimeout(() => setSuccess(''), 5000);

      await loadTFAStatus();
    } catch (err: any) {
      setError(err.message || 'Failed to disable 2FA');
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccess('Copied to clipboard!');
    setTimeout(() => setSuccess(''), 2000);
  };

  const getStatusBadge = () => {
    const { tfa_status } = tfaStatus;

    if (tfa_status === 'enforced') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
          Enforced
        </span>
      );
    } else if (tfa_status === 'enabled') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          Enabled
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          Disabled
        </span>
      );
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold text-gt-gray-900">
          Two-Factor Authentication
        </h3>
        <p className="text-sm text-gt-gray-600 mt-1">
          Add an extra layer of security to your account using a time-based one-time password (TOTP).
        </p>
      </div>

      {/* Status and Toggle */}
      <div className="bg-white border border-gt-gray-200 rounded-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gt-gray-900">
                  Status:
                </span>
                {getStatusBadge()}
              </div>
              {tfaStatus.tfa_required && (
                <p className="text-xs text-orange-600 mt-1">
                  2FA is required by your administrator
                </p>
              )}
            </div>
          </div>

          <Switch
            checked={tfaStatus.tfa_enabled}
            onCheckedChange={handleToggleChange}
            disabled={isLoading || (tfaStatus.tfa_enabled && tfaStatus.tfa_required)}
          />
        </div>

        {/* Info text */}
        {!tfaStatus.tfa_enabled && !tfaStatus.tfa_required && (
          <div className="bg-gt-blue-50 border border-gt-blue-200 rounded-lg p-4">
            <p className="text-sm text-gt-blue-900">
              <strong>Recommended:</strong> Enable 2FA to protect your account with Google Authenticator or any TOTP-compatible app.
            </p>
          </div>
        )}

        {tfaStatus.tfa_enabled && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-sm text-green-900">
              Your account is protected with 2FA. You'll need to enter a code from your authenticator app each time you log in.
            </p>
          </div>
        )}
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center">
            <svg
              className="w-4 h-4 text-green-600 mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            <p className="text-sm text-green-700">{success}</p>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
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

      {/* Enable TFA Modal */}
      <Dialog open={showEnableModal} onOpenChange={setShowEnableModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Setup Two-Factor Authentication</DialogTitle>
            <DialogDescription>
              {setupStep === 'qr'
                ? 'Scan the QR code with your authenticator app'
                : 'Enter the 6-digit code from your authenticator app'}
            </DialogDescription>
          </DialogHeader>

          <div className="p-6 space-y-4">
            {setupStep === 'qr' && (
              <>
                {/* QR Code Display */}
                <div className="bg-white p-4 rounded-lg border-2 border-gt-gray-200 flex justify-center">
                  <img
                    src={qrCodeUri}
                    alt="QR Code"
                    className="w-48 h-48"
                  />
                </div>

                {/* Manual Entry Key */}
                <div>
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

                {/* Instructions */}
                <div className="bg-gt-blue-50 border border-gt-blue-200 rounded-lg p-4">
                  <p className="text-sm text-gt-blue-900">
                    <strong>Instructions:</strong>
                  </p>
                  <ol className="text-sm text-gt-blue-800 mt-2 ml-4 list-decimal space-y-1">
                    <li>Download Google Authenticator or any TOTP app</li>
                    <li>Scan the QR code or enter the manual key as shown above</li>
                    <li>Click "Next" to verify your setup</li>
                  </ol>
                </div>
              </>
            )}

            {setupStep === 'verify' && (
              <form onSubmit={handleVerifySetup} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gt-gray-700 mb-2">
                    6-Digit Code
                  </label>
                  <Input
                    type="text"
                    value={setupCode}
                    onChange={(value) => setSetupCode(value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="000000"
                    maxLength={6}
                    autoFocus
                    disabled={isLoading}
                    className="text-center text-2xl tracking-widest font-mono"
                  />
                </div>

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <p className="text-sm text-red-700">{error}</p>
                  </div>
                )}
              </form>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => {
                setShowEnableModal(false);
                setSetupStep('qr');
                setSetupCode('');
                setError('');
              }}
              disabled={isLoading}
            >
              Cancel
            </Button>
            {setupStep === 'qr' ? (
              <Button
                variant="primary"
                onClick={() => setSetupStep('verify')}
              >
                Next
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleVerifySetup}
                loading={isLoading}
                disabled={setupCode.length !== 6 || isLoading}
              >
                {isLoading ? 'Verifying...' : 'Verify and Enable'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Disable TFA Modal */}
      <Dialog open={showDisableModal} onOpenChange={setShowDisableModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Disable Two-Factor Authentication</DialogTitle>
            <DialogDescription>
              Enter your password to confirm disabling 2FA
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleDisableTFA} className="p-6 space-y-4">
            <Input
              type="password"
              label="Password"
              value={disablePassword}
              onChange={setDisablePassword}
              placeholder="Enter your password"
              autoFocus
              disabled={isLoading}
            />

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-sm text-yellow-900">
                <strong>Warning:</strong> Disabling 2FA will make your account less secure.
                You will only need your password to log in.
              </p>
            </div>
          </form>

          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => {
                setShowDisableModal(false);
                setDisablePassword('');
                setError('');
              }}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDisableTFA}
              loading={isLoading}
              disabled={!disablePassword || isLoading}
            >
              {isLoading ? 'Disabling...' : 'Disable 2FA'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
