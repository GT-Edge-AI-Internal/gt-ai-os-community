'use client';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';
import type { Team } from '@/services';

interface DeleteTeamDialogProps {
  open: boolean;
  team: Team | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (teamId: string) => Promise<void>;
  loading?: boolean;
}

export function DeleteTeamDialog({
  open,
  team,
  onOpenChange,
  onConfirm,
  loading = false
}: DeleteTeamDialogProps) {
  const handleConfirm = async () => {
    if (!team) return;

    try {
      await onConfirm(team.id);
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to delete team:', error);
    }
  };

  if (!team) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <DialogTitle className="text-xl">Delete Team</DialogTitle>
          </div>
          <DialogDescription className="text-base">
            Are you sure you want to delete <strong className="text-gray-900">{team.name}</strong>?
          </DialogDescription>
        </DialogHeader>

        <div className="px-6 pb-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-900 font-medium mb-2">
              This action cannot be undone. This will:
            </p>
            <ul className="text-sm text-red-800 space-y-1 list-disc list-inside">
              <li>Remove all team members ({team.member_count} {team.member_count === 1 ? 'member' : 'members'})</li>
              <li>Remove all shared resources from members</li>
              <li>Permanently delete the team</li>
            </ul>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={loading}
            className="bg-red-600 hover:bg-red-700 text-white"
          >
            {loading ? 'Deleting...' : 'Delete Team'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
