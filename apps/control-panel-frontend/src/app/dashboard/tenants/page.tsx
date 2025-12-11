'use client';

import { useEffect, useState } from 'react';
import { Search, Edit, Trash2, Building2, Loader2, Power } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { tenantsApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface Tenant {
  id: number;
  uuid: string;
  name: string;
  domain: string;
  template: string;
  status: string;
  max_users: number;
  user_count: number;
  resource_limits: any;
  namespace: string;
  frontend_url?: string;
  optics_enabled?: boolean;
  created_at: string;
  updated_at: string;
  // Budget configuration
  monthly_budget_cents?: number | null;
  budget_warning_threshold?: number | null;
  budget_critical_threshold?: number | null;
  budget_enforcement_enabled?: boolean | null;
  // Storage pricing - Hot tier only
  storage_price_dataset_hot?: number | null;
  storage_price_conversation_hot?: number | null;
  // Cold tier allocation-based
  cold_storage_allocated_tibs?: number | null;
  cold_storage_price_per_tib?: number | null;
}

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  
  // Form fields (simplified for Community Edition)
  const [formData, setFormData] = useState({
    name: '',
    frontend_url: '',
  });

  useEffect(() => {
    fetchTenants();
  }, []);

  const fetchTenants = async () => {
    try {
      setIsLoading(true);
      const response = await tenantsApi.list(1, 100, searchQuery, selectedStatus === 'all' ? undefined : selectedStatus);
      setTenants(response.data.tenants || []);
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
      toast.error('Failed to load tenants');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedTenant) return;

    try {
      setIsUpdating(true);

      await tenantsApi.update(selectedTenant.id, {
        name: formData.name,
        frontend_url: formData.frontend_url,
      });
      toast.success('Tenant updated successfully');
      setShowEditDialog(false);
      fetchTenants();
    } catch (error: any) {
      console.error('Failed to update tenant:', error);
      toast.error(error.response?.data?.detail || 'Failed to update tenant');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async (tenant: Tenant) => {
    if (!confirm(`Are you sure you want to archive ${tenant.name}?`)) return;

    try {
      await tenantsApi.delete(tenant.id);
      toast.success('Tenant archived successfully');
      fetchTenants();
    } catch (error: any) {
      console.error('Failed to delete tenant:', error);
      toast.error(error.response?.data?.detail || 'Failed to archive tenant');
    }
  };

  const handleDeploy = async (tenant: Tenant) => {
    try {
      await tenantsApi.deploy(tenant.id);
      toast.success('Deployment initiated for ' + tenant.name);
      fetchTenants();
    } catch (error: any) {
      console.error('Failed to deploy tenant:', error);
      toast.error(error.response?.data?.detail || 'Failed to deploy tenant');
    }
  };

  const handleStatusChange = async (tenant: Tenant, newStatus: string) => {
    try {
      if (newStatus === 'active') {
        await tenantsApi.activate(tenant.id);
        toast.success('Tenant activated');
      } else if (newStatus === 'suspended') {
        await tenantsApi.suspend(tenant.id);
        toast.success('Tenant suspended');
      }
      fetchTenants();
    } catch (error: any) {
      console.error('Failed to change tenant status:', error);
      toast.error(error.response?.data?.detail || 'Failed to change status');
    }
  };

  const openEditDialog = (tenant: Tenant) => {
    setSelectedTenant(tenant);
    setFormData({
      ...formData,
      name: tenant.name,
      frontend_url: tenant.frontend_url || '',
    });
    setShowEditDialog(true);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-600">Active</Badge>;
      case 'pending':
        return <Badge variant="secondary">Pending</Badge>;
      case 'suspended':
        return <Badge variant="destructive">Suspended</Badge>;
      case 'deploying':
        return <Badge variant="secondary">Deploying</Badge>;
      case 'archived':
        return <Badge variant="secondary">Archived</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const filteredTenants = tenants.filter(tenant => {
    if (searchQuery && !tenant.name.toLowerCase().includes(searchQuery.toLowerCase()) && 
        !tenant.domain.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (selectedStatus !== 'all' && tenant.status !== selectedStatus) {
      return false;
    }
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading tenants...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Tenants</h1>
          <p className="text-muted-foreground">
            Manage your tenants and their configurations
          </p>
          <p className="text-sm text-amber-600 mt-1">
            GT AI OS Community Edition: Limited to 5 users per tenant
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>All Tenants</CardTitle>
            <div className="flex items-center space-x-2">
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search tenants..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery((e as React.ChangeEvent<HTMLInputElement>).target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchTenants()}
                  className="pl-8 w-[250px]"
                />
              </div>
              <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="All Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="suspended">Suspended</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {filteredTenants.length === 0 ? (
            <div className="text-center py-12">
              <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No tenants found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Frontend URL</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Users (max 5)</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTenants.map((tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell className="font-medium">{tenant.name}</TableCell>
                    <TableCell>
                      {tenant.frontend_url ? (
                        <span className="text-sm text-muted-foreground">{tenant.frontend_url}</span>
                      ) : (
                        <span className="text-sm text-muted-foreground italic">localhost:3002</span>
                      )}
                    </TableCell>
                    <TableCell>{getStatusBadge(tenant.status)}</TableCell>
                    <TableCell>{tenant.user_count}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end space-x-2">
                        {tenant.status === 'pending' && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleDeploy(tenant)}
                            title="Deploy"
                          >
                            <Power className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => openEditDialog(tenant)}
                          title="Edit"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleDelete(tenant)}
                          title="Archive"
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

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Tenant</DialogTitle>
            <DialogDescription>
              Update tenant configuration
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Tenant Name</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: (e as React.ChangeEvent<HTMLInputElement>).target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-frontend_url">Frontend URL (Optional)</Label>
              <Input
                id="edit-frontend_url"
                value={formData.frontend_url}
                onChange={(e) => setFormData({ ...formData, frontend_url: (e as React.ChangeEvent<HTMLInputElement>).target.value })}
                placeholder="https://app.company.com or http://localhost:3002"
              />
              <p className="text-xs text-muted-foreground">
                Custom frontend URL for this tenant. Leave blank to use http://localhost:3002
              </p>
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
                'Update Tenant'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}