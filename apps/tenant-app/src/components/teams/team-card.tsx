'use client';

import {
  Users,
  Edit3,
  Trash2,
  Crown,
  LogOut
} from 'lucide-react';
import { cn, formatDateTime } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { Team } from '@/services';

export interface TeamCardProps {
  team: Team;
  onManage?: (teamId: string) => void;
  onEdit?: (teamId: string) => void;
  onDelete?: (teamId: string) => void;
  onLeave?: (teamId: string) => void;
  className?: string;
}

export function TeamCard({
  team,
  onManage,
  onEdit,
  onDelete,
  onLeave,
  className = ''
}: TeamCardProps) {
  return (
    <div
      className={cn(
        'bg-gt-white border rounded-lg p-4 hover:shadow-md transition-all duration-200 cursor-pointer',
        className
      )}
      onClick={() => onManage?.(team.id)}
    >
      {/* Multi-breakpoint Responsive Grid */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] lg:grid-cols-[1fr_auto_auto] gap-x-4 gap-y-3 items-center">
        {/* Left Section: Team Name and Info */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="text-base font-bold text-gray-900 truncate flex items-center gap-2">
              <Users className="w-4 h-4 text-gt-green flex-shrink-0" />
              {team.name}
            </h3>
            {team.is_owner && (
              <Badge className="bg-gt-green text-white text-xs flex-shrink-0 flex items-center gap-1">
                <Crown className="w-3 h-3" />
                Owner
              </Badge>
            )}
          </div>
          {team.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{team.description}</p>
          )}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-600 mt-1">
            {team.owner_name && (
              <span className="text-gray-600">
                Owner: <span className="font-medium">{team.owner_name}</span>
              </span>
            )}
            <span className="text-gray-400">•</span>
            <span className="text-gray-400">Created {formatDateTime(team.created_at)}</span>
          </div>
        </div>

        {/* Middle Section: Stats */}
        <div className="flex items-center gap-3 md:gap-4 justify-start md:justify-end">
          <div className="text-center">
            <p className="font-semibold text-gray-900 text-sm">{team.member_count}</p>
            <p className="text-xs text-gray-500 whitespace-nowrap">
              {team.member_count === 1 ? 'Member' : 'Members'}
            </p>
          </div>
        </div>

        {/* Right Section: Actions */}
        <div className="flex items-center gap-2 justify-start md:justify-end md:col-start-2 lg:col-start-3">
          {/* Updated Date */}
          <div className="text-xs text-gray-500 lg:max-w-[100px] lg:text-right leading-tight">
            Updated {formatDateTime(team.updated_at)}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-1 flex-shrink-0">
            {team.can_manage ? (
              <>
                {/* Edit Button - Owner/Admin only */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit?.(team.id);
                  }}
                  className="p-2 h-auto text-gray-400 hover:text-green-600 hover:bg-green-50"
                  title="Edit team"
                >
                  <Edit3 className="w-4 h-4" />
                </Button>

                {/* Delete Button - Owner/Admin only */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete?.(team.id);
                  }}
                  className="p-2 h-auto text-gray-400 hover:text-red-600 hover:bg-red-50"
                  title="Delete team"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </>
            ) : (
              <>
                {/* Leave Button - Members only (not owner) */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onLeave?.(team.id);
                  }}
                  className="p-2 h-auto text-gray-400 hover:text-orange-600 hover:bg-orange-50"
                  title="Leave team"
                >
                  <LogOut className="w-4 h-4" />
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
