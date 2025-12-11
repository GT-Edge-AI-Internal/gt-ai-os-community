"use client";

import { useState, useEffect } from 'react';
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
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/components/ui/use-toast';
import {
  Cpu,
  TestTube,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  ExternalLink,
  Users,
  Loader2
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface CustomEndpoint {
  provider: string;
  name: string;
  endpoint: string;
  enabled: boolean;
  health_status: 'healthy' | 'unhealthy' | 'testing' | 'unknown';
  description: string;
  is_external: boolean;
  requires_api_key: boolean;
  last_test?: string;
  is_custom?: boolean;
  model_type?: 'llm' | 'embedding' | 'both';
}

interface ModelConfig {
  model_id: string;
  name: string;
  provider: string;
  model_type: string;
  endpoint: string;
  description: string | null;
  specifications: {
    context_window: number | null;
    max_tokens: number | null;
    dimensions: number | null;
  };
  cost: {
    per_million_input: number;
    per_million_output: number;
  };
  status: {
    is_active: boolean;
    is_compound?: boolean;
  };
}

interface TenantRateLimitConfig {
  id: number;
  tenant_id: number;
  tenant_name: string;
  tenant_domain: string;
  model_id: string;
  is_enabled: boolean;
  rate_limits: {
    requests_per_minute: number;
    max_tokens_per_request?: number;
    concurrent_requests?: number;
    max_cost_per_hour?: number;
  };
}

interface EditModelDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model: ModelConfig | null;
  onModelUpdated: () => void;
}

