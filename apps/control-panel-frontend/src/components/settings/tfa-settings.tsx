'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { enableTFA, verifyTFASetup, disableTFA, getTFAStatus } from '@/services/tfa';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { AlertCircle, CheckCircle, Copy, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

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

  // Enable TFA modal state
  const [showEnableModal, setShowEnableModal] = useState(false);
  const [qrCodeUri, setQrCodeUri] = useState('');
  const [manualEntryKey, setManualEntryKey] = useState('');
  const [setupCode, setSetupCode] = useState('');
  const [setupStep, setSetupStep] = useState<'qr' | 'verify'>('qr');
  const [setupError, setSetupError] = useState('');

  // Disable TFA modal state
  const [showDisableModal, setShowDisableModal] = useState(false);
  const [disablePassword, setDisablePassword] = useState('');
  const [disableError, setDisableError] = useState('');

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
        toast.error('Cannot disable 2FA - it is required by your administrator');
        return;
      }
      setShowDisableModal(true);
    }
  };

  const handleEnableTFA = async () => {
    setIsLoading(true);
    setSetupError('');

    try {
      const result = await enableTFA();
      setQrCodeUri(result.qr_code_uri);
      setManualEntryKey(result.manual_entry_key);
      setSetupStep('qr');
      setShowEnableModal(true);
    } catch (err: any) {
      toast.error(err.message || 'Failed to enable 2FA');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifySetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setSetupError('');

    // Validate code format (6 digits)
    if (!/^\d{6}$/.test(setupCode)) {
      setSetupError('Please enter a valid 6-digit code');
      return;
    }

    setIsLoading(true);

    try {
      await verifyTFASetup(setupCode);

      // Success! Close modal and refresh status
      setShowEnableModal(false);
      setSetupCode('');
      setSetupStep('qr');
      toast.success('2FA enabled successfully!');

      await loadTFAStatus();
    } catch (err: any) {
      setSetupError(err.message || 'Invalid verification code');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisableTFA = async (e: React.FormEvent) => {
    e.preventDefault();
    setDisableError('');

    if (!disablePassword) {
      setDisableError('Password is required');
      return;
    }

    setIsLoading(true);

    try {
      await disableTFA(disablePassword);

      // Success! Close modal and refresh status
      setShowDisableModal(false);
      setDisablePassword('');
      toast.success('2FA disabled successfully');

      await loadTFAStatus();
    } catch (err: any) {
      setDisableError(err.message || 'Failed to disable 2FA');
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard!');
  };

  const getStatusBadge = () => {
    const { tfa_status } = tfaStatus;

    if (tfa_status === 'enforced') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
          Enforced
        </span>
      );
    } else if (tfa_status === 'enabled') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Enabled
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200">
          Disabled
        </span>
      );
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h3 className="text-lg font-semibold">
          Two-Factor Authentication
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          Add an extra layer of security to your account using a time-based one-time password (TOTP).
        </p>
      </div>

      {/* Status and Toggle */}
      <div className="border rounded-lg p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  Status:
                </span>
                {getStatusBadge()}
              </div>
              {tfaStatus.tfa_required && (
                <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">
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
          <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <p className="text-sm text-blue-900 dark:text-blue-100">
              <strong>Recommended:</strong> Enable 2FA to protect your account with Google Authenticator or any TOTP-compatible app.
            </p>
          </div>
        )}

        {tfaStatus.tfa_enabled && (
          <div className="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-4">
            <p className="text-sm text-green-900 dark:text-green-100">
              Your account is protected with 2FA. You'll need to enter a code from your authenticator app each time you log in.
            </p>
          </div>
        )}
      </div>

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

          <div className="space-y-4">
            {setupStep === 'qr' && (
              <>
                {/* QR Code Display */}
                <div className="bg-white p-4 rounded-lg border-2 border-border flex justify-center">
                  <img
                    src={qrCodeUri}
                    alt="QR Code"
                    className="w-48 h-48"
                  />
                </div>

                {/* Manual Entry Key */}
                <div>
                  <Label className="text-sm font-medium mb-2">
                    Manual Entry Key
                  </Label>
                  <div className="flex items-center gap-2 mt-2">
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

                {/* Instructions */}
                <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
                    Instructions:
                  </p>
                  <ol className="text-sm text-blue-800 dark:text-blue-200 mt-2 ml-4 list-decimal space-y-1">
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
                  <Label className="text-sm font-medium mb-2">
                    6-Digit Code
                  </Label>
                  <Input
                    type="text"
                    value={setupCode}
                    onChange={(e) => setSetupCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="000000"
                    maxLength={6}
                    autoFocus
                    disabled={isLoading}
                    className="text-center text-2xl tracking-widest font-mono mt-2"
                  />
                </div>

                {setupError && (
                  <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3">
                    <div className="flex items-center">
                      <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 mr-2" />
                      <p className="text-sm text-red-700 dark:text-red-300">{setupError}</p>
                    </div>
                  </div>
                )}
              </form>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowEnableModal(false);
                setSetupStep('qr');
                setSetupCode('');
                setSetupError('');
              }}
              disabled={isLoading}
            >
              Cancel
            </Button>
            {setupStep === 'qr' ? (
              <Button
                onClick={() => setSetupStep('verify')}
              >
                Next
              </Button>
            ) : (
              <Button
                onClick={handleVerifySetup}
                disabled={setupCode.length !== 6 || isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  'Verify and Enable'
                )}
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

          <form onSubmit={handleDisableTFA} className="space-y-4">
            <div>
              <Label htmlFor="disable-password">Password</Label>
              <Input
                id="disable-password"
                type="password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
                placeholder="Enter your password"
                autoFocus
                disabled={isLoading}
                className="mt-2"
              />
            </div>

            {disableError && (
              <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-3">
                <div className="flex items-center">
                  <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400 mr-2" />
                  <p className="text-sm text-red-700 dark:text-red-300">{disableError}</p>
                </div>
              </div>
            )}

            <div className="bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
              <p className="text-sm text-yellow-900 dark:text-yellow-100">
                <strong>Warning:</strong> Disabling 2FA will make your account less secure.
                You will only need your password to log in.
              </p>
            </div>
          </form>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowDisableModal(false);
                setDisablePassword('');
                setDisableError('');
              }}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDisableTFA}
              disabled={!disablePassword || isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Disabling...
                </>
              ) : (
                'Disable 2FA'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
