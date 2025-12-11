"use client";

import { useState, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert } from '@/components/ui/alert';
import { usersApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { Loader2, Upload, Download, FileText, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

interface BulkUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploadComplete?: () => void;
}

interface UploadError {
  row: number;
  email: string;
  reason: string;
}

interface UploadResult {
  success_count: number;
  failed_count: number;
  total_rows: number;
  errors: UploadError[];
}

export default function BulkUploadDialog({ open, onOpenChange, onUploadComplete }: BulkUploadDialogProps) {
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        toast.error('Please select a CSV file');
        return;
      }
      setFile(selectedFile);
      setUploadResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a file');
      return;
    }

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await usersApi.bulkUpload(formData);
      const result = response.data;

      setUploadResult(result);

      if (result.failed_count === 0) {
        toast.success(`Successfully uploaded ${result.success_count} users`);
        if (onUploadComplete) {
          onUploadComplete();
        }
      } else {
        toast.error(`Uploaded ${result.success_count} users, ${result.failed_count} failed`);
      }
    } catch (error: any) {
      console.error('Failed to upload users:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to upload users';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadTemplate = () => {
    const csvContent = `email,full_name,password,user_type,tenant_id,tfa_required
john.doe@example.com,John Doe,SecurePass123!,tenant_user,1,false
jane.smith@example.com,Jane Smith,AnotherPass456!,tenant_admin,1,true
admin@example.com,Admin User,AdminPass789!,super_admin,,false`;

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'user-upload-template.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const handleClose = () => {
    setFile(null);
    setUploadResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Bulk Upload Users</DialogTitle>
          <DialogDescription>
            Upload a CSV file to create multiple users at once
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Template Download */}
          <Alert>
            <Download className="h-4 w-4" />
            <div className="ml-2">
              <p className="font-medium">Need a template?</p>
              <p className="text-sm mt-1">
                Download the CSV template with example data to get started.
              </p>
              <Button
                variant="link"
                size="sm"
                onClick={handleDownloadTemplate}
                className="p-0 h-auto mt-2"
              >
                <Download className="h-3 w-3 mr-1" />
                Download Template
              </Button>
            </div>
          </Alert>

          {/* CSV Format Info */}
          <div className="bg-muted p-4 rounded-md space-y-2">
            <p className="font-medium text-sm">CSV Format Requirements:</p>
            <ul className="text-sm space-y-1 list-disc list-inside">
              <li>Required columns: email, full_name, password, user_type</li>
              <li>Optional columns: tenant_id (required for tenant_user and tenant_admin), tfa_required</li>
              <li>Valid user types: tenant_user, tenant_admin, super_admin</li>
              <li>Password cannot be empty</li>
              <li>Leave tenant_id blank for super_admin users</li>
              <li>tfa_required values: true/false, 1/0, yes/no (default: false)</li>
            </ul>
          </div>

          {/* File Upload */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Upload CSV File</label>
            <div className="flex items-center space-x-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="hidden"
              />
              <Button
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                className="w-full"
              >
                <Upload className="h-4 w-4 mr-2" />
                {file ? file.name : 'Choose CSV File'}
              </Button>
            </div>
            {file && (
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                <span>{file.name} ({(file.size / 1024).toFixed(2)} KB)</span>
              </div>
            )}
          </div>

          {/* Upload Results */}
          {uploadResult && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-muted p-3 rounded-md">
                  <div className="text-sm text-muted-foreground">Total Rows</div>
                  <div className="text-2xl font-bold">{uploadResult.total_rows}</div>
                </div>
                <div className="bg-green-50 dark:bg-green-950 p-3 rounded-md">
                  <div className="text-sm text-green-600 dark:text-green-400 flex items-center">
                    <CheckCircle className="h-3 w-3 mr-1" />
                    Success
                  </div>
                  <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {uploadResult.success_count}
                  </div>
                </div>
                <div className="bg-red-50 dark:bg-red-950 p-3 rounded-md">
                  <div className="text-sm text-red-600 dark:text-red-400 flex items-center">
                    <XCircle className="h-3 w-3 mr-1" />
                    Failed
                  </div>
                  <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                    {uploadResult.failed_count}
                  </div>
                </div>
              </div>

              {/* Error Details */}
              {uploadResult.errors.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center space-x-2 text-sm font-medium">
                    <AlertTriangle className="h-4 w-4 text-destructive" />
                    <span>Errors ({uploadResult.errors.length})</span>
                  </div>
                  <div className="max-h-40 overflow-y-auto space-y-2">
                    {uploadResult.errors.map((error, index) => (
                      <div key={index} className="bg-destructive/10 p-2 rounded-md text-sm">
                        <div className="font-medium">Row {error.row}: {error.email}</div>
                        <div className="text-muted-foreground">{error.reason}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={loading}
          >
            {uploadResult ? 'Close' : 'Cancel'}
          </Button>
          {!uploadResult && (
            <Button
              type="button"
              onClick={handleUpload}
              disabled={!file || loading}
            >
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Upload Users
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}