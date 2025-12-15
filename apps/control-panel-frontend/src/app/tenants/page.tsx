'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Plus,
  Search,
  Building2,
  Users,
  Cpu,
  Activity,
  CheckCircle,
  Clock,
  XCircle,
  AlertTriangle,
  Play,
  Pause,
  Archive,
  Settings,
  Eye,
  Rocket,
  Timer,
  Shield,
  Database,
  Cloud,
  MoreVertical,
} from 'lucide-react';

interface Tenant {
  id: number;
  name: string;
  domain: string;
  template: string;
  status: 'active' | 'pending' | 'suspended' | 'archived';
  max_users: number;
  current_users: number;
  namespace: string;
  resource_count: number;
  created_at: string;
  last_activity?: string;
  deployment_status?: 'deployed' | 'deploying' | 'failed' | 'not_deployed';
  storage_used_gb?: number;
  api_calls_today?: number;
}

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [filteredTenants, setFilteredTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedTenants, setSelectedTenants] = useState<Set<number>>(new Set());

  // Mock data for development
  useEffect(() => {
    const mockTenants: Tenant[] = [
      {
        id: 1,
        name: 'Acme Corporation',
        domain: 'acme',
        template: 'enterprise',
        status: 'active',
        max_users: 500,
        current_users: 247,
        namespace: 'gt-tenant-acme',
        resource_count: 12,
        created_at: '2024-01-15T10:00:00Z',
        last_activity: new Date().toISOString(),
        deployment_status: 'deployed',
        storage_used_gb: 45.2,
        api_calls_today: 15234,
      },
      {
        id: 2,
        name: 'TechStart Inc',
        domain: 'techstart',
        template: 'startup',
        status: 'pending',
        max_users: 100,
        current_users: 0,
        namespace: 'gt-tenant-techstart',
        resource_count: 8,
        created_at: '2024-01-14T14:30:00Z',
        deployment_status: 'deploying',
        storage_used_gb: 0,
        api_calls_today: 0,
      },
      {
        id: 3,
        name: 'Global Solutions',
        domain: 'global',
        template: 'enterprise',
        status: 'active',
        max_users: 1000,
        current_users: 623,
        namespace: 'gt-tenant-global',
        resource_count: 24,
        created_at: '2024-01-13T09:15:00Z',
        last_activity: new Date(Date.now() - 3600000).toISOString(),
        deployment_status: 'deployed',
        storage_used_gb: 128.7,
        api_calls_today: 42156,
      },
      {
        id: 4,
        name: 'Education First',
        domain: 'edufirst',
        template: 'education',
        status: 'active',
        max_users: 2000,
        current_users: 1456,
        namespace: 'gt-tenant-edufirst',
        resource_count: 18,
        created_at: '2024-01-10T11:00:00Z',
        last_activity: new Date(Date.now() - 600000).toISOString(),
        deployment_status: 'deployed',
        storage_used_gb: 89.3,
        api_calls_today: 28934,
      },
      {
        id: 5,
        name: 'CyberDefense Corp',
        domain: 'cyberdef',
        template: 'cybersecurity',
        status: 'active',
        max_users: 300,
        current_users: 189,
        namespace: 'gt-tenant-cyberdef',
        resource_count: 21,
        created_at: '2024-01-08T08:45:00Z',
        last_activity: new Date(Date.now() - 1800000).toISOString(),
        deployment_status: 'deployed',
        storage_used_gb: 67.4,
        api_calls_today: 19876,
      },
      {
        id: 6,
        name: 'Beta Testers LLC',
        domain: 'betatest',
        template: 'development',
        status: 'suspended',
        max_users: 10,
        current_users: 12,
        namespace: 'gt-tenant-betatest',
        resource_count: 5,
        created_at: '2024-01-05T15:20:00Z',
        last_activity: new Date(Date.now() - 86400000).toISOString(),
        deployment_status: 'deployed',
        storage_used_gb: 12.1,
        api_calls_today: 0,
      },
    ];

    setTenants(mockTenants);
    setFilteredTenants(mockTenants);
    setLoading(false);
  }, []);

  // Filter tenants based on search and status
  useEffect(() => {
    let filtered = tenants;

    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter(t => t.status === statusFilter);
    }

    // Filter by search query
    if (searchQuery) {
      filtered = filtered.filter(t =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.template.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredTenants(filtered);
  }, [statusFilter, searchQuery, tenants]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-600"><CheckCircle className="h-3 w-3 mr-1" />Active</Badge>;
      case 'pending':
        return <Badge variant="secondary"><Clock className="h-3 w-3 mr-1" />Pending</Badge>;
      case 'suspended':
        return <Badge variant="destructive"><Pause className="h-3 w-3 mr-1" />Suspended</Badge>;
      case 'archived':
        return <Badge variant="secondary"><Archive className="h-3 w-3 mr-1" />Archived</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getDeploymentBadge = (status?: string) => {
    switch (status) {
      case 'deployed':
        return <Badge variant="secondary" className="text-green-600"><Cloud className="h-3 w-3 mr-1" />Deployed</Badge>;
      case 'deploying':
        return <Badge variant="secondary" className="text-blue-600"><Rocket className="h-3 w-3 mr-1" />Deploying</Badge>;
      case 'failed':
        return <Badge variant="secondary" className="text-red-600"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>;
      default:
        return <Badge variant="secondary"><AlertTriangle className="h-3 w-3 mr-1" />Not Deployed</Badge>;
    }
  };

  const getTemplateBadge = (template: string) => {
    const colors: Record<string, string> = {
      enterprise: 'bg-purple-600',
      startup: 'bg-blue-600',
      education: 'bg-green-600',
      cybersecurity: 'bg-red-600',
      development: 'bg-yellow-600',
    };
    return (
      <Badge className={colors[template] || 'bg-gray-600'}>
        {template.charAt(0).toUpperCase() + template.slice(1)}
      </Badge>
    );
  };

  const statusTabs = [
    { id: 'all', label: 'All Tenants', count: tenants.length },
    { id: 'active', label: 'Active', count: tenants.filter(t => t.status === 'active').length },
    { id: 'pending', label: 'Pending', count: tenants.filter(t => t.status === 'pending').length },
    { id: 'suspended', label: 'Suspended', count: tenants.filter(t => t.status === 'suspended').length },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Tenant Management</h1>
          <p className="text-muted-foreground">
            Manage tenant deployments with 5-minute onboarding
          </p>
        </div>
        <div className="flex space-x-2">
          <Button variant="secondary">
            <Timer className="h-4 w-4 mr-2" />
            Bulk Deploy
          </Button>
          <Button className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700">
            <Rocket className="h-4 w-4 mr-2" />
            5-Min Onboarding
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Tenants</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{tenants.length}</div>
            <p className="text-xs text-muted-foreground">
              {tenants.filter(t => t.status === 'active').length} active
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {tenants.reduce((sum, t) => sum + t.current_users, 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Across all tenants
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(tenants.reduce((sum, t) => sum + (t.storage_used_gb || 0), 0) / 1024).toFixed(1)} TB
            </div>
            <p className="text-xs text-muted-foreground">
              Total consumption
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">API Calls Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {tenants.reduce((sum, t) => sum + (t.api_calls_today || 0), 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              All tenants combined
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Status Tabs */}
      <div className="flex space-x-2 border-b">
        {statusTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setStatusFilter(tab.id)}
            className={`px-4 py-2 border-b-2 transition-colors ${
              statusFilter === tab.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <span>{tab.label}</span>
            <Badge variant="secondary" className="ml-2">{tab.count}</Badge>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex space-x-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search tenants by name, domain, or template..."
            value={searchQuery}
            onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
            className="pl-10"
          />
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedTenants.size > 0 && (
        <Card className="bg-muted/50">
          <CardContent className="flex items-center justify-between py-3">
            <span className="text-sm">
              {selectedTenants.size} tenant{selectedTenants.size > 1 ? 's' : ''} selected
            </span>
            <div className="flex space-x-2">
              <Button variant="secondary" size="sm">
                <Cpu className="h-4 w-4 mr-2" />
                Assign Resources
              </Button>
              <Button variant="secondary" size="sm">
                <Play className="h-4 w-4 mr-2" />
                Deploy All
              </Button>
              <Button variant="secondary" size="sm" className="text-destructive">
                <Pause className="h-4 w-4 mr-2" />
                Suspend
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tenants Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Activity className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th className="p-4 text-left">
                      <input
                        type="checkbox"
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedTenants(new Set(filteredTenants.map(t => t.id)));
                          } else {
                            setSelectedTenants(new Set());
                          }
                        }}
                        checked={selectedTenants.size === filteredTenants.length && filteredTenants.length > 0}
                      />
                    </th>
                    <th className="p-4 text-left font-medium">Tenant</th>
                    <th className="p-4 text-left font-medium">Status</th>
                    <th className="p-4 text-left font-medium">Template</th>
                    <th className="p-4 text-left font-medium">Users</th>
                    <th className="p-4 text-left font-medium">Resources</th>
                    <th className="p-4 text-left font-medium">Usage</th>
                    <th className="p-4 text-left font-medium">Activity</th>
                    <th className="p-4 text-left font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTenants.map(tenant => (
                    <tr key={tenant.id} className="border-b hover:bg-muted/30">
                      <td className="p-4">
                        <input
                          type="checkbox"
                          checked={selectedTenants.has(tenant.id)}
                          onChange={(e) => {
                            const newSelected = new Set(selectedTenants);
                            if (e.target.checked) {
                              newSelected.add(tenant.id);
                            } else {
                              newSelected.delete(tenant.id);
                            }
                            setSelectedTenants(newSelected);
                          }}
                        />
                      </td>
                      <td className="p-4">
                        <div>
                          <div className="font-medium">{tenant.name}</div>
                          <div className="text-sm text-muted-foreground">{tenant.domain}.gt2.com</div>
                          <div className="text-xs text-muted-foreground mt-1">{tenant.namespace}</div>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="space-y-1">
                          {getStatusBadge(tenant.status)}
                          {getDeploymentBadge(tenant.deployment_status)}
                        </div>
                      </td>
                      <td className="p-4">
                        {getTemplateBadge(tenant.template)}
                      </td>
                      <td className="p-4">
                        <div>
                          <div className="font-medium">{tenant.current_users}</div>
                          <div className="text-xs text-muted-foreground">of {tenant.max_users}</div>
                          <div className="w-full bg-secondary rounded-full h-1.5 mt-1">
                            <div
                              className="bg-primary h-1.5 rounded-full"
                              style={{ width: `${(tenant.current_users / tenant.max_users) * 100}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center space-x-1">
                          <Cpu className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{tenant.resource_count}</span>
                        </div>
                      </td>
                      <td className="p-4">
                        <div className="space-y-1 text-sm">
                          {tenant.storage_used_gb && (
                            <div className="flex items-center space-x-1">
                              <Database className="h-3 w-3 text-muted-foreground" />
                              <span>{tenant.storage_used_gb.toFixed(1)} GB</span>
                            </div>
                          )}
                          {tenant.api_calls_today && (
                            <div className="flex items-center space-x-1">
                              <Activity className="h-3 w-3 text-muted-foreground" />
                              <span>{tenant.api_calls_today.toLocaleString()}</span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="p-4">
                        {tenant.last_activity && (
                          <div className="text-sm text-muted-foreground">
                            {new Date(tenant.last_activity).toLocaleTimeString()}
                          </div>
                        )}
                      </td>
                      <td className="p-4">
                        <div className="flex space-x-1">
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}