'use client';

import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, Clock, Cpu, Database, Globe, Loader2, TrendingUp, Users } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { monitoringApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_io: number;
  active_connections: number;
  api_calls_per_minute: number;
}

interface TenantMetric {
  tenant_id: number;
  tenant_name: string;
  api_calls: number;
  storage_used: number;
  active_users: number;
  status: string;
}

interface Alert {
  id: number;
  severity: string;
  title: string;
  description: string;
  timestamp: string;
  acknowledged: boolean;
}

export default function MonitoringPage() {
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [tenantMetrics, setTenantMetrics] = useState<TenantMetric[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState('24h');
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchMonitoringData();
    
    // Set up auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchMonitoringData();
    }, 30000);
    
    setRefreshInterval(interval);
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [selectedPeriod]);

  const fetchMonitoringData = async () => {
    try {
      setIsLoading(true);
      
      // Fetch all monitoring data in parallel
      const [systemResponse, tenantResponse, alertsResponse] = await Promise.all([
        monitoringApi.systemMetrics().catch(() => null),
        monitoringApi.tenantMetrics().catch(() => null),
        monitoringApi.alerts(1, 20).catch(() => null)
      ]);

      // Set data from API responses or empty defaults
      setSystemMetrics(systemResponse?.data || {
        cpu_usage: 0,
        memory_usage: 0,
        disk_usage: 0,
        network_io: 0,
        active_connections: 0,
        api_calls_per_minute: 0
      });

      setTenantMetrics(tenantResponse?.data?.tenants || []);
      setAlerts(alertsResponse?.data?.alerts || []);
    } catch (error) {
      console.error('Failed to fetch monitoring data:', error);
      toast.error('Failed to load monitoring data');
      
      // Set empty data on error
      setSystemMetrics({
        cpu_usage: 0,
        memory_usage: 0,
        disk_usage: 0,
        network_io: 0,
        active_connections: 0,
        api_calls_per_minute: 0
      });
      setTenantMetrics([]);
      setAlerts([]);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-600">Active</Badge>;
      case 'warning':
        return <Badge variant="default" className="bg-yellow-600">Warning</Badge>;
      case 'critical':
        return <Badge variant="destructive">Critical</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Badge variant="destructive">Critical</Badge>;
      case 'warning':
        return <Badge variant="default" className="bg-yellow-600">Warning</Badge>;
      case 'info':
        return <Badge variant="secondary">Info</Badge>;
      default:
        return <Badge variant="secondary">{severity}</Badge>;
    }
  };

  const formatPercentage = (value: number) => {
    return `${Math.round(value)}%`;
  };

  const getUsageColor = (value: number) => {
    if (value > 80) return 'text-red-600';
    if (value > 60) return 'text-yellow-600';
    return 'text-green-600';
  };

  if (isLoading && !systemMetrics) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading monitoring data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">System Monitoring</h1>
          <p className="text-muted-foreground">
            Real-time system metrics and performance monitoring
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last Hour</SelectItem>
              <SelectItem value="24h">Last 24h</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
              <SelectItem value="30d">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={fetchMonitoringData} variant="secondary">
            <Activity className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* System Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Cpu className="h-4 w-4 mr-2" />
              CPU Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getUsageColor(systemMetrics?.cpu_usage || 0)}`}>
              {formatPercentage(systemMetrics?.cpu_usage || 0)}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Database className="h-4 w-4 mr-2" />
              Memory
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getUsageColor(systemMetrics?.memory_usage || 0)}`}>
              {formatPercentage(systemMetrics?.memory_usage || 0)}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Database className="h-4 w-4 mr-2" />
              Disk Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getUsageColor(systemMetrics?.disk_usage || 0)}`}>
              {formatPercentage(systemMetrics?.disk_usage || 0)}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Globe className="h-4 w-4 mr-2" />
              Network I/O
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemMetrics?.network_io || 0} MB/s
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Users className="h-4 w-4 mr-2" />
              Connections
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemMetrics?.active_connections || 0}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <TrendingUp className="h-4 w-4 mr-2" />
              API Calls/min
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemMetrics?.api_calls_per_minute || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tenant Metrics */}
        <Card>
          <CardHeader>
            <CardTitle>Tenant Activity</CardTitle>
            <CardDescription>Resource usage by tenant</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Tenant</TableHead>
                  <TableHead>API Calls</TableHead>
                  <TableHead>Storage</TableHead>
                  <TableHead>Users</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenantMetrics.map((tenant) => (
                  <TableRow key={tenant.tenant_id}>
                    <TableCell className="font-medium">{tenant.tenant_name}</TableCell>
                    <TableCell>{tenant.api_calls.toLocaleString()}</TableCell>
                    <TableCell>{tenant.storage_used} GB</TableCell>
                    <TableCell>{tenant.active_users}</TableCell>
                    <TableCell>{getStatusBadge(tenant.status)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Alerts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <AlertTriangle className="h-5 w-5 mr-2" />
              Recent Alerts
            </CardTitle>
            <CardDescription>System alerts and notifications</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {alerts.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">No active alerts</p>
              ) : (
                alerts.map((alert) => (
                  <div key={alert.id} className="border rounded-lg p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        {getSeverityBadge(alert.severity)}
                        <span className="font-medium">{alert.title}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(alert.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">{alert.description}</p>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Performance Graph Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <BarChart3 className="h-5 w-5 mr-2" />
            Performance Trends
          </CardTitle>
          <CardDescription>System performance over time</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] flex items-center justify-center border-2 border-dashed rounded-lg">
            <div className="text-center text-muted-foreground">
              <BarChart3 className="h-12 w-12 mx-auto mb-4" />
              <p>Performance charts will be displayed here</p>
              <p className="text-sm mt-2">Coming soon: Real-time graphs and analytics</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}