export default function EditModelDialog({
  open,
  onOpenChange,
  model,
  onModelUpdated
}: EditModelDialogProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [customEndpoints, setCustomEndpoints] = useState<CustomEndpoint[]>([]);

  // Tenant rate limits state
  const [tenantConfigs, setTenantConfigs] = useState<TenantRateLimitConfig[]>([]);
  const [loadingTenantConfigs, setLoadingTenantConfigs] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editedRateLimits, setEditedRateLimits] = useState<Record<number, { requests_per_minute: string; is_enabled: boolean }>>({});

  const [formData, setFormData] = useState({
    model_id: '',
    name: '',
    provider: '',
    model_type: '',
    endpoint: '',
    description: '',
    context_window: '',
    max_tokens: '',
    dimensions: '',
  });

  const { toast } = useToast();

  // Load custom endpoints from localStorage
  useEffect(() => {
    const loadCustomEndpoints = () => {
      try {
        const stored = localStorage.getItem('custom_endpoints');
        if (stored) {
          setCustomEndpoints(JSON.parse(stored));
        }
      } catch (error) {
        console.error('Failed to load custom endpoints:', error);
      }
    };

    if (open) {
      loadCustomEndpoints();
    }
  }, [open]);

  // Load tenant rate limit configurations when dialog opens
  useEffect(() => {
    const loadTenantConfigs = async () => {
      if (!model || !open) return;

      setLoadingTenantConfigs(true);
      try {
        const response = await fetch(`/api/v1/models/tenant-rate-limits/${encodeURIComponent(model.model_id)}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setTenantConfigs(data.tenant_configs || []);

          // Initialize edited values
          const initialEdits: Record<number, { requests_per_minute: string; is_enabled: boolean }> = {};
          (data.tenant_configs || []).forEach((config: TenantRateLimitConfig) => {
            initialEdits[config.tenant_id] = {
              requests_per_minute: config.rate_limits.requests_per_minute.toString(),
              is_enabled: config.is_enabled,
            };
          });
          setEditedRateLimits(initialEdits);
        }
      } catch (error) {
        console.error('Failed to load tenant configs:', error);
      } finally {
        setLoadingTenantConfigs(false);
      }
    };

    loadTenantConfigs();
  }, [model, open]);

  // Reset form when model changes
  useEffect(() => {
    if (model && open) {
      setFormData({
        model_id: model.model_id,
        name: model.name,
        provider: model.provider,
        model_type: model.model_type,
        endpoint: model.endpoint,
        description: model.description || '',
        context_window: model.specifications.context_window?.toString() || '',
        max_tokens: model.specifications.max_tokens?.toString() || '',
        dimensions: model.specifications.dimensions?.toString() || '',
      });
      setTestResult(null);
    }
  }, [model, open]);

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  // Handle tenant rate limit changes
  const handleTenantRateLimitChange = (tenantId: number, field: 'requests_per_minute' | 'is_enabled', value: string | boolean) => {
    setEditedRateLimits(prev => ({
      ...prev,
      [tenantId]: {
        ...prev[tenantId],
        [field]: value,
      }
    }));
  };

  // Get changed tenant rate limits
  const getChangedTenantRateLimits = () => {
    const changes: Array<{ tenantId: number; requests_per_minute: number; is_enabled: boolean }> = [];

    for (const config of tenantConfigs) {
      const edited = editedRateLimits[config.tenant_id];
      if (edited) {
        const hasChanges =
          edited.requests_per_minute !== config.rate_limits.requests_per_minute.toString() ||
          edited.is_enabled !== config.is_enabled;

        if (hasChanges) {
          changes.push({
            tenantId: config.tenant_id,
            requests_per_minute: parseInt(edited.requests_per_minute) || 1000,
            is_enabled: edited.is_enabled,
          });
        }
      }
    }

    return changes;
  };


  const handleProviderChange = (providerId: string) => {
    console.log('Provider changed to:', providerId);
    console.log('Available custom endpoints:', customEndpoints);

    // Check if this is a custom endpoint
    const customEndpoint = customEndpoints.find(ep => ep.provider === providerId);
    console.log('Found custom endpoint:', customEndpoint);

    if (customEndpoint) {
      // Selected a configured endpoint - keep the endpoint ID as provider for Select consistency
      console.log('Setting endpoint URL to:', customEndpoint.endpoint);
      setFormData(prev => ({
        ...prev,
        provider: providerId, // Use the endpoint ID to maintain Select consistency
        endpoint: customEndpoint.endpoint, // Auto-fill the configured URL
        model_type: customEndpoint.model_type || prev.model_type
      }));
    } else {
      // Selected a default provider
      setFormData(prev => {
        const updated = { ...prev, provider: providerId };

        // Auto-populate default endpoints
        switch (providerId) {
          case 'nvidia':
            updated.endpoint = 'https://integrate.api.nvidia.com/v1/chat/completions';
            break;
          case 'groq':
            updated.endpoint = 'https://api.groq.com/openai/v1/chat/completions';
            break;
          case 'ollama-dgx-x86':
            updated.endpoint = 'http://ollama-host:11434/v1/chat/completions';
            break;
          case 'ollama-macos':
            updated.endpoint = 'http://host.docker.internal:11434/v1/chat/completions';
            break;
          case 'local':
            updated.endpoint = 'http://localhost:8000/v1/chat/completions';
            break;
          default:
            updated.endpoint = '';
        }

        return updated;
      });
    }
  };

  const handleTestEndpoint = async () => {
    if (!formData.endpoint) {
      toast({
        title: "Missing Endpoint",
        description: "Please enter an endpoint URL to test",
        variant: "destructive",
      });
      return;
    }

    setTesting(true);
    setTestResult(null);

    try {
      // Test the specific model endpoint
      const response = await fetch(`/api/v1/models/${encodeURIComponent(formData.model_id)}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json',
        },
      });
      
      const result = await response.json();
      
      setTestResult({
        success: result.healthy || false,
        message: result.error || "Endpoint is responding correctly"
      });
    } catch (error) {
      setTestResult({
        success: false,
        message: "Connection test failed"
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      // Prepare submission data - use form data directly for now
      const submissionData = { ...formData };

      // Note: Pricing (cost, is_compound) is managed on the Billing page, not here
      const updateData = {
        model_id: submissionData.model_id,
        name: submissionData.name,
        provider: submissionData.provider,
        model_type: submissionData.model_type,
        endpoint: submissionData.endpoint,
        description: submissionData.description || null,
        specifications: {
          context_window: submissionData.context_window ? parseInt(submissionData.context_window) : null,
          max_tokens: submissionData.max_tokens ? parseInt(submissionData.max_tokens) : null,
          dimensions: submissionData.dimensions ? parseInt(submissionData.dimensions) : null,
        },
      };

      // Update model configuration
      const response = await fetch(`/api/v1/models/${encodeURIComponent(formData.model_id)}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData)
      });

      if (!response.ok) {
        const errorData = await response.text();
        toast({
          title: "Failed to Update Model",
          description: `Server returned ${response.status}: ${errorData.substring(0, 100)}`,
          variant: "destructive",
        });
        return;
      }

      // Save any changed tenant rate limits
      const rateLimitChanges = getChangedTenantRateLimits();
      const rateLimitErrors: string[] = [];

      for (const change of rateLimitChanges) {
        try {
          const rateLimitResponse = await fetch(
            `/api/v1/models/tenant-rate-limits/${encodeURIComponent(formData.model_id)}/${change.tenantId}`,
            {
              method: 'PATCH',
              headers: {
                'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
                'Content-Type': 'application/json',
              },
              body: JSON.stringify({
                requests_per_minute: change.requests_per_minute,
                is_enabled: change.is_enabled,
              }),
            }
          );

          if (!rateLimitResponse.ok) {
            rateLimitErrors.push(`Tenant ${change.tenantId}`);
          }
        } catch {
          rateLimitErrors.push(`Tenant ${change.tenantId}`);
        }
      }

      // Show appropriate toast
      if (rateLimitErrors.length > 0) {
        toast({
          title: "Model Updated with Warnings",
          description: `Model saved, but failed to update rate limits for: ${rateLimitErrors.join(', ')}`,
          variant: "destructive",
        });
      } else {
        toast({
          title: "Model Updated",
          description: rateLimitChanges.length > 0
            ? `Successfully updated ${formData.name} and ${rateLimitChanges.length} tenant rate limit(s)`
            : `Successfully updated ${formData.name}`,
        });
      }

      onModelUpdated();
      onOpenChange(false);
    } catch (error) {
      toast({
        title: "Network Error",
        description: error instanceof Error ? error.message : "Could not connect to server",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };


  if (!model) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Cpu className="w-5 h-5" />
            Edit Model: {model.model_id}
          </DialogTitle>
          <DialogDescription>
            Update the configuration for this model. Changes will be synced across all clusters.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Basic Information */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Basic Information</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="model_id">Model ID *</Label>
                  <Input
                    id="model_id"
                    value={formData.model_id}
                    onChange={(e) => handleInputChange('model_id', e.target.value)}
                    placeholder="e.g., gemma3, llama-3.3-70b"
                  />
                </div>
                
                <div>
                  <Label htmlFor="name">Display Name *</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => handleInputChange('name', e.target.value)}
                    placeholder="Llama 3.3 70B Versatile"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="provider">Provider *</Label>
                  <Select value={formData.provider} onValueChange={(value) => handleProviderChange(value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select provider/endpoint" />
                    </SelectTrigger>
                    <SelectContent>
                      {/* Default providers */}
                      <SelectItem key="nvidia" value="nvidia">NVIDIA NIM (build.nvidia.com)</SelectItem>
                      <SelectItem key="groq" value="groq">Groq (External API)</SelectItem>
                      <SelectItem key="ollama-dgx-x86" value="ollama-dgx-x86">Local Ollama (DGX/X86)</SelectItem>
                      <SelectItem key="ollama-macos" value="ollama-macos">Local Ollama (MacOS)</SelectItem>
                      <SelectItem key="local" value="local">Custom Endpoint</SelectItem>

                      {/* Custom configured endpoints */}
                      {customEndpoints.length > 0 && (
                        <>
                          <SelectItem key="separator" value="separator" disabled className="text-xs text-muted-foreground font-medium px-2 py-1">
                            ── Configured Endpoints ──
                          </SelectItem>
                          {customEndpoints.map((endpoint) => (
                            <SelectItem key={endpoint.provider} value={endpoint.provider}>
                              {endpoint.name} ({endpoint.provider})
                              {endpoint.model_type && (
                                <span className="ml-2 text-xs text-muted-foreground">
                                  [{endpoint.model_type}]
                                </span>
                              )}
                            </SelectItem>
                          ))}
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="model_type">Model Type *</Label>
                  <Select value={formData.model_type} onValueChange={(value) => handleInputChange('model_type', value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select model type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="llm">Language Model (LLM)</SelectItem>
                      <SelectItem value="embedding">Embedding Model</SelectItem>
                      <SelectItem value="audio">Audio Model</SelectItem>
                      <SelectItem value="tts">Text-to-Speech</SelectItem>
                      <SelectItem value="vision">Vision Model</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>


              <div>
                <Label htmlFor="endpoint">Endpoint URL *</Label>
                <div className="flex gap-2">
                  <Input
                    id="endpoint"
                    value={formData.endpoint}
                    onChange={(e) => handleInputChange('endpoint', e.target.value)}
                    placeholder="https://api.groq.com/openai/v1/chat/completions"
                    className={formData.provider === 'local' ? "border-green-200 bg-green-50" : "border-purple-200 bg-purple-50"}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleTestEndpoint}
                    disabled={!formData.endpoint || testing}
                  >
                    {testing ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <TestTube className="w-4 h-4" />
                    )}
                  </Button>
                </div>
                
                {testResult && (
                  <div className={`flex items-center gap-2 mt-2 text-sm ${testResult.success ? 'text-green-600' : 'text-red-600'}`}>
                    {testResult.success ? (
                      <CheckCircle className="w-4 h-4" />
                    ) : (
                      <AlertCircle className="w-4 h-4" />
                    )}
                    {testResult.message}
                  </div>
                )}
                {formData.provider === 'groq' && (
                  <div className="mt-2 p-3 rounded-md bg-orange-50 border border-orange-200">
                    <p className="text-sm font-medium text-orange-800 mb-2">Groq Setup Steps:</p>
                    <ol className="text-sm text-orange-700 space-y-2 list-decimal list-inside">
                      <li>
                        <a
                          href="https://console.groq.com"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline hover:text-orange-900"
                        >
                          Create a Groq account
                        </a>{' '}
                        and{' '}
                        <a
                          href="https://console.groq.com/keys"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline hover:text-orange-900"
                        >
                          generate an API key
                        </a>
                      </li>
                      <li>
                        Add your API key on the{' '}
                        <a href="/dashboard/api-keys" className="underline hover:text-orange-900">
                          API Keys page
                        </a>
                      </li>
                      <li>
                        Configure your model in the Control Panel:
                        <ul className="mt-1 ml-4 space-y-1 list-disc">
                          <li>
                            <strong>Model ID:</strong> Use the exact Groq model name (e.g.,{' '}
                            <code className="bg-orange-100 px-1 rounded">llama-3.3-70b-versatile</code>)
                          </li>
                          <li>
                            <strong>Display Name:</strong> A friendly name (e.g., "Llama 3.3 70B")
                          </li>
                          <li>
                            <strong>Context Window:</strong> Check{' '}
                            <a
                              href="https://console.groq.com/docs/models"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline hover:text-orange-900"
                            >
                              Groq docs
                            </a>{' '}
                            (e.g., 128K for Llama 3.3)
                          </li>
                          <li>
                            <strong>Max Tokens:</strong> Typically 8192; check model docs
                          </li>
                        </ul>
                      </li>
                    </ol>
                  </div>
                )}
                {formData.provider === 'nvidia' && (
                  <div className="mt-2 p-3 rounded-md bg-green-50 border border-green-200">
                    <p className="text-sm font-medium text-green-800 mb-2">NVIDIA NIM Setup Steps:</p>
                    <ol className="text-sm text-green-700 space-y-2 list-decimal list-inside">
                      <li>
                        <a
                          href="https://build.nvidia.com"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline hover:text-green-900"
                        >
                          Create an NVIDIA account
                        </a>{' '}
                        and generate an API key
                      </li>
                      <li>
                        Add your API key on the{' '}
                        <a href="/dashboard/api-keys" className="underline hover:text-green-900">
                          API Keys page
                        </a>
                      </li>
                      <li>
                        Configure your model in the Control Panel:
                        <ul className="mt-1 ml-4 space-y-1 list-disc">
                          <li>
                            <strong>Model ID:</strong> Use the NVIDIA model name (e.g.,{' '}
                            <code className="bg-green-100 px-1 rounded">meta/llama-3.1-70b-instruct</code>)
                          </li>
                          <li>
                            <strong>Display Name:</strong> A friendly name (e.g., "Llama 3.1 70B")
                          </li>
                          <li>
                            <strong>Context Window:</strong> Check the{' '}
                            <a
                              href="https://build.nvidia.com/models"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline hover:text-green-900"
                            >
                              model page
                            </a>{' '}
                            (e.g., 128K for Llama 3.1)
                          </li>
                          <li>
                            <strong>Max Tokens:</strong> Typically 4096-8192; check model docs
                          </li>
                        </ul>
                      </li>
                    </ol>
                  </div>
                )}
                {formData.provider === 'local' && (
                  <p className="text-sm text-gray-600 mt-1">
                    Set this to any OpenAI Compatible API endpoint that doesn't require API authentication.
                  </p>
                )}
                {(formData.provider === 'ollama-dgx-x86' || formData.provider === 'ollama-macos') && (
                  <div className="mt-2 p-3 rounded-md bg-blue-50 border border-blue-200">
                    <p className="text-sm font-medium text-blue-800 mb-2">Ollama Setup Steps:</p>
                    <ol className="text-sm text-blue-700 space-y-2 list-decimal list-inside">
                      <li>
                        <a
                          href="https://ollama.com/download"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline hover:text-blue-900"
                        >
                          Download and install
                        </a>{' '}
                        Ollama
                      </li>
                      <li>
                        Select and download your{' '}
                        <a
                          href="https://ollama.com/library"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline hover:text-blue-900"
                        >
                          Model
                        </a>{' '}
                        (run: <code className="bg-blue-100 px-1 rounded">ollama pull model-name</code>)
                      </li>
                      <li>
                        Configure your model in the Control Panel:
                        <ul className="mt-1 ml-4 space-y-1 list-disc">
                          <li><strong>Model ID:</strong> Use the exact Ollama name with size tag (e.g., <code className="bg-blue-100 px-1 rounded">llama3.2:3b</code>, <code className="bg-blue-100 px-1 rounded">mistral:7b</code>)</li>
                          <li><strong>Display Name:</strong> A friendly name (e.g., "Llama 3.2 3B")</li>
                          <li><strong>Context Window:</strong> Find on the model's Ollama page (e.g., 128K for Llama 3.2)</li>
                          <li><strong>Max Tokens:</strong> Typically 2048-4096 for responses; check model docs</li>
                        </ul>
                      </li>
                    </ol>
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  placeholder="Brief description of the model..."
                />
              </div>
            </div>

            <Separator />

            {/* Technical Specifications */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Technical Specifications</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="context_window">Context Window</Label>
                  <Input
                    id="context_window"
                    type="number"
                    value={formData.context_window}
                    onChange={(e) => handleInputChange('context_window', e.target.value)}
                    placeholder="128000"
                  />
                </div>
                
                <div>
                  <Label htmlFor="max_tokens">Max Output Tokens</Label>
                  <Input
                    id="max_tokens"
                    type="number"
                    value={formData.max_tokens}
                    onChange={(e) => handleInputChange('max_tokens', e.target.value)}
                    placeholder="32768"
                  />
                </div>
              </div>

              {formData.model_type === 'embedding' && (
                <div>
                  <Label htmlFor="dimensions">Embedding Dimensions</Label>
                  <Input
                    id="dimensions"
                    type="number"
                    value={formData.dimensions}
                    onChange={(e) => handleInputChange('dimensions', e.target.value)}
                    placeholder="1024"
                  />
                </div>
              )}
            </div>

            <Separator />

            {/* Tenant Rate Limits */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5" />
                <h3 className="text-lg font-medium">Tenant Rate Limits</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Configure per-tenant rate limits for this model. All tenants are automatically assigned to new models.
              </p>

              {loadingTenantConfigs ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">Loading tenant configurations...</span>
                </div>
              ) : tenantConfigs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No tenants configured for this model yet.
                </div>
              ) : (
                <div className="border rounded-md">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tenant</TableHead>
                        <TableHead>Enabled</TableHead>
                        <TableHead>Requests/Min</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {tenantConfigs.map((config) => {
                        const edited = editedRateLimits[config.tenant_id];

                        return (
                          <TableRow key={config.tenant_id}>
                            <TableCell>
                              <div>
                                <div className="font-medium">{config.tenant_name}</div>
                                <div className="text-xs text-muted-foreground">{config.tenant_domain}</div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Switch
                                checked={edited?.is_enabled ?? config.is_enabled}
                                onCheckedChange={(checked) => handleTenantRateLimitChange(config.tenant_id, 'is_enabled', checked)}
                              />
                            </TableCell>
                            <TableCell>
                              <Input
                                type="number"
                                className="w-24"
                                value={edited?.requests_per_minute ?? config.rate_limits.requests_per_minute}
                                onChange={(e) => handleTenantRateLimitChange(config.tenant_id, 'requests_per_minute', e.target.value)}
                              />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </div>
          </div>

        <DialogFooter>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Updating...
                </>
              ) : (
                'Update Model'
              )}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}