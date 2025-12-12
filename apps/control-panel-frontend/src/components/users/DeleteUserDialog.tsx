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
import { Alert } from '@/components/ui/alert';
import { usersApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { Loader2, AlertTriangle } from 'lucide-react';

interface DeleteUserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: {
    id: number;
    email: string;
    full_name: string;
    user_type: string;
  } | null;
  onUserDeleted?: () => void;
}

export default function DeleteUserDialog({ open, onOpenChange, user, onUserDeleted }: DeleteUserDialogProps) {
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    if (!user) return;

    setLoading(true);
    try {
      await usersApi.delete(user.id);
      toast.success('User permanently deleted');

      onOpenChange(false);
      if (onUserDeleted) {
        onUserDeleted();
      }
    } catch (error: any) {
      console.error('Failed to delete user:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to delete user';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  if (!user) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <span>Permanently Delete User</span>
          </DialogTitle>
          <DialogDescription>
            This action cannot be undone. The user will be permanently deleted from the system.
          </DialogDescription>
        </DialogHeader>

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <div className="ml-2">
            <p className="font-medium">Warning: This is permanent!</p>
            <p className="text-sm mt-1">
              All user data, including conversations, documents, and settings will be permanently deleted.
              This action cannot be undone.
            </p>
          </div>
        </Alert>

        <div className="space-y-2 bg-muted p-4 rounded-md">
          <div>
            <span className="text-sm font-medium">Name:</span>
            <span className="ml-2 text-sm">{user.full_name}</span>
          </div>
          <div>
            <span className="text-sm font-medium">Email:</span>
            <span className="ml-2 text-sm">{user.email}</span>
          </div>
          <div>
            <span className="text-sm font-medium">User Type:</span>
            <span className="ml-2 text-sm capitalize">{user.user_type.replace('_', ' ')}</span>
          </div>
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
          <Button
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={loading}
          >
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Permanently Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}