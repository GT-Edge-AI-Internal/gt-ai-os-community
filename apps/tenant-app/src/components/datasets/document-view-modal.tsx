'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, FileText, Download, Eye, Trash2, RefreshCw, Clock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DocumentList } from './document-list';
import { listDocuments, getDocumentsByDataset, deleteDocument } from '@/services/documents';
import type { Document } from '@/services/documents';
import { cn } from '@/lib/utils';

interface DocumentViewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datasetId: string;
  datasetName: string;
  className?: string;
}

interface DocumentStats {
  total: number;
  completed: number;
  processing: number;
  failed: number;
  pending: number;
}

export function DocumentViewModal({
  open,
  onOpenChange,
  datasetId,
  datasetName,
  className = ''
}: DocumentViewModalProps) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<DocumentStats>({
    total: 0,
    completed: 0,
    processing: 0,
    failed: 0,
    pending: 0
  });

  // Load documents when modal opens
  useEffect(() => {
    if (open && datasetId) {
      loadDocuments();
    }
  }, [open, datasetId]);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      // Try to get documents by dataset first, fallback to general list
      let documentsResponse;
      try {
        documentsResponse = await getDocumentsByDataset(datasetId);
      } catch (error) {
        console.warn('getDocumentsByDataset not available, using general list');
        documentsResponse = await listDocuments();
      }

      if (documentsResponse.data) {
        // Filter documents by dataset_id if using general list
        const filteredDocs = documentsResponse.data.filter((doc: Document) =>
          doc.dataset_id === datasetId
        );
        setDocuments(filteredDocs);
        calculateStats(filteredDocs);
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
      setDocuments([]);
      setStats({ total: 0, completed: 0, processing: 0, failed: 0, pending: 0 });
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (docs: Document[]) => {
    const newStats = {
      total: docs.length,
      completed: docs.filter(d => d.processing_status === 'completed').length,
      processing: docs.filter(d => d.processing_status === 'processing').length,
      failed: docs.filter(d => d.processing_status === 'failed').length,
      pending: docs.filter(d => d.processing_status === 'pending').length
    };
    setStats(newStats);
  };

  const handleDocumentView = (documentId: string) => {
    console.log('Viewing document:', documentId);
    // TODO: Implement document preview
  };

  const handleDocumentDownload = (documentId: string) => {
    console.log('Downloading document:', documentId);
    // TODO: Implement document download
  };

  const handleDocumentDelete = async (documentId: string) => {
    if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
      return;
    }

    try {
      const result = await deleteDocument(documentId);
      if (result.error) {
        console.error('Failed to delete document:', result.error);
        alert('Failed to delete document: ' + result.error);
        return;
      }

      console.log('Document deleted successfully:', documentId);
      // Reload documents to reflect the deletion
      await loadDocuments();
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('An error occurred while deleting the document. Please try again.');
    }
  };

  const handleDocumentReprocess = (documentId: string) => {
    console.log('Reprocessing document:', documentId);
    // TODO: Implement document reprocessing
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <FileText className="w-4 h-4 text-green-500" />;
      case 'processing':
        return <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <X className="w-4 h-4 text-red-500" />;
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />;
      default:
        return <FileText className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: string, count: number) => {
    if (count === 0) return null;

    const colors = {
      completed: 'bg-green-100 text-green-700',
      processing: 'bg-blue-100 text-blue-700',
      failed: 'bg-red-100 text-red-700',
      pending: 'bg-yellow-100 text-yellow-700'
    };

    return (
      <Badge className={`${colors[status as keyof typeof colors]} text-xs`}>
        <span className="flex items-center gap-1">
          {getStatusIcon(status)}
          {count} {status}
        </span>
      </Badge>
    );
  };

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 bg-black/50 flex items-center justify-end z-50">
      {/* Modal backdrop */}
      <div className="fixed inset-0" onClick={() => onOpenChange(false)} />

      {/* Modal content - slide in from right */}
      <div className={cn(
        "bg-white h-full w-full max-w-4xl overflow-hidden shadow-xl",
        "transform transition-all duration-300 ease-out",
        "translate-x-0 opacity-100",
        className
      )}>

        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center">
              <FileText className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                Documents in "{datasetName}"
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                {stats.total} total documents
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Status badges */}
            <div className="flex gap-2">
              {getStatusBadge('completed', stats.completed)}
              {getStatusBadge('processing', stats.processing)}
              {getStatusBadge('pending', stats.pending)}
              {getStatusBadge('failed', stats.failed)}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={loadDocuments}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOpenChange(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden h-[calc(100vh-140px)]">
          {loading ? (
            <div className="flex items-center justify-center h-full p-6">
              <div className="flex items-center gap-3">
                <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
                <span className="text-gray-600">Loading documents...</span>
              </div>
            </div>
          ) : (
            <div className="p-6 h-full overflow-y-auto">
              <DocumentList
                documents={documents}
                loading={false}
                onDocumentView={handleDocumentView}
                onDocumentDownload={handleDocumentDownload}
                onDocumentDelete={handleDocumentDelete}
                onDocumentReprocess={handleDocumentReprocess}
                showDatasetColumn={false}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-200 p-6 bg-gray-50">
          <div className="text-sm text-gray-600">
            {stats.total > 0 && (
              <>
                {stats.completed} of {stats.total} documents processed successfully
                {stats.processing > 0 && ` • ${stats.processing} currently processing`}
                {stats.failed > 0 && ` • ${stats.failed} failed`}
              </>
            )}
          </div>

          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="flex items-center gap-2"
          >
            <X className="w-4 h-4" />
            Close
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}