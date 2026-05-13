'use client';

import React, { useState, useMemo } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetBody,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Search, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EnhancedAgent } from '@/services/agents-enhanced';

export interface FavoriteAgentSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  agents: EnhancedAgent[];
  currentFavorites: string[];
  onSave: (favoriteIds: string[]) => Promise<void>;
}

type SortBy = 'name' | 'created_at';

/**
 * Favorite Agent Selector Modal
 *
 * Allows users to select which agents appear on their Quick View dashboard.
 * Multi-select with search/filter capability.
 */
export function FavoriteAgentSelectorModal({
  isOpen,
  onClose,
  agents,
  currentFavorites,
  onSave
}: FavoriteAgentSelectorModalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>(currentFavorites);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortBy>('name');
  const [isSaving, setIsSaving] = useState(false);

  // Reset selections when modal opens with new currentFavorites
  React.useEffect(() => {
    if (isOpen) {
      setSelectedIds(currentFavorites);
      setSearchQuery('');
      setSelectedCategory('all');
    }
  }, [isOpen, currentFavorites]);

  // Extract unique categories
  const categories = useMemo(() => {
    const categorySet = new Set<string>();
    agents.forEach(agent => {
      if (agent.category) categorySet.add(agent.category);
    });
    return Array.from(categorySet).sort();
  }, [agents]);

  // Filter and sort agents
  const filteredAgents = useMemo(() => {
    let filtered = agents.filter(agent => {
      // Search filter
      const matchesSearch = !searchQuery ||
        agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        agent.description?.toLowerCase().includes(searchQuery.toLowerCase());

      // Category filter
      const matchesCategory = selectedCategory === 'all' || agent.category === selectedCategory;

      return matchesSearch && matchesCategory;
    });

    // Sort agents
    filtered.sort((a, b) => {
      if (sortBy === 'name') {
        return a.name.localeCompare(b.name);
      } else {
        return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
      }
    });

    return filtered;
  }, [agents, searchQuery, selectedCategory, sortBy]);

  const handleToggleAgent = (agentId: string) => {
    setSelectedIds(prev =>
      prev.includes(agentId)
        ? prev.filter(id => id !== agentId)
        : [...prev, agentId]
    );
  };

  const handleSelectAll = () => {
    const allIds = filteredAgents.map(a => a.id);
    setSelectedIds(allIds);
  };

  const handleDeselectAll = () => {
    setSelectedIds([]);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(selectedIds);
      onClose();
    } catch (error) {
      console.error('Failed to save favorite agents:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setSelectedIds(currentFavorites);
    onClose();
  };

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && handleCancel()}>
      <SheetContent side="right" className="flex flex-col w-full sm:max-w-2xl">
        <SheetHeader onClose={handleCancel}>
          <SheetTitle>Add Favorite Agents</SheetTitle>
          <SheetDescription>
            Select agents from the catalog to add to your Favorites for quick access. You can select multiple agents.
          </SheetDescription>
        </SheetHeader>

        <SheetBody className="flex flex-col gap-4">
          {/* Search and Filters */}
          <div className="flex flex-col gap-3">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 z-10" />
              <Input
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(value: string) => setSearchQuery(value)}
                className="pl-10"
                clearable
              />
            </div>

            <div className="flex gap-2">
              {/* Category Filter */}
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent className="z-[100] backdrop-blur-sm bg-gt-white/95 border shadow-lg" position="popper" sideOffset={5}>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map(category => (
                    <SelectItem key={category} value={category}>
                      {category}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Sort */}
              <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortBy)}>
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent className="z-[100] backdrop-blur-sm bg-gt-white/95 border shadow-lg" position="popper" sideOffset={5}>
                  <SelectItem value="name">Name</SelectItem>
                  <SelectItem value="created_at">Date Created</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center justify-between py-2 border-y">
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleSelectAll}>
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={handleDeselectAll}>
                Deselect All
              </Button>
            </div>
            <div className="text-sm text-gray-600">
              {selectedIds.length} of {filteredAgents.length} selected
            </div>
          </div>

          {/* Agent List */}
          <div className="flex-1 overflow-y-auto border rounded-lg">
            {filteredAgents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <p className="text-gray-600">No agents found matching your filters.</p>
              </div>
            ) : (
              <div className="divide-y">
                {filteredAgents.map((agent) => {
                  const isSelected = selectedIds.includes(agent.id);
                  return (
                    <div
                      key={agent.id}
                      className={cn(
                        'flex items-center gap-4 p-4 cursor-pointer hover:bg-gray-50 transition-colors',
                        isSelected && 'bg-gt-green/5 hover:bg-gt-green/10'
                      )}
                      onClick={() => handleToggleAgent(agent.id)}
                    >
                      {/* Checkbox */}
                      <div
                        className={cn(
                          'flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors',
                          isSelected
                            ? 'bg-gt-green border-gt-green'
                            : 'border-gray-300 hover:border-gt-green'
                        )}
                      >
                        {isSelected && <Check className="w-3.5 h-3.5 text-white" />}
                      </div>

                      {/* Agent Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold text-gray-900">{agent.name}</h4>
                          {agent.category && (
                            <span className="text-xs text-gray-500">• {agent.category}</span>
                          )}
                        </div>
                        {agent.description && (
                          <p className="text-sm text-gray-600 line-clamp-1 mt-0.5">
                            {agent.description}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </SheetBody>

        <SheetFooter>
          <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving} className="bg-gt-green hover:bg-gt-green/90">
            {isSaving ? 'Saving...' : 'Save Selection'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
