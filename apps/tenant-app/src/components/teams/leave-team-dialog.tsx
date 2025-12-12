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

interface LeaveTeamDialogProps {
  open: boolean;
  team: Team | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (teamId: string) => Promise<void>;
  loading?: boolean;
}

export function LeaveTeamDialog({
  open,
  team,
  onOpenChange,
  onConfirm,
  loading = false
}: LeaveTeamDialogProps) {
  const handleConfirm = async () => {
    if (!team) return;

    try {
      await onConfirm(team.id);
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to leave team:', error);
    }
  };

  if (!team) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
            </div>
            <DialogTitle className="text-xl">Leave Team</DialogTitle>
          </div>
          <DialogDescription className="text-base">
            Are you sure you want to leave <strong className="text-gray-900">{team.name}</strong>?
          </DialogDescription>
        </DialogHeader>

        <div className="px-6 pb-4">
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
            <p className="text-sm text-orange-900 font-medium mb-2">
              After leaving this team, you will:
            </p>
            <ul className="text-sm text-orange-800 space-y-1 list-disc list-inside">
              <li>Lose access to all shared agents and datasets</li>
              <li>No longer see team resources in your workspace</li>
              <li>Need a new invitation to rejoin this team</li>
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
            className="bg-orange-600 hover:bg-orange-700 text-white"
          >
            {loading ? 'Leaving...' : 'Leave Team'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
