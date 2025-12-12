'use client';

import { useState, useRef, useCallback } from 'react';
import { Upload, X, FileText, AlertCircle, CheckCircle, Loader2, Database } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { getAuthToken, getTenantInfo } from '@/services/auth';

interface UploadFile {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
  error?: string;
  documentId?: string;
}

interface DocumentUploadProps {
  datasetId?: string;
  datasetName?: string;
  onUploadComplete?: (files: { id: string; documentId: string; filename: string }[]) => void;
  onUploadStart?: (files: File[]) => void;
  onFileRemove?: (fileId: string) => void;
  maxFiles?: number;
  maxSize?: number; // in MB
  acceptedTypes?: string[];
  disabled?: boolean;
  className?: string;
}

export function DocumentUpload({
  datasetId,
  datasetName,
  onUploadComplete,
  onUploadStart,
  onFileRemove,
  maxFiles = 10,
  maxSize = 50,
  acceptedTypes = ['pdf', 'docx', 'txt', 'md', 'csv', 'json'],
  disabled = false,
  className = ''
}: DocumentUploadProps) {
  const [files, setFiles] = useState<UploadFile[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);

  const validateFile = (file: File): string | null => {
    // Check file size
    if (file.size > maxSize * 1024 * 1024) {
      return `File size exceeds ${maxSize}MB limit`;
    }

    // Check file type
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!extension || !acceptedTypes.includes(extension)) {
      return `File type .${extension} is not supported. Supported types: ${acceptedTypes.join(', ')}`;
    }

    return null;
  };

  const generateFileId = () => {
    return `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  };

  const addFiles = useCallback((newFiles: File[]) => {
    if (disabled) return;

    const validFiles: UploadFile[] = [];
    const errors: string[] = [];

    newFiles.forEach(file => {
      const error = validateFile(file);
      if (error) {
        errors.push(`${file.name}: ${error}`);
      } else if (files.length + validFiles.length < maxFiles) {
        validFiles.push({
          id: generateFileId(),
          file,
          status: 'pending',
          progress: 0
        });
      } else {
        errors.push(`Maximum ${maxFiles} files allowed`);
      }
    });

    if (validFiles.length > 0) {
      setFiles(prev => [...prev, ...validFiles]);
      onUploadStart?.(validFiles.map(f => f.file));
    }

    // Show errors if any
    if (errors.length > 0) {
      console.error('File validation errors:', errors);
      // You could show toast notifications here
    }
  }, [files.length, maxFiles, maxSize, acceptedTypes, disabled, onUploadStart]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (disabled) return;

    const droppedFiles = Array.from(e.dataTransfer.files);
    addFiles(droppedFiles);
  }, [addFiles, disabled]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      addFiles(selectedFiles);
    }
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (fileId: string) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
    onFileRemove?.(fileId);
  };

  // Poll document processing status
  const pollDocumentStatus = async (fileId: string, documentId: string, token: string, domain: string) => {
    const maxAttempts = 60; // 5 minutes at 5-second intervals
    let attempts = 0;

    while (attempts < maxAttempts) {
      try {
        const response = await fetch(`/api/v1/files/${documentId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Tenant-Domain': domain,
          },
        });

        if (response.ok) {
          const fileInfo = await response.json();
          const status = fileInfo.processing_status;

          if (status === 'completed') {
            // Mark as completed
            setFiles(prev => prev.map(f =>
              f.id === fileId
                ? { ...f, status: 'completed' as const, progress: 100 }
                : f
            ));
            return;
          } else if (status === 'failed') {
            // Mark as failed
            setFiles(prev => prev.map(f =>
              f.id === fileId
                ? { ...f, status: 'failed' as const, error: fileInfo.error_message || 'Processing failed' }
                : f
            ));
            return;
          }
          // Still processing, continue polling
        }
      } catch (error) {
        console.error('Error polling document status:', error);
      }

      attempts++;
      await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
    }

    // Timeout - mark as failed
    setFiles(prev => prev.map(f =>
      f.id === fileId
        ? { ...f, status: 'failed' as const, error: 'Processing timeout' }
        : f
    ));
  };

  const startUpload = async () => {
    if (files.length === 0 || isUploading) return;

    // Validate that datasetId is provided
    if (!datasetId) {
      console.error('Dataset ID is required for upload');
      // Show error for all pending files
      setFiles(prev => prev.map(f =>
        f.status === 'pending'
          ? {
              ...f,
              status: 'failed' as const,
              error: 'Please select a dataset before uploading'
            }
          : f
      ));
      return;
    }

    setIsUploading(true);

    try {
      const uploadPromises = files.map(async (uploadFile) => {
        if (uploadFile.status !== 'pending') return uploadFile;

        // Update status to uploading
        setFiles(prev => prev.map(f => 
          f.id === uploadFile.id 
            ? { ...f, status: 'uploading' as const, progress: 0 }
            : f
        ));

        try {
          // Set initial upload progress
          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? { ...f, progress: 10 }
              : f
          ));

          // Create FormData for upload
          const formData = new FormData();
          formData.append('file', uploadFile.file);
          formData.append('dataset_id', datasetId);

          // Get authentication headers
          const token = getAuthToken();
          const tenantInfo = getTenantInfo();

          if (!token || !tenantInfo) {
            throw new Error('Authentication required');
          }

          // Update progress for upload
          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? { ...f, progress: 50 }
              : f
          ));

          const response = await fetch('/api/v1/documents', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'X-Tenant-Domain': tenantInfo.domain,
            },
            body: formData,
          });

          if (!response.ok) {
            let errorMessage = `Upload failed: ${response.statusText}`;
            try {
              const errorData = await response.json();
              if (errorData.detail) {
                errorMessage = typeof errorData.detail === 'string' ? errorData.detail : errorMessage;
              }
            } catch {
              // Use default error message if response parsing fails
            }
            throw new Error(errorMessage);
          }

          const result = await response.json();

          // Update to processing status - DO NOT mark as completed yet
          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? {
                  ...f,
                  status: 'processing' as const,
                  progress: 90,
                  documentId: result.id
                }
              : f
          ));

          // Start polling for real processing status
          await pollDocumentStatus(uploadFile.id, result.id, token, tenantInfo.domain);

          return {
            id: uploadFile.id,
            documentId: result.id,
            filename: uploadFile.file.name
          };

        } catch (error) {
          // Enhanced error handling with specific messages
          let errorMessage = 'Upload failed';
          if (error instanceof Error) {
            errorMessage = error.message;
            // Provide user-friendly messages for common errors
            if (errorMessage.includes('dataset_id is required')) {
              errorMessage = 'Please select a dataset before uploading';
            } else if (errorMessage.includes('Authentication')) {
              errorMessage = 'Authentication required. Please log in again.';
            } else if (errorMessage.includes('Network')) {
              errorMessage = 'Network error. Please check your connection and try again.';
            }
          }

          // Update to failed status
          setFiles(prev => prev.map(f =>
            f.id === uploadFile.id
              ? {
                  ...f,
                  status: 'failed' as const,
                  error: errorMessage
                }
              : f
          ));
          throw error;
        }
      });

      const results = await Promise.allSettled(uploadPromises);
      const successfulUploads = results
        .filter((result): result is PromiseFulfilledResult<any> => 
          result.status === 'fulfilled' && result.value
        )
        .map(result => result.value);

      if (successfulUploads.length > 0) {
        onUploadComplete?.(successfulUploads);
      }

    } finally {
      setIsUploading(false);
    }
  };

  const getFileIcon = (filename: string) => {
    return <FileText className="w-5 h-5 text-blue-500" />;
  };

  const getStatusIcon = (status: UploadFile['status']) => {
    switch (status) {
      case 'pending':
        return <FileText className="w-4 h-4 text-gray-400" />;
      case 'uploading':
      case 'processing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getStatusColor = (status: UploadFile['status']) => {
    switch (status) {
      case 'pending':
        return 'bg-gray-100 text-gray-700';
      case 'uploading':
        return 'bg-blue-100 text-blue-700';
      case 'processing':
        return 'bg-yellow-100 text-yellow-700';
      case 'completed':
        return 'bg-green-100 text-green-700';
      case 'failed':
        return 'bg-red-100 text-red-700';
    }
  };

  const canUpload = files.length > 0 && !isUploading && files.some(f => f.status === 'pending') && datasetId;
  const completedCount = files.filter(f => f.status === 'completed').length;
  const failedCount = files.filter(f => f.status === 'failed').length;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Dataset Info */}
      {datasetId && datasetName && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="flex items-center gap-2 text-sm text-blue-800">
            <Database className="w-4 h-4" />
            <span className="font-medium">Uploading to dataset:</span>
            <span className="font-semibold">{datasetName}</span>
          </div>
        </div>
      )}

      {/* Drop Zone */}
      <div
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
          dragActive 
            ? 'border-blue-400 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload className="w-10 h-10 text-gray-400 mx-auto mb-4" />
        <p className="text-lg font-medium text-gray-900 mb-2">
          Drop files here or click to browse
        </p>
        <p className="text-sm text-gray-600 mb-4">
          Supported formats: {acceptedTypes.map(type => `.${type}`).join(', ')}
        </p>
        <p className="text-xs text-gray-500 mb-4">
          Maximum {maxFiles} files, {maxSize}MB each
        </p>
        <Button
          type="button"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
        >
          Select Files
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={acceptedTypes.map(type => `.${type}`).join(',')}
          onChange={handleFileSelect}
          className="hidden"
          disabled={disabled}
        />
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-gray-900">
              Files ({files.length})
            </h4>
            <Button
              onClick={startUpload}
              disabled={!canUpload || isUploading}
              size="sm"
              className={!datasetId ? 'opacity-50 cursor-not-allowed' : ''}
              title={!datasetId ? 'Please select a dataset first' : ''}
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                'Upload All'
              )}
            </Button>
            {!datasetId && files.length > 0 && (
              <p className="text-sm text-orange-600 font-medium">
                Please select a dataset to upload files
              </p>
            )}
          </div>

          <div className="space-y-2 max-h-60 overflow-y-auto">
            {files.map((uploadFile) => (
              <div
                key={uploadFile.id}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
              >
                {getFileIcon(uploadFile.file.name)}
                
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">
                    {uploadFile.file.name}
                  </p>
                  <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span>{(uploadFile.file.size / (1024 * 1024)).toFixed(1)}MB</span>
                    <Badge className={cn('text-xs', getStatusColor(uploadFile.status))}>
                      <span className="flex items-center gap-1">
                        {getStatusIcon(uploadFile.status)}
                        {uploadFile.status}
                      </span>
                    </Badge>
                  </div>
                  
                  {(uploadFile.status === 'uploading' || uploadFile.status === 'processing') && (
                    <Progress value={uploadFile.progress} className="h-2 mt-2" />
                  )}
                  
                  {uploadFile.error && (
                    <p className="text-xs text-red-600 mt-1">{uploadFile.error}</p>
                  )}
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(uploadFile.id)}
                  disabled={uploadFile.status === 'uploading' || uploadFile.status === 'processing'}
                  className="p-1 h-auto text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>

          {/* Summary */}
          {(completedCount > 0 || failedCount > 0) && (
            <div className="flex items-center justify-between text-sm text-gray-600 pt-2 border-t">
              <span>
                {completedCount > 0 && `${completedCount} completed`}
                {completedCount > 0 && failedCount > 0 && ', '}
                {failedCount > 0 && `${failedCount} failed`}
              </span>
              {failedCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setFiles(prev => prev.filter(f => f.status !== 'failed'))}
                  className="text-red-600 hover:text-red-700"
                >
                  Remove failed
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}