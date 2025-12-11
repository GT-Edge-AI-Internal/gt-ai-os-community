'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Play, 
  Loader2, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Zap,
  BarChart3,
  Calendar,
  DollarSign,
  AlertCircle,
  Workflow,
  ArrowRight,
  TrendingUp,
  Timer
} from 'lucide-react';
import { cn, formatTime, formatDateTime } from '@/lib/utils';
import type { 
  Workflow,
  WorkflowExecution,
  WorkflowInterfaceProps,
  ButtonInterfaceConfig,
  ExecutionSummary
} from '@/types/workflow';

interface WorkflowButtonInterfaceProps extends WorkflowInterfaceProps {
  config?: Partial<ButtonInterfaceConfig>;
  showDetailedStats?: boolean;
  recentExecutions?: ExecutionSummary[];
  onViewExecution?: (executionId: string) => void;
}

interface QuickStatsProps {
  workflow: Workflow;
  recentExecutions?: ExecutionSummary[];
  className?: string;
}

function QuickStats({ workflow, recentExecutions = [], className }: QuickStatsProps) {
  const last24hExecutions = recentExecutions.filter(
    exec => new Date(exec.started_at) > new Date(Date.now() - 24 * 60 * 60 * 1000)
  ).length;

  const successfulExecutions = recentExecutions.filter(
    exec => exec.status === 'completed'
  ).length;

  const avgExecutionTime = recentExecutions.length > 0
    ? recentExecutions
        .filter(exec => exec.duration_ms)
        .reduce((sum, exec) => sum + (exec.duration_ms || 0), 0) / 
      recentExecutions.filter(exec => exec.duration_ms).length
    : workflow.average_execution_time_ms || 0;

  const totalCost = recentExecutions.reduce(
    (sum, exec) => sum + exec.cost_cents, 0
  );

  return (
    <div className={cn("grid grid-cols-2 gap-4", className)}>
      <div className="text-center p-3 bg-blue-50 rounded-lg border border-blue-200">
        <div className="flex items-center justify-center gap-1 mb-1">
          <BarChart3 className="w-4 h-4 text-blue-600" />
          <span className="text-sm font-medium text-blue-900">Total Runs</span>
        </div>
        <div className="text-2xl font-bold text-blue-700">
          {workflow.execution_count.toLocaleString()}
        </div>
        {last24hExecutions > 0 && (
          <div className="text-xs text-blue-600 mt-1">
            +{last24hExecutions} today
          </div>
        )}
      </div>

      <div className="text-center p-3 bg-green-50 rounded-lg border border-green-200">
        <div className="flex items-center justify-center gap-1 mb-1">
          <TrendingUp className="w-4 h-4 text-green-600" />
          <span className="text-sm font-medium text-green-900">Success Rate</span>
        </div>
        <div className="text-2xl font-bold text-green-700">
          {recentExecutions.length > 0 
            ? Math.round((successfulExecutions / recentExecutions.length) * 100)
            : 95
          }%
        </div>
        <div className="text-xs text-green-600 mt-1">
          {successfulExecutions}/{recentExecutions.length || workflow.execution_count} runs
        </div>
      </div>

      <div className="text-center p-3 bg-purple-50 rounded-lg border border-purple-200">
        <div className="flex items-center justify-center gap-1 mb-1">
          <Timer className="w-4 h-4 text-purple-600" />
          <span className="text-sm font-medium text-purple-900">Avg Time</span>
        </div>
        <div className="text-2xl font-bold text-purple-700">
          {avgExecutionTime > 0 
            ? `${(avgExecutionTime / 1000).toFixed(1)}s`
            : '—'
          }
        </div>
        <div className="text-xs text-purple-600 mt-1">
          per execution
        </div>
      </div>

      <div className="text-center p-3 bg-orange-50 rounded-lg border border-orange-200">
        <div className="flex items-center justify-center gap-1 mb-1">
          <DollarSign className="w-4 h-4 text-orange-600" />
          <span className="text-sm font-medium text-orange-900">Total Cost</span>
        </div>
        <div className="text-2xl font-bold text-orange-700">
          ${((workflow.total_cost_cents + totalCost) / 100).toFixed(2)}
        </div>
        <div className="text-xs text-orange-600 mt-1">
          all time
        </div>
      </div>
    </div>
  );
}

interface RecentExecutionsProps {
  executions: ExecutionSummary[];
  onViewExecution?: (executionId: string) => void;
  className?: string;
}

