'use client';

import { useEffect, useState } from 'react';
import { Edit, Building2, Loader2, Power } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
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
      const response = await tenantsApi.list(1, 100);
      setTenants(response.data.tenants || []);
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
      toast.error('Failed to load tenant');
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[600px]">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-muted-foreground">Loading tenant...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Tenant</h1>
          <p className="text-muted-foreground">
            Manage your tenant configuration
          </p>
          <p className="text-sm text-amber-600 mt-1">
            GT AI OS Community Edition: Limited to 10 users per tenant
          </p>
        </div>
      </div>

      {tenants.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <Building2 className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No tenant configured</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        tenants.map((tenant) => (
          <Card key={tenant.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Building2 className="h-6 w-6 text-muted-foreground" />
                  <div>
                    <CardTitle>{tenant.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {tenant.frontend_url || 'http://localhost:3002'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {getStatusBadge(tenant.status)}
                  {tenant.status === 'pending' && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleDeploy(tenant)}
                    >
                      <Power className="h-4 w-4 mr-2" />
                      Deploy
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => openEditDialog(tenant)}
                  >
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Users</p>
                  <p className="text-2xl font-bold">{tenant.user_count} <span className="text-sm font-normal text-muted-foreground">/ 10</span></p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Domain</p>
                  <p className="text-lg font-medium">{tenant.domain}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Created</p>
                  <p className="text-lg font-medium">{new Date(tenant.created_at).toLocaleDateString()}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Status</p>
                  <p className="text-lg font-medium capitalize">{tenant.status}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))
      )}

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