'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { apiKeysApi } from '@/lib/api';
import { useToast } from '@/components/ui/use-toast';
import AddApiKeyDialog, { ProviderConfig } from '@/components/api-keys/AddApiKeyDialog';
import {
  Key,
  Plus,
  TestTube,
  Trash2,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  AlertTriangle,
} from 'lucide-react';

// Hardcoded tenant for GT AI OS Local (single-tenant deployment)
const TEST_COMPANY_TENANT = {
  id: 1,
  name: 'HW Workstation Test Deployment',
  domain: 'test-company',
};

interface APIKeyStatus {
  configured: boolean;
  enabled: boolean;
  updated_at: string | null;
  metadata: Record<string, unknown> | null;
}

// Provider configuration - NVIDIA first (above Groq), then Groq
const PROVIDER_CONFIG: ProviderConfig[] = [
  {
    id: 'nvidia',
    name: 'NVIDIA NIM',
    description: 'GPU-accelerated inference on DGX Cloud via build.nvidia.com',
    keyPrefix: 'nvapi-',
    consoleUrl: 'https://build.nvidia.com/settings/api-keys',
    consoleName: 'build.nvidia.com',
  },
  {
    id: 'groq',
    name: 'Groq Cloud LLM',
    description: 'LPU-accelerated inference via api.groq.com',
    keyPrefix: 'gsk_',
    consoleUrl: 'https://console.groq.com/keys',
    consoleName: 'console.groq.com',
  },
];