function RecentExecutions({ executions, onViewExecution, className }: RecentExecutionsProps) {
  if (executions.length === 0) {
    return (
      <div className={cn("text-center py-6 text-gray-500", className)}>
        <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No recent executions</p>
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <h4 className="text-sm font-medium text-gray-700 mb-3">Recent Executions</h4>
      {executions.slice(0, 5).map((execution) => (
        <div
          key={execution.id}
          className={cn(
            "flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors",
            "hover:bg-gray-50",
            execution.status === 'completed' && "bg-green-50 border-green-200",
            execution.status === 'failed' && "bg-red-50 border-red-200",
            execution.status === 'running' && "bg-blue-50 border-blue-200"
          )}
          onClick={() => onViewExecution?.(execution.id)}
        >
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1">
              {execution.status === 'completed' && (
                <CheckCircle className="w-4 h-4 text-green-600" />
              )}
              {execution.status === 'failed' && (
                <XCircle className="w-4 h-4 text-red-600" />
              )}
              {execution.status === 'running' && (
                <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
              )}
              {execution.status === 'pending' && (
                <Clock className="w-4 h-4 text-yellow-600" />
              )}
              
              <span className={cn(
                "text-xs font-medium capitalize",
                execution.status === 'completed' && "text-green-700",
                execution.status === 'failed' && "text-red-700",
                execution.status === 'running' && "text-blue-700",
                execution.status === 'pending' && "text-yellow-700"
              )}>
                {execution.status}
              </span>
            </div>
            
            <Badge variant="secondary" className="text-xs">
              {execution.interaction_mode}
            </Badge>
          </div>

          <div className="flex items-center gap-4 text-xs text-gray-600">
            {execution.duration_ms && (
              <span>{(execution.duration_ms / 1000).toFixed(1)}s</span>
            )}
            
            {execution.cost_cents > 0 && (
              <span>${(execution.cost_cents / 100).toFixed(4)}</span>
            )}
            
            <span>{formatTime(execution.started_at)}</span>
            
            <ArrowRight className="w-3 h-3" />
          </div>
        </div>
      ))}
    </div>
  );
}

interface LastExecutionInfoProps {
  workflow: Workflow;
  recentExecutions?: ExecutionSummary[];
  className?: string;
}

function LastExecutionInfo({ workflow, recentExecutions = [], className }: LastExecutionInfoProps) {
  const lastExecution = recentExecutions[0];
  
  if (!workflow.last_executed && !lastExecution) {
    return (
      <div className={cn("text-center py-4 text-gray-500", className)}>
        <Calendar className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">Never executed</p>
      </div>
    );
  }

  const executionDate = lastExecution 
    ? new Date(lastExecution.started_at)
    : new Date(workflow.last_executed!);

  const timeAgo = () => {
    const now = new Date();
    const diffMs = now.getTime() - executionDate.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  return (
    <div className={cn("text-center py-4", className)}>
      <div className="flex items-center justify-center gap-2 mb-2">
        <Calendar className="w-4 h-4 text-gray-600" />
        <span className="text-sm font-medium text-gray-700">Last Execution</span>
      </div>
      
      <div className="space-y-1">
        <p className="text-lg font-semibold text-gray-900">
          {timeAgo()}
        </p>
        
        <p className="text-xs text-gray-500">
          {formatDateTime(executionDate)}
        </p>
        
        {lastExecution && (
          <div className="flex items-center justify-center gap-2 mt-2">
            <Badge 
              variant={lastExecution.status === 'completed' ? 'default' : 'destructive'}
              className="text-xs"
            >
              {lastExecution.status}
            </Badge>
            
            {lastExecution.duration_ms && (
              <span className="text-xs text-gray-600">
                {(lastExecution.duration_ms / 1000).toFixed(1)}s
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function WorkflowButtonInterface({
  workflow,
  onExecute,
  onExecutionUpdate,
  config = {},
  showDetailedStats = false,
  recentExecutions = [],
  onViewExecution,
  className
}: WorkflowButtonInterfaceProps) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastExecution, setLastExecution] = useState<WorkflowExecution | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const buttonConfig: ButtonInterfaceConfig = {
    button_text: `Execute ${workflow.name}`,
    button_variant: 'default',
    button_size: 'lg',
    description: workflow.description,
    show_stats: true,
    show_last_execution: true,
    auto_execute_on_load: false,
    ...config
  };

  // Auto-execute on load if configured
  useEffect(() => {
    if (buttonConfig.auto_execute_on_load && !isExecuting && !lastExecution) {
      handleExecute();
    }
  }, [buttonConfig.auto_execute_on_load]);

  const handleExecute = async () => {
    if (isExecuting) return;

    setIsExecuting(true);
    setExecutionError(null);

    try {
      const execution = await onExecute({
        interaction_mode: 'button',
        trigger_type: 'manual',
        triggered_at: new Date().toISOString()
      });

      setLastExecution(execution);

      // If execution is running, poll for updates
      if (execution.status === 'running') {
        pollExecutionStatus(execution.id);
      } else {
        setIsExecuting(false);
      }

      if (onExecutionUpdate) {
        onExecutionUpdate(execution);
      }

    } catch (error) {
      console.error('Failed to execute workflow:', error);
      setExecutionError(error instanceof Error ? error.message : 'Unknown error');
      setIsExecuting(false);
    }
  };

  const pollExecutionStatus = async (executionId: string) => {
    try {
      // Simulate polling for execution status
      // In a real implementation, this would call the backend API
      setTimeout(() => {
        const updatedExecution: WorkflowExecution = {
          ...lastExecution!,
          status: 'completed',
          progress_percentage: 100,
          completed_at: new Date().toISOString(),
          duration_ms: 1800,
          output_data: {
            result: 'Workflow executed successfully via button interface'
          },
          tokens_used: 75,
          cost_cents: 3
        };

        setLastExecution(updatedExecution);
        setIsExecuting(false);

        if (onExecutionUpdate) {
          onExecutionUpdate(updatedExecution);
        }
      }, 1800);

    } catch (error) {
      console.error('Error polling execution status:', error);
      setExecutionError('Error monitoring execution');
      setIsExecuting(false);
    }
  };

  const getButtonIcon = () => {
    if (isExecuting) {
      return <Loader2 className="w-5 h-5 animate-spin" />;
    }
    return <Play className="w-5 h-5" />;
  };

  const getButtonText = () => {
    if (isExecuting) {
      return 'Executing...';
    }
    return buttonConfig.button_text;
  };

  return (
    <Card className={cn("w-full max-w-2xl", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Workflow className="w-5 h-5" />
          {workflow.name}
        </CardTitle>
        {buttonConfig.description && (
          <p className="text-sm text-gray-600 mt-1">
            {buttonConfig.description}
          </p>
        )}
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Main Execute Button */}
        <div className="text-center space-y-4">
          <Button
            onClick={handleExecute}
            disabled={isExecuting}
            variant={buttonConfig.button_variant}
            size={buttonConfig.button_size}
            className="w-full max-w-md mx-auto"
          >
            {getButtonIcon()}
            {getButtonText()}
          </Button>

          {/* Execution Status */}
          {lastExecution && (
            <div className="flex items-center justify-center gap-2">
              {lastExecution.status === 'completed' && (
                <>
                  <CheckCircle className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-green-700">
                    Completed successfully
                  </span>
                </>
              )}
              
              {lastExecution.status === 'failed' && (
                <>
                  <XCircle className="w-4 h-4 text-red-600" />
                  <span className="text-sm text-red-700">
                    Execution failed
                  </span>
                </>
              )}
              
              {lastExecution.status === 'running' && (
                <>
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  <span className="text-sm text-blue-700">
                    Running... {lastExecution.progress_percentage}%
                  </span>
                </>
              )}
            </div>
          )}

          {executionError && (
            <div className="flex items-center justify-center gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <span className="text-sm text-red-700">{executionError}</span>
            </div>
          )}
        </div>

        {/* Quick Stats */}
        {buttonConfig.show_stats && (
          <div className="border-t pt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Quick Stats
            </h3>
            <QuickStats 
              workflow={workflow} 
              recentExecutions={recentExecutions}
            />
          </div>
        )}

        {/* Last Execution Info */}
        {buttonConfig.show_last_execution && !showDetailedStats && (
          <div className="border-t pt-4">
            <LastExecutionInfo 
              workflow={workflow}
              recentExecutions={recentExecutions}
            />
          </div>
        )}

        {/* Detailed Stats */}
        {showDetailedStats && (
          <div className="border-t pt-4">
            <RecentExecutions 
              executions={recentExecutions}
              onViewExecution={onViewExecution}
            />
          </div>
        )}

        {/* Last Execution Output */}
        {lastExecution?.output_data && (
          <div className="border-t pt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Last Execution Result
            </h3>
            <div className="p-3 bg-gray-50 rounded-lg border">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                {typeof lastExecution.output_data === 'string' 
                  ? lastExecution.output_data 
                  : JSON.stringify(lastExecution.output_data, null, 2)
                }
              </pre>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}