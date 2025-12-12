'use client';

import { useEffect, useState } from 'react';
import { Server, Database, HardDrive, Activity, CheckCircle, XCircle, AlertTriangle, Loader2, RefreshCw, Settings2, Cloud, Layers } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { systemApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { BackupManager } from '@/components/system/BackupManager';
import { UpdateModal } from '@/components/system/UpdateModal';

interface SystemHealth {
  overall_status: string;
  uptime: string;
  version: string;
  environment: string;
}

interface ClusterInfo {
  name: string;
  status: string;
  nodes: number;
  pods: number;
  cpu_usage: number;
  memory_usage: number;
  storage_usage: number;
}

interface ServiceStatus {
  name: string;
  status: string;
  health: string;
  version: string;
  uptime: string;
  last_check: string;
}

interface SystemConfig {
  key: string;
  value: string;
  category: string;
  editable: boolean;
}

interface SystemHealthDetailed {
  overall_status: string;
  containers: Array<{
    name: string;
    cluster: string;
    state: string;
    health: string;
    uptime: string;
    ports: string[];
  }>;
  clusters: Array<{
    name: string;
    healthy: number;
    unhealthy: number;
    total: number;
  }>;
  database: {
    connections_active: number;
    connections_max: number;
    cache_hit_ratio: number;
    database_size: string;
    transactions_committed: number;
  };
  version: string;
}

interface UpdateInfo {
  current_version: string;
  latest_version: string;
  update_type: 'major' | 'minor' | 'patch';
  release_notes: string;
  released_at: string;
}

export default function SystemPage() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [healthData, setHealthData] = useState<SystemHealthDetailed | null>(null);
  const [clusters, setClusters] = useState<ClusterInfo[]>([]);
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [configs, setConfigs] = useState<SystemConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentVersion, setCurrentVersion] = useState<string>('');
  const [isCheckingUpdate, setIsCheckingUpdate] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  useEffect(() => {
    fetchSystemData();
  }, []);

  const fetchSystemData = async (showRefreshIndicator = false) => {
    try {
      if (showRefreshIndicator) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }

      // Fetch system data from API
      const [healthResponse, healthDetailedResponse] = await Promise.all([
        systemApi.health().catch(() => null),
        systemApi.healthDetailed().catch(() => null)
      ]);

      // Set system health from API response or defaults
      setSystemHealth({
        overall_status: healthDetailedResponse?.data?.overall_status || healthResponse?.data?.status || 'unknown',
        uptime: '0 days',
        version: healthDetailedResponse?.data?.version || '2.0.0',
        environment: 'development'
      });

      // Set detailed health data for Database & Storage section
      if (healthDetailedResponse?.data) {
        setHealthData(healthDetailedResponse.data);
      }

      // Clear clusters, services, configs - not used in current UI
      setClusters([]);
      setServices([]);
      setConfigs([]);

      // Fetch version info
      try {
        const versionResponse = await systemApi.version();
        // Use either 'current_version' or 'version' field for compatibility
        setCurrentVersion(versionResponse.data.current_version || versionResponse.data.version || '2.0.0');
      } catch (error) {
        console.error('Failed to fetch version:', error);
      }

      if (showRefreshIndicator) {
        toast.success('System data refreshed');
      }
    } catch (error) {
      console.error('Failed to fetch system data:', error);
      toast.error('Failed to load system data');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'running':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'warning':
        return <AlertTriangle className="h-5 w-5 text-yellow-600" />;
      case 'unhealthy':
      case 'stopped':
        return <XCircle className="h-5 w-5 text-red-600" />;
      default:
        return <Activity className="h-5 w-5 text-gray-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'running':
        return <Badge variant="default" className="bg-green-600">Healthy</Badge>;
      case 'warning':
        return <Badge variant="default" className="bg-yellow-600">Warning</Badge>;
      case 'unhealthy':
      case 'stopped':
        return <Badge variant="destructive">Unhealthy</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getUsageColor = (value: number) => {
    if (value > 80) return 'bg-red-600';
    if (value > 60) return 'bg-yellow-600';
    return 'bg-green-600';
  };

  const handleCheckForUpdates = async () => {
    setIsCheckingUpdate(true);
    try {
      const response = await systemApi.checkUpdate();
      if (response.data.update_available) {
        // Map backend response to UpdateInfo format
        const info: UpdateInfo = {
          current_version: response.data.current_version,
          latest_version: response.data.latest_version,
          update_type: response.data.update_type || 'patch',
          release_notes: response.data.release_notes || '',
          released_at: response.data.released_at || response.data.published_at || ''
        };
        setUpdateInfo(info);
        setShowUpdateModal(true);
        toast.success(`Update available: v${response.data.latest_version}`);
      } else {
        toast.success('System is up to date');
      }
    } catch (error) {
      console.error('Failed to check for updates:', error);
      toast.error('Failed to check for updates');
    } finally {
      setIsCheckingUpdate(false);
    }
  };

  const handleUpdateModalClose = () => {
    setShowUpdateModal(false);
    // Refresh system data after modal closes (in case update was performed)
    fetchSystemData();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading system information...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">System Management</h1>
          <p className="text-muted-foreground">
            System health, cluster status, and configuration
          </p>
        </div>
        <Button 
          onClick={() => fetchSystemData(true)} 
          disabled={isRefreshing}
        >
          {isRefreshing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Refreshing...
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </>
          )}
        </Button>
      </div>

      {/* System Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">System Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              {getStatusIcon(systemHealth?.overall_status || 'unknown')}
              <span className="text-2xl font-bold capitalize">
                {systemHealth?.overall_status || 'Unknown'}
              </span>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Uptime</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemHealth?.uptime || '-'}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Version</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{systemHealth?.version || '-'}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{systemHealth?.environment || '-'}</div>
          </CardContent>
        </Card>
      </div>

      {/* Software Updates */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Cloud className="h-5 w-5 mr-2" />
            Software Updates
          </CardTitle>
          <CardDescription>Manage system software updates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">Current Version</div>
              <div className="text-2xl font-bold">{currentVersion || systemHealth?.version || '-'}</div>
            </div>
            <div className="flex items-end">
              <Button
                onClick={handleCheckForUpdates}
                disabled={isCheckingUpdate}
                className="w-full"
              >
                {isCheckingUpdate ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Checking...
                  </>
                ) : (
                  'Check for Updates'
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Backup Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <HardDrive className="h-5 w-5 mr-2" />
            Backup Management
          </CardTitle>
          <CardDescription>Create and restore system backups</CardDescription>
        </CardHeader>
        <CardContent>
          <BackupManager />
        </CardContent>
      </Card>

      {/* Database Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Database className="h-5 w-5 mr-2" />
            Database & Storage
          </CardTitle>
          <CardDescription>Database connections and storage metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">PostgreSQL Connections</div>
              <div className="text-2xl font-bold">
                {healthData?.database?.connections_active ?? '-'} / {healthData?.database?.connections_max ?? '-'}
              </div>
              <Progress value={healthData?.database ? (healthData.database.connections_active / healthData.database.connections_max) * 100 : 0} className="h-2" />
            </div>
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">Cache Hit Ratio</div>
              <div className="text-2xl font-bold">{healthData?.database?.cache_hit_ratio ?? '-'}%</div>
              <Progress value={healthData?.database?.cache_hit_ratio ?? 0} className="h-2" />
            </div>
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">Database Size</div>
              <div className="text-2xl font-bold">{healthData?.database?.database_size ?? '-'}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Update Modal */}
      {updateInfo && (
        <UpdateModal
          updateInfo={updateInfo}
          open={showUpdateModal}
          onClose={handleUpdateModalClose}
        />
      )}
    </div>
  );
}