'use client';

import { useState, useEffect } from 'react';
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  Clock, 
  FileText, 
  Zap, 
  Database,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface ProcessingStep {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  error?: string;
  duration?: number; // in milliseconds
}

interface ProcessingStatusProps {
  documentId: string;
  documentName: string;
  overallStatus: 'pending' | 'processing' | 'completed' | 'failed';
  steps: ProcessingStep[];
  onRetry?: () => void;
  onCancel?: () => void;
  showDetails?: boolean;
  className?: string;
}

const DEFAULT_STEPS: ProcessingStep[] = [
  {
    id: 'upload',
    name: 'File Upload',
    description: 'Uploading file to secure storage',
    status: 'pending'
  },
  {
    id: 'validation',
    name: 'File Validation',
    description: 'Checking file format and content',
    status: 'pending'
  },
  {
    id: 'extraction',
    name: 'Text Extraction',
    description: 'Extracting text from document',
    status: 'pending'
  },
  {
    id: 'chunking',
    name: 'Text Chunking',
    description: 'Breaking text into optimal chunks',
    status: 'pending'
  },
  {
    id: 'embedding',
    name: 'Vector Generation',
    description: 'Generating embeddings with BAAI/bge-m3',
    status: 'pending'
  },
  {
    id: 'indexing',
    name: 'Vector Indexing',
    description: 'Storing vectors in search index',
    status: 'pending'
  }
];

export function ProcessingStatus({
  documentId,
  documentName,
  overallStatus,
  steps = DEFAULT_STEPS,
  onRetry,
  onCancel,
  showDetails = true,
  className = ''
}: ProcessingStatusProps) {
  const [expandedDetails, setExpandedDetails] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [startTime] = useState(Date.now());

  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (overallStatus === 'processing') {
      interval = setInterval(() => {
        setElapsedTime(Date.now() - startTime);
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [overallStatus, startTime]);

  const getStepIcon = (step: ProcessingStep) => {
    switch (step.status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-400" />;
      case 'processing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getStepIconForType = (stepId: string) => {
    switch (stepId) {
      case 'upload':
        return <FileText className="w-4 h-4" />;
      case 'validation':
        return <AlertCircle className="w-4 h-4" />;
      case 'extraction':
        return <FileText className="w-4 h-4" />;
      case 'chunking':
        return <Database className="w-4 h-4" />;
      case 'embedding':
        return <Zap className="w-4 h-4" />;
      case 'indexing':
        return <Database className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const getOverallProgress = () => {
    const completedSteps = steps.filter(s => s.status === 'completed').length;
    const processingStep = steps.find(s => s.status === 'processing');
    
    let baseProgress = (completedSteps / steps.length) * 100;
    
    if (processingStep && processingStep.progress) {
      baseProgress += (processingStep.progress / steps.length);
    }
    
    return Math.min(100, baseProgress);
  };

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const getOverallStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-gray-100 text-gray-700 border-gray-200';
      case 'processing':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'completed':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'failed':
        return 'bg-red-100 text-red-700 border-red-200';
    }
  };

  const currentStep = steps.find(s => s.status === 'processing');
  const failedStep = steps.find(s => s.status === 'failed');

  return (
    <div className={cn('bg-white border rounded-lg p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
            {overallStatus === 'processing' ? (
              <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
            ) : overallStatus === 'completed' ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : overallStatus === 'failed' ? (
              <XCircle className="w-5 h-5 text-red-600" />
            ) : (
              <Clock className="w-5 h-5 text-gray-600" />
            )}
          </div>
          
          <div>
            <h3 className="font-semibold text-gray-900">{documentName}</h3>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Badge className={cn('text-xs border', getOverallStatusColor(overallStatus))}>
                {overallStatus}
              </Badge>
              {overallStatus === 'processing' && (
                <span>{formatDuration(elapsedTime)}</span>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {showDetails && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpandedDetails(!expandedDetails)}
            >
              {expandedDetails ? 'Hide Details' : 'Show Details'}
            </Button>
          )}
          
          {overallStatus === 'failed' && onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
          )}
          
          {overallStatus === 'processing' && onCancel && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onCancel}
              className="text-red-600 hover:text-red-700"
            >
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Overall Progress */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm text-gray-600 mb-2">
          <span>
            {currentStep ? `${currentStep.name}...` : 
             overallStatus === 'completed' ? 'Processing complete' :
             overallStatus === 'failed' ? 'Processing failed' :
             'Waiting to start'}
          </span>
          <span>{Math.round(getOverallProgress())}%</span>
        </div>
        <Progress value={getOverallProgress()} className="h-2" />
      </div>

      {/* Current Step Details */}
      {currentStep && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
            <span className="font-medium text-blue-900">{currentStep.name}</span>
          </div>
          <p className="text-sm text-blue-700">{currentStep.description}</p>
          {currentStep.progress !== undefined && (
            <Progress value={currentStep.progress} className="mt-2 h-1" />
          )}
        </div>
      )}

      {/* Failed Step Details */}
      {failedStep && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <XCircle className="w-4 h-4 text-red-600" />
            <span className="font-medium text-red-900">Failed at: {failedStep.name}</span>
          </div>
          {failedStep.error && (
            <p className="text-sm text-red-700">{failedStep.error}</p>
          )}
        </div>
      )}

      {/* Detailed Steps */}
      {expandedDetails && (
        <div className="space-y-3 pt-4 border-t border-gray-200">
          <h4 className="font-medium text-gray-900">Processing Steps</h4>
          
          {steps.map((step, index) => (
            <div
              key={step.id}
              className={cn(
                'flex items-center gap-3 p-3 rounded-lg border',
                step.status === 'completed' ? 'bg-green-50 border-green-200' :
                step.status === 'processing' ? 'bg-blue-50 border-blue-200' :
                step.status === 'failed' ? 'bg-red-50 border-red-200' :
                'bg-gray-50 border-gray-200'
              )}
            >
              <div className="flex items-center gap-2">
                <span className={cn(
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium',
                  step.status === 'completed' ? 'bg-green-600 text-white' :
                  step.status === 'processing' ? 'bg-blue-600 text-white' :
                  step.status === 'failed' ? 'bg-red-600 text-white' :
                  'bg-gray-400 text-white'
                )}>
                  {index + 1}
                </span>
                {getStepIcon(step)}
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h5 className="font-medium text-gray-900">{step.name}</h5>
                  <Badge variant="outline" className="text-xs">
                    {step.status}
                  </Badge>
                </div>
                <p className="text-sm text-gray-600">{step.description}</p>
                
                {step.status === 'processing' && step.progress !== undefined && (
                  <Progress value={step.progress} className="mt-2 h-1" />
                )}
                
                {step.error && (
                  <p className="text-sm text-red-600 mt-1">{step.error}</p>
                )}
                
                {step.duration && step.status === 'completed' && (
                  <p className="text-xs text-gray-500 mt-1">
                    Completed in {formatDuration(step.duration)}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}