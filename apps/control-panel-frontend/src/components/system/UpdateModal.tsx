'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, AlertCircle, Loader2, HardDrive, Database, Activity, Clock } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { systemApi } from '@/lib/api';
import toast from 'react-hot-toast';
import { UpdateProgress } from './UpdateProgress';

interface UpdateInfo {
  current_version: string;
  latest_version: string;
  update_type: 'major' | 'minor' | 'patch';
  release_notes: string;
  released_at: string;
}

interface ValidationCheck {
  name: string;
  backendName: string;  // Backend uses snake_case names
  status: 'pending' | 'checking' | 'passed' | 'failed';
  message?: string;
  icon: React.ReactNode;
}

interface UpdateModalProps {
  updateInfo: UpdateInfo;
  open: boolean;
  onClose: () => void;
}

// Map backend check names to display names
const CHECK_NAME_MAP: Record<string, string> = {
  'disk_space': 'Disk Space',
  'container_health': 'Container Health',
  'database_connectivity': 'Database Connectivity',
  'recent_backup': 'Last Backup Age'
};

export function UpdateModal({ updateInfo, open, onClose }: UpdateModalProps) {
  const [validationChecks, setValidationChecks] = useState<ValidationCheck[]>([
    {
      name: 'Disk Space',
      backendName: 'disk_space',
      status: 'pending',
      icon: <HardDrive className="h-5 w-5" />
    },
    {
      name: 'Container Health',
      backendName: 'container_health',
      status: 'pending',
      icon: <Activity className="h-5 w-5" />
    },
    {
      name: 'Database Connectivity',
      backendName: 'database_connectivity',
      status: 'pending',
      icon: <Database className="h-5 w-5" />
    },
    {
      name: 'Last Backup Age',
      backendName: 'recent_backup',
      status: 'pending',
      icon: <Clock className="h-5 w-5" />
    }
  ]);

  const [createBackup, setCreateBackup] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [validationComplete, setValidationComplete] = useState(false);
  const [updateStarted, setUpdateStarted] = useState(false);
  const [updateId, setUpdateId] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      runValidation();
    }
  }, [open]);

  const runValidation = async () => {
    setIsValidating(true);

    try {
      const response = await systemApi.validateUpdate(updateInfo.latest_version);
      const validationResults = response.data;

      // Update checks based on API response - match by backendName
      const updatedChecks = validationChecks.map(check => {
        const result = validationResults.checks.find((c: any) => c.name === check.backendName);
        if (result) {
          return {
            ...check,
            status: result.passed ? 'passed' : 'failed',
            message: result.message
          };
        }
        return check;
      });

      setValidationChecks(updatedChecks);
      setValidationComplete(true);
    } catch (error) {
      console.error('Validation failed:', error);
      toast.error('Failed to validate system for update');

      // Mark all checks as failed
      const failedChecks = validationChecks.map(check => ({
        ...check,
        status: 'failed' as const,
        message: 'Validation check failed'
      }));
      setValidationChecks(failedChecks);
      setValidationComplete(true);
    } finally {
      setIsValidating(false);
    }
  };

  const handleStartUpdate = async () => {
    if (!allChecksPassed) {
      toast.error('Cannot start update: validation checks failed');
      return;
    }

    try {
      const response = await systemApi.startUpdate(updateInfo.latest_version, createBackup);
      const data = response.data;

      setUpdateId(data.update_id);
      setUpdateStarted(true);
      toast.success('Update started successfully');
    } catch (error) {
      console.error('Failed to start update:', error);
      toast.error('Failed to start update');
    }
  };

  const handleUpdateComplete = () => {
    toast.success('Update completed successfully!');
    setTimeout(() => {
      window.location.reload();
    }, 2000);
  };

  const handleUpdateFailed = () => {
    toast.error('Update failed. Check logs for details.');
  };

  const getCheckIcon = (status: string) => {
    switch (status) {
      case 'passed':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-600" />;
      case 'checking':
        return <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />;
      default:
        return <AlertCircle className="h-5 w-5 text-gray-400" />;
    }
  };

  const getCheckClass = (status: string) => {
    switch (status) {
      case 'passed':
        return 'bg-green-50 border-green-200';
      case 'failed':
        return 'bg-red-50 border-red-200';
      case 'checking':
        return 'bg-blue-50 border-blue-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getUpdateTypeBadge = () => {
    switch (updateInfo.update_type) {
      case 'major':
        return <Badge className="bg-red-600">Major Update</Badge>;
      case 'minor':
        return <Badge className="bg-amber-600">Minor Update</Badge>;
      case 'patch':
        return <Badge className="bg-blue-600">Patch Update</Badge>;
      default:
        return <Badge>Update</Badge>;
    }
  };

  const allChecksPassed = validationComplete && validationChecks.every(check => check.status === 'passed');

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Software Update Available</span>
            {getUpdateTypeBadge()}
          </DialogTitle>
          <DialogDescription>
            Update GT 2.0 from v{updateInfo.current_version} to v{updateInfo.latest_version}
          </DialogDescription>
        </DialogHeader>

        {!updateStarted ? (
          <div className="space-y-6">
            {/* Release Notes */}
            <div className="space-y-2">
              <h3 className="font-medium text-sm">Release Notes</h3>
              <Card>
                <CardContent className="p-4 prose prose-sm max-w-none">
                  <div
                    className="text-sm text-muted-foreground whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{ __html: updateInfo.release_notes }}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Pre-update Validation */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-sm">Pre-Update Validation</h3>
                {isValidating && (
                  <span className="text-sm text-muted-foreground flex items-center">
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Validating...
                  </span>
                )}
              </div>

              {validationChecks.map((check, index) => (
                <Card key={index} className={`${getCheckClass(check.status)} border`}>
                  <CardContent className="p-3">
                    <div className="flex items-center space-x-3">
                      <div>{check.icon}</div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm">{check.name}</span>
                          <div>{getCheckIcon(check.status)}</div>
                        </div>
                        {check.message && (
                          <p className="text-xs text-muted-foreground mt-1">{check.message}</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Backup Option */}
            <div className="flex items-center space-x-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <input
                type="checkbox"
                id="create-backup"
                checked={createBackup}
                onChange={(e) => setCreateBackup(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600"
              />
              <label htmlFor="create-backup" className="text-sm font-medium cursor-pointer">
                Create backup before update (recommended)
              </label>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end space-x-3">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                onClick={handleStartUpdate}
                disabled={!allChecksPassed || isValidating}
              >
                {isValidating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Validating...
                  </>
                ) : (
                  'Start Update'
                )}
              </Button>
            </div>
          </div>
        ) : (
          <UpdateProgress
            updateId={updateId!}
            onComplete={handleUpdateComplete}
            onFailed={handleUpdateFailed}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
