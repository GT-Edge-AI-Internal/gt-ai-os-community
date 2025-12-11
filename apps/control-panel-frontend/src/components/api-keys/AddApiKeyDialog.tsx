"use client";

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { apiKeysApi } from '@/lib/api';
import {
  Key,
  Eye,
  EyeOff,
  TestTube,
  Loader2,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';

// Provider configuration type
export interface ProviderConfig {
  id: string;
  name: string;
  description: string;
  keyPrefix: string;
  consoleUrl: string;
  consoleName: string;
}

interface AddApiKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenantId: number;
  tenantName: string;
  existingKey?: boolean;
  onKeyAdded?: () => void;
  provider: ProviderConfig;
}

export default function AddApiKeyDialog({
  open,
  onOpenChange,
  tenantId,
  tenantName,
  existingKey = false,
  onKeyAdded,
  provider,
}: AddApiKeyDialogProps) {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const { toast } = useToast();

  // Validate key format based on provider
  const isValidFormat = apiKey.startsWith(provider.keyPrefix) && apiKey.length > 10;

  const handleTest = async () => {
    if (!isValidFormat) {
      toast({
        title: "Invalid Format",
        description: `${provider.name} API keys must start with '${provider.keyPrefix}'`,
        variant: "destructive",
      });
      return;
    }

    setIsTesting(true);
    setTestResult(null);

    try {
      // First save the key temporarily to test it
      await apiKeysApi.setKey({
        tenant_id: tenantId,
        provider: provider.id,
        api_key: apiKey,
        enabled: true,
      });

      // Then test it
      const response = await apiKeysApi.testKey(tenantId, provider.id);
      const result = response.data;

      setTestResult({
        success: result.valid,
        message: result.message,
      });

      if (result.valid) {
        toast({
          title: "Connection Successful",
          description: `The ${provider.name} API key is valid and working`,
        });
      } else {
        toast({
          title: "Connection Failed",
          description: result.message || "The API key could not be validated",
          variant: "destructive",
        });
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Connection test failed';
      setTestResult({
        success: false,
        message: errorMessage,
      });
      toast({
        title: "Test Failed",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSubmit = async () => {
    if (!isValidFormat) {
      toast({
        title: "Invalid Format",
        description: `${provider.name} API keys must start with '${provider.keyPrefix}'`,
        variant: "destructive",
      });
      return;
    }

    setIsSaving(true);

    try {
      await apiKeysApi.setKey({
        tenant_id: tenantId,
        provider: provider.id,
        api_key: apiKey,
        enabled: true,
      });

      toast({
        title: existingKey ? "API Key Updated" : "API Key Added",
        description: `${provider.name} API key has been ${existingKey ? 'updated' : 'configured'} for ${tenantName}`,
      });

      // Reset form
      setApiKey('');
      setTestResult(null);
      onOpenChange(false);

      // Notify parent
      if (onKeyAdded) {
        onKeyAdded();
      }
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to save API key';
      toast({
        title: "Save Failed",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleClose = () => {
    setApiKey('');
    setTestResult(null);
    setShowKey(false);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Key className="w-5 h-5" />
            {existingKey ? 'Update' : 'Add'} {provider.name} API Key
          </DialogTitle>
          <DialogDescription>
            Configure the {provider.name} API key for <strong>{tenantName}</strong>.
            This key will be encrypted and stored securely.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="api_key">API Key</Label>
            <div className="relative">
              <Input
                id="api_key"
                type={showKey ? 'text' : 'password'}
                placeholder={`${provider.keyPrefix}xxxxxxxxxxxxxxxxxxxx`}
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setTestResult(null);
                }}
                className="pr-10 font-mono"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
                onClick={() => setShowKey(!showKey)}
              >
                {showKey ? (
                  <EyeOff className="h-4 w-4 text-gray-400" />
                ) : (
                  <Eye className="h-4 w-4 text-gray-400" />
                )}
              </button>
            </div>
            <p className="text-sm text-muted-foreground">
              Get your API key from{' '}
              <a
                href={provider.consoleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline"
              >
                {provider.consoleName}
              </a>
            </p>
            {apiKey && !isValidFormat && (
              <p className="text-sm text-destructive">
                {provider.name} API keys must start with &apos;{provider.keyPrefix}&apos;
              </p>
            )}
          </div>

          {/* Test Connection Button */}
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleTest}
              disabled={!isValidFormat || isTesting}
              className="flex-1"
            >
              {isTesting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <TestTube className="mr-2 h-4 w-4" />
                  Test Connection
                </>
              )}
            </Button>
          </div>

          {/* Test Result */}
          {testResult && (
            <div
              className={`flex items-center gap-2 p-3 rounded-md text-sm ${
                testResult.success
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              {testResult.success ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <AlertCircle className="h-4 w-4" />
              )}
              {testResult.message}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isValidFormat || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>{existingKey ? 'Update' : 'Add'} Key</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
