'use client';

import { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  Filter,
  List,
  FileSearch,
  Trash2,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  SortAsc,
  SortDesc
} from 'lucide-react';
import { cn, formatDateOnly, formatFileSize } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  file_size_bytes: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count?: number;
  chunks_processed?: number;
  total_chunks_expected?: number;
  processing_progress?: number;
  processing_stage?: string;
  error_message?: string;
  created_at: string;
  processed_at?: string;
  content_preview?: string;
  metadata?: Record<string, any>;
  dataset_id?: string;
}

interface DocumentListProps {
  documents: Document[];
  loading?: boolean;
  onDocumentSummary?: (documentId: string) => void;
  onDocumentDelete?: (documentId: string) => void;
  onDocumentReprocess?: (documentId: string) => void;
  selectedDocuments?: string[];
  onSelectionChange?: (selectedIds: string[]) => void;
  showDatasetColumn?: boolean;
  onRefresh?: () => void;
  className?: string;
}

type ViewMode = 'grid' | 'list';
type SortField = 'name' | 'size' | 'date' | 'status';
type SortOrder = 'asc' | 'desc';

export function DocumentList({
  documents,
  loading = false,
  onDocumentSummary,
  onDocumentDelete,
  onDocumentReprocess,
  selectedDocuments = [],
  onSelectionChange,
  showDatasetColumn = false,
  onRefresh,
  className = ''
}: DocumentListProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Set up polling for documents that are currently processing
  useEffect(() => {
    if (!onRefresh) return;

    const hasProcessingDocuments = documents.some(doc => doc.processing_status === 'processing');

    if (!hasProcessingDocuments) return;

    // Poll every 2 seconds while documents are processing
    const interval = setInterval(() => {
      onRefresh();
    }, 2000);

    return () => clearInterval(interval);
  }, [documents, onRefresh]);

  // Filter documents based on search and filters
  const filteredDocuments = documents
    .filter(doc => {
      const matchesSearch = searchQuery === '' ||
        doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesStatus = statusFilter === 'all' || doc.processing_status === statusFilter;
      const matchesType = typeFilter === 'all' || doc.file_type === typeFilter;
      
      return matchesSearch && matchesStatus && matchesType;
    })
    .sort((a, b) => {
      let aValue: string | number;
      let bValue: string | number;
      
      switch (sortField) {
        case 'name':
          aValue = a.filename.toLowerCase();
          bValue = b.filename.toLowerCase();
          break;
        case 'size':
          aValue = a.file_size_bytes;
          bValue = b.file_size_bytes;
          break;
        case 'date':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'status':
          aValue = a.processing_status;
          bValue = b.processing_status;
          break;
        default:
          return 0;
      }
      
      if (sortOrder === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

  const getStatusIcon = (status: Document['processing_status']) => {
    switch (status) {
      case 'pending': return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'processing': return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed': return <XCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getStatusColor = (status: Document['processing_status']) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'processing': return 'bg-blue-100 text-blue-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
    }
  };


  const getFileIcon = (fileType: string) => {
    // Return appropriate icon based on file type
    return <FileText className="w-5 h-5 text-blue-500" />;
  };

  const renderProcessingProgress = (document: Document) => {
    if (document.processing_status !== 'processing') {
      return null;
    }

    const progress = document.processing_progress || 0;
    const chunksProcessed = document.chunks_processed || 0;
    const totalChunks = document.total_chunks_expected || 0;
    const stage = document.processing_stage || 'Processing...';

    return (
      <div className="space-y-1 mt-2">
        <div className="flex justify-between items-center text-xs">
          <span className="text-gray-600">{stage}</span>
          {totalChunks > 0 && (
            <span className="text-gray-500">
              {chunksProcessed}/{totalChunks} chunks
            </span>
          )}
        </div>
        <Progress value={progress} className="h-1.5" />
        <div className="text-xs text-gray-500">
          {progress}% complete
        </div>
      </div>
    );
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return null;
    return sortOrder === 'asc' ? <SortAsc className="w-4 h-4 ml-1" /> : <SortDesc className="w-4 h-4 ml-1" />;
  };

  const uniqueFileTypes = [...new Set(documents.map(doc => doc.file_type).filter(type => type && typeof type === 'string'))].sort();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gt-green"></div>
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
        <div className="flex flex-col sm:flex-row gap-4 flex-1">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 z-10" />
            <Input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(value) => setSearchQuery(value)}
              className="pl-10"
              clearable
            />
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>

            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {uniqueFileTypes.map(type => (
                  <SelectItem key={type} value={type}>
                    {type.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Sort Controls (List View) */}
      {viewMode === 'list' && (
        <div className="flex items-center gap-4 px-4 py-2 bg-gray-50 rounded-lg text-sm">
          <button
            onClick={() => handleSort('name')}
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            Name{getSortIcon('name')}
          </button>
          <button
            onClick={() => handleSort('size')}
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            Size{getSortIcon('size')}
          </button>
          <button
            onClick={() => handleSort('date')}
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            Date{getSortIcon('date')}
          </button>
          <button
            onClick={() => handleSort('status')}
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            Status{getSortIcon('status')}
          </button>
        </div>
      )}

      {/* Document List */}
        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="divide-y divide-gray-200">
            {filteredDocuments.map((document) => (
              <div key={document.id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {getFileIcon(document.file_type)}
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-gray-900 truncate">
                        {document.original_filename}
                      </p>
                      <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
                        <span>{formatFileSize(document.file_size_bytes)}</span>
                        <span>{formatDateOnly(document.created_at)}</span>
                        {document.chunk_count !== undefined && (
                          <span>{document.chunk_count} chunks</span>
                        )}
                      </div>
                      {renderProcessingProgress(document)}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <Badge className={cn('text-xs', getStatusColor(document.processing_status))}>
                      <span className="flex items-center gap-1">
                        {getStatusIcon(document.processing_status)}
                        {document.processing_status}
                      </span>
                    </Badge>
                    
                    <div className="flex items-center gap-1">
                      {document.processing_status === 'completed' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onDocumentSummary?.(document.id)}
                          className="p-1 h-auto text-blue-600 hover:text-blue-700"
                          title="View summary"
                        >
                          <FileSearch className="w-4 h-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDocumentDelete?.(document.id)}
                        className="p-1 h-auto text-red-600 hover:text-red-700"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

      {filteredDocuments.length === 0 && (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No documents found</h3>
          <p className="text-gray-600">
            {searchQuery || statusFilter !== 'all' || typeFilter !== 'all'
              ? 'No documents match your current filters'
              : 'Upload documents to get started'
            }
          </p>
        </div>
      )}
    </div>
  );
}