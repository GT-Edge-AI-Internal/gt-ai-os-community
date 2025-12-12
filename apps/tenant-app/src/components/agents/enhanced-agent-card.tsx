'use client';

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AgentAvatar } from './agent-avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Globe, Lock, Users, Star, MessageSquare,
  GitFork, MoreVertical, Shield, Database, Settings,
  Play, Edit, Trash2, ExternalLink,
  TrendingUp, Clock, Zap, AlertCircle, Download
} from 'lucide-react';
import { cn, formatDateOnly } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { citationCard, scaleOnHover, staggerItem } from '@/lib/animations/gt-animations';
import { exportAgent } from '@/services/agents';

interface EnhancedAgentCardProps {
  agent: {
    id: string;
    name: string;
    description: string;
    disclaimer?: string;
    category: string;
    customCategory?: string;
    visibility: 'private' | 'team' | 'public';
    featured: boolean;
    personalityType: 'geometric' | 'organic' | 'minimal' | 'technical';
    personalityProfile?: any;
    customAvatarUrl?: string;
    examplePrompts: Array<{ text: string; category: string; expectedBehavior?: string }>;
    datasetConnection: 'all' | 'none' | 'selected';
    selectedDatasetIds?: string[];
    modelParameters: {
      temperature: number;
      maxTokens: number;
      maxHistoryItems?: number;
      topP?: number;
    };
    usageCount: number;
    averageRating?: number;
    tags: string[];
    canFork: boolean;
    owner: {
      id: string;
      name: string;
      avatar?: string;
    };
    safetyFlags?: string[];
    version: number;
    createdAt: string;
    updatedAt: string;
    lastUsedAt?: string;
  };
  onSelect: (agent: any) => void;
  onFork?: (agent: any) => void;
  onEdit?: (agent: any) => void;
  onDelete?: (agent: any) => void;
  onShare?: (agent: any) => void;
  isOwner?: boolean;
  canExport?: boolean;  // New prop for export permission
  showAnalytics?: boolean;
  view?: 'grid' | 'list';
  className?: string;
}

