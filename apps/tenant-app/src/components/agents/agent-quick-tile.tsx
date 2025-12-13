'use client';

import React from 'react';
import { Bot, Calendar } from 'lucide-react';
import { cn, formatDateOnly, cleanModelName } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import type { EnhancedAgent } from '@/services/agents-enhanced';

export interface AgentQuickTileProps {
  agent: EnhancedAgent;
  onSelect: (agent: EnhancedAgent) => void;
  className?: string;
}

/**
 * Quick View Agent Tile - Read-only, clickable card for dashboard
 *
 * Displays: Agent Name, Description, Created Date, Updated Date
 * No edit/delete buttons - focused on quick access
 * Dynamic grid layout (responsive, auto-fit)
 */
export function AgentQuickTile({
  agent,
  onSelect,
  className = ''
}: AgentQuickTileProps) {
  return (
    <div
      className={cn(
        'group bg-gt-white border rounded-xl p-5 cursor-pointer transition-all duration-200',
        'hover:shadow-lg hover:border-gt-green hover:-translate-y-1',
        'flex flex-col',
        className
      )}
      onClick={() => onSelect(agent)}
    >
      {/* Header with Name */}
      <div className="mb-3">
        <h3 className="font-bold text-lg text-gray-900 group-hover:text-gt-green transition-colors break-words">
          {agent.name}
        </h3>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 mb-4 flex-1 break-words">
        {agent.description || 'No description provided'}
      </p>

      {/* Dates */}
      <div className="flex items-center gap-2 text-xs text-gray-500 pt-3 border-t">
        <Calendar className="w-3.5 h-3.5" />
        <span>Created {formatDateOnly(agent.created_at)}</span>
        <span>•</span>
        <span>Updated {formatDateOnly(agent.updated_at)}</span>
      </div>

      {/* Category and Tags */}
      {(agent.category || (agent.tags && agent.tags.length > 0)) && (
        <div className="pt-3 border-t mt-3 space-y-2">
          {agent.category && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-700">Category:</span>
              <Badge variant="secondary" className="text-xs">
                {agent.category}
              </Badge>
            </div>
          )}
          {agent.tags && agent.tags.length > 0 && (
            <div className="flex items-start gap-2">
              <span className="text-xs font-medium text-gray-700 shrink-0 mt-0.5">Tags:</span>
              <div className="flex flex-wrap gap-1.5 flex-1">
                {agent.tags.map((tag, idx) => (
                  <Badge key={idx} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
