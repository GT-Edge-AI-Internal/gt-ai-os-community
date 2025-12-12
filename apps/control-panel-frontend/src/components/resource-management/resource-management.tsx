'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Cpu,
  HardDrive,
  Zap,
  Brain,
  Activity,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  DollarSign,
  Scale,
  RefreshCw,
  Loader2,
  Settings,
  Download,
  Upload,
  Clock
} from 'lucide-react';
import toast from 'react-hot-toast';

interface ResourceUsage {
  resource_type: string;
  current_usage: number;
  max_allowed: number;
  percentage_used: number;
  cost_accrued: number;
  last_updated: string;
}

interface ResourceAlert {
  id: number;
  tenant_id: number;
  resource_type: string;
  alert_level: string;
  message: string;
  current_usage: number;
  max_value: number;
  percentage_used: number;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  created_at: string;
}

interface TenantCosts {
  tenant_id: number;
  period_start: string;
  period_end: string;
  total_cost: number;
  costs_by_resource: Record<string, any>;
  currency: string;
}

interface SystemOverview {
  timestamp: string;
  resource_overview: Record<string, any>;
  total_tenants: number;
}

interface Tenant {
  id: number;
  name: string;
  domain: string;
  status: string;
}

export function ResourceManagement() {
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [resourceUsage, setResourceUsage] = useState<Record<string, ResourceUsage>>({});
  const [alerts, setAlerts] = useState<ResourceAlert[]>([]);
  const [costs, setCosts] = useState<TenantCosts | null>(null);
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isScaling, setIsScaling] = useState(false);
  const [scalingResource, setScalingResource] = useState('');
  const [scaleFactor, setScaleFactor] = useState('1.0');

  // Resource templates
  const resourceTemplates = {
    startup: {
      name: 'Startup',
      description: 'Basic resources for small teams',
      monthly_cost: 99,
      resources: {
        cpu: { limit: 2.0, unit: 'cores' },
        memory: { limit: 4096, unit: 'MB' },
        storage: { limit: 10240, unit: 'MB' },
        api_calls: { limit: 10000, unit: 'calls/hour' },
        model_inference: { limit: 1000, unit: 'tokens' }
      }
    },
    standard: {
      name: 'Standard',
      description: 'Standard resources for production',
      monthly_cost: 299,
      resources: {
        cpu: { limit: 4.0, unit: 'cores' },
        memory: { limit: 8192, unit: 'MB' },
        storage: { limit: 51200, unit: 'MB' },
        api_calls: { limit: 50000, unit: 'calls/hour' },
        model_inference: { limit: 10000, unit: 'tokens' }
      }
    },
    enterprise: {
      name: 'Enterprise',
      description: 'High-performance resources',
      monthly_cost: 999,
      resources: {
        cpu: { limit: 16.0, unit: 'cores' },
        memory: { limit: 32768, unit: 'MB' },
        storage: { limit: 102400, unit: 'MB' },
        api_calls: { limit: 200000, unit: 'calls/hour' },
        model_inference: { limit: 100000, unit: 'tokens' },
        gpu_time: { limit: 1000, unit: 'minutes' }
      }
    }
  };

  useEffect(() => {
    fetchTenants();
    fetchSystemOverview();
    fetchAlerts();
  }, []);

  useEffect(() => {
    if (selectedTenant) {
      fetchTenantResourceUsage();
      fetchTenantCosts();
    }
  }, [selectedTenant]);

  const fetchTenants = async () => {
    try {
      // Mock tenants for now - replace with actual API call
      const mockTenants = [
        { id: 1, name: 'Acme Corp', domain: 'acme', status: 'active' },
        { id: 2, name: 'Tech Solutions', domain: 'techsol', status: 'active' },
        { id: 3, name: 'Startup Inc', domain: 'startup', status: 'pending' }
      ];
      setTenants(mockTenants);
      if (mockTenants.length > 0) {
        setSelectedTenant(mockTenants[0]);
      }
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
      toast.error('Failed to load tenants');
    }
  };

  const fetchTenantResourceUsage = async () => {
    if (!selectedTenant) return;
    
    try {
      setIsLoading(true);
      
      // Mock resource usage data - replace with actual API call
      const mockUsage: Record<string, ResourceUsage> = {
        cpu: {
          resource_type: 'cpu',
          current_usage: 2.4,
          max_allowed: 4.0,
          percentage_used: 60,
          cost_accrued: 24.0,
          last_updated: new Date().toISOString()
        },
        memory: {
          resource_type: 'memory',
          current_usage: 6144,
          max_allowed: 8192,
          percentage_used: 75,
          cost_accrued: 307.2,
          last_updated: new Date().toISOString()
        },
        storage: {
          resource_type: 'storage',
          current_usage: 35000,
          max_allowed: 51200,
          percentage_used: 68,
          cost_accrued: 350.0,
          last_updated: new Date().toISOString()
        },
        api_calls: {
          resource_type: 'api_calls',
          current_usage: 38500,
          max_allowed: 50000,
          percentage_used: 77,
          cost_accrued: 38.5,
          last_updated: new Date().toISOString()
        },
        model_inference: {
          resource_type: 'model_inference',
          current_usage: 7800,
          max_allowed: 10000,
          percentage_used: 78,
          cost_accrued: 15.6,
          last_updated: new Date().toISOString()
        }
      };
      
      setResourceUsage(mockUsage);
    } catch (error) {
      console.error('Failed to fetch resource usage:', error);
      toast.error('Failed to load resource usage');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchTenantCosts = async () => {
    if (!selectedTenant) return;
    
    try {
      // Mock cost data - replace with actual API call
      const mockCosts: TenantCosts = {
        tenant_id: selectedTenant.id,
        period_start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
        period_end: new Date().toISOString(),
        total_cost: 735.3,
        costs_by_resource: {
          cpu: { total_usage: 72.0, total_cost: 24.0, usage_events: 720 },
          memory: { total_usage: 6144.0, total_cost: 307.2, usage_events: 720 },
          storage: { total_usage: 35000.0, total_cost: 350.0, usage_events: 30 },
          api_calls: { total_usage: 1155000.0, total_cost: 38.5, usage_events: 1155 },
          model_inference: { total_usage: 234000.0, total_cost: 15.6, usage_events: 234 }
        },
        currency: 'USD'
      };
      
      setCosts(mockCosts);
    } catch (error) {
      console.error('Failed to fetch tenant costs:', error);
      toast.error('Failed to load cost data');
    }
  };

  const fetchSystemOverview = async () => {
    try {
      // Mock system overview - replace with actual API call
      const mockOverview: SystemOverview = {
        timestamp: new Date().toISOString(),
        resource_overview: {
          cpu: { total_usage: 12.8, total_allocated: 20.0, utilization_percentage: 64.0, tenant_count: 3 },
          memory: { total_usage: 18432, total_allocated: 32768, utilization_percentage: 56.25, tenant_count: 3 },
          storage: { total_usage: 125000, total_allocated: 204800, utilization_percentage: 61.04, tenant_count: 3 },
          api_calls: { total_usage: 145000, total_allocated: 300000, utilization_percentage: 48.33, tenant_count: 3 }
        },
        total_tenants: 3
      };
      
      setSystemOverview(mockOverview);
    } catch (error) {
      console.error('Failed to fetch system overview:', error);
      toast.error('Failed to load system overview');
    }
  };

  const fetchAlerts = async () => {
    try {
      // Mock alerts - replace with actual API call
      const mockAlerts: ResourceAlert[] = [
        {
          id: 1,
          tenant_id: 1,
          resource_type: 'memory',
          alert_level: 'warning',
          message: 'Memory usage at 75.0%',
          current_usage: 6144,
          max_value: 8192,
          percentage_used: 75.0,
          acknowledged: false,
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
        },
        {
          id: 2,
          tenant_id: 2,
          resource_type: 'api_calls',
          alert_level: 'critical',
          message: 'API calls usage at 95.0%',
          current_usage: 47500,
          max_value: 50000,
          percentage_used: 95.0,
          acknowledged: false,
          created_at: new Date(Date.now() - 30 * 60 * 1000).toISOString()
        }
      ];
      
      setAlerts(mockAlerts);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
      toast.error('Failed to load alerts');
    }
  };

  const handleScaleResources = async () => {
    if (!selectedTenant || !scalingResource || !scaleFactor) {
      toast.error('Please select a resource and scale factor');
      return;
    }

    try {
      setIsScaling(true);
      
      // Mock scaling API call - replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      toast.success(`Scaled ${scalingResource} by ${scaleFactor}x successfully`);
      
      // Refresh data
      await fetchTenantResourceUsage();
      setScalingResource('');
      setScaleFactor('1.0');
    } catch (error) {
      console.error('Failed to scale resources:', error);
      toast.error('Failed to scale resources');
    } finally {
      setIsScaling(false);
    }
  };

  const acknowledgeAlert = async (alertId: number) => {
    try {
      // Mock acknowledge API call - replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setAlerts(prev => prev.map(alert => 
        alert.id === alertId 
          ? { ...alert, acknowledged: true, acknowledged_at: new Date().toISOString() }
          : alert
      ));
      
      toast.success('Alert acknowledged');
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
      toast.error('Failed to acknowledge alert');
    }
  };

  const getResourceIcon = (resourceType: string) => {
    switch (resourceType) {
      case 'cpu':
        return <Cpu className="h-5 w-5" />;
      case 'memory':
        return <Cpu className="h-5 w-5" />;
      case 'storage':
        return <HardDrive className="h-5 w-5" />;
      case 'api_calls':
        return <Zap className="h-5 w-5" />;
      case 'model_inference':
        return <Brain className="h-5 w-5" />;
      case 'gpu_time':
        return <Activity className="h-5 w-5" />;
      default:
        return <Settings className="h-5 w-5" />;
    }
  };

  const getResourceName = (resourceType: string) => {
    switch (resourceType) {
      case 'cpu':
        return 'CPU';
      case 'memory':
        return 'Memory';
      case 'storage':
        return 'Storage';
      case 'api_calls':
        return 'API Calls';
      case 'model_inference':
        return 'Model Inference';
      case 'gpu_time':
        return 'GPU Time';
      default:
        return resourceType;
    }
  };

  const getResourceUnit = (resourceType: string) => {
    switch (resourceType) {
      case 'cpu':
        return 'cores';
      case 'memory':
        return 'MB';
      case 'storage':
        return 'MB';
      case 'api_calls':
        return 'calls/hour';
      case 'model_inference':
        return 'tokens';
      case 'gpu_time':
        return 'minutes';
      default:
        return 'units';
    }
  };

  const getAlertBadge = (level: string) => {
    switch (level) {
      case 'critical':
        return <Badge variant="destructive">Critical</Badge>;
      case 'warning':
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Warning</Badge>;
      case 'info':
        return <Badge variant="secondary">Info</Badge>;
      default:
        return <Badge variant="secondary">{level}</Badge>;
    }
  };

  if (isLoading && Object.keys(resourceUsage).length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading resource data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Resource Management</h2>
          <p className="text-muted-foreground">
            Monitor and manage resource allocation across all tenants
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <Select value={selectedTenant?.id.toString()} onValueChange={(value) => {
            const tenant = tenants.find(t => t.id.toString() === value);
            if (tenant) setSelectedTenant(tenant);
          }}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select tenant" />
            </SelectTrigger>
            <SelectContent>
              {tenants.map((tenant) => (
                <SelectItem key={tenant.id} value={tenant.id.toString()}>
                  {tenant.name} ({tenant.domain})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="secondary" onClick={() => {
            fetchTenantResourceUsage();
            fetchSystemOverview();
            fetchAlerts();
          }}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <Tabs defaultValue="usage" className="space-y-4">
        <TabsList>
          <TabsTrigger value="usage">Resource Usage</TabsTrigger>
          <TabsTrigger value="costs">Cost Analysis</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="system">System Overview</TabsTrigger>
        </TabsList>

        <TabsContent value="usage" className="space-y-4">
          {selectedTenant && (
            <>
              {/* Current Tenant Resources */}
              <Card>
                <CardHeader>
                  <CardTitle>
                    Resource Usage - {selectedTenant.name}
                  </CardTitle>
                  <CardDescription>
                    Current resource utilization and limits
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(resourceUsage).map(([resourceType, usage]) => (
                      <Card key={resourceType} className="relative">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                          <CardTitle className="text-sm font-medium">
                            <div className="flex items-center space-x-2">
                              {getResourceIcon(resourceType)}
                              <span>{getResourceName(resourceType)}</span>
                            </div>
                          </CardTitle>
                          <div className="text-xs text-muted-foreground">
                            ${usage.cost_accrued.toFixed(2)}
                          </div>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                              <span>
                                {usage.current_usage.toLocaleString()} / {usage.max_allowed.toLocaleString()} {getResourceUnit(resourceType)}
                              </span>
                              <span className="font-medium">
                                {usage.percentage_used.toFixed(1)}%
                              </span>
                            </div>
                            <Progress 
                              value={usage.percentage_used} 
                              className={`h-2 ${
                                usage.percentage_used >= 95 
                                  ? 'bg-red-100' 
                                  : usage.percentage_used >= 80 
                                    ? 'bg-yellow-100' 
                                    : 'bg-green-100'
                              }`}
                            />
                            <div className="text-xs text-muted-foreground">
                              Last updated: {new Date(usage.last_updated).toLocaleTimeString()}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Resource Scaling */}
              <Card>
                <CardHeader>
                  <CardTitle>Resource Scaling</CardTitle>
                  <CardDescription>
                    Scale resources up or down for {selectedTenant.name}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                    <div>
                      <Label htmlFor="scaling-resource">Resource Type</Label>
                      <Select value={scalingResource} onValueChange={setScalingResource}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select resource" />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.keys(resourceUsage).map((resourceType) => (
                            <SelectItem key={resourceType} value={resourceType}>
                              {getResourceName(resourceType)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label htmlFor="scale-factor">Scale Factor</Label>
                      <Input
                        id="scale-factor"
                        type="number"
                        min="0.1"
                        max="10.0"
                        step="0.1"
                        value={scaleFactor}
                        onChange={(e) => setScaleFactor((e as React.ChangeEvent<HTMLInputElement>).target.value)}
                        placeholder="1.5"
                      />
                    </div>
                    <Button 
                      onClick={handleScaleResources}
                      disabled={isScaling || !scalingResource || !scaleFactor}
                    >
                      {isScaling ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Scaling...
                        </>
                      ) : (
                        <>
                          <Scale className="h-4 w-4 mr-2" />
                          Scale Resource
                        </>
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="costs" className="space-y-4">
          {costs && (
            <Card>
              <CardHeader>
                <CardTitle>Cost Breakdown - Last 30 Days</CardTitle>
                <CardDescription>
                  Resource costs for {selectedTenant?.name}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
                    <div>
                      <div className="text-2xl font-bold">
                        ${costs.total_cost.toFixed(2)} {costs.currency}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Total cost for period
                      </div>
                    </div>
                    <DollarSign className="h-8 w-8 text-muted-foreground" />
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Object.entries(costs.costs_by_resource).map(([resourceType, data]: [string, any]) => (
                      <Card key={resourceType}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                          <CardTitle className="text-sm font-medium">
                            <div className="flex items-center space-x-2">
                              {getResourceIcon(resourceType)}
                              <span>{getResourceName(resourceType)}</span>
                            </div>
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-1">
                            <div className="text-2xl font-bold">
                              ${data.total_cost.toFixed(2)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {data.total_usage.toLocaleString()} {getResourceUnit(resourceType)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {data.usage_events} events
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Resource Alerts</CardTitle>
              <CardDescription>
                Recent resource usage alerts across all tenants
              </CardDescription>
            </CardHeader>
            <CardContent>
              {alerts.length === 0 ? (
                <div className="text-center py-8">
                  <CheckCircle className="h-12 w-12 text-green-600 mx-auto mb-4" />
                  <p className="text-muted-foreground">No active alerts</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {alerts.map((alert) => (
                    <div 
                      key={alert.id} 
                      className={`p-4 rounded-lg border ${
                        alert.acknowledged ? 'bg-muted/50' : 'bg-background'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            {getAlertBadge(alert.alert_level)}
                            {getResourceIcon(alert.resource_type)}
                            <span className="font-medium">
                              {getResourceName(alert.resource_type)}
                            </span>
                            <span className="text-sm text-muted-foreground">
                              - Tenant {alert.tenant_id}
                            </span>
                          </div>
                          <p className="text-sm">{alert.message}</p>
                          <div className="text-xs text-muted-foreground">
                            <Clock className="h-3 w-3 inline mr-1" />
                            {new Date(alert.created_at).toLocaleString()}
                            {alert.acknowledged && (
                              <span className="ml-4">
                                ✓ Acknowledged {alert.acknowledged_at && 
                                  `at ${new Date(alert.acknowledged_at).toLocaleString()}`}
                              </span>
                            )}
                          </div>
                        </div>
                        {!alert.acknowledged && (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => acknowledgeAlert(alert.id)}
                          >
                            Acknowledge
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system" className="space-y-4">
          {systemOverview && (
            <Card>
              <CardHeader>
                <CardTitle>System Resource Overview</CardTitle>
                <CardDescription>
                  Aggregate resource usage across all {systemOverview.total_tenants} tenants
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {Object.entries(systemOverview.resource_overview).map(([resourceType, data]: [string, any]) => (
                    <Card key={resourceType}>
                      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">
                          <div className="flex items-center space-x-2">
                            {getResourceIcon(resourceType)}
                            <span>{getResourceName(resourceType)}</span>
                          </div>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          <div className="text-2xl font-bold">
                            {data.utilization_percentage.toFixed(1)}%
                          </div>
                          <Progress value={data.utilization_percentage} className="h-2" />
                          <div className="text-xs text-muted-foreground space-y-1">
                            <div>
                              {data.total_usage.toLocaleString()} / {data.total_allocated.toLocaleString()} {getResourceUnit(resourceType)}
                            </div>
                            <div>
                              {data.tenant_count} tenants using
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}