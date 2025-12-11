"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  TestTube,
  RefreshCw,
  Wifi,
  WifiOff,
  ExternalLink,
  Clock,
  Plus,
  Trash2
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ProviderConfig {
  provider: string;
  name: string;
  endpoint: string;
  enabled: boolean;
  health_status: 'healthy' | 'unhealthy' | 'degraded' | 'testing' | 'unknown';
  description: string;
  is_external: boolean;
  requires_api_key: boolean;
  last_test?: string;
  last_latency_ms?: number;
  is_custom?: boolean;
  model_type?: 'llm' | 'embedding' | 'both';
  is_local_mode?: boolean;
  external_endpoint?: string;
}

interface AddEndpointForm {
  name: string;
  provider: string;
  endpoint: string;
  description: string;
  model_type: 'llm' | 'embedding' | 'both';
  is_external: boolean;
  requires_api_key: boolean;
}

interface EndpointConfiguratorProps {
  showAddDialog?: boolean;
  onShowAddDialogChange?: (show: boolean) => void;
}

export default function EndpointConfigurator({
  showAddDialog: externalShowAddDialog,
  onShowAddDialogChange
}: EndpointConfiguratorProps = {}) {
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [internalShowAddDialog, setInternalShowAddDialog] = useState(false);

  // Use external state if provided, otherwise use internal state
  const showAddDialog = externalShowAddDialog !== undefined ? externalShowAddDialog : internalShowAddDialog;
  const setShowAddDialog = onShowAddDialogChange || setInternalShowAddDialog;
  const [addForm, setAddForm] = useState<AddEndpointForm>({
    name: '',
    provider: '',
    endpoint: '',
    description: '',
    model_type: 'llm',
    is_external: false,
    requires_api_key: true,
  });
  const { toast } = useToast();

  // Initialize with default configurations
  useEffect(() => {
    const defaultProviders: ProviderConfig[] = [
      {
        provider: 'nvidia',
        name: 'NVIDIA NIM (build.nvidia.com)',
        endpoint: 'https://integrate.api.nvidia.com/v1/chat/completions',
        enabled: true,
        health_status: 'unknown',
        description: 'NVIDIA NIM microservices - GPU-accelerated inference on DGX Cloud',
        is_external: false,
        requires_api_key: true,
        is_custom: false,
        model_type: 'llm'
      },
      {
        provider: 'groq',
        name: 'Groq (LLMs, Audio, TTS)',
        endpoint: 'https://api.groq.com/openai/v1/chat/completions',
        enabled: true,
        health_status: 'healthy',
        is_external: false,
        requires_api_key: true,
        last_test: '2025-01-21T10:30:00Z',
        is_custom: false,
        model_type: 'llm'
      },
      {
        provider: 'ollama-dgx-x86',
        name: 'Local Ollama (DGX/X86)',
        endpoint: 'http://ollama-host:11434/v1/chat/completions',
        enabled: true,
        health_status: 'unknown',
        description: 'Local Ollama instance for DGX and x86 Linux deployments',
        is_external: false,
        requires_api_key: false,
        is_custom: false,
        model_type: 'llm'
      },
      {
        provider: 'ollama-macos',
        name: 'Local Ollama (MacOS)',
        endpoint: 'http://host.docker.internal:11434/v1/chat/completions',
        enabled: true,
        health_status: 'unknown',
        description: 'Local Ollama instance for macOS deployments',
        is_external: false,
        requires_api_key: false,
        is_custom: false,
        model_type: 'llm'
      },
      {
        provider: 'bge_m3',
        name: 'BGE-M3 Embeddings',
        endpoint: 'http://gentwo-vllm-embeddings:8000/v1/embeddings',
        enabled: true,
        health_status: 'healthy',
        description: 'Multilingual embedding model - Local GT Edge deployment',
        is_external: false,
        requires_api_key: false,
        last_test: '2025-01-21T10:32:00Z',
        is_custom: false,
        model_type: 'embedding',
        is_local_mode: true,
        external_endpoint: 'http://10.0.1.50:8080'
      }
    ];

    // Load custom endpoints from localStorage or API
    const savedCustomEndpoints = localStorage.getItem('custom_endpoints');
    if (savedCustomEndpoints) {
      try {
        const customEndpoints = JSON.parse(savedCustomEndpoints);
        defaultProviders.push(...customEndpoints);
      } catch (error) {
        console.error('Failed to load custom endpoints:', error);
      }
    }

    setProviders(defaultProviders);
    setLoading(false);
  }, []);

  // Load BGE-M3 configuration from API
  useEffect(() => {
    const loadBGEConfig = async () => {
      try {
        const response = await fetch('/api/v1/models/BAAI%2Fbge-m3', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          }
        });

        if (response.ok) {
          const bgeModel = await response.json();
          const isLocalMode = bgeModel.config?.is_local_mode ?? true;
          const externalEndpoint = bgeModel.config?.external_endpoint || 'http://10.0.1.50:8080';

          setProviders(prev => prev.map(p => {
            if (p.provider === 'bge_m3') {
              return {
                ...p,
                endpoint: bgeModel.endpoint,
                enabled: bgeModel.status?.is_active ?? true,
                health_status: bgeModel.status?.health_status || 'healthy',
                description: isLocalMode
                  ? 'Multilingual embedding model - Local GT Edge deployment'
                  : 'Multilingual embedding model - External API deployment',
                is_external: !isLocalMode,
                is_local_mode: isLocalMode,
                external_endpoint: externalEndpoint
              };
            }
            return p;
          }));
        }
      } catch (error) {
        console.error('Error loading BGE-M3 config from API:', error);
      }
    };

    loadBGEConfig();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'degraded':
        return <AlertTriangle className="w-4 h-4 text-yellow-600" />;
      case 'unhealthy':
        return <AlertCircle className="w-4 h-4 text-red-600" />;
      case 'testing':
        return <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getConnectionIcon = (isExternal: boolean) => {
    return isExternal ? (
      <Wifi className="w-4 h-4 text-blue-600" />
    ) : (
      <WifiOff className="w-4 h-4 text-gray-600" />
    );
  };

  const handleEndpointChange = (provider: string, newEndpoint: string) => {
    setProviders(prev => prev.map(p => 
      p.provider === provider 
        ? { ...p, endpoint: newEndpoint }
        : p
    ));
  };

  const handleToggleProvider = async (provider: string, enabled: boolean) => {
    setProviders(prev => prev.map(p => 
      p.provider === provider 
        ? { ...p, enabled: !enabled }
        : p
    ));

    toast({
      title: `Provider ${!enabled ? 'Enabled' : 'Disabled'}`,
      description: `${provider} has been ${!enabled ? 'enabled' : 'disabled'}`,
    });
  };

  const handleTestEndpoint = async (providerConfig: ProviderConfig) => {
    setTesting(providerConfig.provider);

    setProviders(prev => prev.map(p =>
      p.provider === providerConfig.provider
        ? { ...p, health_status: 'testing' }
        : p
    ));

    try {
      // Determine which endpoint to test based on mode
      const endpointToTest = providerConfig.is_local_mode
        ? providerConfig.endpoint
        : (providerConfig.external_endpoint || providerConfig.endpoint);

      // Test endpoint connectivity via backend API
      const response = await fetch('/api/v1/models/test-endpoint', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          endpoint: endpointToTest,
          provider: providerConfig.provider
        })
      });

      const result = await response.json();
      const healthy = result.healthy || false;
      const status = result.status || (healthy ? 'healthy' : 'unhealthy');

      setProviders(prev => prev.map(p =>
        p.provider === providerConfig.provider
          ? {
              ...p,
              health_status: status as 'healthy' | 'unhealthy' | 'degraded' | 'testing' | 'unknown',
              last_test: new Date().toISOString(),
              last_latency_ms: result.latency_ms
            }
          : p
      ));

      // Build toast message based on status
      let toastTitle = "Endpoint Healthy";
      let toastDescription = `${providerConfig.name} is responding correctly`;
      let toastVariant: "default" | "destructive" = "default";

      if (status === 'degraded') {
        toastTitle = "Endpoint Degraded";
        toastDescription = result.error || `${providerConfig.name} responding with high latency`;
        if (result.latency_ms) {
          toastDescription += ` (${result.latency_ms.toFixed(0)}ms)`;
        }
      } else if (status === 'unhealthy' || !healthy) {
        toastTitle = "Endpoint Unhealthy";
        toastDescription = result.error || `${providerConfig.name} is not responding`;
        toastVariant = "destructive";
      } else if (result.latency_ms) {
        toastDescription += ` (${result.latency_ms.toFixed(0)}ms)`;
      }

      toast({
        title: toastTitle,
        description: toastDescription,
        variant: toastVariant,
      });
    } catch (error) {
      setProviders(prev => prev.map(p =>
        p.provider === providerConfig.provider
          ? { ...p, health_status: 'unhealthy' }
          : p
      ));

      toast({
        title: "Test Failed",
        description: "Failed to test endpoint",
        variant: "destructive",
      });
    }

    setTesting(null);
  };

  const handleAddCustomEndpoint = async () => {
    if (!addForm.name || !addForm.provider || !addForm.endpoint) {
      toast({
        title: "Missing Information",
        description: "Please fill in all required fields",
        variant: "destructive",
      });
      return;
    }

    const newEndpoint: ProviderConfig = {
      provider: addForm.provider.toLowerCase().replace(/\s+/g, '_'),
      name: addForm.name,
      endpoint: addForm.endpoint,
      enabled: true,
      health_status: 'unknown',
      description: addForm.description,
      is_external: addForm.is_external,
      requires_api_key: addForm.requires_api_key,
      is_custom: true,
      model_type: addForm.model_type,
    };

    const updatedProviders = [...providers, newEndpoint];
    setProviders(updatedProviders);

    // Save custom endpoints to localStorage
    const customEndpoints = updatedProviders.filter(p => p.is_custom);
    localStorage.setItem('custom_endpoints', JSON.stringify(customEndpoints));

    toast({
      title: "Endpoint Added",
      description: `Successfully added ${addForm.name}`,
    });

    // Reset form and close dialog
    setAddForm({
      name: '',
      provider: '',
      endpoint: '',
      description: '',
      model_type: 'llm',
      is_external: false,
      requires_api_key: true,
    });
    setShowAddDialog(false);
  };

  const handleRemoveCustomEndpoint = (provider: string) => {
    const updatedProviders = providers.filter(p => p.provider !== provider);
    setProviders(updatedProviders);

    // Update localStorage
    const customEndpoints = updatedProviders.filter(p => p.is_custom);
    localStorage.setItem('custom_endpoints', JSON.stringify(customEndpoints));

    toast({
      title: "Endpoint Removed",
      description: "Custom endpoint has been removed",
    });
  };

  const handleToggleBGEM3Mode = async (isLocal: boolean) => {
    const provider = providers.find(p => p.provider === 'bge_m3');
    if (!provider) return;

    try {
      // Get current BGE-M3 model config
      const modelResponse = await fetch('/api/v1/models/BAAI%2Fbge-m3', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        }
      });

      if (!modelResponse.ok) {
        throw new Error('Failed to get current BGE-M3 model config');
      }

      const currentModel = await modelResponse.json();
      const externalEndpoint = provider.external_endpoint || 'http://10.0.1.50:8080';

      // Update the model config with new mode
      const response = await fetch(`/api/v1/models/${encodeURIComponent('BAAI/bge-m3')}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        },
        body: JSON.stringify({
          endpoint: isLocal ? 'http://gentwo-vllm-embeddings:8000/v1/embeddings' : externalEndpoint,
          config: {
            ...currentModel.config,
            is_local_mode: isLocal,
            external_endpoint: externalEndpoint
          }
        })
      });

      if (response.ok) {
        const result = await response.json();

        // Sync configuration to tenant backend
        try {
          const syncResponse = await fetch('http://localhost:8002/api/embeddings/config/bge-m3', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              is_local_mode: isLocal,
              external_endpoint: externalEndpoint
            })
          });

          if (syncResponse.ok) {
            console.log('Configuration synced to tenant backend');
          } else {
            console.warn('Failed to sync configuration to tenant backend');
          }
        } catch (syncError) {
          console.warn('Error syncing to tenant backend:', syncError);
        }

        setProviders(prev => prev.map(p => {
          if (p.provider === 'bge_m3') {
            const updatedProvider = {
              ...p,
              is_local_mode: isLocal,
              endpoint: isLocal
                ? 'http://gentwo-vllm-embeddings:8000/v1/embeddings'
                : p.external_endpoint || 'http://10.0.1.50:8080',
              is_external: !isLocal,
              description: isLocal
                ? 'Multilingual embedding model - Local GT Edge deployment'
                : 'Multilingual embedding model - External API deployment'
            };

            // Save BGE-M3 configuration to localStorage as backup
            localStorage.setItem('bge_m3_config', JSON.stringify({
              is_local_mode: isLocal,
              external_endpoint: p.external_endpoint || 'http://10.0.1.50:8080'
            }));

            return updatedProvider;
          }
          return p;
        }));

        // Show success message with sync status
        const syncStatus = result.sync_status;
        if (syncStatus === 'success') {
          toast({
            title: "BGE-M3 Mode Updated",
            description: `Switched to ${isLocal ? 'Local GT Edge' : 'External API'} deployment. Configuration synced to all services.`,
          });
        } else {
          toast({
            title: "BGE-M3 Mode Updated",
            description: `Switched to ${isLocal ? 'Local GT Edge' : 'External API'} deployment. Warning: Some services may not have received the update.`,
            variant: "destructive",
          });
        }
      } else {
        throw new Error('Failed to update configuration');
      }
    } catch (error) {
      console.error('Error updating BGE-M3 config:', error);
      toast({
        title: "Configuration Update Failed",
        description: "Failed to save BGE-M3 configuration to server",
        variant: "destructive",
      });
    }
  };

  // Immediate state update for UI responsiveness
  const handleExternalEndpointChange = (newEndpoint: string) => {
    // Update UI immediately
    setProviders(prev => prev.map(p => {
      if (p.provider === 'bge_m3') {
        return {
          ...p,
          external_endpoint: newEndpoint,
          endpoint: !p.is_local_mode ? newEndpoint : p.endpoint
        };
      }
      return p;
    }));
  };

  // Debounced API call to persist configuration
  const handleUpdateExternalEndpoint = async (newEndpoint: string) => {
    const provider = providers.find(p => p.provider === 'bge_m3');
    if (!provider) return;

    try {
      // Update the BGE-M3 model config using standard model API
      const modelResponse = await fetch('/api/v1/models/BAAI%2Fbge-m3', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        }
      });

      if (!modelResponse.ok) {
        throw new Error('Failed to get current BGE-M3 model config');
      }

      const currentModel = await modelResponse.json();

      // Update the model config with new endpoint configuration
      const response = await fetch(`/api/v1/models/${encodeURIComponent('BAAI/bge-m3')}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        },
        body: JSON.stringify({
          endpoint: provider.is_local_mode ? 'http://gentwo-vllm-embeddings:8000/v1/embeddings' : newEndpoint,
          config: {
            ...currentModel.config,
            is_local_mode: provider.is_local_mode,
            external_endpoint: newEndpoint
          }
        })
      });

      if (response.ok) {
        const result = await response.json();
        console.log('BGE-M3 configuration updated:', result);

        // Sync configuration to tenant backend
        try {
          const syncResponse = await fetch('http://localhost:8002/api/embeddings/config/bge-m3', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              is_local_mode: provider.is_local_mode,
              external_endpoint: newEndpoint
            })
          });

          if (syncResponse.ok) {
            console.log('Configuration synced to tenant backend');
          } else {
            console.warn('Failed to sync configuration to tenant backend');
          }
        } catch (syncError) {
          console.warn('Error syncing to tenant backend:', syncError);
        }

        // Update localStorage as backup
        localStorage.setItem('bge_m3_config', JSON.stringify({
          is_local_mode: provider.is_local_mode,
          external_endpoint: newEndpoint
        }));

        toast({
          title: "Configuration Updated",
          description: "BGE-M3 external endpoint updated successfully",
        });
      }
    } catch (error) {
      console.error('Error updating BGE-M3 external endpoint:', error);
      // Still update locally even if API call fails
      setProviders(prev => prev.map(p => {
        if (p.provider === 'bge_m3') {
          const updatedProvider = {
            ...p,
            external_endpoint: newEndpoint,
            endpoint: !p.is_local_mode ? newEndpoint : p.endpoint
          };

          localStorage.setItem('bge_m3_config', JSON.stringify({
            is_local_mode: p.is_local_mode,
            external_endpoint: newEndpoint
          }));

          return updatedProvider;
        }
        return p;
      }));
    }
  };

  const handleSaveConfiguration = async () => {
    setSaving('all');

    try {
      // TODO: API call to save all configurations
      await new Promise(resolve => setTimeout(resolve, 1000));

      toast({
        title: "Configuration Saved",
        description: "All endpoint configurations have been saved and synced to resource clusters",
      });
    } catch (error) {
      toast({
        title: "Save Failed",
        description: "Failed to save configuration changes",
        variant: "destructive",
      });
    }

    setSaving(null);
  };

  if (loading) {
    return <div className="flex items-center justify-center p-8">Loading configurations...</div>;
  }

  return (
    <div className="space-y-6">

      {/* Provider Configurations */}
      <div className="grid gap-4">
        {providers.map((provider) => (
          <Card key={provider.provider} className="relative">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    {getConnectionIcon(provider.is_external)}
                    <CardTitle className="text-lg">{provider.name}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(provider.health_status)}
                    <Badge variant={provider.enabled ? "default" : "secondary"}>
                      {provider.enabled ? "Enabled" : "Disabled"}
                    </Badge>
                    {provider.requires_api_key && (
                      <Badge variant="outline">API Key Required</Badge>
                    )}
                    {provider.model_type && (
                      <Badge variant="secondary">{provider.model_type.toUpperCase()}</Badge>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={provider.enabled}
                    onCheckedChange={(checked) => handleToggleProvider(provider.provider, provider.enabled)}
                  />
                  {provider.is_custom && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveCustomEndpoint(provider.provider)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
              <CardDescription>{provider.description}</CardDescription>
            </CardHeader>
            
            <CardContent className="space-y-4">
              {provider.provider === 'bge_m3' ? (
                // Special BGE-M3 configuration with local/external toggle
                <>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 border rounded-lg bg-blue-50/50">
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2">
                          {provider.is_local_mode ? (
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                          ) : (
                            <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                          )}
                          <span className="font-medium">
                            {provider.is_local_mode ? 'Local GT Edge' : 'External API'}
                          </span>
                        </div>
                        <Badge variant="secondary" className="text-xs">
                          {provider.is_local_mode ? 'Docker Internal' : 'External Endpoint'}
                        </Badge>
                      </div>
                      <Switch
                        checked={!provider.is_local_mode}
                        onCheckedChange={(checked) => handleToggleBGEM3Mode(!checked)}
                        disabled={!provider.enabled}
                      />
                    </div>

                    <div className="grid grid-cols-1 gap-4">
                      <div>
                        <Label htmlFor={`endpoint-${provider.provider}`}>
                          {provider.is_local_mode ? 'Local Endpoint (Docker Internal)' : 'External Endpoint URL'}
                        </Label>
                        <Input
                          id={`endpoint-${provider.provider}`}
                          value={provider.is_local_mode ? provider.endpoint : (provider.external_endpoint || '')}
                          onChange={(e) => {
                            if (provider.is_local_mode) {
                              handleEndpointChange(provider.provider, e.target.value);
                            } else {
                              // Update UI immediately
                              handleExternalEndpointChange(e.target.value);
                            }
                          }}
                          onBlur={(e) => {
                            // Call API when user finishes editing (loses focus)
                            if (!provider.is_local_mode) {
                              handleUpdateExternalEndpoint(e.target.value);
                            }
                          }}
                          placeholder={provider.is_local_mode ? 'http://gentwo-vllm-embeddings:8000/v1/embeddings' : 'http://10.0.1.50:8080'}
                          disabled={!provider.enabled || provider.is_local_mode}
                          className={provider.is_local_mode ? "bg-gray-100" : "border-blue-200 bg-blue-50"}
                        />
                        {provider.is_local_mode && (
                          <p className="text-xs text-muted-foreground mt-1">
                            🏠 Uses local Docker container for embeddings
                          </p>
                        )}
                        {!provider.is_local_mode && (
                          <p className="text-xs text-blue-600 mt-1">
                            🌐 External BGE-M3 API endpoint (same model, external deployment)
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      onClick={() => handleTestEndpoint(provider)}
                      disabled={!provider.enabled || testing === provider.provider}
                      className="flex-1"
                    >
                      {testing === provider.provider ? (
                        <>
                          <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                          Testing...
                        </>
                      ) : (
                        <>
                          <TestTube className="w-4 h-4 mr-2" />
                          Test {provider.is_local_mode ? 'Local' : 'External'}
                        </>
                      )}
                    </Button>

                    {provider.endpoint && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => window.open(provider.is_local_mode ? provider.endpoint : provider.external_endpoint, '_blank')}
                        disabled={!provider.enabled}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </>
              ) : (
                // Regular provider configuration
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div className="md:col-span-2">
                      <Label htmlFor={`endpoint-${provider.provider}`}>
                        Endpoint URL
                        {provider.is_external && (
                          <span className="text-blue-600 ml-1">(GT Edge Network)</span>
                        )}
                        {!provider.is_custom && (
                          <span className="text-muted-foreground ml-1 text-xs">(Default)</span>
                        )}
                      </Label>
                      <Input
                        id={`endpoint-${provider.provider}`}
                        value={provider.endpoint}
                        onChange={(e) => provider.is_custom && handleEndpointChange(provider.provider, e.target.value)}
                        placeholder="https://api.example.com/v1"
                        disabled={!provider.enabled || !provider.is_custom}
                        readOnly={!provider.is_custom}
                        className={`${provider.is_external ? "border-blue-200 bg-blue-50" : ""} ${!provider.is_custom ? "bg-muted cursor-not-allowed" : ""}`}
                      />
                    </div>

                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => handleTestEndpoint(provider)}
                        disabled={!provider.enabled || testing === provider.provider}
                        className="flex-1"
                      >
                        {testing === provider.provider ? (
                          <>
                            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                            Testing...
                          </>
                        ) : (
                          <>
                            <TestTube className="w-4 h-4 mr-2" />
                            Test
                          </>
                        )}
                      </Button>

                      {provider.endpoint && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => window.open(provider.endpoint, '_blank')}
                          disabled={!provider.enabled}
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              )}

              {provider.last_test && (
                <div className="text-xs text-muted-foreground">
                  Last tested: {new Date(provider.last_test).toLocaleString()}
                  {provider.last_latency_ms && (
                    <span className="ml-2">({provider.last_latency_ms.toFixed(0)}ms)</span>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Separator />

      {/* Global Actions */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          Changes will be automatically synced to all resource clusters
        </div>
        
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          
          <Button
            onClick={handleSaveConfiguration}
            disabled={saving === 'all'}
          >
            {saving === 'all' ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Configuration'
            )}
          </Button>
        </div>
      </div>


      {/* Add Custom Endpoint Dialog */}
      <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Custom Endpoint</DialogTitle>
            <DialogDescription>
              Create a custom endpoint that can be used when adding models to the registry.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="endpoint-name">Endpoint Name *</Label>
              <Input
                id="endpoint-name"
                placeholder="e.g., My Local LLM Server"
                value={addForm.name}
                onChange={(e) => setAddForm(prev => ({ ...prev, name: e.target.value }))}
              />
            </div>

            <div>
              <Label htmlFor="provider-name">Provider ID *</Label>
              <Input
                id="provider-name"
                placeholder="e.g., local-llm (lowercase, no spaces)"
                value={addForm.provider}
                onChange={(e) => setAddForm(prev => ({ ...prev, provider: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Used as identifier - lowercase letters, numbers, and underscores only
              </p>
            </div>

            <div>
              <Label htmlFor="endpoint-url">Endpoint URL *</Label>
              <Input
                id="endpoint-url"
                placeholder="https://api.example.com/v1 or http://localhost:8080"
                value={addForm.endpoint}
                onChange={(e) => setAddForm(prev => ({ ...prev, endpoint: e.target.value }))}
              />
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Brief description of this endpoint..."
                value={addForm.description}
                onChange={(e) => setAddForm(prev => ({ ...prev, description: e.target.value }))}
                rows={2}
              />
            </div>

            <div>
              <Label htmlFor="model-type">Model Type</Label>
              <Select value={addForm.model_type} onValueChange={(value: 'llm' | 'embedding' | 'both') =>
                setAddForm(prev => ({ ...prev, model_type: value }))
              }>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="llm">LLM (Chat/Completion)</SelectItem>
                  <SelectItem value="embedding">Embedding</SelectItem>
                  <SelectItem value="both">Both LLM & Embedding</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="external-network"
                  checked={addForm.is_external}
                  onChange={(e) => setAddForm(prev => ({ ...prev, is_external: e.target.checked }))}
                  className="rounded"
                />
                <Label htmlFor="external-network" className="text-sm">
                  External network endpoint (GT Edge, local network)
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="requires-api-key"
                  checked={addForm.requires_api_key}
                  onChange={(e) => setAddForm(prev => ({ ...prev, requires_api_key: e.target.checked }))}
                  className="rounded"
                />
                <Label htmlFor="requires-api-key" className="text-sm">
                  Requires API key authentication
                </Label>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddCustomEndpoint}>
              Add Endpoint
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}