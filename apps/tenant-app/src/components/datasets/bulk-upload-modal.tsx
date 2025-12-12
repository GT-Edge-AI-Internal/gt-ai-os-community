'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, Upload, File, AlertTriangle, CheckCircle, Clock, Loader2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { cn, formatCost } from '@/lib/utils';
import { api } from '@/services/api';
import {
  uploadMultipleDocuments,
  validateFiles,
  subscribeToProcessingUpdates,
  type UploadProgressEvent,
  type ProcessingProgressEvent,
  type BulkUploadOptions,
  type Document
} from '@/services/documents';

interface BudgetStatus {
  within_budget: boolean;
  current_usage_cents: number;
  budget_limit_cents: number | null;
  percentage_used: number;
  warning_level: 'normal' | 'warning' | 'critical' | 'exceeded';
  enforcement_enabled: boolean;
}

interface BulkUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datasetId?: string;
  onUploadComplete?: (documents: Document[]) => void;
  uploadOptions?: BulkUploadOptions;
}

interface FileUploadItem {
  file: File;
  id: string;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
  error?: string;
  document?: Document;
  processingStage?: string;
}

export function BulkUploadModal({
  open,
  onOpenChange,
  datasetId,
  onUploadComplete,
  uploadOptions = {}
}: BulkUploadModalProps) {
  const [files, setFiles] = useState<FileUploadItem[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
  const [budgetLoading, setBudgetLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsCleanupRef = useRef<(() => void) | null>(null);

  // Check if budget is exceeded AND enforcement is enabled
  const isBudgetExceeded = budgetStatus?.warning_level === 'exceeded' && budgetStatus?.enforcement_enabled;
  // Show warning (but don't block) when budget exceeded but enforcement disabled
  const isBudgetWarning = budgetStatus?.warning_level === 'exceeded' && !budgetStatus?.enforcement_enabled;

  // Fetch budget status when modal opens
  useEffect(() => {
    async function fetchBudgetStatus() {
      if (!open) return;

      setBudgetLoading(true);
      try {
        const response = await api.get<BudgetStatus>('/api/v1/optics/budget-status');
        if (response.data) {
          setBudgetStatus(response.data);
        }
      } catch (error) {
        console.error('Failed to fetch budget status:', error);
        // Don't block uploads if budget check fails
        setBudgetStatus(null);
      } finally {
        setBudgetLoading(false);
      }
    }

    fetchBudgetStatus();
  }, [open]);

  // Merge default options with provided ones
  const options: BulkUploadOptions = {
    dataset_id: datasetId,
    auto_process: true,
    ...uploadOptions
  };

  const handleFileSelect = useCallback((selectedFiles: FileList | null) => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    const { valid, invalid } = validateFiles(selectedFiles);
    
    // Show validation errors for invalid files
    if (invalid.length > 0) {
      // You could show a toast notification here
      console.warn('Invalid files:', invalid);
    }

    // Add valid files to the upload list
    const newFiles: FileUploadItem[] = valid.map(file => ({
      file,
      id: crypto.randomUUID(),
      status: 'pending',
      progress: 0
    }));

    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileSelect(e.dataTransfer.files);
  }, [handleFileSelect]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const removeFile = useCallback((fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
  }, []);

  const startUpload = useCallback(async () => {
    if (files.length === 0) return;

    setUploading(true);

    // Close modal and trigger callback immediately
    onOpenChange(false);

    try {
      const filesToUpload = files.filter(f => f.status === 'pending');

      // Start upload with progress tracking
      const uploadPromises = await uploadMultipleDocuments(
        filesToUpload.map(f => f.file),
        options,
        (progressEvents) => {
          // Update file statuses based on progress events
          setFiles(prev => prev.map(file => {
            const progressEvent = progressEvents.find(e => e.filename === file.file.name);
            if (progressEvent) {
              return {
                ...file,
                status: progressEvent.status as FileUploadItem['status'],
                progress: progressEvent.percentage,
                error: progressEvent.error
              };
            }
            return file;
          }));
        }
      );

      // Process upload results
      const successfulDocuments: Document[] = [];
      const documentIds: string[] = [];

      uploadPromises.forEach((result, index) => {
        const fileItem = filesToUpload[index];

        if (result.status === 'fulfilled' && result.value.data) {
          const document = result.value.data;
          successfulDocuments.push(document);
          documentIds.push(document.id);

          setFiles(prev => prev.map(f =>
            f.id === fileItem.id
              ? { ...f, status: 'processing', document, progress: 100 }
              : f
          ));
        } else {
          const error = result.status === 'rejected'
            ? result.reason?.message || 'Upload failed'
            : result.value.error || 'Unknown error';

          setFiles(prev => prev.map(f =>
            f.id === fileItem.id
              ? { ...f, status: 'failed', error, progress: 0 }
              : f
          ));
        }
      });

      // Subscribe to processing updates if auto-processing is enabled
      if (options.auto_process && documentIds.length > 0) {
        wsCleanupRef.current = subscribeToProcessingUpdates(
          documentIds,
          (event: ProcessingProgressEvent) => {
            setFiles(prev => prev.map(file => {
              if (file.document?.id === event.document_id) {
                return {
                  ...file,
                  status: event.status as FileUploadItem['status'],
                  progress: event.progress_percentage,
                  processingStage: event.stage,
                  error: event.error
                };
              }
              return file;
            }));
          },
          (error) => {
            console.error('WebSocket error:', error);
          }
        );
      }

      // Call completion callback with successful documents
      if (successfulDocuments.length > 0) {
        onUploadComplete?.(successfulDocuments);
      }

    } catch (error) {
      console.error('Bulk upload error:', error);

      // Mark all pending files as failed
      setFiles(prev => prev.map(file =>
        file.status === 'pending'
          ? { ...file, status: 'failed', error: 'Upload initialization failed' }
          : file
      ));
    } finally {
      setUploading(false);
    }
  }, [files, options, onUploadComplete, onOpenChange]);

  const handleClose = useCallback(() => {
    // Clean up WebSocket connection
    if (wsCleanupRef.current) {
      wsCleanupRef.current();
      wsCleanupRef.current = null;
    }
    
    setFiles([]);
    setUploading(false);
    onOpenChange(false);
  }, [onOpenChange]);

  const getStatusIcon = (status: FileUploadItem['status']) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-400" />;
      case 'uploading':
      case 'processing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: FileUploadItem['status']) => {
    switch (status) {
      case 'pending':
        return 'text-gray-600';
      case 'uploading':
        return 'text-blue-600';
      case 'processing':
        return 'text-blue-600';
      case 'completed':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getProgressColor = (status: FileUploadItem['status']) => {
    switch (status) {
      case 'uploading':
      case 'processing':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-300';
    }
  };

  const completedCount = files.filter(f => f.status === 'completed').length;
  const failedCount = files.filter(f => f.status === 'failed').length;
  const processingCount = files.filter(f => f.status === 'processing' || f.status === 'uploading').length;

  if (!open) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[999]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            className="fixed right-0 top-0 h-screen w-full max-w-2xl bg-white shadow-2xl z-[1000] overflow-hidden flex flex-col"
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
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 z-10">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center">
                    <Upload className="w-5 h-5 text-gt-green" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">Upload Documents</h2>
                    <p className="text-sm text-gray-600">
                      Upload multiple files to {datasetId ? 'dataset' : 'document library'}
                    </p>
                  </div>
                </div>
                <Button variant="ghost" size="sm" onClick={handleClose} className="p-1 h-auto">
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Budget Exceeded Warning */}
            {isBudgetExceeded && budgetStatus && (
              <Alert variant="destructive">
                <XCircle className="h-4 w-4" />
                <AlertTitle>Budget Exceeded</AlertTitle>
                <AlertDescription>
                  <p className="mb-1">Monthly budget limit exceeded. Document uploads are blocked until the next billing cycle.</p>
                  <p className="font-semibold">
                    Current usage: {formatCost(budgetStatus.current_usage_cents)} / {formatCost(budgetStatus.budget_limit_cents || 0)}
                  </p>
                </AlertDescription>
              </Alert>
            )}

            {/* Drop Zone */}
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center transition-colors",
                isBudgetExceeded
                  ? "border-red-200 bg-red-50 cursor-not-allowed opacity-60"
                  : isDragOver
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-300 hover:border-gray-400 cursor-pointer"
              )}
              onDrop={isBudgetExceeded ? undefined : handleDrop}
              onDragOver={isBudgetExceeded ? undefined : handleDragOver}
              onDragLeave={isBudgetExceeded ? undefined : handleDragLeave}
              onClick={isBudgetExceeded ? undefined : () => fileInputRef.current?.click()}
            >
              <Upload className={cn(
                "w-12 h-12 mx-auto mb-4",
                isBudgetExceeded ? "text-red-300" : isDragOver ? "text-blue-500" : "text-gray-400"
              )} />
              <p className={cn(
                "text-lg font-medium mb-2",
                isBudgetExceeded ? "text-red-400" : "text-gray-900"
              )}>
                {isBudgetExceeded ? "Uploads disabled - budget exceeded" : "Drop files here or click to browse"}
              </p>
              <p className="text-sm text-gray-600 mb-4">
                Supports PDF, DOCX, TXT, MD, CSV, XLSX, PPTX, HTML, JSON
              </p>
              <p className="text-xs text-gray-500">
                Maximum file size: 50MB • Maximum files: 50
              </p>

              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.pptx,.html,.json"
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files)}
                disabled={isBudgetExceeded}
              />
            </div>

            {/* File List */}
            {files.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium">Files ({files.length})</h3>
                  <div className="flex gap-2">
                    {completedCount > 0 && (
                      <Badge variant="secondary" className="bg-green-100 text-green-800">
                        {completedCount} completed
                      </Badge>
                    )}
                    {processingCount > 0 && (
                      <Badge variant="secondary" className="bg-blue-100 text-blue-800">
                        {processingCount} processing
                      </Badge>
                    )}
                    {failedCount > 0 && (
                      <Badge variant="secondary" className="bg-red-100 text-red-800">
                        {failedCount} failed
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {files.map((fileItem) => (
                    <div key={fileItem.id} className="p-3 border border-gray-200 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <File className="w-4 h-4 text-gray-400 flex-shrink-0" />
                          <span className="text-sm font-medium text-gray-900 truncate">
                            {fileItem.file.name}
                          </span>
                          <span className="text-xs text-gray-500 flex-shrink-0">
                            ({Math.round(fileItem.file.size / 1024)} KB)
                          </span>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          {getStatusIcon(fileItem.status)}
                          <span className={cn("text-xs font-medium", getStatusColor(fileItem.status))}>
                            {fileItem.status === 'processing' && fileItem.processingStage 
                              ? `${fileItem.processingStage}`
                              : fileItem.status
                            }
                          </span>
                          {fileItem.status === 'pending' && !uploading && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeFile(fileItem.id)}
                              className="h-6 w-6 p-0"
                            >
                              <X className="w-3 h-3" />
                            </Button>
                          )}
                        </div>
                      </div>
                      
                      {(fileItem.status === 'uploading' || fileItem.status === 'processing') && (
                        <div className="w-full">
                          <Progress 
                            value={fileItem.progress} 
                            className="h-2"
                          />
                          <p className="text-xs text-gray-600 mt-1">
                            {fileItem.progress}%
                            {fileItem.processingStage && ` - ${fileItem.processingStage}`}
                          </p>
                        </div>
                      )}
                      
                      {fileItem.error && (
                        <p className="text-xs text-red-600 mt-1">
                          {fileItem.error}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <Button variant="outline" onClick={handleClose} disabled={uploading}>
              Cancel
            </Button>
            <Button
              onClick={startUpload}
              disabled={files.length === 0 || uploading || isBudgetExceeded}
              className="flex items-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Uploading...
                </>
              ) : isBudgetExceeded ? (
                <>
                  <XCircle className="w-4 h-4" />
                  Budget Exceeded
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Upload {files.length} Files
                </>
              )}
            </Button>
          </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}