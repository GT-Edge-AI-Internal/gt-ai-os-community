'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Play,
  Pause,
  Square,
  RefreshCw,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Eye,
  Download,
  Share,
  Copy,
  ChevronDown,
  ChevronRight,
  Zap,
  Timer,
  DollarSign,
  Hash,
  Calendar,
  Activity,
  FileText,
  Workflow,
  ArrowDown,
  Terminal,
  Database,
  Globe,
  Bot,
  Code,
  Settings
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { 
  Workflow,
  WorkflowExecution,
  NodeExecution,
  WorkflowExecutionViewProps
} from '@/types/workflow';

interface NodeExecutionCardProps {
  nodeExecution: NodeExecution;
  workflow?: Workflow;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

function NodeExecutionCard({ nodeExecution, workflow, isExpanded, onToggleExpand }: NodeExecutionCardProps) {
  const node = workflow?.definition.nodes.find(n => n.id === nodeExecution.node_id);
  const nodeName = node?.data.label || nodeExecution.node_id;

  const getNodeIcon = () => {
    switch (nodeExecution.node_type) {
      case 'agent': return <Bot className="w-4 h-4" />;
      case 'trigger': return <Zap className="w-4 h-4" />;
      case 'integration': return <Globe className="w-4 h-4" />;
      case 'logic': return <Code className="w-4 h-4" />;
      case 'output': return <Share className="w-4 h-4" />;
      default: return <Settings className="w-4 h-4" />;
    }
  };

  const getStatusColor = () => {
    switch (nodeExecution.status) {
      case 'completed': return 'text-green-600 bg-green-50 border-green-200';
      case 'failed': return 'text-red-600 bg-red-50 border-red-200';
      case 'running': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'pending': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getStatusIcon = () => {
    switch (nodeExecution.status) {
      case 'completed': return <CheckCircle className="w-4 h-4" />;
      case 'failed': return <XCircle className="w-4 h-4" />;
      case 'running': return <Loader2 className="w-4 h-4 animate-spin" />;
      case 'pending': return <Clock className="w-4 h-4" />;
      default: return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const formatDuration = (durationMs?: number) => {
    if (!durationMs) return '—';
    if (durationMs < 1000) return `${durationMs}ms`;
    return `${(durationMs / 1000).toFixed(1)}s`;
  };

  return (
    <Card className={cn("border", getStatusColor())}>
      <CardHeader 
        className="pb-3 cursor-pointer"
        onClick={onToggleExpand}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              {getNodeIcon()}
              {getStatusIcon()}
            </div>
            
            <div>
              <h4 className="font-medium">{nodeName}</h4>
              <p className="text-sm text-gray-500 capitalize">
                {nodeExecution.node_type} node
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right text-sm">
              <div className="font-medium capitalize">
                {nodeExecution.status}
              </div>
              <div className="text-gray-500">
                {formatDuration(nodeExecution.duration_ms)}
              </div>
            </div>
            
            {onToggleExpand && (
              <Button variant="ghost" size="sm">
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0 space-y-4">
          {/* Execution Details */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Started:</span>
              <div className="font-mono">
                {new Date(nodeExecution.started_at).toLocaleString()}
              </div>
            </div>
            
            {nodeExecution.completed_at && (
              <div>
                <span className="text-gray-500">Completed:</span>
                <div className="font-mono">
                  {new Date(nodeExecution.completed_at).toLocaleString()}
                </div>
              </div>
            )}
            
            {nodeExecution.tokens_used > 0 && (
              <div>
                <span className="text-gray-500">Tokens:</span>
                <div className="font-mono">
                  {nodeExecution.tokens_used.toLocaleString()}
                </div>
              </div>
            )}
            
            {nodeExecution.cost_cents > 0 && (
              <div>
                <span className="text-gray-500">Cost:</span>
                <div className="font-mono">
                  ${(nodeExecution.cost_cents / 100).toFixed(4)}
                </div>
              </div>
            )}
          </div>

          {/* Simulation Notice */}
          {nodeExecution.is_simulated && (
            <div className="flex items-center gap-2 p-2 bg-yellow-50 border border-yellow-200 rounded">
              <AlertTriangle className="w-4 h-4 text-yellow-600" />
              <span className="text-sm text-yellow-700">
                This node was simulated - external connections not implemented
              </span>
            </div>
          )}

          {/* Input Data */}
          {nodeExecution.input_data && Object.keys(nodeExecution.input_data).length > 0 && (
            <div>
              <h5 className="font-medium mb-2 flex items-center gap-2">
                <ArrowDown className="w-4 h-4" />
                Input Data
              </h5>
              <div className="p-3 bg-gray-50 rounded border">
                <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
                  {JSON.stringify(nodeExecution.input_data, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Output Data */}
          {nodeExecution.output_data && Object.keys(nodeExecution.output_data).length > 0 && (
            <div>
              <h5 className="font-medium mb-2 flex items-center gap-2">
                <Share className="w-4 h-4" />
                Output Data
              </h5>
              <div className="p-3 bg-gray-50 rounded border">
                <pre className="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
                  {JSON.stringify(nodeExecution.output_data, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Error Details */}
          {nodeExecution.error_message && (
            <div>
              <h5 className="font-medium mb-2 flex items-center gap-2 text-red-600">
                <XCircle className="w-4 h-4" />
                Error Details
              </h5>
              <div className="p-3 bg-red-50 border border-red-200 rounded">
                <p className="text-sm text-red-700">{nodeExecution.error_message}</p>
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

interface ExecutionTimelineProps {
  execution: WorkflowExecution;
  workflow?: Workflow;
  className?: string;
}

function ExecutionTimeline({ execution, workflow, className }: ExecutionTimelineProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  
  const toggleNodeExpanded = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  const sortedNodeExecutions = [...execution.node_executions].sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
  );

  return (
    <div className={cn("space-y-4", className)}>
      <h3 className="text-lg font-medium flex items-center gap-2">
        <Activity className="w-5 h-5" />
        Execution Timeline
      </h3>
      
      {sortedNodeExecutions.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No node executions recorded</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sortedNodeExecutions.map((nodeExecution, index) => (
            <div key={nodeExecution.id} className="relative">
              {/* Timeline connector */}
              {index < sortedNodeExecutions.length - 1 && (
                <div className="absolute left-6 top-16 w-0.5 h-8 bg-gray-200" />
              )}
              
              <NodeExecutionCard
                nodeExecution={nodeExecution}
                workflow={workflow}
                isExpanded={expandedNodes.has(nodeExecution.node_id)}
                onToggleExpand={() => toggleNodeExpanded(nodeExecution.node_id)}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface ExecutionMetricsProps {
  execution: WorkflowExecution;
  className?: string;
}

function ExecutionMetrics({ execution, className }: ExecutionMetricsProps) {
  const completedNodes = execution.node_executions.filter(n => n.status === 'completed').length;
  const failedNodes = execution.node_executions.filter(n => n.status === 'failed').length;
  const totalNodes = execution.node_executions.length;
  
  const formatDuration = (durationMs?: number) => {
    if (!durationMs) return '—';
    if (durationMs < 1000) return `${durationMs}ms`;
    if (durationMs < 60000) return `${(durationMs / 1000).toFixed(1)}s`;
    return `${(durationMs / 60000).toFixed(1)}m`;
  };

  return (
    <div className={cn("grid grid-cols-2 lg:grid-cols-4 gap-4", className)}>
      <Card>
        <CardContent className="p-4 text-center">
          <div className="flex items-center justify-center gap-1 mb-2">
            <Timer className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium text-gray-700">Duration</span>
          </div>
          <div className="text-2xl font-bold text-blue-700">
            {formatDuration(execution.duration_ms)}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 text-center">
          <div className="flex items-center justify-center gap-1 mb-2">
            <Activity className="w-4 h-4 text-green-600" />
            <span className="text-sm font-medium text-gray-700">Progress</span>
          </div>
          <div className="text-2xl font-bold text-green-700">
            {execution.progress_percentage}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {completedNodes}/{totalNodes} nodes
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 text-center">
          <div className="flex items-center justify-center gap-1 mb-2">
            <Hash className="w-4 h-4 text-purple-600" />
            <span className="text-sm font-medium text-gray-700">Tokens</span>
          </div>
          <div className="text-2xl font-bold text-purple-700">
            {execution.tokens_used.toLocaleString()}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 text-center">
          <div className="flex items-center justify-center gap-1 mb-2">
            <DollarSign className="w-4 h-4 text-orange-600" />
            <span className="text-sm font-medium text-gray-700">Cost</span>
          </div>
          <div className="text-2xl font-bold text-orange-700">
            ${(execution.cost_cents / 100).toFixed(4)}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function WorkflowExecutionView({
  execution,
  workflow,
  onRerun,
  onCancel,
  realtime = false,
  className
}: WorkflowExecutionViewProps) {
  const [currentExecution, setCurrentExecution] = useState(execution);
  const [isPolling, setIsPolling] = useState(false);

  // Update execution when prop changes
  useEffect(() => {
    setCurrentExecution(execution);
  }, [execution]);

  // Start polling if execution is running and realtime is enabled
  useEffect(() => {
    if (realtime && currentExecution.status === 'running' && !isPolling) {
      setIsPolling(true);
      pollExecutionStatus();
    }
  }, [currentExecution.status, realtime, isPolling]);

  const pollExecutionStatus = async () => {
    try {
      // In a real implementation, this would call the backend API
      // For now, we'll simulate status updates
      const interval = setInterval(() => {
        setCurrentExecution(prev => {
          if (prev.status !== 'running') {
            clearInterval(interval);
            setIsPolling(false);
            return prev;
          }

          // Simulate progress
          const newProgress = Math.min(prev.progress_percentage + 10, 100);
          const isComplete = newProgress >= 100;

          return {
            ...prev,
            progress_percentage: newProgress,
            status: isComplete ? 'completed' : 'running',
            completed_at: isComplete ? new Date().toISOString() : prev.completed_at,
            duration_ms: isComplete ? 
              new Date().getTime() - new Date(prev.started_at).getTime() : 
              prev.duration_ms
          };
        });
      }, 1000);

      return () => clearInterval(interval);
    } catch (error) {
      console.error('Error polling execution status:', error);
      setIsPolling(false);
    }
  };

  const getStatusColor = () => {
    switch (currentExecution.status) {
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      case 'running': return 'text-blue-600';
      case 'pending': return 'text-yellow-600';
      case 'cancelled': return 'text-gray-600';
      default: return 'text-gray-600';
    }
  };

  const getStatusIcon = () => {
    switch (currentExecution.status) {
      case 'completed': return <CheckCircle className="w-5 h-5" />;
      case 'failed': return <XCircle className="w-5 h-5" />;
      case 'running': return <Loader2 className="w-5 h-5 animate-spin" />;
      case 'pending': return <Clock className="w-5 h-5" />;
      case 'cancelled': return <Square className="w-5 h-5" />;
      default: return <AlertTriangle className="w-5 h-5" />;
    }
  };

  const canCancel = currentExecution.status === 'running' || currentExecution.status === 'pending';
  const canRerun = currentExecution.status === 'completed' || currentExecution.status === 'failed';

  const copyExecutionId = () => {
    navigator.clipboard.writeText(currentExecution.id);
  };

  const downloadExecution = () => {
    const data = JSON.stringify(currentExecution, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `execution-${currentExecution.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={cn("space-y-6", className)}>
      {/* Execution Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn("flex items-center gap-2", getStatusColor())}>
                {getStatusIcon()}
                <CardTitle className="capitalize">
                  {currentExecution.status}
                </CardTitle>
              </div>
              
              {workflow && (
                <Badge variant="secondary">
                  {workflow.name}
                </Badge>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={copyExecutionId}
                className="hidden sm:flex"
              >
                <Copy className="w-4 h-4" />
                Copy ID
              </Button>
              
              <Button
                variant="secondary"
                size="sm"
                onClick={downloadExecution}
                className="hidden sm:flex"
              >
                <Download className="w-4 h-4" />
                Download
              </Button>

              {canCancel && onCancel && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onCancel}
                >
                  <Square className="w-4 h-4" />
                  Cancel
                </Button>
              )}

              {canRerun && onRerun && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onRerun}
                >
                  <RefreshCw className="w-4 h-4" />
                  Rerun
                </Button>
              )}
            </div>
          </div>

          {/* Execution Info */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <Hash className="w-4 h-4" />
              <span className="font-mono text-xs truncate">
                {currentExecution.id}
              </span>
            </div>
            
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              <span>
                {new Date(currentExecution.started_at).toLocaleString()}
              </span>
            </div>
            
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-xs">
                {currentExecution.interaction_mode}
              </Badge>
            </div>
          </div>

          {/* Progress Bar */}
          {currentExecution.status === 'running' && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <span>{currentExecution.progress_percentage}%</span>
              </div>
              <Progress value={currentExecution.progress_percentage} className="h-2" />
              
              {currentExecution.current_node_id && (
                <p className="text-sm text-gray-600">
                  Currently processing: {currentExecution.current_node_id}
                </p>
              )}
            </div>
          )}
        </CardHeader>
      </Card>

      {/* Execution Metrics */}
      <ExecutionMetrics execution={currentExecution} />

      {/* Error Details */}
      {currentExecution.error_details && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-red-700 flex items-center gap-2">
              <XCircle className="w-5 h-5" />
              Error Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-700">{currentExecution.error_details}</p>
          </CardContent>
        </Card>
      )}

      {/* Input/Output Data */}
      {(Object.keys(currentExecution.input_data).length > 0 || 
        Object.keys(currentExecution.output_data).length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Object.keys(currentExecution.input_data).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="w-5 h-5" />
                  Input Data
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs bg-gray-50 p-3 rounded border overflow-x-auto">
                  {JSON.stringify(currentExecution.input_data, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}

          {Object.keys(currentExecution.output_data).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Output Data
                </CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="text-xs bg-gray-50 p-3 rounded border overflow-x-auto">
                  {JSON.stringify(currentExecution.output_data, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Execution Timeline */}
      <ExecutionTimeline 
        execution={currentExecution}
        workflow={workflow}
      />
    </div>
  );
}