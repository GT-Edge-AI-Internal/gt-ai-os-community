'use client';

import { useState } from 'react';
import {
  Database,
  FileText,
  Upload,
  FolderOpen,
  Edit3,
  Trash2,
  MoreHorizontal,
  Settings,
  Zap,
  RefreshCw,
  Lock,
  Users,
  Globe
} from 'lucide-react';
import { cn, formatDateTime, formatStorageSize } from '@/lib/utils';
import { getAccessLevelDisplay } from '@/lib/access-helpers';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export interface DatasetCardProps {
  dataset: {
    id: string;
    name: string;
    description?: string;
    owner_name?: string;  // Full name of creator
    access_group: 'individual' | 'team' | 'organization';
    document_count: number;
    chunk_count: number;
    vector_count: number;
    storage_size_mb: number;
    tags: string[];
    created_at: string;
    updated_at: string;
    is_owner: boolean;
    can_edit: boolean;
    can_delete: boolean;
    embedding_model?: string;
    search_method?: 'vector' | 'hybrid' | 'keyword';
    processing_status?: 'idle' | 'processing' | 'failed';
    processing_progress?: number;
    shared_via_team?: boolean;  // Flag for team members viewing shared resources
    team_shares?: Array<{
      team_id: string;
      user_permissions: Record<string, 'read' | 'edit'>;
    }>;
  };
  onView?: (datasetId: string) => void;
  onEdit?: (datasetId: string) => void;
  onDelete?: (datasetId: string) => void;
  onUpload?: (datasetId: string) => void;
  onProcess?: (datasetId: string) => void;
  onReindex?: (datasetId: string) => void;
  className?: string;
}

export function DatasetCard({
  dataset,
  onView,
  onEdit,
  onDelete,
  onUpload,
  onProcess,
  onReindex,
  className = ''
}: DatasetCardProps) {
  const [isProcessing, setIsProcessing] = useState(dataset.processing_status === 'processing');


  const getAccessIcon = (accessGroup: string) => {
    switch (accessGroup) {
      case 'individual': return <Lock className="w-3 h-3" />;
      case 'team': return <Users className="w-3 h-3" />;
      case 'organization': return <Globe className="w-3 h-3" />;
      default: return <Lock className="w-3 h-3" />;
    }
  };

  const getAccessColor = (accessGroup: string) => {
    switch (accessGroup) {
      case 'individual': return 'text-gray-600 bg-gray-50 border-gray-200';
      case 'team': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'organization': return 'text-green-600 bg-green-50 border-green-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getSearchMethodColor = (method?: string) => {
    switch (method) {
      case 'vector': return 'bg-purple-100 text-purple-800';
      case 'hybrid': return 'bg-blue-100 text-blue-800';
      case 'keyword': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };


  // Determine effective access group based on sharing status
  // Check team_shares first (for owners), then shared_via_team (for members), then access_group
  // This provides a fallback for datasets shared before the visibility sync was added
  const effectiveAccessGroup =
    (dataset.team_shares && dataset.team_shares.length > 0) ? 'team' :
    dataset.shared_via_team ? 'team' :
    dataset.access_group;

  return (
    <div
      className={cn(
        'bg-white border rounded-lg p-4 hover:shadow-md transition-all duration-200',
        isProcessing && 'border-blue-300 bg-blue-50/30',
        dataset.processing_status === 'failed' && 'border-red-300 bg-red-50/30',
        className
      )}
    >
      {/* Multi-breakpoint Responsive Grid: Transitions smoothly at each screen size */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] lg:grid-cols-[1fr_auto_auto] gap-x-4 gap-y-3 items-center">
        {/* Left Section: Dataset Name and Basic Info */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="text-base font-bold text-gray-900 truncate">{dataset.name}</h3>
            {dataset.is_owner && (
              <Badge className="bg-gt-green text-white text-xs flex-shrink-0">You</Badge>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-600">
            <div className={cn(
              'flex items-center gap-1',
              getAccessColor(effectiveAccessGroup).replace('bg-', 'text-')
            )}>
              {getAccessIcon(effectiveAccessGroup)}
              <span>{getAccessLevelDisplay(effectiveAccessGroup)}</span>
            </div>
            {effectiveAccessGroup === 'team' && dataset.team_shares && dataset.team_shares.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {dataset.team_shares.slice(0, 2).map((share) => (
                  <Badge key={share.team_id} variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                    {share.team_name}
                  </Badge>
                ))}
                {dataset.team_shares.length > 2 && (
                  <Badge variant="outline" className="text-xs bg-blue-100 text-blue-800 border-blue-300">
                    +{dataset.team_shares.length - 2} more
                  </Badge>
                )}
              </div>
            )}
            {dataset.owner_name && (
              <>
                <span>•</span>
                <span className={dataset.is_owner ? "font-semibold text-gt-green" : ""}>
                  {dataset.owner_name}
                </span>
              </>
            )}
            {dataset.embedding_model && (
              <>
                <span>•</span>
                <span className="truncate">{dataset.embedding_model}</span>
              </>
            )}
          </div>
          {dataset.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{dataset.description}</p>
          )}
        </div>

        {/* Middle Section: Stats - Responsive layout with breakpoints */}
        <div className="flex items-center gap-3 md:gap-4 justify-start md:justify-end">
          <div className="text-center">
            <p className="font-semibold text-gray-900 text-sm">{dataset.document_count}</p>
            <p className="text-xs text-gray-500 whitespace-nowrap">Docs</p>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900 text-sm">{dataset.chunk_count.toLocaleString()}</p>
            <p className="text-xs text-gray-500 whitespace-nowrap">Chunks</p>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900 text-sm">{dataset.vector_count.toLocaleString()}</p>
            <p className="text-xs text-gray-500 whitespace-nowrap">Vectors</p>
          </div>
          <div className="text-center">
            <p className="font-semibold text-gray-900 text-sm">{formatStorageSize(dataset.storage_size_mb)}</p>
            <p className="text-xs text-gray-500 whitespace-nowrap">Storage</p>
          </div>
        </div>

        {/* Right Section: Date and Actions - Joins stats column on md, separates on lg */}
        <div className="flex items-center gap-2 justify-start md:justify-end md:col-start-2 lg:col-start-3">
          {/* Updated Date - wraps naturally based on available space */}
          <div className="text-xs text-gray-500 lg:max-w-[100px] lg:text-right leading-tight">
            Updated {formatDateTime(dataset.updated_at)}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-1 flex-shrink-0">
            {dataset.can_edit && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit?.(dataset.id);
                  }}
                  className="p-2 h-auto text-gray-400 hover:text-blue-600 hover:bg-blue-50"
                  title="Edit dataset"
                >
                  <Edit3 className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onUpload?.(dataset.id);
                  }}
                  className="p-2 h-auto text-gray-400 hover:text-green-600 hover:bg-green-50"
                  title="Upload documents"
                >
                  <Upload className="w-4 h-4" />
                </Button>
              </>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onView?.(dataset.id);
              }}
              className="p-2 h-auto text-gray-400 hover:text-purple-600 hover:bg-purple-50"
              title="View documents"
            >
              <FolderOpen className="w-4 h-4" />
            </Button>
            {dataset.can_delete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete?.(dataset.id);
                }}
                className="p-2 h-auto text-gray-400 hover:text-red-600 hover:bg-red-50"
                title="Delete dataset"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}