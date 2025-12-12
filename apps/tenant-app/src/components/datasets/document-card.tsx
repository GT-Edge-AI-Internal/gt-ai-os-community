'use client';

import { useState } from 'react';
import { 
  FileText, 
  Download, 
  Eye, 
  Trash2, 
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  MoreHorizontal,
  Copy,
  Share
} from 'lucide-react';
import { cn, formatDateOnly, formatFileSize } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Progress } from '@/components/ui/progress';

interface Document {
  id: string;
  filename: string;
  original_name: string;
  file_type: string;
  file_size_bytes: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  chunk_count?: number;
  vector_count?: number;
  error_message?: string;
  created_at: string;
  processed_at?: string;
  content_preview?: string;
  dataset_name?: string;
  processing_progress?: number;
}

interface DocumentCardProps {
  document: Document;
  onView?: (documentId: string) => void;
  onDownload?: (documentId: string) => void;
  onDelete?: (documentId: string) => void;
  onReprocess?: (documentId: string) => void;
  onShare?: (documentId: string) => void;
  showDataset?: boolean;
  className?: string;
}

export function DocumentCard({
  document,
  onView,
  onDownload,
  onDelete,
  onReprocess,
  onShare,
  showDataset = false,
  className = ''
}: DocumentCardProps) {
  const [isProcessing, setIsProcessing] = useState(document.processing_status === 'processing');

  const getFileTypeIcon = (fileType: string) => {
    // You can expand this to show different icons for different file types
    return <FileText className="w-6 h-6 text-blue-500" />;
  };

  const getStatusIcon = (status: Document['processing_status']) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case 'processing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getStatusColor = (status: Document['processing_status']) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'processing':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
    }
  };


  const formatDate = (dateString: string) => {
    return formatDateOnly(dateString);
  };

  return (
    <div className={cn(
      'bg-white border rounded-lg p-4 hover:shadow-md transition-all duration-200',
      isProcessing && 'border-blue-300 bg-blue-50/30',
      document.processing_status === 'failed' && 'border-red-300 bg-red-50/30',
      className
    )}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="flex-shrink-0">
            {getFileTypeIcon(document.file_type)}
          </div>
          
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate text-sm" title={document.original_name}>
              {document.original_name}
            </h3>
            <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
              <span className="uppercase font-medium">{document.file_type}</span>
              <span>•</span>
              <span>{formatFileSize(document.file_size_bytes)}</span>
              <span>•</span>
              <span>{formatDate(document.created_at)}</span>
            </div>
            
            {showDataset && document.dataset_name && (
              <div className="mt-1">
                <Badge variant="outline" className="text-xs">
                  {document.dataset_name}
                </Badge>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onView?.(document.id)}
            className="p-1 h-auto text-gray-400 hover:text-gray-600"
            title="View document"
          >
            <Eye className="w-4 h-4" />
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="p-1 h-auto text-gray-400 hover:text-gray-600"
              >
                <MoreHorizontal className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onDownload?.(document.id)}>
                <Download className="w-4 h-4 mr-2" />
                Download
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onShare?.(document.id)}>
                <Share className="w-4 h-4 mr-2" />
                Share
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigator.clipboard.writeText(document.id)}>
                <Copy className="w-4 h-4 mr-2" />
                Copy ID
              </DropdownMenuItem>
              {document.processing_status === 'failed' && (
                <DropdownMenuItem onClick={() => onReprocess?.(document.id)}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Reprocess
                </DropdownMenuItem>
              )}
              <DropdownMenuItem 
                onClick={() => onDelete?.(document.id)}
                className="text-red-600 hover:text-red-700"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Processing Status */}
      <div className="mb-3">
        <div className={cn(
          'flex items-center gap-2 px-2 py-1 rounded-md border text-xs font-medium',
          getStatusColor(document.processing_status)
        )}>
          {getStatusIcon(document.processing_status)}
          <span className="capitalize">{document.processing_status}</span>
          
          {document.processing_status === 'completed' && document.processed_at && (
            <span className="text-gray-500">
              • {formatDate(document.processed_at)}
            </span>
          )}
        </div>

        {/* Processing Progress */}
        {isProcessing && document.processing_progress !== undefined && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
              <span>Processing...</span>
              <span>{Math.round(document.processing_progress)}%</span>
            </div>
            <Progress value={document.processing_progress} className="h-1" />
          </div>
        )}

        {/* Error Message */}
        {document.processing_status === 'failed' && document.error_message && (
          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
            <p className="font-medium">Processing failed:</p>
            <p className="mt-1">{document.error_message}</p>
          </div>
        )}
      </div>

      {/* Stats */}
      {document.processing_status === 'completed' && (
        <div className="flex items-center justify-between text-xs text-gray-600 mb-3">
          <div className="flex items-center gap-4">
            {document.chunk_count !== undefined && (
              <span>{document.chunk_count.toLocaleString()} chunks</span>
            )}
            {document.vector_count !== undefined && (
              <span>{document.vector_count.toLocaleString()} vectors</span>
            )}
          </div>
        </div>
      )}

      {/* Content Preview */}
      {document.content_preview && (
        <div className="mt-3 p-3 bg-gray-50 rounded-md">
          <p className="text-xs text-gray-700 line-clamp-3">
            {document.content_preview}
          </p>
        </div>
      )}

      {/* Footer Actions */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100 mt-3">
        <div className="text-xs text-gray-500">
          ID: {document.id.substring(0, 8)}...
        </div>
        
        <div className="flex items-center gap-1">
          {document.processing_status === 'completed' && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDownload?.(document.id)}
                className="text-xs px-2 py-1 h-auto"
              >
                Download
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onView?.(document.id)}
                className="text-xs px-2 py-1 h-auto"
              >
                View
              </Button>
            </>
          )}
          
          {document.processing_status === 'failed' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onReprocess?.(document.id)}
              className="text-xs px-2 py-1 h-auto"
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              Retry
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}