'use client';

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Search, Database, Users, Calendar } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';

interface Dataset {
  id: string;
  name: string;
  description?: string;
  document_count: number;
  created_at: string;
  updated_at: string;
  is_public: boolean;
  total_chunks?: number;
}

interface DatasetSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedDatasets: string[];
  onSelectionChange: (datasetIds: string[]) => void;
  availableDatasets: Dataset[];
  title?: string;
  description?: string;
  allowMultiple?: boolean;
}

export function DatasetSelectorModal({
  isOpen,
  onClose,
  selectedDatasets,
  onSelectionChange,
  availableDatasets,
  title = "Select Datasets",
  description = "Choose which datasets to use for this conversation",
  allowMultiple = true
}: DatasetSelectorModalProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'mine' | 'shared'>('all');
  const [localSelectedDatasets, setLocalSelectedDatasets] = useState<string[]>(selectedDatasets);

  // Update local state when prop changes
  useEffect(() => {
    setLocalSelectedDatasets(selectedDatasets);
  }, [selectedDatasets]);

  // Filter datasets based on search query and filter type
  const filteredDatasets = availableDatasets.filter(dataset => {
    const matchesSearch = dataset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      dataset.description?.toLowerCase().includes(searchQuery.toLowerCase());

    if (filterType === 'mine') {
      return matchesSearch && !dataset.is_public;
    } else if (filterType === 'shared') {
      return matchesSearch && dataset.is_public;
    }

    return matchesSearch;
  });

  const handleDatasetToggle = (datasetId: string, checked: boolean) => {
    if (!allowMultiple) {
      // Single selection mode
      setLocalSelectedDatasets(checked ? [datasetId] : []);
    } else {
      // Multiple selection mode
      if (checked) {
        setLocalSelectedDatasets(prev => [...prev, datasetId]);
      } else {
        setLocalSelectedDatasets(prev => prev.filter(id => id !== datasetId));
      }
    }
  };

  const handleConfirm = () => {
    onSelectionChange(localSelectedDatasets);
    onClose();
  };

  const handleCancel = () => {
    // Reset local state to original selection
    setLocalSelectedDatasets(selectedDatasets);
    onClose();
  };

  const handleSelectAll = () => {
    if (allowMultiple) {
      setLocalSelectedDatasets(filteredDatasets.map(d => d.id));
    }
  };

  const handleClearAll = () => {
    setLocalSelectedDatasets([]);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-600" />
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription>
              {description}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col space-y-4">
          {/* Search and Controls */}
          <div className="space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 z-10" />
              <Input
                placeholder="Search datasets..."
                value={searchQuery}
                onChange={(value) => setSearchQuery(value)}
                className="pl-10"
                clearable
              />
            </div>

            {/* Filter Buttons */}
            <div className="flex gap-2">
              <Button
                variant={filterType === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('all')}
              >
                All
              </Button>
              <Button
                variant={filterType === 'mine' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('mine')}
              >
                My Datasets
              </Button>
              <Button
                variant={filterType === 'shared' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType('shared')}
              >
                Shared
              </Button>
            </div>

            {allowMultiple && (
              <div className="flex items-center justify-between">
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSelectAll}
                    disabled={filteredDatasets.length === 0}
                  >
                    Select All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleClearAll}
                    disabled={localSelectedDatasets.length === 0}
                  >
                    Clear All
                  </Button>
                </div>
                <div className="text-sm text-gray-600">
                  {localSelectedDatasets.length} of {filteredDatasets.length} selected
                </div>
              </div>
            )}
          </div>

          {/* Dataset List */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-2">
            {filteredDatasets.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Database className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p>No datasets found</p>
                {searchQuery && (
                  <p className="text-sm">Try adjusting your search terms</p>
                )}
              </div>
            ) : (
              filteredDatasets.map((dataset) => {
                const isSelected = localSelectedDatasets.includes(dataset.id);

                return (
                  <div
                    key={dataset.id}
                    className={`p-3 rounded-lg border transition-colors cursor-pointer ${
                      isSelected
                        ? 'border-blue-200 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                    onClick={() => handleDatasetToggle(dataset.id, !isSelected)}
                  >
                    <div className="flex items-start gap-3">
                      <Checkbox
                        checked={isSelected}
                        onChange={(checked) => handleDatasetToggle(dataset.id, checked)}
                        className="mt-1"
                        onClick={(e) => e.stopPropagation()}
                      />

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-gray-900 truncate">
                            {dataset.name}
                          </h4>
                          {dataset.is_public && (
                            <Badge variant="secondary" className="text-xs">
                              <Users className="h-3 w-3 mr-1" />
                              Public
                            </Badge>
                          )}
                        </div>

                        {dataset.description && (
                          <p className="text-sm text-gray-600 mb-2 line-clamp-2">
                            {dataset.description}
                          </p>
                        )}

                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Database className="h-3 w-3" />
                            {dataset.document_count} documents
                          </span>
                          {dataset.total_chunks && (
                            <span>{dataset.total_chunks} chunks</span>
                          )}
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {format(new Date(dataset.created_at), 'MMM d, yyyy')}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
          <Button onClick={handleConfirm}>
            Confirm Selection
            {localSelectedDatasets.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {localSelectedDatasets.length}
              </Badge>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default DatasetSelectorModal;