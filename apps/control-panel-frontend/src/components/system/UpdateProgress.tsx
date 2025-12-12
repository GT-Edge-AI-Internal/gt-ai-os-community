'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { systemApi } from '@/lib/api';
import toast from 'react-hot-toast';

interface UpdateStage {
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  error?: string;
}

// Backend response format
interface BackendUpdateStatus {
  uuid: string;
  target_version: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'rolled_back';
  started_at: string;
  completed_at: string | null;
  current_stage: string | null;  // e.g., "creating_backup", "executing_update"
  logs: Array<{ timestamp: string; level: string; message: string }>;
  error_message: string | null;
  backup_id: number | null;
}

// Frontend display format
interface UpdateStatus {
  update_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'rolled_back';
  current_stage: number;
  stages: UpdateStage[];
  overall_progress: number;
  logs: string[];
}

interface UpdateProgressProps {
  updateId: string;
  onComplete: () => void;
  onFailed: () => void;
}

const STAGE_NAMES = [
  'Creating Backup',
  'Executing Update',
  'Verifying Health'
];

// Map backend stage names to indices
const STAGE_MAP: Record<string, number> = {
  'creating_backup': 0,
  'executing_update': 1,
  'completed': 2,
  'failed': 2,
  'rolling_back': 2,
  'rolled_back': 2
};

const POLL_INTERVAL = 2000; // 2 seconds

// Transform backend response to frontend format
function transformStatus(backend: BackendUpdateStatus): UpdateStatus {
  const currentStageIndex = backend.current_stage ? STAGE_MAP[backend.current_stage] ?? 1 : 0;

  // Build stages array based on current progress
  const stages: UpdateStage[] = STAGE_NAMES.map((name, index) => {
    let stageStatus: UpdateStage['status'] = 'pending';
    let progress = 0;

    if (backend.status === 'completed' || backend.status === 'rolled_back') {
      stageStatus = 'completed';
      progress = 100;
    } else if (backend.status === 'failed') {
      if (index < currentStageIndex) {
        stageStatus = 'completed';
        progress = 100;
      } else if (index === currentStageIndex) {
        stageStatus = 'failed';
        progress = 50;
      }
    } else if (index < currentStageIndex) {
      stageStatus = 'completed';
      progress = 100;
    } else if (index === currentStageIndex) {
      stageStatus = 'in_progress';
      progress = 50;
    }

    return {
      name,
      status: stageStatus,
      progress,
      error: index === currentStageIndex && backend.status === 'failed' ? backend.error_message || undefined : undefined
    };
  });

  // Calculate overall progress
  let overallProgress = 0;
  if (backend.status === 'completed' || backend.status === 'rolled_back') {
    overallProgress = 100;
  } else if (backend.status === 'failed') {
    overallProgress = ((currentStageIndex + 0.5) / STAGE_NAMES.length) * 100;
  } else {
    overallProgress = ((currentStageIndex + 0.5) / STAGE_NAMES.length) * 100;
  }

  // Transform logs from objects to strings
  const logs = backend.logs.map(log =>
    `[${new Date(log.timestamp).toLocaleTimeString()}] [${log.level.toUpperCase()}] ${log.message}`
  );

  return {
    update_id: backend.uuid,
    status: backend.status,
    current_stage: currentStageIndex,
    stages,
    overall_progress: overallProgress,
    logs
  };
}

