'use client';

import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { Upload, X, FileText, FolderOpen, Database, XCircle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { InfoHover } from '@/components/ui/info-hover';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { getAuthToken, getTenantInfo } from '@/services/auth';
import { api } from '@/services/api';
import { formatCost } from '@/lib/utils';

interface BudgetStatus {
  within_budget: boolean;
  current_usage_cents: number;
  budget_limit_cents: number | null;
  percentage_used: number;
  warning_level: 'normal' | 'warning' | 'critical' | 'exceeded';
  enforcement_enabled: boolean;
}

interface Dataset {
  id: string;
  name: string;
  document_count: number;
}

interface BulkUploadProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datasets: Dataset[];
  preselectedDatasetId?: string;
  onCreateDataset?: () => void;
  onUploadStart?: (datasetId: string, documents?: any[]) => void; // Pass initial document data
  onUploadComplete?: (results: { datasetId: string; documentIds: string[] }[]) => void;
  className?: string;
}

interface UploadFile {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress?: number;
  error?: string;
}

// Helper function to create temporary document representation from File object
// This allows immediate display in documents modal before backend processes upload
const createTempDocument = (file: File, tempId: string): any => ({
  id: tempId, // Temporary ID that will be replaced with backend ID
  name: file.name,
  filename: file.name,
  original_filename: file.name,
  file_path: '',
  file_type: file.type || 'application/octet-stream',
  file_extension: file.name.split('.').pop() || '',
  file_size_bytes: file.size,
  uploaded_by: '',
  processing_status: 'uploading' as const, // Start as "uploading"
  chunk_count: 0,
  chunks_processed: 0,
  processing_progress: 0,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  can_delete: false // Can't delete during upload
});

