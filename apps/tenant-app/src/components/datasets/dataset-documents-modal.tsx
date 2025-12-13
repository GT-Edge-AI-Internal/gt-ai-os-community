'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, FileText, Clock, CheckCircle, AlertCircle, RefreshCw, Trash2, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { datasetService, documentService, Document, deleteDocument, DocumentStatus } from '@/services';
import { cn, formatDateOnly, formatFileSize } from '@/lib/utils';

interface DatasetDocumentsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datasetId: string | null;
  datasetName?: string;
  initialDocuments?: Document[]; // Documents to display immediately (e.g., from recent upload)
}

// Helper function to get processing stage labels
const getProcessingStageLabel = (stage?: string): string => {
  const labels: Record<string, string> = {
    'extracting': 'Extracting text...',
    'chunking': 'Chunking document...',
    'embedding': 'Embedding chunks...',
    'indexing': 'Indexing vectors...'
  };
  return labels[stage || ''] || 'Processing...';
};

// Helper function to calculate progress with smart fallbacks
const calculateProgress = (doc: Document): number => {
  // Use backend-calculated progress if available
  if (doc.processing_progress != null && doc.processing_progress > 0) {
    return doc.processing_progress;
  }

  // Calculate from chunks
  if (doc.chunks_processed != null && doc.chunk_count != null && doc.chunk_count > 0) {
    const calculated = (doc.chunks_processed / doc.chunk_count) * 100;
    // Always show at least 5% when processing to indicate activity
    return Math.max(5, Math.round(calculated));
  }

  // Show minimal progress during initialization
  return 5;
};

