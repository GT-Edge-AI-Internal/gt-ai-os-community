"use client";

import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Cpu, Activity } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import ModelRegistryTable from '@/components/models/ModelRegistryTable';
import EndpointConfigurator from '@/components/models/EndpointConfigurator';
import AddModelDialog from '@/components/models/AddModelDialog';

interface ModelStats {
  total_models: number;
  active_models: number;
  inactive_models: number;
  providers: Record<string, number>;
}

interface ModelConfig {
  model_id: string;
  name: string;
  provider: string;
  model_type: string;
  endpoint: string;
  description: string | null;
  health_status: 'healthy' | 'unhealthy' | 'unknown';
  is_active: boolean;
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
    health_status: string;
  };
}

export default function ModelsPage() {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [activeTab, setActiveTab] = useState('registry');
  const [stats, setStats] = useState<ModelStats | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState<number>(0);
  const { toast } = useToast();

  // Cache data for 30 seconds to prevent excessive requests
  const CACHE_DURATION = 30000;

  // Fetch all data once at the top level
  useEffect(() => {
    const fetchAllData = async () => {
      // Check cache first
      const now = Date.now();
      if (models.length > 0 && now - lastFetch < CACHE_DURATION) {
        console.log('Using cached data, skipping API call');
        return;
      }

      try {
        // Fetch both stats and models in parallel
        const [statsResponse, modelsResponse] = await Promise.all([
          fetch('/api/v1/models/stats/overview', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          }),
          fetch('/api/v1/models?include_stats=true', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          })
        ]);

        if (!statsResponse.ok) {
          throw new Error(`Stats error! status: ${statsResponse.status}`);
        }

        if (!modelsResponse.ok) {
          throw new Error(`Models error! status: ${modelsResponse.status}`);
        }

        const [statsData, modelsData] = await Promise.all([
          statsResponse.json(),
          modelsResponse.json()
        ]);

        setStats(statsData);

        // Map API response to component interface
        const mappedModels: ModelConfig[] = modelsData.map((model: any) => ({
          model_id: model.model_id,
          name: model.name,
          provider: model.provider,
          model_type: model.model_type,
          endpoint: model.endpoint,
          description: model.description,
          health_status: model.status?.health_status || 'unknown',
          is_active: model.status?.is_active || false,
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
        setLastFetch(Date.now());
      } catch (error) {
        console.error('Failed to fetch data:', error);
        toast({
          title: "Failed to Load Data",
          description: "Unable to fetch model data from the server",
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  }, []); // Remove toast dependency to prevent re-renders

  // Refresh data when models are updated
  const handleModelUpdated = () => {
    setLoading(true);
    const fetchAllData = async () => {
      try {
        console.log('Model updated, forcing fresh data fetch');
        const [statsResponse, modelsResponse] = await Promise.all([
          fetch('/api/v1/models/stats/overview', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          }),
          fetch('/api/v1/models?include_stats=true', {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
              'Content-Type': 'application/json',
            },
          })
        ]);

        if (statsResponse.ok && modelsResponse.ok) {
          const [statsData, modelsData] = await Promise.all([
            statsResponse.json(),
            modelsResponse.json()
          ]);

          setStats(statsData);

          const mappedModels: ModelConfig[] = modelsData.map((model: any) => ({
            model_id: model.model_id,
            name: model.name,
            provider: model.provider,
            model_type: model.model_type,
            endpoint: model.endpoint,
            description: model.description,
            health_status: model.status?.health_status || 'unknown',
            is_active: model.status?.is_active || false,
            context_window: model.specifications?.context_window,
            max_tokens: model.specifications?.max_tokens,
            dimensions: model.specifications?.dimensions,
            cost_per_1k_input: model.cost?.per_1k_input || 0,
            cost_per_1k_output: model.cost?.per_1k_output || 0,
            capabilities: model.capabilities || {},
            last_health_check: model.status?.last_health_check,
            created_at: model.timestamps?.created_at,
            specifications: model.specifications,
            cost: model.cost,
            status: model.status,
          }));

          setModels(mappedModels);
          setLastFetch(Date.now());
        }
      } catch (error) {
        console.error('Failed to refresh data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Models</h1>
          <p className="text-muted-foreground">
            Configure AI model endpoints and providers
          </p>
        </div>
        <Button onClick={() => setShowAddDialog(true)} className="flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Add Model
        </Button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Models</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? '...' : (stats?.total_models || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              {loading ? 'Loading...' : `${stats?.active_models || 0} active, ${stats?.inactive_models || 0} inactive`}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Models</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {loading ? '...' : (stats?.active_models || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Available for tenant use
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="registry">Model Registry</TabsTrigger>
          <TabsTrigger value="endpoints">Endpoint Configuration</TabsTrigger>
        </TabsList>
        
        <TabsContent value="registry" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Registered Models</CardTitle>
              <CardDescription>
                Manage AI models available for your tenant. Use the delete option to permanently remove models.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ModelRegistryTable
                showArchived={false}
                models={models}
                loading={loading}
                onModelUpdated={handleModelUpdated}
              />
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="endpoints" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Endpoint Configurations</CardTitle>
              <CardDescription>
                API endpoints for model providers
              </CardDescription>
            </CardHeader>
            <CardContent>
              <EndpointConfigurator />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Add Model Dialog */}
      <AddModelDialog
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
        onModelAdded={handleModelUpdated}
      />
    </div>
  );
}