export function UpdateProgress({ updateId, onComplete, onFailed }: UpdateProgressProps) {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [isLogsExpanded, setIsLogsExpanded] = useState(false);
  const [isRollingBack, setIsRollingBack] = useState(false);

  useEffect(() => {
    fetchStatus();

    const interval = setInterval(() => {
      fetchStatus();
    }, POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [updateId]);

  const fetchStatus = async () => {
    try {
      const response = await systemApi.getUpdateStatus(updateId);
      const backendData = response.data as BackendUpdateStatus;
      const transformedData = transformStatus(backendData);
      setStatus(transformedData);

      if (transformedData.status === 'completed') {
        onComplete();
      } else if (transformedData.status === 'failed') {
        onFailed();
      }
    } catch (error) {
      console.error('Failed to fetch update status:', error);
      toast.error('Failed to fetch update status');
    }
  };

  const handleRollback = async () => {
    if (!confirm('Are you sure you want to rollback this update? This will restore the previous version.')) {
      return;
    }

    setIsRollingBack(true);
    try {
      await systemApi.rollback(updateId);
      toast.success('Rollback initiated successfully');
      // Refresh status
      fetchStatus();
    } catch (error) {
      console.error('Failed to initiate rollback:', error);
      toast.error('Failed to initiate rollback');
    } finally {
      setIsRollingBack(false);
    }
  };

  const getStageIcon = (stage: UpdateStage) => {
    switch (stage.status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-600" />;
      case 'in_progress':
        return <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />;
      default:
        return <div className="h-5 w-5 rounded-full border-2 border-gray-300" />;
    }
  };

  const getStageClass = (stage: UpdateStage) => {
    switch (stage.status) {
      case 'completed':
        return 'bg-green-50 border-green-200';
      case 'failed':
        return 'bg-red-50 border-red-200';
      case 'in_progress':
        return 'bg-blue-50 border-blue-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  if (!status) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>Loading update status...</span>
      </div>
    );
  }

  const showRollbackButton = status.status === 'failed' && !isRollingBack;
  const showCloseButton = status.status === 'completed';

  return (
    <div className="space-y-6" role="region" aria-label="Update progress">
      {/* Overall Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Overall Progress</span>
          <span className="text-muted-foreground">{Math.round(status.overall_progress)}%</span>
        </div>
        <Progress value={status.overall_progress} className="h-3" />
      </div>

      {/* Stage Progress */}
      <div className="space-y-3">
        {status.stages.map((stage, index) => (
          <Card key={index} className={`${getStageClass(stage)} border`}>
            <CardContent className="p-4">
              <div className="flex items-start space-x-3">
                <div className="mt-0.5">{getStageIcon(stage)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{stage.name}</span>
                    {stage.status === 'in_progress' && (
                      <span className="text-sm text-muted-foreground">{Math.round(stage.progress)}%</span>
                    )}
                  </div>
                  {stage.error && (
                    <div className="mt-2 text-sm text-red-600 flex items-start">
                      <AlertCircle className="h-4 w-4 mr-1 mt-0.5 shrink-0" />
                      <span>{stage.error}</span>
                    </div>
                  )}
                  {stage.status === 'in_progress' && (
                    <Progress value={stage.progress} className="h-2 mt-2" />
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Log Viewer */}
      {status.logs.length > 0 && (
        <div className="border rounded-lg overflow-hidden">
          <button
            onClick={() => setIsLogsExpanded(!isLogsExpanded)}
            className="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-sm font-medium transition-colors"
            aria-expanded={isLogsExpanded}
            aria-controls="update-logs"
          >
            <span>View Update Logs ({status.logs.length} entries)</span>
            {isLogsExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
          {isLogsExpanded && (
            <div
              id="update-logs"
              className="bg-gray-900 text-gray-100 p-4 max-h-64 overflow-y-auto font-mono text-xs"
              role="log"
              aria-live="polite"
            >
              {status.logs.map((log, index) => (
                <div key={index} className="py-0.5">
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Action Buttons */}
      {(showRollbackButton || showCloseButton) && (
        <div className="flex justify-end space-x-3 pt-4">
          {showRollbackButton && (
            <Button
              variant="destructive"
              onClick={handleRollback}
              disabled={isRollingBack}
            >
              {isRollingBack ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Rolling Back...
                </>
              ) : (
                'Rollback'
              )}
            </Button>
          )}
          {showCloseButton && (
            <Button variant="default" onClick={onComplete}>
              Close
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
