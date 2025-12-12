"use client";

import { useState } from 'react';
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
import { usersApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { Loader2 } from 'lucide-react';

interface AddUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUserAdded?: () => void;
}

export default function AddUserDialog({ open, onOpenChange, onUserAdded }: AddUserDialogProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    user_type: 'tenant_user',
    tenant_id: '1', // Auto-select test_company tenant for GT AI OS Local
    tfa_required: false,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.email || !formData.full_name || !formData.password) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (!formData.password) {
      toast.error('Password cannot be empty');
      return;
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      toast.error('Please enter a valid email address');
      return;
    }

    // tenant_id is auto-assigned to test_company for GT AI OS Local

    setLoading(true);
    try {
      const payload = {
        email: formData.email,
        full_name: formData.full_name,
        password: formData.password,
        user_type: formData.user_type,
        tenant_id: formData.tenant_id ? parseInt(formData.tenant_id) : null,
        tfa_required: formData.tfa_required,
      };

      await usersApi.create(payload);
      toast.success('User created successfully');

      // Reset form
      setFormData({
        email: '',
        full_name: '',
        password: '',
        user_type: 'tenant_user',
        tenant_id: '1', // Auto-select test_company tenant for GT AI OS Local
        tfa_required: false,
      });

      onOpenChange(false);
      if (onUserAdded) {
        onUserAdded();
      }
    } catch (error: any) {
      console.error('Failed to create user:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to create user';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Add New User</DialogTitle>
          <DialogDescription>
            Create a new user account. All fields are required.
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
            <Label htmlFor="password">Password *</Label>
            <Input
              id="password"
              type="password"
              placeholder="Enter password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required
            />
            <p className="text-xs text-muted-foreground">
              Cannot be empty
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

          <div className="flex items-center space-x-2 pt-2">
            <input
              id="tfa_required"
              type="checkbox"
              checked={formData.tfa_required}
              onChange={(e) => setFormData({ ...formData, tfa_required: e.target.checked })}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Label htmlFor="tfa_required" className="cursor-pointer font-normal">
              Require 2FA for this user
            </Label>
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
              Create User
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}