export function EnhancedAgentCard({
  agent,
  onSelect,
  onFork,
  onEdit,
  onDelete,
  onShare,
  isOwner = false,
  canExport = false,
  showAnalytics = false,
  view = 'grid',
  className
}: EnhancedAgentCardProps) {
  const [showExamples, setShowExamples] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
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

  const getVisibilityIcon = () => {
    switch (agent.visibility) {
      case 'private': return <Lock className="w-3 h-3 text-gray-500" />;
      case 'team': return <Users className="w-3 h-3 text-blue-500" />;
      case 'public': return <Globe className="w-3 h-3 text-green-500" />;
    }
  };

  const getVisibilityBadge = () => {
    const variants = {
      private: 'bg-gray-100 text-gray-700',
      team: 'bg-blue-100 text-blue-700',
      public: 'bg-green-100 text-green-700'
    };
    return (
      <Badge className={`${variants[agent.visibility]} text-xs`}>
        {getVisibilityIcon()}
        <span className="ml-1 capitalize">{agent.visibility}</span>
      </Badge>
    );
  };

  const getDatasetBadge = () => {
    switch (agent.datasetConnection) {
      case 'all': 
        return <Badge variant="default" className="text-xs bg-gt-green/10 text-gt-green border-gt-green/20">
          <Database className="w-3 h-3 mr-1" />
          All Datasets
        </Badge>;
      case 'none': 
        return <Badge variant="secondary" className="text-xs">
          No RAG
        </Badge>;
      case 'selected': 
        return (
          <Badge variant="secondary" className="text-xs">
            <Database className="w-3 h-3 mr-1" />
            {agent.selectedDatasetIds?.length || 0} Datasets
          </Badge>
        );
    }
  };

  const formatLastUsed = (dateString?: string) => {
    if (!dateString) return 'Never used';
    
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) return 'Less than an hour ago';
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    
    return formatDateOnly(date);
  };

  const getRatingStars = (rating?: number) => {
    if (!rating) return null;
    
    return (
      <div className="flex items-center gap-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star
            key={i}
            className={cn(
              'w-3 h-3',
              i < Math.floor(rating) 
                ? 'text-yellow-400 fill-current' 
                : 'text-gray-300'
            )}
          />
        ))}
        <span className="text-xs text-gray-500 ml-1">{rating.toFixed(1)}</span>
      </div>
    );
  };

  // List view rendering
  if (view === 'list') {
    return (
      <motion.div
        variants={staggerItem}
        className={cn(
          "bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-gt-green transition-all duration-200",
          className
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <div className="flex items-center gap-4">
          {/* Avatar */}
          <AgentAvatar
            personality={agent.personalityType}
            state="idle"
            size="small"
            confidence={1}
            customImageUrl={agent.customAvatarUrl}
          />

          {/* Main Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                {agent.name}
              </h3>
              {agent.featured && (
                <Badge className="bg-gradient-to-r from-yellow-400 to-orange-500 text-white text-xs px-2 py-0">
                  ⭐ Featured
                </Badge>
              )}
              {getVisibilityBadge()}
              {agent.visibility === 'team' && agent.team_shares && agent.team_shares.length > 0 && (
                <>
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
                </>
              )}
            </div>
            
            <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-1 mb-2">
              {agent.description}
            </p>
            
            <div className="flex items-center gap-4 text-xs text-gray-500">
              <span className="flex items-center gap-1">
                <MessageSquare className="w-3 h-3" />
                {agent.usageCount.toLocaleString()} uses
              </span>
              {agent.averageRating && (
                <div className="flex items-center gap-1">
                  {getRatingStars(agent.averageRating)}
                </div>
              )}
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatLastUsed(agent.lastUsedAt)}
              </span>
            </div>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-1 max-w-40">
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

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => onSelect(agent)}
              className="bg-gt-green hover:bg-gt-green/90"
            >
              Use Agent
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" size="sm">
                  <MoreVertical className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {isOwner && (
                  <>
                    <DropdownMenuItem onClick={() => onEdit?.(agent)}>
                      <Edit className="w-4 h-4 mr-2" />
                      Edit Agent
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => onDelete?.(agent)} className="text-red-600">
                      <Trash2 className="w-4 h-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                  </>
                )}
                {agent.canFork && (
                  <DropdownMenuItem onClick={() => onFork?.(agent)}>
                    <GitFork className="w-4 h-4 mr-2" />
                    Fork Agent
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onClick={() => onShare?.(agent)}>
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Share
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </motion.div>
    );
  }

  // Grid view rendering (default)
  return (
    <TooltipProvider>
      <motion.div
        variants={citationCard}
        className={cn('relative group h-full', className)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        whileHover={{ y: -4, scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
      >
        <Card className="h-full overflow-hidden border-2 transition-all duration-300 hover:border-gt-green hover:shadow-xl">
          {/* Featured Badge */}
          {agent.featured && (
            <div className="absolute top-0 right-0 bg-gradient-to-r from-yellow-400 to-orange-500 text-white text-xs px-3 py-1 rounded-bl-lg z-10">
              ⭐ Featured
            </div>
          )}

          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-3 flex-1">
                {/* Avatar with custom image support */}
                <div className="relative">
                  <AgentAvatar
                    personality={agent.personalityType}
                    state="idle"
                    size="medium"
                    confidence={1}
                    customImageUrl={agent.customAvatarUrl}
                    onClick={() => setShowExamples(!showExamples)}
                  />
                  
                  {/* Personality indicator */}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-gt-green rounded-full flex items-center justify-center">
                        <div className={cn(
                          'w-2 h-2 rounded-sm',
                          agent.personalityType === 'geometric' && 'bg-white rotate-45',
                          agent.personalityType === 'organic' && 'bg-white rounded-full',
                          agent.personalityType === 'minimal' && 'bg-white',
                          agent.personalityType === 'technical' && 'bg-white'
                        )} />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="capitalize">{agent.personalityType} personality</p>
                    </TooltipContent>
                  </Tooltip>
                </div>
                
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-lg leading-tight truncate">
                    {agent.name}
                  </CardTitle>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    <Badge variant="secondary" className="text-xs">
                      {agent.category}
                    </Badge>
                    {getVisibilityBadge()}
                    {agent.visibility === 'team' && agent.team_shares && agent.team_shares.length > 0 && (
                      <>
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
                      </>
                    )}
                    <span className="text-xs text-gray-500">v{agent.version}</span>
                  </div>
                </div>
              </div>

              {/* Action Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="z-[100] bg-white">
                  {isOwner && (
                    <>
                      <DropdownMenuItem onClick={() => onEdit?.(agent)}>
                        <Edit className="w-4 h-4 mr-2" />
                        Edit Agent
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => {}}>
                        <TrendingUp className="w-4 h-4 mr-2" />
                        View Analytics
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onDelete?.(agent)} className="text-red-600">
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  {canExport && (
                    <>
                      <DropdownMenuItem onClick={handleExportDownload} disabled={isExporting}>
                        <Download className="w-4 h-4 mr-2" />
                        {isExporting ? 'Exporting...' : 'Export CSV'}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  {agent.canFork && (
                    <DropdownMenuItem onClick={() => onFork?.(agent)}>
                      <GitFork className="w-4 h-4 mr-2" />
                      Fork Agent
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onClick={() => onShare?.(agent)}>
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Share Agent
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardHeader>

          <CardContent className="pt-0 space-y-3">
            {/* Description */}
            <CardDescription className="text-sm text-gray-600 line-clamp-2">
              {agent.description}
            </CardDescription>

            {/* Disclaimer */}
            {agent.disclaimer && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-2">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-3 h-3 text-amber-600 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-amber-800 dark:text-amber-200">
                    {agent.disclaimer}
                  </p>
                </div>
              </div>
            )}

            {/* Model Parameters & Dataset Info */}
            <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
              <div className="flex items-center gap-1">
                <span>🌡️ Temp: {agent.modelParameters.temperature}</span>
              </div>
              <div className="flex items-center gap-1">
                <span>📝 Tokens: {agent.modelParameters.maxTokens}</span>
              </div>
            </div>

            <div className="flex items-center justify-between">
              {getDatasetBadge()}
              {agent.safetyFlags && agent.safetyFlags.length > 0 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex items-center gap-1 text-xs text-green-600">
                      <Shield className="w-3 h-3" />
                      <span>{agent.safetyFlags.length}</span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{agent.safetyFlags.length} safety filters active</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>

            {/* Example Prompts */}
            <AnimatePresence>
              {showExamples && agent.examplePrompts.length > 0 && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="space-y-2"
                >
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    Example Prompts:
                  </p>
                  {agent.examplePrompts.slice(0, 2).map((example, idx) => (
                    <div 
                      key={idx}
                      className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2 text-xs text-gray-600 dark:text-gray-400 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                      onClick={() => onSelect(agent)}
                    >
                      "{example.text}"
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Tags */}
            {agent.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {agent.tags.slice(0, 4).map(tag => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    #{tag}
                  </Badge>
                ))}
                {agent.tags.length > 4 && (
                  <Badge variant="secondary" className="text-xs">
                    +{agent.tags.length - 4}
                  </Badge>
                )}
              </div>
            )}

            {/* Stats & Rating */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-gray-500">
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <MessageSquare className="w-3 h-3" />
                    {agent.usageCount.toLocaleString()}
                  </span>
                  {agent.averageRating && (
                    <div className="flex items-center gap-1">
                      {getRatingStars(agent.averageRating)}
                    </div>
                  )}
                </div>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatLastUsed(agent.lastUsedAt)}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t border-gray-100 dark:border-gray-800">
              <Button
                size="sm"
                onClick={() => onSelect(agent)}
                className="flex-1 bg-gt-green hover:bg-gt-green/90"
              >
                <Play className="w-3 h-3 mr-1" />
                Use Agent
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setShowExamples(!showExamples)}
              >
                Examples
              </Button>
              {isOwner && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onEdit?.(agent)}
                >
                  <Settings className="w-3 h-3" />
                </Button>
              )}
            </div>

            {/* Owner Info */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-800">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <div className="w-4 h-4 rounded-full bg-gradient-to-br from-gt-green to-gt-blue flex items-center justify-center text-white text-[8px] font-semibold">
                  {agent.owner.name.charAt(0).toUpperCase()}
                </div>
                <span>by {agent.owner.name}</span>
              </div>
              <span className="text-xs text-gray-400">
                {formatDateOnly(agent.createdAt)}
              </span>
            </div>
          </CardContent>

          {/* Hover Analytics Preview */}
          {showAnalytics && isHovered && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-4 text-white rounded-b-lg"
            >
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="text-center">
                  <p className="opacity-70">Avg Response</p>
                  <p className="font-semibold">1.2s</p>
                </div>
                <div className="text-center">
                  <p className="opacity-70">Success Rate</p>
                  <p className="font-semibold">98.5%</p>
                </div>
                <div className="text-center">
                  <p className="opacity-70">Active Users</p>
                  <p className="font-semibold">342</p>
                </div>
              </div>
            </motion.div>
          )}
        </Card>
      </motion.div>
    </TooltipProvider>
  );
}