// Processing Timer Component
function ProcessingTimer({ startTime, endTime, status, chunkCount }: { startTime: string; endTime?: string; status: string; chunkCount?: number }) {
  const [duration, setDuration] = useState(() => {
    const start = new Date(startTime).getTime();
    if (status === 'completed' || status === 'failed') {
      const end = endTime ? new Date(endTime).getTime() : Date.now();
      return Math.floor((end - start) / 1000);
    }
    return 0;
  });

  useEffect(() => {
    if (status === 'pending' || status === 'processing') {
      const start = new Date(startTime).getTime();
      const interval = setInterval(() => {
        setDuration(Math.floor((Date.now() - start) / 1000));
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [startTime, status]);

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (status === 'completed') {
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-green-600">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm">Embedded in {formatDuration(duration)}</span>
        </div>
        {chunkCount ? (
          <span className="text-xs text-gray-500">{chunkCount} chunks</span>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-blue-600">
      <RefreshCw className="w-4 h-4 animate-spin" />
      <span className="text-sm">
        {status === 'uploading' ? 'Uploading...' : 'Embedding...'} {formatDuration(duration)}
      </span>
    </div>
  );
}

export function DatasetDocumentsModal({
  open,
  onOpenChange,
  datasetId,
  datasetName,
  initialDocuments
}: DatasetDocumentsModalProps) {
  const [documents, setDocuments] = useState<Document[]>(initialDocuments || []);
  const [loading, setLoading] = useState(false);
  const [deletingDocuments, setDeletingDocuments] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<'all' | DocumentStatus>('all');
  const [modalOpenedAt, setModalOpenedAt] = useState<number | null>(null);

  useEffect(() => {
    if (open && datasetId) {
      // Skip initial fetch if we already have temp documents from upload
      // This prevents the "No documents found" flash when opening with temp docs
      if (!initialDocuments || initialDocuments.length === 0) {
        loadDocuments();
      }
      setModalOpenedAt(Date.now()); // Track when modal opens for aggressive initial polling
    } else {
      setModalOpenedAt(null);
      // Reset to initial documents when modal closes
      setDocuments(initialDocuments || []);
    }
  }, [open, datasetId, initialDocuments]); // Add initialDocuments to dependencies

  // Update documents if initialDocuments changes while modal is open
  useEffect(() => {
    if (initialDocuments && initialDocuments.length > 0) {
      setDocuments(prev => {
        // Merge initial documents with existing, avoiding duplicates
        const existingIds = new Set(prev.map(d => d.id));
        const newDocs = initialDocuments.filter(d => !existingIds.has(d.id));
        return [...newDocs, ...prev];
      });
    }
  }, [initialDocuments]);

  // Poll for updates and check for status changes
  useEffect(() => {
    if (!open || !datasetId) return;

    const hasProcessing = documents.some(d =>
      d.processing_status === 'processing' || d.processing_status === 'pending' || d.processing_status === 'uploading'
    );

    // Determine polling interval:
    // - First 10 seconds after modal opens: 1 second (aggressive for new uploads)
    // - After 10 seconds: 2 seconds if processing, 3 seconds if idle
    const getPollingInterval = () => {
      if (modalOpenedAt && (Date.now() - modalOpenedAt) < 10000) {
        return 1000; // Aggressive 1-second polling for first 10 seconds
      }
      return hasProcessing ? 2000 : 3000; // Normal polling after initial period
    };

    // Always poll when modal is open to catch new uploads
    const interval = setInterval(async () => {
      const response = await documentService.listDocuments({ dataset_id: datasetId });
      if (response.data) {
        setDocuments(prev => {
          // Identify temp documents (IDs starting with 'file-')
          const tempDocs = prev.filter(d => d.id && d.id.toString().startsWith('file-'));

          // Replace temp documents with backend documents when they match by filename
          const backendDocs = response.data.map(backendDoc => {
            const matchingTemp = tempDocs.find(temp =>
              temp.filename === backendDoc.filename ||
              temp.original_filename === backendDoc.original_filename
            );

            // If we found a temp document for this backend document, use backend version
            return backendDoc;
          });

          // Keep temp documents that haven't been uploaded yet (no backend match)
          const stillUploading = tempDocs.filter(temp =>
            !response.data.some(backend =>
              backend.filename === temp.filename ||
              backend.original_filename === temp.original_filename
            )
          );

          // Combine: temp documents still uploading + backend documents
          return [...stillUploading, ...backendDocs];
        });
      }
    }, getPollingInterval());

    return () => clearInterval(interval);
  }, [open, datasetId, documents, modalOpenedAt]);

  const loadDocuments = async () => {
    if (!datasetId) return;

    setLoading(true);
    try {
      const response = await documentService.listDocuments({ dataset_id: datasetId });
      if (response.data) {
        setDocuments(response.data);
      }
    } catch (error) {
      console.error('Error loading documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (documentId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) {
      return;
    }

    setDeletingDocuments(prev => new Set([...prev, documentId]));

    try {
      const response = await deleteDocument(documentId);
      if (response.error) {
        console.error('Failed to delete document:', response.error);
        alert('Failed to delete document: ' + response.error);
      } else {
        // Remove document from local state
        setDocuments(prev => prev.filter(doc => doc.id !== documentId));
        console.log('Document deleted successfully');
      }
    } catch (error) {
      console.error('Error deleting document:', error);
      alert('Failed to delete document. Please try again.');
    } finally {
      setDeletingDocuments(prev => {
        const newSet = new Set(prev);
        newSet.delete(documentId);
        return newSet;
      });
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'processing':
        return <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-600" />;
      case 'pending':
      default:
        return <Clock className="w-4 h-4 text-yellow-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-100 text-green-800 border-green-200">Processed</Badge>;
      case 'processing':
        return <Badge className="bg-blue-100 text-blue-800 border-blue-200">Processing</Badge>;
      case 'failed':
        return <Badge className="bg-red-100 text-red-800 border-red-200">Failed</Badge>;
      case 'pending':
      default:
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">Pending</Badge>;
    }
  };


  const statusCounts = documents.reduce((acc, doc) => {
    acc[doc.processing_status || 'pending'] = (acc[doc.processing_status || 'pending'] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Handle ESC key to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) {
        onOpenChange(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onOpenChange]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[60]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => onOpenChange(false)}
          />

          {/* Shelf Panel */}
          <motion.div
            key="panel"
            className="fixed right-0 top-0 h-screen w-full max-w-3xl bg-gt-white shadow-2xl z-[60] overflow-hidden flex flex-col"
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              height: '100vh',
              margin: 0,
              padding: 0
            }}
            variants={slideLeft}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onOpenChange(false)}
                  className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Datasets
                </button>
                {datasetName && (
                  <>
                    <span className="text-gray-400">/</span>
                    <span className="text-sm font-medium text-gray-900">{datasetName} Documents</span>
                  </>
                )}
              </div>
              <button
                onClick={() => onOpenChange(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

        {/* Status Filter Buttons */}
        {!loading && documents.length > 0 && (
          <div className="px-6 py-4 border-b">
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setStatusFilter('all')}
                className={cn(
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  statusFilter === 'all'
                    ? 'bg-gt-green text-white border-gt-green'
                    : 'bg-gt-white text-gt-gray-700 border-gt-gray-300 hover:bg-gt-gray-50'
                )}
              >
                All ({documents.length})
              </button>
              <button
                onClick={() => setStatusFilter('completed')}
                className={cn(
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  statusFilter === 'completed'
                    ? 'bg-gt-green text-white border-gt-green'
                    : 'bg-gt-white text-gt-gray-700 border-gt-gray-300 hover:bg-gt-gray-50'
                )}
              >
                Processed ({statusCounts.completed || 0})
              </button>
              <button
                onClick={() => setStatusFilter('processing')}
                className={cn(
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  statusFilter === 'processing'
                    ? 'bg-gt-green text-white border-gt-green'
                    : 'bg-gt-white text-gt-gray-700 border-gt-gray-300 hover:bg-gt-gray-50'
                )}
              >
                Processing ({statusCounts.processing || 0})
              </button>
              <button
                onClick={() => setStatusFilter('pending')}
                className={cn(
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  statusFilter === 'pending'
                    ? 'bg-gt-green text-white border-gt-green'
                    : 'bg-gt-white text-gt-gray-700 border-gt-gray-300 hover:bg-gt-gray-50'
                )}
              >
                Pending ({statusCounts.pending || 0})
              </button>
              <button
                onClick={() => setStatusFilter('failed')}
                className={cn(
                  'px-4 py-2 rounded-lg border text-sm font-medium transition-colors',
                  statusFilter === 'failed'
                    ? 'bg-gt-green text-white border-gt-green'
                    : 'bg-gt-white text-gt-gray-700 border-gt-gray-300 hover:bg-gt-gray-50'
                )}
              >
                Failed ({statusCounts.failed || 0})
              </button>
            </div>
          </div>
        )}

        {/* Documents List */}
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
                  <Skeleton className="w-8 h-8 rounded" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                  <Skeleton className="w-20 h-6 rounded-full" />
                </div>
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No documents found</h3>
              <p className="text-gray-600">This dataset doesn't contain any documents yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents
                .filter(doc => statusFilter === 'all' || doc.processing_status === statusFilter)
                .map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center gap-4 p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-400" />
                      <h4 className="font-medium text-gray-900 truncate">
                        {doc.original_filename || doc.filename}
                      </h4>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
                      <span>Size: {doc.file_size_bytes ? formatFileSize(doc.file_size_bytes) : 'Unknown'}</span>
                      <span>Type: {doc.file_type || 'Unknown'}</span>
                      {doc.created_at && (
                        <span>Uploaded: {formatDateOnly(doc.created_at)}</span>
                      )}
                    </div>
                    {(doc.processing_status === 'processing' || doc.processing_status === 'completed') && doc.created_at && (
                      <div className="mt-2">
                        <div className="flex items-center gap-4">
                          <ProcessingTimer
                            startTime={doc.created_at}
                            endTime={doc.processing_status === 'completed' ? doc.updated_at : undefined}
                            status={doc.processing_status || 'pending'}
                            chunkCount={doc.chunk_count}
                          />
                          {doc.processing_status === 'processing' && (
                            <div className="flex-1 space-y-1 min-w-[200px]">
                              <div className="flex items-center justify-between text-xs text-gray-600">
                                <span>{getProcessingStageLabel(doc.processing_stage)}</span>
                                <span>
                                  {doc.chunks_processed != null && doc.chunks_processed > 0 && doc.chunk_count
                                    ? `${doc.chunks_processed}/${doc.chunk_count} chunks`
                                    : 'Initializing...'}
                                </span>
                              </div>
                              <Progress
                                value={calculateProgress(doc)}
                                className="h-2"
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {getStatusBadge(doc.processing_status || 'pending')}
                    {doc.can_delete && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteDocument(doc.id, doc.original_filename || doc.filename)}
                        disabled={deletingDocuments.has(doc.id)}
                        className="p-1 h-auto text-gray-400 hover:text-red-600 hover:bg-red-50"
                        title="Delete document"
                      >
                        {deletingDocuments.has(doc.id) ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50">
          <div className="text-sm text-gray-600">
            {documents.length} document{documents.length !== 1 ? 's' : ''} total
            {documents.some(d => d.processing_status === 'processing' || d.processing_status === 'pending') && (
              <span className="ml-2 text-blue-600">• Auto-refreshing</span>
            )}
          </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}