export function BulkUpload({
  open,
  onOpenChange,
  datasets,
  preselectedDatasetId,
  onCreateDataset,
  onUploadStart,
  onUploadComplete,
  className = ''
}: BulkUploadProps) {
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>(preselectedDatasetId || '');
  const [isUploading, setIsUploading] = useState(false);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check if budget is exceeded AND enforcement is enabled
  const isBudgetExceeded = budgetStatus?.warning_level === 'exceeded' && budgetStatus?.enforcement_enabled;
  // Show warning (but don't block) when budget exceeded but enforcement disabled
  const isBudgetWarning = budgetStatus?.warning_level === 'exceeded' && !budgetStatus?.enforcement_enabled;

  // Update selectedDataset when preselectedDatasetId changes
  React.useEffect(() => {
    if (preselectedDatasetId) {
      setSelectedDataset(preselectedDatasetId);
    }
  }, [preselectedDatasetId]);

  // Fetch budget status when modal opens
  useEffect(() => {
    async function fetchBudgetStatus() {
      if (!open) return;

      try {
        const response = await api.get<BudgetStatus>('/api/v1/optics/budget-status');
        if (response.data) {
          setBudgetStatus(response.data);
        }
      } catch (error) {
        console.error('Failed to fetch budget status:', error);
        // Don't block uploads if budget check fails
        setBudgetStatus(null);
      }
    }

    fetchBudgetStatus();
  }, [open]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    const newUploadFiles: UploadFile[] = files.map((file, index) => ({
      id: `file-${Date.now()}-${index}`,
      file,
      status: 'pending' as const
    }));

    setUploadFiles(prev => [...prev, ...newUploadFiles]);

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (fileId: string) => {
    setUploadFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const startUpload = async () => {
    if (uploadFiles.length === 0) {
      alert('Please select files to upload');
      return;
    }

    if (!selectedDataset) {
      alert('Please select a dataset');
      return;
    }

    setIsUploading(true);

    try {
      // Get authentication using proper auth service functions
      const token = getAuthToken();
      const tenantInfo = getTenantInfo();

      if (!token || !tenantInfo) {
        alert('Authentication required. Please log in again.');
        return;
      }

      // Create temporary document representations IMMEDIATELY for instant UI feedback
      const tempDocuments = uploadFiles.map(uf => createTempDocument(uf.file, uf.id));

      // Open documents modal IMMEDIATELY with temp documents (before uploads start)
      onUploadStart?.(selectedDataset, tempDocuments);
      onOpenChange(false); // Close bulk upload modal

      // Upload files in background
      const documentIds = [];
      const uploadedDocuments: any[] = [];

      for (const uploadFile of uploadFiles) {
        try {
          // Update status
          setUploadFiles(prev => prev.map(f =>
            f.id === uploadFile.id ? { ...f, status: 'uploading' as const } : f
          ));

          const formData = new FormData();
          formData.append('file', uploadFile.file);
          formData.append('dataset_id', selectedDataset);

          // Create progress tracking
          const xhr = new XMLHttpRequest();

          const uploadResponse = await new Promise<Response>((resolve, reject) => {
            xhr.upload.addEventListener('progress', (event) => {
              if (event.lengthComputable) {
                const progress = Math.round((event.loaded / event.total) * 100);
                setUploadFiles(prev => prev.map(f =>
                  f.id === uploadFile.id ? { ...f, progress } : f
                ));
              }
            });

            xhr.onload = () => {
              // Use responseText for proper JSON parsing
              resolve(new Response(xhr.responseText, {
                status: xhr.status,
                statusText: xhr.statusText,
                headers: { 'Content-Type': 'application/json' }
              }));
            };
            xhr.onerror = () => reject(new Error('Network error'));

            xhr.open('POST', '/api/v1/documents/');
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
            xhr.setRequestHeader('X-Tenant-Domain', tenantInfo.domain);
            xhr.send(formData);
          });

          if (!uploadResponse.ok) {
            throw new Error(`Upload failed: ${uploadResponse.statusText}`);
          }

          const result = await uploadResponse.json();
          documentIds.push(result.id);
          uploadedDocuments.push(result); // Store full document data

          // Mark as completed
          setUploadFiles(prev => prev.map(f =>
            f.id === uploadFile.id ? { ...f, status: 'completed' as const } : f
          ));

        } catch (error) {
          // Mark as failed
          setUploadFiles(prev => prev.map(f =>
            f.id === uploadFile.id ? {
              ...f,
              status: 'failed' as const,
              error: error instanceof Error ? error.message : 'Upload failed'
            } : f
          ));
        }
      }

      // Close modal and call completion handler immediately
      onOpenChange(false);

      onUploadComplete?.([{
        datasetId: selectedDataset,
        documentIds
      }]);

    } finally {
      setIsUploading(false);
      resetUploads();
    }
  };

  const resetUploads = () => {
    setUploadFiles([]);
    setSelectedDataset('');
  };

  const totalFiles = uploadFiles.length;
  const completedFiles = uploadFiles.filter(f => f.status === 'completed').length;
  const failedFiles = uploadFiles.filter(f => f.status === 'failed').length;

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
            onClick={() => onOpenChange(false)}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            className="fixed right-0 top-0 h-screen w-full max-w-2xl bg-gt-white shadow-2xl z-[1000] overflow-hidden flex flex-col"
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
            <div className="sticky top-0 bg-gt-white border-b border-gray-200 px-6 py-4 z-10">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center">
                    <Upload className="w-5 h-5 text-gt-green" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-semibold text-gray-900">Upload Documents</h2>
                      <InfoHover content="Supported formats: PDF, DOCX, TXT, Markdown, CSV. Maximum 10MB per file. For best results, convert XLSX files to CSV before uploading. Large files may take longer to process." />
                    </div>
                    <p className="text-sm text-gray-600">Upload documents to datasets</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  className="p-1 h-auto"
                >
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Dataset Selection */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Select Dataset</h3>

            <Select value={selectedDataset} onValueChange={setSelectedDataset}>
              <SelectTrigger>
                <SelectValue placeholder="Select existing dataset" />
              </SelectTrigger>
              <SelectContent>
                {datasets.map(dataset => (
                  <SelectItem key={dataset.id} value={dataset.id}>
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4" />
                      <span>{dataset.name} ({dataset.document_count} docs)</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Budget Exceeded Warning (enforcement enabled - blocking) */}
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

          {/* Budget Exceeded Warning (enforcement disabled - warning only) */}
          {isBudgetWarning && budgetStatus && (
            <Alert className="border-orange-200 bg-orange-50">
              <AlertCircle className="h-4 w-4 text-orange-600" />
              <AlertTitle className="text-orange-800">Budget Exceeded</AlertTitle>
              <AlertDescription className="text-orange-700">
                <p className="mb-1">Monthly budget limit exceeded. Budget enforcement is disabled, so uploads are still allowed.</p>
                <p className="font-semibold">
                  Current usage: {formatCost(budgetStatus.current_usage_cents)} / {formatCost(budgetStatus.budget_limit_cents || 0)}
                </p>
              </AlertDescription>
            </Alert>
          )}

          {/* File Upload */}
          <div className="space-y-4">
            <h3 className="text-lg font-medium">Select Files</h3>

            <div className={`border-2 border-dashed rounded-lg p-8 text-center ${
              isBudgetExceeded
                ? 'border-red-200 bg-red-50 opacity-60'
                : 'border-gray-300'
            }`}>
              <Upload className={`w-10 h-10 mx-auto mb-4 ${
                isBudgetExceeded ? 'text-red-300' : 'text-gray-400'
              }`} />
              <p className={`text-lg font-medium mb-2 ${
                isBudgetExceeded ? 'text-red-400' : 'text-gray-900'
              }`}>
                {isBudgetExceeded ? 'Uploads disabled - budget exceeded' : 'Choose files to upload'}
              </p>
              <p className="text-sm text-gray-600 mb-4">
                PDF, DOCX, TXT, MD, CSV, JSON files up to 50MB each
              </p>
              <Button
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || isBudgetExceeded}
              >
                {isBudgetExceeded ? 'Budget Exceeded' : 'Select Files'}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md,.csv,.json"
                onChange={handleFileSelect}
                className="hidden"
                disabled={isBudgetExceeded}
              />
            </div>
          </div>

          {/* Selected Files */}
          {uploadFiles.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">Selected Files ({uploadFiles.length})</h3>
                <div className="text-sm text-gray-600">
                  {completedFiles} completed • {failedFiles} failed
                </div>
              </div>

              <div className="space-y-2 max-h-60 overflow-y-auto">
                {uploadFiles.map((uploadFile) => (
                  <div key={uploadFile.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <FileText className="w-5 h-5 text-blue-500" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">{uploadFile.file.name}</p>
                      <p className="text-sm text-gray-500">
                        {(uploadFile.file.size / (1024 * 1024)).toFixed(1)}MB
                        {uploadFile.status !== 'pending' && ` • ${uploadFile.status}`}
                      </p>
                      {uploadFile.error && (
                        <p className="text-xs text-red-600">{uploadFile.error}</p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeFile(uploadFile.id)}
                      disabled={isUploading}
                      className="p-1 h-auto text-gray-400 hover:text-red-600"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-6 border-t">
            <Button
              variant="secondary"
              onClick={resetUploads}
              disabled={isUploading}
            >
              Clear All
            </Button>
            <Button
              onClick={startUpload}
              disabled={uploadFiles.length === 0 || !selectedDataset || isUploading || isBudgetExceeded}
            >
              {isUploading ? 'Uploading...' : isBudgetExceeded ? 'Budget Exceeded' : totalFiles === 1 ? 'Upload File' : `Upload ${totalFiles} Files`}
            </Button>
          </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}