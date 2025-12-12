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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/components/ui/use-toast';
import {
  Cpu,
  TestTube,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  ExternalLink,
  Users,
  Info
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

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

interface AddModelDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onModelAdded?: () => void;
}

export default function AddModelDialog({ open, onOpenChange, onModelAdded }: AddModelDialogProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    status?: 'healthy' | 'degraded' | 'unhealthy';
    message: string;
    latency_ms?: number;
    error_type?: string;
  } | null>(null);
  const [customEndpoints, setCustomEndpoints] = useState<CustomEndpoint[]>([]);

  const [formData, setFormData] = useState({
    model_id: '',
    name: '',
    provider: '', // No default provider
    model_type: '',
    endpoint: '', // No default endpoint
    description: '',
    context_window: '',
    max_tokens: '',
    dimensions: '', // For embedding models
  });

  const { toast } = useToast();

  // Load custom endpoints from localStorage
  useEffect(() => {
    const loadCustomEndpoints = () => {
      try {
        const stored = localStorage.getItem('custom_endpoints');
        console.log('Raw stored endpoints from localStorage:', stored);
        if (stored) {
          const parsed = JSON.parse(stored);
          console.log('Parsed custom endpoints:', parsed);
          setCustomEndpoints(parsed);
        } else {
          console.log('No custom endpoints found in localStorage');
        }
      } catch (error) {
        console.error('Failed to load custom endpoints:', error);
      }
    };

    if (open) {
      loadCustomEndpoints();
    }
  }, [open]);

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

  const handleInputChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
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
      // Test endpoint connectivity via backend API
      const response = await fetch('/api/v1/models/test-endpoint', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          endpoint: formData.endpoint,
          provider: formData.provider
        })
      });

      const result = await response.json();

      // Build message based on status
      let message = result.error || "Endpoint is responding correctly";
      if (result.status === 'degraded' && !result.error) {
        message = "Endpoint responding but with high latency";
      }

      setTestResult({
        success: result.healthy || false,
        status: result.status || (result.healthy ? 'healthy' : 'unhealthy'),
        message: message,
        latency_ms: result.latency_ms,
        error_type: result.error_type
      });
    } catch (error) {
      setTestResult({
        success: false,
        status: 'unhealthy',
        message: "Connection test failed",
        error_type: 'connection_error'
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async () => {
    try {
      // Prepare submission data - resolve custom endpoint provider if needed
      const submissionData: Record<string, any> = { ...formData };

      // Check if the provider is actually a custom endpoint ID
      const customEndpoint = customEndpoints.find(ep => ep.provider === formData.provider);
      if (customEndpoint) {
        // Use the actual provider name from the custom endpoint
        submissionData.provider = customEndpoint.provider;
      }

      // Set default status (pricing is now managed on the Billing page)
      submissionData.status = {
        is_active: true,
        is_compound: false
      };

      // Set default pricing (managed on Billing page)
      submissionData.cost_per_million_input = 0;
      submissionData.cost_per_million_output = 0;

      const apiUrl = '/api/v1/models/';
      console.log('Making API request to:', apiUrl);
      console.log('Submission data:', submissionData);

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(submissionData)
      });
      
      console.log('Response status:', response.status);
      console.log('Response headers:', Object.fromEntries(response.headers.entries()));
      
      if (response.ok) {
        const result = await response.json();
        console.log('Success response:', result);
        
        toast({
          title: "Model Added",
          description: `Successfully added ${formData.name} to the model registry`,
        });
        
        // Reset form and close dialog
        setFormData({
          model_id: '',
          name: '',
          provider: '', // No default provider
          model_type: '',
          endpoint: '', // No default endpoint
          description: '',
          context_window: '',
          max_tokens: '',
          dimensions: '',
        });
        setTestResult(null);
        onOpenChange(false);

        // Notify parent to refresh data
        if (onModelAdded) {
          onModelAdded();
        }
      } else {
        const errorData = await response.text();
        console.error('API error response:', errorData);
        
        toast({
          title: "Failed to Add Model",
          description: `Server returned ${response.status}: ${errorData.substring(0, 100)}`,
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Network error:', error);
      
      toast({
        title: "Network Error",
        description: error instanceof Error ? error.message : "Could not connect to server",
        variant: "destructive",
      });
    }
  };


  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Cpu className="w-5 h-5" />
            Add New Model
          </DialogTitle>
          <DialogDescription>
            Add a new AI model to the GT 2.0 registry. This will make it available across all clusters.
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
                    placeholder="llama-3.3-70b-versatile"
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
                      <SelectItem key="ollama-dgx-x86" value="ollama-dgx-x86">Local Ollama (Ubuntu x86 / DGX ARM)</SelectItem>
                      <SelectItem key="ollama-macos" value="ollama-macos">Local Ollama (macOS Apple Silicon)</SelectItem>
                      <SelectItem key="groq" value="groq">Groq (api.groq.com)</SelectItem>
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
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="llm">Language Model (LLM)</SelectItem>
                      <SelectItem value="embedding">Embedding Model</SelectItem>
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
                    placeholder={
                      formData.provider === 'groq'
                        ? "https://api.groq.com/openai/v1/chat/completions"
                        : "http://localhost:8000/v1/chat/completions"
                    }
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
                            <strong>Model Type:</strong> Select <code className="bg-orange-100 px-1 rounded">LLM</code> for chat models (most common for AI agents)
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
                            <strong>Model Type:</strong> Select <code className="bg-green-100 px-1 rounded">LLM</code> for chat models (most common for AI agents)
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
                          <li><strong>Model Type:</strong> Select <code className="bg-blue-100 px-1 rounded">LLM</code> for chat models (most common for AI agents)</li>
                          <li><strong>Context Window:</strong> Find on the model's Ollama page (e.g., 128K for Llama 3.2)</li>
                          <li><strong>Max Tokens:</strong> Typically 2048-4096 for responses; check model docs</li>
                        </ul>
                      </li>
                    </ol>
                  </div>
                )}

                {testResult && (
                  <div className={`flex items-center gap-2 mt-2 p-2 rounded-md text-sm ${
                    testResult.status === 'healthy' ? 'bg-green-50 text-green-700 border border-green-200' :
                    testResult.status === 'degraded' ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' :
                    'bg-red-50 text-red-700 border border-red-200'
                  }`}>
                    {testResult.status === 'healthy' && <CheckCircle className="w-4 h-4 flex-shrink-0" />}
                    {testResult.status === 'degraded' && <AlertTriangle className="w-4 h-4 flex-shrink-0" />}
                    {testResult.status === 'unhealthy' && <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                    <div className="flex-1">
                      <span>{testResult.message}</span>
                      {testResult.latency_ms && (
                        <span className="ml-2 text-xs opacity-75">({testResult.latency_ms.toFixed(0)}ms)</span>
                      )}
                    </div>
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

            {/* Tenant Access Info */}
            <Alert>
              <Users className="h-4 w-4" />
              <AlertTitle>Automatic Tenant Access</AlertTitle>
              <AlertDescription>
                This model will be automatically assigned to all tenants with default rate limits (1000 requests/minute).
                You can customize per-tenant rate limits after creation via the Edit Model dialog.
              </AlertDescription>
            </Alert>
          </div>

        <DialogFooter>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmit}>
              Add Model
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}