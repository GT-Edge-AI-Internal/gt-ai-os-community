'use client';

import { useState } from 'react';
import {
  Bot,
  Star,
  Edit,
  Trash2,
  Lock,
  Users,
  Globe,
  MessageSquare,
  Database as DatabaseIcon,
  Calendar,
  Download
} from 'lucide-react';
import { cn, formatDateOnly, cleanModelName } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { EnhancedAgent } from '@/services/agents-enhanced';
import { exportAgent } from '@/services/agents';

export interface AgentCardProps {
  agent: EnhancedAgent;
  onSelect?: (agent: EnhancedAgent) => void;
  onEdit?: (agent: EnhancedAgent) => void;
  onDelete?: (agent: EnhancedAgent) => void;
  canExport?: boolean;
  className?: string;
}

export function AgentCard({
  agent,
  onSelect,
  onEdit,
  onDelete,
  canExport = false,
  className = ''
}: AgentCardProps) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExportDownload = async () => {
    setIsExporting(true);
    try {
      await exportAgent(agent.id, 'download');
    } catch (error) {
      console.error('Export failed:', error);
      alert(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsExporting(false);
    }
  };
  // Debug logging
  if (agent.visibility === 'organization') {
    console.log('🔐 AgentCard rendering:', agent.name, {
      can_edit: agent.can_edit,
      can_delete: agent.can_delete,
      is_owner: agent.is_owner,
      visibility: agent.visibility
    });
  }

  const getAccessIcon = (visibility?: string) => {
    switch (visibility) {
      case 'individual': return <Lock className="w-3 h-3" />;
      case 'team': return <Users className="w-3 h-3" />;
      case 'organization': return <Globe className="w-3 h-3" />;
      default: return <Lock className="w-3 h-3" />;
    }
  };

  const getAccessColor = (visibility?: string) => {
    switch (visibility) {
      case 'individual': return 'text-gray-600';
      case 'team': return 'text-blue-600';
      case 'organization': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  const getAccessLabel = (visibility?: string) => {
    switch (visibility) {
      case 'individual': return 'Myself';
      case 'team': return 'Team';
      case 'organization': return 'Organization';
      default: return 'Private';
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Unknown';
    return formatDateOnly(dateString);
  };

  return (
    <div
      className={cn(
        'bg-white border rounded-lg p-4 hover:shadow-md transition-all duration-200 flex flex-col lg:flex-row lg:items-center gap-4 lg:gap-6 cursor-pointer',
        className
      )}
      onClick={() => onSelect?.(agent)}
    >
      {/* Agent Name and Basic Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <h3 className="text-base font-bold text-gray-900 break-words min-w-0">{agent.name}</h3>
          {agent.featured && (
            <Star className="w-4 h-4 text-yellow-500 fill-current flex-shrink-0" />
          )}
          {agent.is_owner && (
            <Badge className="bg-gt-green text-white text-xs flex-shrink-0">You</Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
          <div className={cn(
            'flex items-center gap-1',
            getAccessColor(agent.visibility)
          )}>
            {getAccessIcon(agent.visibility)}
            <span>{getAccessLabel(agent.visibility)}</span>
          </div>
          {agent.visibility === 'team' && agent.team_shares && agent.team_shares.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {agent.team_shares.slice(0, 2).map((share) => (
                <Badge key={share.team_id} variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                  {share.team_name}
                </Badge>
              ))}
              {agent.team_shares.length > 2 && (
                <Badge variant="outline" className="text-xs bg-blue-100 text-blue-800 border-blue-300">
                  +{agent.team_shares.length - 2} more
                </Badge>
              )}
            </div>
          )}
          {agent.owner_name && (
            <>
              <span>•</span>
              <span className={agent.is_owner ? "font-semibold text-gt-green" : ""}>
                {agent.owner_name}
              </span>
            </>
          )}
          {agent.category && (
            <>
              <span>•</span>
              <span>{agent.category}</span>
            </>
          )}
          {agent.model_id && (
            <>
              <span>•</span>
              <span>{cleanModelName(agent.model_id)}</span>
            </>
          )}
        </div>
        {agent.description && (
          <p className="text-xs text-gray-500 mt-0.5 break-words">{agent.description}</p>
        )}
        {/* Tags Display */}
        {agent.tags && agent.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {agent.tags.slice(0, 3).map(tag => (
              <Badge key={tag} variant="secondary" className="text-xs">
                #{tag}
              </Badge>
            ))}
            {agent.tags.length > 3 && (
              <Badge variant="secondary" className="text-xs">
                +{agent.tags.length - 3}
              </Badge>
            )}
          </div>
        )}
      </div>

      {/* Stats - Compact Inline */}
      <div className="flex items-center flex-wrap gap-4 text-sm lg:flex-nowrap">
        <div className="text-center min-w-[80px]">
          <p className="font-semibold text-gray-900">{agent.usage_count || 0}</p>
          <p className="text-xs text-gray-500">Conversations</p>
        </div>
        <div className="text-center min-w-[60px]">
          <p className="font-semibold text-gray-900">{agent.selected_dataset_ids?.length || 0}</p>
          <p className="text-xs text-gray-500">Datasets</p>
        </div>
        <div className="text-center min-w-[80px]">
          <p className="font-semibold text-gray-900">{formatDate(agent.created_at)}</p>
          <p className="text-xs text-gray-500">Created</p>
        </div>
        <div className="text-center min-w-[80px]">
          <p className="font-semibold text-gray-900">{formatDate(agent.updated_at)}</p>
          <p className="text-xs text-gray-500">Updated</p>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-1 lg:ml-auto">
        {agent.can_edit && (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onEdit?.(agent);
            }}
            className="p-2 h-auto text-gray-400 hover:text-blue-600 hover:bg-blue-50"
            title="Edit agent"
          >
            <Edit className="w-4 h-4" />
          </Button>
        )}
        {agent.can_delete && (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onDelete?.(agent);
            }}
            className="p-2 h-auto text-gray-400 hover:text-red-600 hover:bg-red-50"
            title="Archive agent"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        )}
        {canExport && (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              handleExportDownload();
            }}
            disabled={isExporting}
            className="p-2 h-auto text-gray-400 hover:text-gt-green hover:bg-gt-green/10"
            title="Export agent CSV"
          >
            <Download className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  );
}