"use client";

import { useState, useEffect } from 'react';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';
import { 
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  MoreHorizontal,
  Edit,
  TestTube,
  Power,
  PowerOff,
  ExternalLink,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Clock,
  RotateCcw,
  Trash2,
  RefreshCw
} from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import EditModelDialog from './EditModelDialog';

interface ModelConfig {
  model_id: string;
  name: string;
  provider: string;
  model_type: string;
  endpoint: string;
  description: string | null;
  health_status: 'healthy' | 'unhealthy' | 'unknown';
  is_active: boolean;
  is_compound?: boolean;
  context_window?: number;
  max_tokens?: number;
  dimensions?: number;
  cost_per_million_input?: number;
  cost_per_million_output?: number;
  capabilities?: Record<string, any>;
  last_health_check?: string;
  created_at: string;
  specifications?: {
    context_window: number | null;
    max_tokens: number | null;
    dimensions: number | null;
  };
  cost?: {
    per_million_input: number;
    per_million_output: number;
  };
  status?: {
    is_active: boolean;
    is_compound?: boolean;
    health_status: string;
  };
}

interface ModelRegistryTableProps {
  showArchived?: boolean;
  models?: ModelConfig[];
  loading?: boolean;
  onModelUpdated?: () => void;
}

export default function ModelRegistryTable({
  showArchived = false,
  models: propModels,
  loading: propLoading,
  onModelUpdated
}: ModelRegistryTableProps) {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingEndpoint, setEditingEndpoint] = useState<{
    modelId: string;
    currentEndpoint: string;
  } | null>(null);
  const [newEndpoint, setNewEndpoint] = useState('');
  const [testingModel, setTestingModel] = useState<string | null>(null);
  const [editingModel, setEditingModel] = useState<ModelConfig | null>(null);
  const [deletingModel, setDeletingModel] = useState<string | null>(null);
  const [restoringModel, setRestoringModel] = useState<string | null>(null);
  const { toast } = useToast();

  // Fetch models from API
  // Use props if provided, otherwise fetch data
  useEffect(() => {
    if (propModels && propLoading !== undefined) {
      // Use data from props (parent is managing the data)
      setModels(propModels);
      setLoading(propLoading);
    } else {
      // Fallback: fetch data if no props provided (legacy support)
      const fetchModels = async () => {
        try {
          const response = await fetch('/api/v1/models?include_stats=true', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          });

          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const data = await response.json();

          const mappedModels: ModelConfig[] = data.map((model: any) => ({
            model_id: model.model_id,
            name: model.name,
            provider: model.provider,
            model_type: model.model_type,
            endpoint: model.endpoint,
            description: model.description,
            health_status: model.status?.health_status || 'unknown',
            is_active: model.status?.is_active || false,
            is_compound: model.status?.is_compound || false,
            context_window: model.specifications?.context_window,
            max_tokens: model.specifications?.max_tokens,
            dimensions: model.specifications?.dimensions,
            cost_per_million_input: model.cost?.per_million_input || 0,
            cost_per_million_output: model.cost?.per_million_output || 0,
            capabilities: model.capabilities || {},
            last_health_check: model.status?.last_health_check,
            created_at: model.timestamps?.created_at,
            specifications: model.specifications,
            cost: model.cost,
            status: model.status,
          }));

          const filteredModels = showArchived
            ? mappedModels.filter(model => !model.is_active)
            : mappedModels.filter(model => model.is_active);

          setModels(filteredModels);
        } catch (error) {
          console.error('Failed to fetch models:', error);
          toast({
            title: "Failed to Load Models",
            description: "Unable to fetch model configurations from the server",
            variant: "destructive",
          });
        } finally {
          setLoading(false);
        }
      };

      fetchModels();
    }
  }, [propModels, propLoading, showArchived]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'unhealthy':
        return <AlertCircle className="w-4 h-4 text-red-600" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      healthy: "default",
      unhealthy: "destructive", 
      unknown: "secondary"
    };
    
    return (
      <Badge variant={variants[status] || "secondary"} className="flex items-center gap-1">
        {getStatusIcon(status)}
        {status}
      </Badge>
    );
  };

  const getProviderBadge = (provider: string) => {
    const colors: Record<string, string> = {
      groq: "bg-purple-100 text-purple-800",
      external: "bg-blue-100 text-blue-800",
      openai: "bg-green-100 text-green-800",
      anthropic: "bg-orange-100 text-orange-800"
    };
    
    return (
      <Badge className={colors[provider] || "bg-gray-100 text-gray-800"}>
        {provider}
      </Badge>
    );
  };

  const getModelTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      llm: "bg-indigo-100 text-indigo-800",
      embedding: "bg-cyan-100 text-cyan-800",
      audio: "bg-pink-100 text-pink-800",
      tts: "bg-yellow-100 text-yellow-800"
    };
    
    return (
      <Badge className={colors[type] || "bg-gray-100 text-gray-800"}>
        {type}
      </Badge>
    );
  };

  const handleEditEndpoint = (modelId: string, currentEndpoint: string) => {
    setEditingEndpoint({ modelId, currentEndpoint });
    setNewEndpoint(currentEndpoint);
  };

  const handleSaveEndpoint = async () => {
    if (!editingEndpoint) return;
    
    try {
      const response = await fetch(`/api/v1/models/${encodeURIComponent(editingEndpoint.modelId)}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ endpoint: newEndpoint })
      });
      
      if (response.ok) {
        setModels(models.map(model => 
          model.model_id === editingEndpoint.modelId 
            ? { ...model, endpoint: newEndpoint }
            : model
        ));
        
        toast({
          title: "Endpoint Updated",
          description: `Successfully updated endpoint for ${editingEndpoint.modelId}`,
        });
      }
    } catch (error) {
      toast({
        title: "Update Failed",
        description: "Failed to update model endpoint",
        variant: "destructive",
      });
    }
    
    setEditingEndpoint(null);
  };

  const handleTestModel = async (modelId: string) => {
    setTestingModel(modelId);
    
    try {
      const response = await fetch(`/api/v1/models/${encodeURIComponent(modelId)}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        }
      });
      
      const result = await response.json();
      
      toast({
        title: result.healthy ? "Model Healthy" : "Model Unhealthy",
        description: result.error || "Model endpoint is responding correctly",
        variant: result.healthy ? "default" : "destructive",
      });
      
      // Update model status
      setModels(models.map(model => 
        model.model_id === modelId 
          ? { 
              ...model, 
              health_status: result.healthy ? 'healthy' : 'unhealthy',
              last_health_check: new Date().toISOString()
            }
          : model
      ));
    } catch (error) {
      toast({
        title: "Test Failed",
        description: "Failed to test model endpoint",
        variant: "destructive",
      });
    }
    
    setTestingModel(null);
  };

  const handleToggleModel = async (modelId: string, isActive: boolean) => {
    try {
      const response = await fetch(`/api/v1/models/${encodeURIComponent(modelId)}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          status: { is_active: !isActive }
        })
      });
      
      if (response.ok) {
        setModels(models.map(model => 
          model.model_id === modelId 
            ? { ...model, is_active: !isActive }
            : model
        ));
        
        toast({
          title: isActive ? "Model Disabled" : "Model Enabled",
          description: `Successfully ${isActive ? 'disabled' : 'enabled'} ${modelId}`,
        });
      }
    } catch (error) {
      toast({
        title: "Toggle Failed",
        description: "Failed to toggle model status",
        variant: "destructive",
      });
    }
  };

  const handleEditModel = (model: ModelConfig) => {
    setEditingModel(model);
  };


  const handleRestoreModel = async (modelId: string) => {
    setRestoringModel(modelId);
  };

  const confirmRestoreModel = async () => {
    if (!restoringModel) return;
    
    try {
      const response = await fetch(`/api/v1/models/${encodeURIComponent(restoringModel)}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          status: { is_active: true }
        })
      });
      
      if (response.ok) {
        // Remove from archived models list
        setModels(models.filter(model => model.model_id !== restoringModel));
        
        toast({
          title: "Model Restored",
          description: `Successfully restored ${restoringModel}. It's now available in the active models.`,
        });
      } else {
        const errorText = await response.text();
        console.error('Restore API error:', response.status, errorText);
        toast({
          title: "Restore Failed",
          description: `Server returned ${response.status}: ${errorText.substring(0, 100)}`,
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Restore network error:', error);
      toast({
        title: "Restore Failed",
        description: error instanceof Error ? error.message : "Network error occurred",
        variant: "destructive",
      });
    }
    
    setRestoringModel(null);
  };

  const handleDeleteModel = async (modelId: string) => {
    setDeletingModel(modelId);
  };

  const confirmDeleteModel = async () => {
    if (!deletingModel) return;

    try {
      const response = await fetch(`/api/v1/models/${encodeURIComponent(deletingModel)}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        // Remove from models list
        setModels(models.filter(model => model.model_id !== deletingModel));

        if (onModelUpdated) {
          onModelUpdated();
        }

        toast({
          title: "Model Deleted",
          description: `Successfully deleted ${deletingModel}. This action cannot be undone.`,
        });
      } else {
        const errorText = await response.text();
        console.error('Delete API error:', response.status, errorText);
        toast({
          title: "Delete Failed",
          description: `Server returned ${response.status}: ${errorText.substring(0, 100)}`,
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Delete network error:', error);
      toast({
        title: "Delete Failed",
        description: error instanceof Error ? error.message : "Network error occurred",
        variant: "destructive",
      });
    }

    setDeletingModel(null);
  };

  const handleModelUpdated = () => {
    // Refetch models after successful update
    const fetchModels = async () => {
      try {
        const response = await fetch('/api/v1/models?include_stats=true', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
            'Content-Type': 'application/json',
          },
        });
        
        if (response.ok) {
          const data = await response.json();
          const mappedModels: ModelConfig[] = data.map((model: any) => ({
            model_id: model.model_id,
            name: model.name,
            provider: model.provider,
            model_type: model.model_type,
            endpoint: model.endpoint,
            description: model.description,
            health_status: model.status?.health_status || 'unknown',
            is_active: model.status?.is_active || false,
            is_compound: model.status?.is_compound || false,
            context_window: model.specifications?.context_window,
            max_tokens: model.specifications?.max_tokens,
            dimensions: model.specifications?.dimensions,
            cost_per_million_input: model.cost?.per_million_input || 0,
            cost_per_million_output: model.cost?.per_million_output || 0,
            capabilities: model.capabilities || {},
            last_health_check: model.status?.last_health_check,
            created_at: model.timestamps?.created_at,
            specifications: model.specifications,
            cost: model.cost,
            status: model.status,
          }));
          setModels(mappedModels);
        }
      } catch (error) {
        console.error('Failed to refetch models:', error);
      }
    };
    
    fetchModels();
  };

  if (loading) {
    return <div className="flex items-center justify-center p-8">Loading models...</div>;
  }

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model ID</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Endpoint</TableHead>
              <TableHead>Context Window</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {models.map((model) => (
              <TableRow key={model.model_id}>
                <TableCell className="font-medium">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      {model.name || model.model_id}
                      {!model.is_active && <PowerOff className="w-4 h-4 text-gray-400" />}
                    </div>
                    {model.name && (
                      <div className="text-xs text-gray-500 mt-1">
                        {model.model_id}
                      </div>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {getProviderBadge(model.provider)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {getModelTypeBadge(model.model_type)}
                    {model.is_compound && (
                      <Badge variant="outline" className="text-blue-600 border-blue-300 text-xs">Compound</Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="max-w-xs">
                  <div className="flex items-center gap-2">
                    <code className="text-xs bg-gray-100 px-2 py-1 rounded truncate">
                      {model.endpoint}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEditEndpoint(model.model_id, model.endpoint)}
                    >
                      <Edit className="w-3 h-3" />
                    </Button>
                  </div>
                </TableCell>
                <TableCell>
                  {model.context_window?.toLocaleString() || 'N/A'}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" className="h-8 w-8 p-0">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => handleEditModel(model)}
                      >
                        <Edit className="mr-2 h-4 w-4" />
                        Edit Model
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => handleToggleModel(model.model_id, model.is_active)}
                      >
                        {model.is_active ? (
                          <>
                            <PowerOff className="mr-2 h-4 w-4" />
                            Disable
                          </>
                        ) : (
                          <>
                            <Power className="mr-2 h-4 w-4" />
                            Enable
                          </>
                        )}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => window.open(model.endpoint, '_blank')}
                      >
                        <ExternalLink className="mr-2 h-4 w-4" />
                        Open Endpoint
                      </DropdownMenuItem>
                      {showArchived ? (
                        <DropdownMenuItem
                          onClick={() => handleRestoreModel(model.model_id)}
                          className="text-green-600 focus:text-green-600"
                        >
                          <RotateCcw className="mr-2 h-4 w-4" />
                          Restore Model
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onClick={() => handleDeleteModel(model.model_id)}
                          className="text-red-600 focus:text-red-600"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete Model
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Edit Endpoint Dialog */}
      <Dialog open={!!editingEndpoint} onOpenChange={() => setEditingEndpoint(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Model Endpoint</DialogTitle>
            <DialogDescription>
              Update the endpoint URL for {editingEndpoint?.modelId}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="endpoint">Endpoint URL</Label>
            <Input
              id="endpoint"
              value={newEndpoint}
              onChange={(e) => setNewEndpoint(e.target.value)}
              placeholder="https://api.example.com/v1"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingEndpoint(null)}>
              Cancel
            </Button>
            <Button onClick={handleSaveEndpoint}>
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Model Dialog */}
      <EditModelDialog
        open={!!editingModel}
        onOpenChange={(open) => !open && setEditingModel(null)}
        model={editingModel}
        onModelUpdated={handleModelUpdated}
      />

      {/* Restore Confirmation Dialog */}
      <Dialog open={!!restoringModel} onOpenChange={() => setRestoringModel(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Restore Model</DialogTitle>
            <DialogDescription>
              Are you sure you want to restore the model "{restoringModel}"? It will be moved back to the active models section.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setRestoringModel(null)}>
              Cancel
            </Button>
            <Button className="bg-green-600 hover:bg-green-700 text-white" onClick={confirmRestoreModel}>
              Restore Model
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingModel} onOpenChange={() => setDeletingModel(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Model</DialogTitle>
            <DialogDescription>
              Are you sure you want to permanently delete the model "{deletingModel}"? This action cannot be undone and will remove the model from all systems.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setDeletingModel(null)}>
              Cancel
            </Button>
            <Button className="bg-red-600 hover:bg-red-700 text-white" onClick={confirmDeleteModel}>
              Delete Model
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}