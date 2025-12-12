'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  X,
  Database,
  FileText,
  Upload,
  Settings,
  Play,
  Trash2,
  FolderOpen,
  Clock,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import {
  Dataset,
  Document,
  datasetService,
  documentService
} from '@/services';
import {
  DocumentList,
  DatasetEditModal,
  BulkUpload,
  DocumentSummaryModal,
  UpdateDatasetData
} from '@/components/datasets';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn, formatStorageSize } from '@/lib/utils';

interface DatasetDetailsDrawerProps {
  datasetId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onDatasetDeleted?: () => void;
  onDatasetUpdated?: () => void;
}

export function DatasetDetailsDrawer({
  datasetId,
  isOpen,
  onClose,
  onDatasetDeleted,
  onDatasetUpdated
}: DatasetDetailsDrawerProps) {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showSummaryModal, setShowSummaryModal] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>('');
  const [editLoading, setEditLoading] = useState(false);

  // Load dataset and documents when drawer opens
  useEffect(() => {
    if (isOpen && datasetId) {
      loadDatasetData();
    } else if (!isOpen) {
      // Reset state when drawer closes
      setDataset(null);
      setDocuments([]);
    }
  }, [isOpen, datasetId]);

  const loadDatasetData = async () => {
    if (!datasetId) return;

    setLoading(true);
    setDocumentsLoading(true);

    try {
      // Load dataset details
      const datasetResponse = await datasetService.getDataset(datasetId);

      if (datasetResponse.data) {
        setDataset(datasetResponse.data);

        // Load documents for this dataset
        const docsResponse = await documentService.listDocuments({
          dataset_id: datasetId
        });

        if (docsResponse.data) {
          // Handle both array and object responses for robustness
          const docs = Array.isArray(docsResponse.data)
            ? docsResponse.data
            : (docsResponse.data.files || []);
          setDocuments(docs);
        } else {
          setDocuments([]);
        }
      } else if (datasetResponse.error) {
        console.error('Failed to load dataset:', datasetResponse.error);
      }
    } catch (error) {
      console.error('Error loading dataset:', error);
    } finally {
      setLoading(false);
      setDocumentsLoading(false);
    }
  };


  const handleUpdateDataset = async (updateData: UpdateDatasetData) => {
    if (!dataset) return;

    setEditLoading(true);
    try {
      const response = await datasetService.updateDataset(dataset.id, updateData);

      if (response.data && !response.error) {
        // Refresh dataset data
        await loadDatasetData();
        console.log('Dataset updated successfully');
        setShowEditModal(false);
        onDatasetUpdated?.();
      } else if (response.error) {
        console.error('Dataset update error:', response.error);
      }
    } catch (error) {
      console.error('Failed to update dataset:', error);
    } finally {
      setEditLoading(false);
    }
  };

  const handleDeleteDataset = async () => {
    if (!dataset) return;

    if (!confirm('Are you sure you want to delete this dataset? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await datasetService.deleteDataset(dataset.id);
      if (response.data && !response.error) {
        console.log('Dataset deleted successfully');
        onClose();
        onDatasetDeleted?.();
      } else if (response.error) {
        console.error('Dataset deletion error:', response.error);
      }
    } catch (error) {
      console.error('Failed to delete dataset:', error);
    }
  };

  const handleProcessAll = () => {
    console.log('Processing all documents in dataset:', datasetId);
    // TODO: Implement batch processing
  };

  const handleDocumentSummary = (documentId: string) => {
    setSelectedDocumentId(documentId);
    setShowSummaryModal(true);
  };




  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'processing': return <Clock className="w-4 h-4 text-blue-500" />;
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-500" />;
      default: return <FolderOpen className="w-4 h-4 text-gray-500" />;
    }
  };

  // Handle ESC key to close drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />

            {/* Drawer Panel */}
            <motion.div
              className="fixed right-0 top-0 h-full w-full max-w-5xl bg-white shadow-2xl z-40 overflow-hidden flex flex-col"
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b">
              <div className="flex items-center gap-3">
                <button
                  onClick={onClose}
                  className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Datasets
                </button>
                {dataset && (
                  <>
                    <span className="text-gray-400">/</span>
                    <span className="text-sm font-medium text-gray-900">{dataset.name}</span>
                  </>
                )}
              </div>
              <button
                onClick={onClose}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loading ? (
                <div className="space-y-6">
                  {/* Loading skeleton */}
                  <div className="bg-white rounded-lg shadow-sm border p-6 space-y-4">
                    <Skeleton className="h-10 w-64" />
                    <Skeleton className="h-4 w-96" />
                    <div className="flex gap-4">
                      <Skeleton className="h-8 w-24" />
                      <Skeleton className="h-8 w-24" />
                      <Skeleton className="h-8 w-24" />
                    </div>
                  </div>
                </div>
              ) : dataset ? (
                <>
                  {/* Dataset Header */}
                  <div className="bg-white rounded-lg shadow-sm border p-6">
                    <div className="flex justify-between items-start">
                      <div className="space-y-3 flex-1">
                        <div className="flex items-center gap-3">
                          <Database className="w-8 h-8 text-gt-green" />
                          <h1 className="text-2xl font-bold text-gray-900">{dataset.name}</h1>
                          {getStatusIcon()}
                        </div>

                        {dataset.description && (
                          <p className="text-gray-600 max-w-2xl">{dataset.description}</p>
                        )}

                        <div className="flex flex-wrap gap-3">
                          <Badge variant="secondary" className="flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            {dataset.document_count} documents
                          </Badge>
                          <Badge variant="secondary">
                            {dataset.chunk_count} chunks
                          </Badge>
                          <Badge variant="secondary">
                            {formatStorageSize(dataset.storage_size_mb)}
                          </Badge>
                          {dataset.tags.map(tag => (
                            <Badge key={tag} variant="outline">{tag}</Badge>
                          ))}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex gap-2">
                        {dataset.can_edit && (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setShowEditModal(true)}
                              className="flex items-center gap-1"
                            >
                              <Settings className="w-4 h-4" />
                              Edit
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setShowUploadModal(true)}
                              className="flex items-center gap-1"
                            >
                              <Upload className="w-4 h-4" />
                              Upload
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleProcessAll}
                              className="flex items-center gap-1"
                            >
                              <Play className="w-4 h-4" />
                              Process All
                            </Button>
                          </>
                        )}
                        {dataset.can_delete && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleDeleteDataset}
                            className="flex items-center gap-1 text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="w-4 h-4" />
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>


                  {/* Documents Section */}
                  <div className="bg-white rounded-lg shadow-sm border p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      <FileText className="w-5 h-5 text-gt-green" />
                      Documents in Dataset
                    </h2>

                    <DocumentList
                      documents={documents || []}
                      loading={documentsLoading}
                      onDocumentSummary={handleDocumentSummary}
                      onRefresh={loadDatasetData}
                      showDatasetColumn={false}
                    />
                  </div>
                </>
              ) : (
                <div className="text-center py-12">
                  <Database className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Dataset not found</h3>
                </div>
              )}
            </div>

            {/* Modals */}
            {dataset && (
              <>
                <DatasetEditModal
                  open={showEditModal}
                  onOpenChange={setShowEditModal}
                  onUpdateDataset={handleUpdateDataset}
                  dataset={{
                    id: dataset.id,
                    name: dataset.name,
                    description: dataset.description,
                    tags: dataset.tags,
                    access_group: dataset.access_group,
                    team_members: dataset.team_members,
                    chunking_strategy: dataset.chunking_strategy,
                    chunk_size: dataset.chunk_size,
                    chunk_overlap: dataset.chunk_overlap,
                    embedding_model: dataset.embedding_model
                  }}
                  loading={editLoading}
                />

                <BulkUpload
                  open={showUploadModal}
                  onOpenChange={setShowUploadModal}
                  datasets={[{
                    id: dataset.id,
                    name: dataset.name,
                    document_count: dataset.document_count
                  }]}
                  preselectedDatasetId={dataset.id}
                  onUploadComplete={async () => {
                    console.log('Upload completed, refreshing dataset');
                    await loadDatasetData();
                  }}
                />

                <DocumentSummaryModal
                  open={showSummaryModal}
                  onOpenChange={setShowSummaryModal}
                  documentId={selectedDocumentId}
                />
              </>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}