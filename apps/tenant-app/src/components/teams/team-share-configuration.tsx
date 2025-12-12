"use client";

import React, { useState } from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Users, Info } from 'lucide-react';
import Link from 'next/link';

export interface TeamShare {
  team_id: string;
  user_permissions: Record<string, 'read' | 'edit'>;
}

interface TeamShareConfigurationProps {
  userTeams: Array<{
    id: string;
    name: string;
    description?: string;
    user_permission?: string;
    is_owner?: boolean;
    can_manage?: boolean;
  }>;
  value: TeamShare[];
  onChange: (shares: TeamShare[]) => void;
  disabled?: boolean;
}

export function TeamShareConfiguration({
  userTeams,
  value = [],
  onChange,
  disabled = false,
}: TeamShareConfigurationProps) {
  const [selectedTeamIds, setSelectedTeamIds] = useState<Set<string>>(
    new Set(value.map((s) => s.team_id))
  );

  // Filter teams where user has 'share' permission, is owner, or can manage
  const shareableTeams = userTeams?.filter(
    (t) => t.user_permission === 'share' || t.user_permission === 'manager' || t.is_owner || t.can_manage
  ) || [];

  // Handle team selection
  const handleTeamToggle = (teamId: string, checked: boolean) => {
    const newSelected = new Set(selectedTeamIds);

    if (checked) {
      newSelected.add(teamId);
      // Add team with empty permissions (backend will auto-populate with 'read' for all members)
      const existingShare = value.find((s) => s.team_id === teamId);
      if (!existingShare) {
        onChange([...value, { team_id: teamId, user_permissions: {} }]);
      }
    } else {
      newSelected.delete(teamId);
      // Remove team from shares
      onChange(value.filter((s) => s.team_id !== teamId));
    }

    setSelectedTeamIds(newSelected);
  };

  if (shareableTeams.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-6 text-center">
        <Users className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground">
          You don't have permission to share to any teams yet.
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Contact a team owner to get sharing permissions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Info Message */}
      <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
        <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-sm text-blue-800">
            Team members will have <strong>read access by default</strong> when you share to a team.
          </p>
          <p className="text-xs text-blue-700 mt-1">
            For fine-grained permission control (edit access, custom permissions), manage them in{' '}
            <Link href="/teams" className="underline font-medium">
              Team Management
            </Link>.
          </p>
        </div>
      </div>

      {/* Team Selection */}
      <div>
        <Label className="text-sm font-medium mb-2 block">
          Select Teams to Share With
        </Label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {shareableTeams.map((team) => (
            <div
              key={team.id}
              className="flex items-center space-x-2 rounded-md border p-3 hover:bg-accent transition-colors"
            >
              <Checkbox
                id={`team-${team.id}`}
                checked={selectedTeamIds.has(team.id)}
                onCheckedChange={(checked) =>
                  handleTeamToggle(team.id, checked as boolean)
                }
                disabled={disabled}
              />
              <label
                htmlFor={`team-${team.id}`}
                className="flex-1 text-sm font-medium leading-none cursor-pointer"
              >
                {team.name}
                {team.is_owner && (
                  <Badge variant="secondary" className="ml-2 text-xs">
                    Owner
                  </Badge>
                )}
              </label>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
