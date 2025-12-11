'use client';

import { useEffect, useState } from 'react';
import { Plus, Search, Edit, Trash2, Cpu, Loader2, TestTube2, Activity, Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { resourcesApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface Resource {
  id: number;
  uuid: string;
  name: string;
  description: string;
  resource_type: string;
  provider: string;
  model_name: string;
  health_status: string;
  is_active: boolean;
  primary_endpoint: string;
  max_requests_per_minute: number;
  cost_per_1k_tokens: number;
  created_at: string;
  updated_at: string;
}

const RESOURCE_TYPES = [
  { value: 'llm', label: 'Language Model' },
  { value: 'embedding', label: 'Embedding Model' },
  { value: 'vector_database', label: 'Vector Database' },
  { value: 'document_processor', label: 'Document Processor' },
  { value: 'agentic_workflow', label: 'Agent Workflow' },
  { value: 'external_service', label: 'External Service' },
];

const PROVIDERS = [
  { value: 'groq', label: 'Groq' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'cohere', label: 'Cohere' },
  { value: 'local', label: 'Local' },
  { value: 'custom', label: 'Custom' },
];

export default function ResourcesPage() {
  const [resources, setResources] = useState<Resource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedProvider, setSelectedProvider] = useState<string>('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isTesting, setIsTesting] = useState<number | null>(null);
  
  // Form fields
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    resource_type: 'llm',
    provider: 'groq',
    model_name: '',
    primary_endpoint: '',
    max_requests_per_minute: 60,
    cost_per_1k_tokens: 0
  });

  useEffect(() => {
    fetchResources();
  }, []);

  const fetchResources = async () => {
    try {
      setIsLoading(true);
      
      // Add timeout to prevent infinite loading
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      const response = await resourcesApi.list(1, 100);
      clearTimeout(timeoutId);
      
      setResources(response.data?.resources || response.data?.data?.resources || []);
      
    } catch (error) {
      console.error('Failed to fetch resources:', error);
      
      // No fallback mock data - follow GT 2.0 "No Mocks" principle
      setResources([]);
      
      if (error instanceof Error && error.name === 'AbortError') {
        toast.error('Request timed out - please try again');
      } else {
        toast.error('Failed to load resources - please check your connection');
      }
      
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.name || !formData.resource_type) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      setIsCreating(true);
      await resourcesApi.create({
        ...formData,
        api_endpoints: formData.primary_endpoint ? [formData.primary_endpoint] : [],
        failover_endpoints: [],
        configuration: {}
      });
      toast.success('Resource created successfully');
      setShowCreateDialog(false);
      setFormData({
        name: '',
        description: '',
        resource_type: 'llm',
        provider: 'groq',
        model_name: '',
        primary_endpoint: '',
        max_requests_per_minute: 60,
        cost_per_1k_tokens: 0
      });
      fetchResources();
    } catch (error: any) {
      console.error('Failed to create resource:', error);
      toast.error(error.response?.data?.detail || 'Failed to create resource');
    } finally {
      setIsCreating(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedResource) return;

    try {
      setIsUpdating(true);
      await resourcesApi.update(selectedResource.id, {
        name: formData.name,
        description: formData.description,
        max_requests_per_minute: formData.max_requests_per_minute,
        cost_per_1k_tokens: formData.cost_per_1k_tokens
      });
      toast.success('Resource updated successfully');
      setShowEditDialog(false);
      fetchResources();
    } catch (error: any) {
      console.error('Failed to update resource:', error);
      toast.error(error.response?.data?.detail || 'Failed to update resource');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (resource: Resource) => {
    if (!confirm(`Are you sure you want to delete ${resource.name}?`)) return;

    try {
      await resourcesApi.delete(resource.id);
      toast.success('Resource deleted successfully');
      fetchResources();
    } catch (error: any) {
      console.error('Failed to delete resource:', error);
      toast.error(error.response?.data?.detail || 'Failed to delete resource');
    }
  };

  const handleTestConnection = async (resource: Resource) => {
    try {
      setIsTesting(resource.id);
      await resourcesApi.testConnection(resource.id);
      toast.success('Connection test successful');
      fetchResources(); // Refresh to get updated health status
    } catch (error: any) {
      console.error('Failed to test connection:', error);
      toast.error(error.response?.data?.detail || 'Connection test failed');
    } finally {
      setIsTesting(null);
    }
  };

  const openEditDialog = (resource: Resource) => {
    setSelectedResource(resource);
    setFormData({
      name: resource.name,
      description: resource.description || '',
      resource_type: resource.resource_type,
      provider: resource.provider,
      model_name: resource.model_name || '',
      primary_endpoint: resource.primary_endpoint || '',
      max_requests_per_minute: resource.max_requests_per_minute,
      cost_per_1k_tokens: resource.cost_per_1k_tokens
    });
    setShowEditDialog(true);
  };

  const getHealthBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Badge variant="default" className="bg-green-600">Healthy</Badge>;
      case 'unhealthy':
        return <Badge variant="destructive">Unhealthy</Badge>;
      case 'unknown':
        return <Badge variant="secondary">Unknown</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      llm: 'bg-blue-600',
      embedding: 'bg-purple-600',
      vector_database: 'bg-orange-600',
      document_processor: 'bg-green-600',
      agentic_workflow: 'bg-indigo-600',
      external_service: 'bg-pink-600'
    };
    
    return (
      <Badge variant="default" className={colors[type] || 'bg-gray-600'}>
        {type.replace('_', ' ').toUpperCase()}
      </Badge>
    );
  };

  const filteredResources = resources.filter(resource => {
    if (searchQuery && !resource.name.toLowerCase().includes(searchQuery.toLowerCase()) && 
        !resource.model_name?.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (selectedType !== 'all' && resource.resource_type !== selectedType) {
      return false;
    }
    if (selectedProvider !== 'all' && resource.provider !== selectedProvider) {
      return false;
    }
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading resources...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">AI Resources</h1>
          <p className="text-muted-foreground">
            Manage AI models, RAG engines, and external services
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Resource
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Resources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resources.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{resources.filter(r => r.is_active).length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Healthy</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {resources.filter(r => r.health_status === 'healthy').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Unhealthy</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {resources.filter(r => r.health_status === 'unhealthy').length}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Resource Catalog</CardTitle>
            <div className="flex items-center space-x-2">
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search resources..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
                  className="pl-8 w-[250px]"
                />
              </div>
              <Select value={selectedType} onValueChange={setSelectedType}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="All Types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {RESOURCE_TYPES.map(type => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="All Providers" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Providers</SelectItem>
                  {PROVIDERS.map(provider => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {filteredResources.length === 0 ? (
            <div className="text-center py-12">
              <Cpu className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No resources found</p>
              <Button className="mt-4" onClick={() => setShowCreateDialog(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add your first resource
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Health</TableHead>
                  <TableHead>Rate Limit</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredResources.map((resource) => (
                  <TableRow key={resource.id}>
                    <TableCell className="font-medium">{resource.name}</TableCell>
                    <TableCell>{getTypeBadge(resource.resource_type)}</TableCell>
                    <TableCell className="capitalize">{resource.provider}</TableCell>
                    <TableCell>{resource.model_name || '-'}</TableCell>
                    <TableCell>{getHealthBadge(resource.health_status)}</TableCell>
                    <TableCell>{resource.max_requests_per_minute}/min</TableCell>
                    <TableCell>${resource.cost_per_1k_tokens}/1K</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end space-x-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleTestConnection(resource)}
                          disabled={isTesting === resource.id}
                          title="Test Connection"
                        >
                          {isTesting === resource.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <TestTube2 className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => openEditDialog(resource)}
                          title="Edit"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleDelete(resource)}
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add New Resource</DialogTitle>
            <DialogDescription>
              Configure a new AI resource for your platform
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Resource Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: (e as React.ChangeEvent<HTMLInputElement>).target.value })}
                  placeholder="GPT-4 Turbo"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="resource_type">Resource Type *</Label>
                <Select
                  value={formData.resource_type}
                  onValueChange={(value) => setFormData({ ...formData, resource_type: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RESOURCE_TYPES.map(type => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider *</Label>
                <Select
                  value={formData.provider}
                  onValueChange={(value) => setFormData({ ...formData, provider: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PROVIDERS.map(provider => (
                      <SelectItem key={provider.value} value={provider.value}>
                        {provider.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="model_name">Model Name</Label>
                <Input
                  id="model_name"
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: (e as React.ChangeEvent<HTMLInputElement>).target.value })}
                  placeholder="gpt-4-turbo-preview"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Describe this resource..."
                rows={3}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="primary_endpoint">API Endpoint</Label>
              <Input
                id="primary_endpoint"
                value={formData.primary_endpoint}
                onChange={(e) => setFormData({ ...formData, primary_endpoint: (e as React.ChangeEvent<HTMLInputElement>).target.value })}
                placeholder="https://api.example.com/v1"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="max_requests">Rate Limit (req/min)</Label>
                <Input
                  id="max_requests"
                  type="number"
                  value={formData.max_requests_per_minute}
                  onChange={(e) => setFormData({ ...formData, max_requests_per_minute: parseInt((e as React.ChangeEvent<HTMLInputElement>).target.value) || 60 })}
                  min="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cost">Cost per 1K tokens ($)</Label>
                <Input
                  id="cost"
                  type="number"
                  step="0.0001"
                  value={formData.cost_per_1k_tokens}
                  onChange={(e) => setFormData({ ...formData, cost_per_1k_tokens: parseFloat((e as React.ChangeEvent<HTMLInputElement>).target.value) || 0 })}
                  min="0"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={isCreating}>
              {isCreating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Resource'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Resource</DialogTitle>
            <DialogDescription>
              Update resource configuration
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Resource Name</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: (e as React.ChangeEvent<HTMLInputElement>).target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-max_requests">Rate Limit (req/min)</Label>
                <Input
                  id="edit-max_requests"
                  type="number"
                  value={formData.max_requests_per_minute}
                  onChange={(e) => setFormData({ ...formData, max_requests_per_minute: parseInt((e as React.ChangeEvent<HTMLInputElement>).target.value) || 60 })}
                  min="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-cost">Cost per 1K tokens ($)</Label>
                <Input
                  id="edit-cost"
                  type="number"
                  step="0.0001"
                  value={formData.cost_per_1k_tokens}
                  onChange={(e) => setFormData({ ...formData, cost_per_1k_tokens: parseFloat((e as React.ChangeEvent<HTMLInputElement>).target.value) || 0 })}
                  min="0"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setShowEditDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={isUpdating}>
              {isUpdating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                'Update Resource'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}