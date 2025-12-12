'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn, formatStorageSize } from '@/lib/utils';
import {
  Database,
  Layers,
  Brain,
  Plus,
  X,
  Search,
  FileText,
  Clock,
  CheckCircle2,
  Settings,
  Info,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface RAGDataset {
  id: string;
  name: string;
  description: string;
  document_count: number;
  chunk_count: number;
  vector_count: number;
  embedding_model: string;
  created_at: string;
  updated_at: string;
  status: 'active' | 'processing' | 'inactive';
  storage_size_mb: number;
}

interface SelectedContext {
  dataset_id: string;
  search_mode: 'semantic' | 'hybrid' | 'keyword';
  max_results: number;
  relevance_threshold: number;
}

interface ContextSelectorProps {
  selectedContexts: SelectedContext[];
  onContextChange: (contexts: SelectedContext[]) => void;
  disabled?: boolean;
  className?: string;
}

export function ContextSelector({ 
  selectedContexts, 
  onContextChange, 
  disabled = false,
  className 
}: ContextSelectorProps) {
  const [datasets, setDatasets] = useState<RAGDataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [expandedDataset, setExpandedDataset] = useState<string | null>(null);

  // Mock data for development
  useEffect(() => {
    const mockDatasets: RAGDataset[] = [
      {
        id: 'ds_1',
        name: 'Company Policies',
        description: 'HR policies, handbooks, and company guidelines',
        document_count: 12,
        chunk_count: 234,
        vector_count: 234,
        embedding_model: 'BAAI/bge-m3',
        created_at: '2024-01-10T09:00:00Z',
        updated_at: '2024-01-15T10:32:15Z',
        status: 'active',
        storage_size_mb: 15.7,
      },
      {
        id: 'ds_2',
        name: 'Technical Documentation',
        description: 'API docs, technical specifications, and architecture guides',
        document_count: 8,
        chunk_count: 156,
        vector_count: 156,
        embedding_model: 'BAAI/bge-m3',
        created_at: '2024-01-12T14:30:00Z',
        updated_at: '2024-01-15T11:15:00Z',
        status: 'processing',
        storage_size_mb: 8.2,
      },
      {
        id: 'ds_3',
        name: 'Project Documents',
        description: 'Project proposals, meeting notes, and planning documents',
        document_count: 5,
        chunk_count: 67,
        vector_count: 67,
        embedding_model: 'BAAI/bge-m3',
        created_at: '2024-01-08T11:00:00Z',
        updated_at: '2024-01-14T16:21:30Z',
        status: 'active',
        storage_size_mb: 4.1,
      },
      {
        id: 'ds_4',
        name: 'Customer Support',
        description: 'Support tickets, knowledge base articles, and FAQ documents',
        document_count: 18,
        chunk_count: 412,
        vector_count: 412,
        embedding_model: 'BAAI/bge-m3',
        created_at: '2024-01-05T08:00:00Z',
        updated_at: '2024-01-16T09:45:00Z',
        status: 'active',
        storage_size_mb: 22.3,
      },
    ];

    setDatasets(mockDatasets);
    setLoading(false);
  }, []);

  const filteredDatasets = datasets.filter(dataset =>
    dataset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    dataset.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isDatasetSelected = (datasetId: string) => {
    return selectedContexts.some(context => context.dataset_id === datasetId);
  };

  const getSelectedContext = (datasetId: string) => {
    return selectedContexts.find(context => context.dataset_id === datasetId);
  };

  const toggleDataset = (dataset: RAGDataset) => {
    if (disabled) return;

    const isSelected = isDatasetSelected(dataset.id);
    
    if (isSelected) {
      // Remove dataset from selection
      onContextChange(selectedContexts.filter(ctx => ctx.dataset_id !== dataset.id));
    } else {
      // Add dataset with default settings
      const newContext: SelectedContext = {
        dataset_id: dataset.id,
        search_mode: 'semantic',
        max_results: 5,
        relevance_threshold: 0.7,
      };
      onContextChange([...selectedContexts, newContext]);
    }
  };

  const updateContextSettings = (datasetId: string, updates: Partial<SelectedContext>) => {
    if (disabled) return;

    onContextChange(
      selectedContexts.map(ctx =>
        ctx.dataset_id === datasetId ? { ...ctx, ...updates } : ctx
      )
    );
  };

  const getDatasetIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case 'processing':
        return <Clock className="h-4 w-4 text-blue-600 animate-pulse" />;
      case 'inactive':
        return <X className="h-4 w-4 text-gray-400" />;
      default:
        return <Database className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      active: 'bg-green-100 text-green-800',
      processing: 'bg-blue-100 text-blue-800',
      inactive: 'bg-gray-100 text-gray-800',
    };

    return (
      <Badge className={variants[status as keyof typeof variants] || variants.inactive}>
        {status}
      </Badge>
    );
  };

  if (loading) {
    return (
      <Card className={cn("w-full", className)}>
        <CardHeader>
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
            <div className="h-3 bg-gray-200 rounded w-1/2"></div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="animate-pulse flex items-center space-x-3">
                <div className="w-4 h-4 bg-gray-200 rounded"></div>
                <div className="flex-1">
                  <div className="h-3 bg-gray-200 rounded w-3/4 mb-1"></div>
                  <div className="h-2 bg-gray-200 rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center space-x-2">
            <Brain className="h-4 w-4 text-purple-600" />
            <span>Knowledge Context</span>
            {selectedContexts.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {selectedContexts.length} selected
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="h-6 px-2 text-xs"
          >
            <Settings className="h-3 w-3 mr-1" />
            Settings
          </Button>
        </div>
        <p className="text-xs text-gray-600">
          Select datasets to provide context for your conversation
        </p>

        {/* Search */}
        <div className="relative mt-3">
          <Search className="h-3 w-3 text-gray-400 absolute left-2 top-1/2 transform -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-7 pr-3 py-1.5 text-xs border border-gray-300 rounded-md focus:ring-1 focus:ring-gt-green focus:border-transparent"
            disabled={disabled}
          />
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {filteredDatasets.length === 0 ? (
          <div className="text-center py-6">
            <Database className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-xs text-gray-500">No datasets found</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {filteredDatasets.map((dataset) => {
              const isSelected = isDatasetSelected(dataset.id);
              const selectedContext = getSelectedContext(dataset.id);
              const isExpanded = expandedDataset === dataset.id;

              return (
                <div key={dataset.id} className="space-y-2">
                  {/* Dataset Item */}
                  <div
                    className={cn(
                      "flex items-start space-x-3 p-2 rounded-lg border cursor-pointer transition-all",
                      isSelected
                        ? "bg-gt-green/5 border-gt-green/20"
                        : "bg-white border-gray-200 hover:bg-gray-50",
                      disabled && "opacity-50 cursor-not-allowed"
                    )}
                    onClick={() => toggleDataset(dataset)}
                  >
                    <div className="flex-shrink-0 mt-0.5">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        readOnly
                        className="h-3 w-3 text-gt-green focus:ring-gt-green border-gray-300 rounded"
                      />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getDatasetIcon(dataset.status)}
                          <h4 className="text-xs font-medium text-gray-900 truncate">
                            {dataset.name}
                          </h4>
                          {getStatusBadge(dataset.status)}
                        </div>
                        
                        {isSelected && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
                              e.stopPropagation();
                              setExpandedDataset(isExpanded ? null : dataset.id);
                            }}
                            className="h-5 w-5 p-0 hover:bg-gray-200"
                          >
                            {isExpanded ? (
                              <ChevronDown className="h-3 w-3" />
                            ) : (
                              <ChevronRight className="h-3 w-3" />
                            )}
                          </Button>
                        )}
                      </div>

                      <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                        {dataset.description}
                      </p>

                      <div className="flex items-center space-x-3 mt-2 text-xs text-gray-500">
                        <span className="flex items-center space-x-1">
                          <FileText className="h-3 w-3" />
                          <span>{dataset.document_count}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Layers className="h-3 w-3" />
                          <span>{dataset.chunk_count}</span>
                        </span>
                        <span className="flex items-center space-x-1">
                          <Brain className="h-3 w-3" />
                          <span>{dataset.vector_count}</span>
                        </span>
                        <span>{formatStorageSize(dataset.storage_size_mb)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Advanced Settings */}
                  {isSelected && isExpanded && selectedContext && showAdvanced && (
                    <div className="ml-6 p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <h5 className="text-xs font-medium text-gray-700 mb-3">Search Settings</h5>
                      
                      <div className="space-y-3">
                        {/* Search Mode */}
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">Search Mode</label>
                          <select
                            value={selectedContext.search_mode}
                            onChange={(e) => updateContextSettings(dataset.id, {
                              search_mode: e.target.value as 'semantic' | 'hybrid' | 'keyword'
                            })}
                            className="w-full text-xs border border-gray-300 rounded px-2 py-1 focus:ring-1 focus:ring-gt-green focus:border-transparent"
                            disabled={disabled}
                          >
                            <option value="semantic">Semantic (AI-powered)</option>
                            <option value="hybrid">Hybrid (Semantic + Keyword)</option>
                            <option value="keyword">Keyword (Traditional)</option>
                          </select>
                        </div>

                        {/* Max Results */}
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">
                            Max Results: {selectedContext.max_results}
                          </label>
                          <input
                            type="range"
                            min="1"
                            max="20"
                            value={selectedContext.max_results}
                            onChange={(e) => updateContextSettings(dataset.id, {
                              max_results: parseInt(e.target.value)
                            })}
                            className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                            disabled={disabled}
                          />
                        </div>

                        {/* Relevance Threshold */}
                        <div>
                          <label className="text-xs text-gray-600 block mb-1">
                            Relevance Threshold: {selectedContext.relevance_threshold.toFixed(2)}
                          </label>
                          <input
                            type="range"
                            min="0.1"
                            max="1.0"
                            step="0.05"
                            value={selectedContext.relevance_threshold}
                            onChange={(e) => updateContextSettings(dataset.id, {
                              relevance_threshold: parseFloat(e.target.value)
                            })}
                            className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                            disabled={disabled}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Info Footer */}
        {selectedContexts.length > 0 && (
          <div className="mt-4 p-2 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-start space-x-2">
              <Info className="h-3 w-3 text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-blue-700">
                Context from {selectedContexts.length} dataset{selectedContexts.length > 1 ? 's' : ''} will be 
                automatically included in your conversation to provide relevant information.
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}