export default function ApiKeysPage() {
  // Auto-select test_company tenant for GT AI OS Local
  const selectedTenant = TEST_COMPANY_TENANT;
  const selectedTenantId = TEST_COMPANY_TENANT.id;

  const [apiKeyStatus, setApiKeyStatus] = useState<Record<string, APIKeyStatus>>({});
  const [isLoadingKeys, setIsLoadingKeys] = useState(false);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showRemoveDialog, setShowRemoveDialog] = useState(false);
  const [activeProvider, setActiveProvider] = useState<ProviderConfig | null>(null);
  const [testResults, setTestResults] = useState<Record<string, {
    success: boolean;
    message: string;
    error_type?: string;
    rate_limit_remaining?: number;
    rate_limit_reset?: string;
    models_available?: number;
  }>>({});

  const { toast } = useToast();

  // Fetch API keys for test_company tenant
  const fetchApiKeys = useCallback(async (tenantId: number) => {
    setIsLoadingKeys(true);
    setTestResults({});

    try {
      const response = await apiKeysApi.getTenantKeys(tenantId);
      setApiKeyStatus(response.data || {});
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
      setApiKeyStatus({});
    } finally {
      setIsLoadingKeys(false);
    }
  }, []);

  // Load API keys on mount
  useEffect(() => {
    fetchApiKeys(selectedTenantId);
  }, [selectedTenantId, fetchApiKeys]);

  const handleTestConnection = async (provider: ProviderConfig) => {
    if (!selectedTenantId) return;

    setTestingProvider(provider.id);
    setTestResults((prev) => {
      const newResults = { ...prev };
      delete newResults[provider.id];
      return newResults;
    });

    try {
      const response = await apiKeysApi.testKey(selectedTenantId, provider.id);
      const result = response.data;

      setTestResults((prev) => ({
        ...prev,
        [provider.id]: {
          success: result.valid,
          message: result.message,
          error_type: result.error_type,
          rate_limit_remaining: result.rate_limit_remaining,
          rate_limit_reset: result.rate_limit_reset,
          models_available: result.models_available,
        },
      }));

      // Build toast message with additional info
      let description = result.message;
      if (result.valid && result.models_available) {
        description += ` (${result.models_available} models available)`;
      }

      toast({
        title: result.valid ? 'Connection Successful' : 'Connection Failed',
        description: description,
        variant: result.valid ? 'default' : 'destructive',
      });
    } catch (error) {
      const message = 'Failed to test connection';
      setTestResults((prev) => ({
        ...prev,
        [provider.id]: { success: false, message, error_type: 'connection_error' },
      }));
      toast({
        title: 'Test Failed',
        description: message,
        variant: 'destructive',
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const handleRemoveKey = async () => {
    if (!selectedTenantId || !activeProvider) return;

    try {
      await apiKeysApi.removeKey(selectedTenantId, activeProvider.id);
      toast({
        title: 'API Key Removed',
        description: `The ${activeProvider.name} API key has been removed`,
      });
      fetchApiKeys(selectedTenantId);
    } catch (error) {
      toast({
        title: 'Remove Failed',
        description: 'Failed to remove API key',
        variant: 'destructive',
      });
    } finally {
      setShowRemoveDialog(false);
      setActiveProvider(null);
    }
  };

  const handleKeyAdded = () => {
    if (selectedTenantId) {
      fetchApiKeys(selectedTenantId);
    }
  };

  const openAddDialog = (provider: ProviderConfig) => {
    setActiveProvider(provider);
    setShowAddDialog(true);
  };

  const openRemoveDialog = (provider: ProviderConfig) => {
    setActiveProvider(provider);
    setShowRemoveDialog(true);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
          <p className="text-muted-foreground">
            Manage API keys for external AI providers
          </p>
        </div>
      </div>

      {/* API Keys Section - One card per provider */}
      {selectedTenant && (
        <div className="space-y-6">
          {PROVIDER_CONFIG.map((provider) => {
            const keyStatus = apiKeyStatus[provider.id];
            const testResult = testResults[provider.id];
            const isTesting = testingProvider === provider.id;

            return (
              <Card key={provider.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Key className="h-5 w-5" />
                        {provider.name} API Key
                      </CardTitle>
                      <CardDescription>
                        {provider.description} for {selectedTenant.name}
                      </CardDescription>
                    </div>
                    {!keyStatus?.configured && (
                      <Button onClick={() => openAddDialog(provider)}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add Key
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {isLoadingKeys ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : keyStatus?.configured ? (
                    <div className="space-y-4">
                      {/* Status Badges */}
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          Configured
                        </Badge>
                        <Badge
                          variant={keyStatus.enabled ? 'default' : 'destructive'}
                        >
                          {keyStatus.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </div>

                      {/* Key Display */}
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>Key:</span>
                        <code className="bg-muted px-2 py-1 rounded font-mono">
                          {provider.keyPrefix}••••••••••••••••••••
                        </code>
                      </div>

                      {/* Last Updated */}
                      <div className="text-sm text-muted-foreground">
                        Last updated: {formatDate(keyStatus.updated_at)}
                      </div>

                      {/* Test Result */}
                      {testResult && (
                        <div
                          className={`flex flex-col gap-2 p-3 rounded-md text-sm ${
                            testResult.success
                              ? 'bg-green-50 text-green-700 border border-green-200'
                              : testResult.error_type === 'rate_limited'
                              ? 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                              : 'bg-red-50 text-red-700 border border-red-200'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            {testResult.success ? (
                              <CheckCircle className="h-4 w-4 flex-shrink-0" />
                            ) : testResult.error_type === 'rate_limited' ? (
                              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                            ) : (
                              <AlertCircle className="h-4 w-4 flex-shrink-0" />
                            )}
                            <span>{testResult.message}</span>
                          </div>
                          {/* Additional info row */}
                          {(testResult.models_available || testResult.rate_limit_remaining !== undefined) && (
                            <div className="flex items-center gap-4 text-xs opacity-80 ml-6">
                              {testResult.models_available && (
                                <span>{testResult.models_available} models available</span>
                              )}
                              {testResult.rate_limit_remaining !== undefined && (
                                <span>Rate limit: {testResult.rate_limit_remaining} remaining</span>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-4 pt-2">
                        <Button
                          variant="outline"
                          onClick={() => handleTestConnection(provider)}
                          disabled={isTesting || !keyStatus.enabled}
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

                        <Button
                          variant="outline"
                          onClick={() => openAddDialog(provider)}
                        >
                          Update Key
                        </Button>

                        <Button
                          variant="ghost"
                          className="text-destructive hover:text-destructive"
                          onClick={() => openRemoveDialog(provider)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Remove
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <XCircle className="mx-auto h-12 w-12 text-muted-foreground/50" />
                      <h3 className="mt-4 text-lg font-medium">No API Key Configured</h3>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Add a {provider.name} API key to enable AI inference for this tenant.
                      </p>
                      <Button
                        className="mt-4"
                        onClick={() => openAddDialog(provider)}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Configure API Key
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add/Edit Dialog */}
      {selectedTenant && activeProvider && (
        <AddApiKeyDialog
          open={showAddDialog}
          onOpenChange={setShowAddDialog}
          tenantId={selectedTenant.id}
          tenantName={selectedTenant.name}
          existingKey={apiKeyStatus[activeProvider.id]?.configured}
          onKeyAdded={handleKeyAdded}
          provider={activeProvider}
        />
      )}

      {/* Remove Confirmation Dialog */}
      <AlertDialog open={showRemoveDialog} onOpenChange={setShowRemoveDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove API Key?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove the {activeProvider?.name} API key for{' '}
              <strong>{selectedTenant?.name}</strong>. AI inference using this provider will stop
              working for this tenant until a new key is configured.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveKey}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Remove Key
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
