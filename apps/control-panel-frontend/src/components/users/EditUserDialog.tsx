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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { usersApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { Loader2 } from 'lucide-react';

interface EditUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: number | null;
  onUserUpdated?: () => void;
}

interface UserData {
  id: number;
  email: string;
  full_name: string;
  user_type: string;
  tenant_id?: number;
  is_active: boolean;
  tfa_required?: boolean;
}

export default function EditUserDialog({ open, onOpenChange, userId, onUserUpdated }: EditUserDialogProps) {
  const [loading, setLoading] = useState(false);
  const [fetchingUser, setFetchingUser] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    user_type: 'tenant_user',
    tenant_id: '',
    is_active: true,
    tfa_required: false,
    password: '', // Optional - only update if provided
  });
  const [userData, setUserData] = useState<UserData | null>(null);

  // Fetch user data when dialog opens
  useEffect(() => {
    const fetchData = async () => {
      if (!userId || !open) return;

      setFetchingUser(true);
      try {
        // Fetch user data
        const userResponse = await usersApi.get(userId);
        const user = userResponse.data;
        setUserData(user);

        // Pre-populate form (tenant_id preserved from user data, not editable in GT AI OS Local)
        setFormData({
          email: user.email,
          full_name: user.full_name,
          user_type: user.user_type,
          tenant_id: user.tenant_id ? user.tenant_id.toString() : '1',
          is_active: user.is_active,
          tfa_required: user.tfa_required || false,
          password: '',
        });
      } catch (error) {
        console.error('Failed to fetch user data:', error);
        toast.error('Failed to load user data');
        onOpenChange(false);
      } finally {
        setFetchingUser(false);
      }
    };

    fetchData();
  }, [userId, open, onOpenChange]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!userId) return;

    // Validation
    if (!formData.email) {
      toast.error('Email is required');
      return;
    }

    if (!formData.full_name) {
      toast.error('Full name is required');
      return;
    }

    // Password is optional for updates, but if provided it cannot be empty
    // (This validation is actually redundant since empty string is falsy)

    // tenant_id is auto-assigned/preserved for GT AI OS Local

    setLoading(true);
    try {
      const payload: any = {
        email: formData.email,
        full_name: formData.full_name,
        user_type: formData.user_type,
        is_active: formData.is_active,
        tfa_required: formData.tfa_required,
        tenant_id: formData.tenant_id ? parseInt(formData.tenant_id) : null,
      };

      // Only include password if provided
      if (formData.password) {
        payload.password = formData.password;
      }

      await usersApi.update(userId, payload);
      toast.success('User updated successfully');

      onOpenChange(false);
      if (onUserUpdated) {
        onUserUpdated();
      }
    } catch (error: any) {
      console.error('Failed to update user:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to update user';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (fetchingUser) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Loading User Data</DialogTitle>
            <DialogDescription>
              Please wait while we fetch the user information...
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit User</DialogTitle>
          <DialogDescription>
            Update user details. Leave password blank to keep current password.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email *</Label>
            <Input
              id="email"
              type="email"
              placeholder="user@example.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="full_name">Full Name *</Label>
            <Input
              id="full_name"
              type="text"
              placeholder="John Doe"
              value={formData.full_name}
              onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">New Password (Optional)</Label>
            <Input
              id="password"
              type="password"
              placeholder="Leave blank to keep current"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Only fill if you want to change the password
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="user_type">User Type *</Label>
            <Select
              value={formData.user_type}
              onValueChange={(value) => setFormData({ ...formData, user_type: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select user type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="tenant_user">Tenant User</SelectItem>
                <SelectItem value="tenant_admin">Tenant Admin</SelectItem>
                <SelectItem value="super_admin">Super Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between space-x-2">
            <Label htmlFor="is_active">Active Status</Label>
            <Switch
              id="is_active"
              checked={formData.is_active}
              onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
            />
          </div>

          <div className="flex items-center justify-between space-x-2">
            <div>
              <Label htmlFor="tfa_required">Require 2FA</Label>
              <p className="text-xs text-muted-foreground mt-1">
                Force user to setup two-factor authentication
              </p>
            </div>
            <Switch
              id="tfa_required"
              checked={formData.tfa_required}
              onCheckedChange={(checked) => setFormData({ ...formData, tfa_required: checked })}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Update User
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}