'use client';

import React from 'react';
import { X, FileText, CheckCircle, AlertCircle, Clock, Upload } from 'lucide-react';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { formatFileSize } from '@/lib/utils';

interface UploadFileProgress {
  id: string;
  filename: string;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
  progress?: number;
  error?: string;
  fileSize?: number;
}

interface UploadProgressTrackerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  files: UploadFileProgress[];
  datasetName?: string;
  onCancel?: () => void;
  onRetry?: (fileId: string) => void;
  className?: string;
}

export function UploadProgressTracker({
  open,
  onOpenChange,
  files,
  datasetName,
  onCancel,
  onRetry,
  className = ''
}: UploadProgressTrackerProps) {
  const totalFiles = files.length;
  const completedFiles = files.filter(f => f.status === 'completed').length;
  const failedFiles = files.filter(f => f.status === 'failed').length;
  const uploadingFiles = files.filter(f => f.status === 'uploading').length;

  // Calculate overall progress
  const overallProgress = totalFiles > 0 ? (completedFiles / totalFiles) * 100 : 0;

  // Check if all uploads are done (completed or failed)
  const isUploadComplete = uploadingFiles === 0 && files.every(f =>
    f.status === 'completed' || f.status === 'failed'
  );

  const getStatusIcon = (status: string, progress?: number) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'uploading':
        return <Upload className="w-5 h-5 text-blue-500 animate-pulse" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'pending':
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600';
      case 'uploading':
        return 'text-blue-600';
      case 'failed':
        return 'text-red-600';
      case 'pending':
      default:
        return 'text-gray-600';
    }
  };

  const formatFileSizeDisplay = (bytes?: number) => {
    if (!bytes) return '';
    return ` (${formatFileSize(bytes)})`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={`max-w-2xl max-h-[80vh] overflow-y-auto ${className}`}>
        <div className="flex flex-col space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                <Upload className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  Upload Progress
                </h2>
                <p className="text-sm text-gray-600">
                  {datasetName ? `Uploading to "${datasetName}"` : 'Uploading documents'}
                </p>
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

          {/* Overall Progress */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">
                Overall Progress
              </span>
              <span className="text-sm text-gray-600">
                {completedFiles} of {totalFiles} completed
              </span>
            </div>
            <Progress
              value={overallProgress}
              className="h-2"
            />
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{Math.round(overallProgress)}% complete</span>
              <div className="flex items-center space-x-4">
                {uploadingFiles > 0 && (
                  <span className="text-blue-600">
                    {uploadingFiles} uploading
                  </span>
                )}
                {failedFiles > 0 && (
                  <span className="text-red-600">
                    {failedFiles} failed
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* File List */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-700">Files</h3>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {files.map((file) => (
                <div key={file.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                  <FileText className="w-5 h-5 text-gray-400 flex-shrink-0" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="font-medium text-gray-900 truncate">
                        {file.filename}
                        {formatFileSizeDisplay(file.fileSize)}
                      </p>
                      {getStatusIcon(file.status, file.progress)}
                    </div>

                    {/* Individual file progress */}
                    {file.status === 'uploading' && file.progress !== undefined && (
                      <div className="mt-2">
                        <Progress
                          value={file.progress}
                          className="h-1"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          {file.progress}%
                        </p>
                      </div>
                    )}

                    {/* Status text */}
                    <p className={`text-sm ${getStatusColor(file.status)}`}>
                      {file.status === 'pending' && 'Waiting to upload...'}
                      {file.status === 'uploading' && 'Uploading...'}
                      {file.status === 'completed' && 'Upload complete'}
                      {file.status === 'failed' && (file.error || 'Upload failed')}
                    </p>
                  </div>

                  {/* Retry button for failed uploads */}
                  {file.status === 'failed' && onRetry && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRetry(file.id)}
                      className="text-blue-600 hover:text-blue-700"
                    >
                      Retry
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between pt-4 border-t">
            <div className="text-sm text-gray-600">
              {isUploadComplete ? (
                failedFiles > 0 ? (
                  <span className="text-red-600">
                    Upload complete with {failedFiles} failed file{failedFiles !== 1 ? 's' : ''}
                  </span>
                ) : (
                  <span className="text-green-600">
                    All files uploaded successfully!
                  </span>
                )
              ) : (
                `${uploadingFiles} file${uploadingFiles !== 1 ? 's' : ''} uploading...`
              )}
            </div>

            <div className="flex items-center space-x-3">
              {!isUploadComplete && onCancel && (
                <Button
                  variant="outline"
                  onClick={onCancel}
                >
                  Cancel
                </Button>
              )}
              <Button
                variant={isUploadComplete ? "default" : "outline"}
                onClick={() => onOpenChange(false)}
              >
                {isUploadComplete ? 'Done' : 'Close'}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}