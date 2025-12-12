'use client';

import React, { useState, useMemo, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import {
  Bot,
  Plus,
  Star,
  Search,
  Filter,
  ChevronDown
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AgentCard } from './agent-card';
import type { EnhancedAgent, AgentCategory } from '@/services/agents-enhanced';

// Dynamically import configuration panel for better performance
const AgentConfigurationPanel = dynamic(
  () => import('./agent-configuration-panel').then(mod => ({ default: mod.AgentConfigurationPanel })),
  { ssr: false }
);

interface AgentGalleryProps {
  agents: EnhancedAgent[];
  onSelectAgent: (agent: EnhancedAgent) => void;
  onCreateAgent?: (agentData: any) => Promise<void>;
  onEditAgent?: (agentData: any) => Promise<void>;
  onDeleteAgent?: (agentId: string) => Promise<void>;
  onDuplicateAgent?: (agent: EnhancedAgent) => Promise<void>;
  onViewHistory?: (agent: EnhancedAgent) => void;
  className?: string;
  hideHeader?: boolean;
  triggerCreate?: boolean;
  onTriggerComplete?: () => void;
}

type SortBy = 'name' | 'created_at' | 'usage_count' | 'average_rating';

export function AgentGallery({ 
  agents, 
  onSelectAgent, 
  onCreateAgent, 
  onEditAgent,
  onDeleteAgent,
  onDuplicateAgent,
  onViewHistory,
  className,
  hideHeader = false,
  triggerCreate = false,
  onTriggerComplete
}: AgentGalleryProps) {
  // Removed showCreateModal state - using only showConfigPanel
  const [showConfigPanel, setShowConfigPanel] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [editingAgent, setEditingAgent] = useState<EnhancedAgent | null>(null);
  
  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTag, setSelectedTag] = useState<string>('all');
  const [selectedCreator, setSelectedCreator] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortBy>('created_at');

  // Handle external trigger to create agent
  useEffect(() => {
    if (triggerCreate) {
      handleOpenCreateAgent();
      onTriggerComplete?.();
    }
  }, [triggerCreate]);

  // Extract unique categories, tags, and creators for filters
  const { categories, tags, creators } = useMemo(() => {
    const categorySet = new Set<string>();
    const tagSet = new Set<string>();
    const creatorSet = new Set<string>();

    agents.forEach(agent => {
      if (agent.category) categorySet.add(agent.category);
      agent.tags?.forEach(tag => tagSet.add(tag));
      if (agent.owner_name) creatorSet.add(agent.owner_name);
    });

    return {
      categories: Array.from(categorySet).sort(),
      tags: Array.from(tagSet).sort(),
      creators: Array.from(creatorSet).sort()
    };
  }, [agents]);

  // Filter and sort agents
  const filteredAndSortedAgents = useMemo(() => {
    let filtered = agents.filter(agent => {
      // Search filter
      const matchesSearch = !searchQuery ||
        agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));

      // Category filter
      const matchesCategory = selectedCategory === 'all' || agent.category === selectedCategory;

      // Tag filter
      const matchesTag = selectedTag === 'all' || agent.tags?.includes(selectedTag);

      // Creator filter
      const matchesCreator = selectedCreator === 'all' || agent.owner_name === selectedCreator;

      return matchesSearch && matchesCategory && matchesTag && matchesCreator;
    });

    // Sort agents
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'usage_count':
          return (b.usage_count || 0) - (a.usage_count || 0);
        case 'average_rating':
          return (b.average_rating || 0) - (a.average_rating || 0);
        case 'created_at':
        default:
          return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
      }
    });

    return filtered;
  }, [agents, searchQuery, selectedCategory, selectedTag, selectedCreator, sortBy]);

  const handleCreateAgent = async (agentData: any) => {
    if (!onCreateAgent) return;
    
    try {
      setIsCreating(true);
      await onCreateAgent(agentData);
      setShowConfigPanel(false);
    } catch (error) {
      console.error('Failed to create agent:', error);
    } finally {
      setIsCreating(false);
    }
  };

  const handleOpenCreateAgent = () => {
    console.log('🔧 Create Agent button clicked');
    setEditingAgent(null);
    setShowConfigPanel(true);
    console.log('🔧 showConfigPanel set to:', true);
  };

  const handleSaveAgent = async (agentData: Partial<EnhancedAgent>) => {
    if (editingAgent) {
      // Edit existing agent - merge with original agent data and include ID
      const updateData = {
        ...agentData,
        id: editingAgent.id // Ensure ID is included for update
      };
      await onEditAgent?.(updateData);
    } else {
      // Create new agent
      await onCreateAgent?.(agentData);
    }
    setShowConfigPanel(false);
    setEditingAgent(null);
  };

  const handleAgentAction = async (action: string, agent: EnhancedAgent, event: React.MouseEvent) => {
    event.stopPropagation();

    switch (action) {
      case 'edit':
        setEditingAgent(agent);
        setShowConfigPanel(true);
        break;
      case 'delete':
        if (confirm(`Are you sure you want to archive "${agent.name}"? This will hide it from view but preserve it for audit trail purposes.`)) {
          await onDeleteAgent?.(agent.id);
        }
        break;
    }
  };
  if (filteredAndSortedAgents.length === 0 && agents.length === 0) {
    return (
      <div className={cn("space-y-6", className)}>
        {/* Search and Filters - show even when no agents */}
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 z-10" />
            <Input
              placeholder="Search agents..."
              value={searchQuery}
              onChange={(value) => setSearchQuery(value)}
              className="pl-10"
              clearable
            />
          </div>

          {/* Filters */}
          <div className="flex gap-2 items-center">
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map(category => (
                  <SelectItem key={category} value={category}>
                    {category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedTag} onValueChange={setSelectedTag}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Tag" />
              </SelectTrigger>
              <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                <SelectItem value="all">All Tags</SelectItem>
                {tags.map(tag => (
                  <SelectItem key={tag} value={tag}>
                    {tag}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedCreator} onValueChange={setSelectedCreator}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Creator" />
              </SelectTrigger>
              <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                <SelectItem value="all">All Creators</SelectItem>
                {creators.map(creator => (
                  <SelectItem key={creator} value={creator}>
                    {creator}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortBy)}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                <SelectItem value="created_at">Date Created</SelectItem>
                <SelectItem value="name">Name</SelectItem>
                <SelectItem value="usage_count">Usage</SelectItem>
                <SelectItem value="average_rating">Rating</SelectItem>
              </SelectContent>
            </Select>

          </div>
        </div>

        {/* Empty State */}
        <div className="flex flex-col items-center justify-center py-16">
          <div className="text-center max-w-md">
            <Bot className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No agents yet
            </h3>
            <p className="text-gray-600">
              Create your first AI agent to get started with intelligent conversations and automation. Use the "Create Agent" button in the top right corner.
            </p>
          </div>
        </div>
        
        {/* Configuration Panel - unified creation interface */}
        {console.log('🔧 Empty state - Rendering AgentConfigurationPanel with showConfigPanel:', showConfigPanel)}
        <AgentConfigurationPanel
          agent={editingAgent || undefined}
          agents={agents}
          isOpen={showConfigPanel}
          onClose={() => {
            console.log('🔧 Empty state - Closing configuration panel');
            setShowConfigPanel(false);
            setEditingAgent(null);
          }}
          onSave={handleSaveAgent}
          mode={editingAgent ? 'edit' : 'create'}
        />
      </div>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header - only show if not hidden */}
      {!hideHeader && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                <Bot className="w-8 h-8 text-gt-green" />
                Your Agents
              </h1>
              <p className="text-gray-600 mt-1">
                {filteredAndSortedAgents.length} of {agents.length} agents
              </p>
            </div>
            <Button onClick={handleOpenCreateAgent} className="bg-gt-green hover:bg-gt-green/90">
              <Plus className="w-4 h-4 mr-2" />
              Create Agent
            </Button>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 z-10" />
          <Input
            placeholder="Search agents..."
            value={searchQuery}
            onChange={(value) => setSearchQuery(value)}
            className="pl-10"
            clearable
          />
        </div>

        {/* Filters */}
        <div className="flex gap-2 items-center">
          <Select value={selectedCategory} onValueChange={setSelectedCategory}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
              <SelectItem value="all">All Categories</SelectItem>
              {categories.map(category => (
                <SelectItem key={category} value={category}>
                  {category}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedTag} onValueChange={setSelectedTag}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Tag" />
            </SelectTrigger>
            <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
              <SelectItem value="all">All Tags</SelectItem>
              {tags.map(tag => (
                <SelectItem key={tag} value={tag}>
                  {tag}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={selectedCreator} onValueChange={setSelectedCreator}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Creator" />
            </SelectTrigger>
            <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
              <SelectItem value="all">All Creators</SelectItem>
              {creators.map(creator => (
                <SelectItem key={creator} value={creator}>
                  {creator}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortBy)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
              <SelectItem value="created_at">Date Created</SelectItem>
              <SelectItem value="name">Name</SelectItem>
              <SelectItem value="usage_count">Usage</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* No Results */}
      {filteredAndSortedAgents.length === 0 && agents.length > 0 && (
        <div className="text-center py-12">
          <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No agents found</h3>
          <p className="text-gray-600">Try adjusting your search or filter criteria.</p>
        </div>
      )}

      {/* Agent List */}
      <div className="space-y-3">
        {filteredAndSortedAgents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            onSelect={onSelectAgent}
            onEdit={(agent) => {
              setEditingAgent(agent);
              setShowConfigPanel(true);
            }}
            onDelete={(agent) => {
              if (confirm(`Are you sure you want to archive "${agent.name}"?`)) {
                onDeleteAgent?.(agent.id);
              }
            }}
            canExport={agent.is_owner || false}
          />
        ))}
      </div>

      {/* Agent Configuration Panel - unified creation and editing interface */}
      {console.log('🔧 Rendering AgentConfigurationPanel with showConfigPanel:', showConfigPanel)}
      <AgentConfigurationPanel
        agent={editingAgent || undefined}
        agents={agents}
        isOpen={showConfigPanel}
        onClose={() => {
          console.log('🔧 Closing configuration panel');
          setShowConfigPanel(false);
          setEditingAgent(null);
        }}
        onSave={handleSaveAgent}
        mode={editingAgent ? 'edit' : 'create'}
      />
    </div>
  );
}