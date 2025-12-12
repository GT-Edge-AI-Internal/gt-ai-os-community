'use client';

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Play,
  Pause,
  Square,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  FileText,
  Download,
  ExternalLink,
  Loader2
} from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  agent_type: string;
  description?: string;
}

interface AgentExecution {
  id: string;
  agent_id: string;
  task_description: string;
  task_parameters: Record<string, any>;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_percentage: number;
  current_step?: string;
  result_data: Record<string, any>;
  output_artifacts: string[];
  error_details?: string;
  execution_time_ms?: number;
  tokens_used: number;
  cost_cents: number;
  tool_calls_count: number;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

interface AgentExecutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  agent: Agent | null;
  onExecute: (agentId: string, taskDescription: string, parameters: Record<string, any>) => void;
  execution?: AgentExecution | null;
  isLoading?: boolean;
}

export function AgentExecutionModal({
  isOpen,
  onClose,
  agent,
  onExecute,
  execution,
  isLoading = false
}: AgentExecutionModalProps) {
  const [step, setStep] = useState<'configure' | 'executing' | 'results'>('configure');
  const [taskDescription, setTaskDescription] = useState('');
  const [taskParameters, setTaskParameters] = useState('{}');
  const [parametersError, setParametersError] = useState('');

  useEffect(() => {
    if (execution) {
      if (execution.status === 'pending' || execution.status === 'running') {
        setStep('executing');
      } else if (execution.status === 'completed' || execution.status === 'failed') {
        setStep('results');
      }
    }
  }, [execution]);

  const validateParameters = (value: string) => {
    try {
      JSON.parse(value);
      setParametersError('');
      return true;
    } catch (e) {
      setParametersError('Invalid JSON format');
      return false;
    }
  };

  const handleParametersChange = (value: string) => {
    setTaskParameters(value);
    if (value.trim()) {
      validateParameters(value);
    } else {
      setParametersError('');
    }
  };

  const handleExecute = () => {
    if (!agent || !taskDescription.trim()) return;

    let parameters = {};
    if (taskParameters.trim()) {
      if (!validateParameters(taskParameters)) {
        return;
      }
      parameters = JSON.parse(taskParameters);
    }

    onExecute(agent.id, taskDescription, parameters);
    setStep('executing');
  };

  const handleClose = () => {
    setStep('configure');
    setTaskDescription('');
    setTaskParameters('{}');
    setParametersError('');
    onClose();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-600" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'cancelled':
        return <Square className="h-4 w-4 text-gray-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-600" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      pending: 'bg-yellow-100 text-yellow-800',
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-100 text-gray-800',
    };

    return (
      <Badge className={variants[status as keyof typeof variants] || variants.pending}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  const formatCost = (cents: number) => {
    return `$${(cents / 100).toFixed(4)}`;
  };

  const renderResultData = (data: Record<string, any>) => {
    if (!data || Object.keys(data).length === 0) {
      return <p className="text-sm text-gray-500">No result data available</p>;
    }

    return (
      <div className="space-y-3">
        {data.summary && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Summary</h4>
            <p className="text-sm text-gray-700">{data.summary}</p>
          </div>
        )}

        {data.findings && Array.isArray(data.findings) && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Key Findings</h4>
            <ul className="list-disc list-inside space-y-1">
              {data.findings.map((finding: string, index: number) => (
                <li key={index} className="text-sm text-gray-700">{finding}</li>
              ))}
            </ul>
          </div>
        )}

        {data.insights && Array.isArray(data.insights) && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Insights</h4>
            <ul className="list-disc list-inside space-y-1">
              {data.insights.map((insight: string, index: number) => (
                <li key={index} className="text-sm text-gray-700">{insight}</li>
              ))}
            </ul>
          </div>
        )}

        {data.generated_code && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Generated Code</h4>
            <pre className="text-xs bg-gray-100 p-3 rounded-md overflow-x-auto">
              <code>{data.generated_code}</code>
            </pre>
          </div>
        )}

        {data.metrics && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Metrics</h4>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(data.metrics).map(([key, value]: [string, any]) => (
                <div key={key} className="text-sm">
                  <span className="text-gray-600">{key}:</span>
                  <span className="ml-1 font-medium">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.sources && Array.isArray(data.sources) && (
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Sources</h4>
            <div className="flex flex-wrap gap-1">
              {data.sources.map((source: string, index: number) => (
                <Badge key={index} variant="secondary" className="text-xs">
                  {source}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center space-x-2">
              <Play className="h-5 w-5" />
              <span>
                {step === 'configure' ? 'Execute Agent' : 
                 step === 'executing' ? 'Agent Execution' : 'Execution Results'}
              </span>
              {agent && (
                <Badge variant="secondary">{agent.name}</Badge>
              )}
            </div>
          </DialogTitle>
        </DialogHeader>

        {step === 'configure' && (
          <div className="space-y-4">
            {agent && (
              <div className="p-3 bg-gray-50 rounded-lg">
                <h3 className="text-sm font-medium text-gray-900">{agent.name}</h3>
                <p className="text-xs text-gray-600 mt-1">{agent.description}</p>
                <Badge variant="secondary" className="mt-2 text-xs">
                  {agent.agent_type}
                </Badge>
              </div>
            )}

            <div>
              <Label htmlFor="task">Task Description *</Label>
              <Textarea
                id="task"
                value={taskDescription}
                onChange={(e) => setTaskDescription((e as React.ChangeEvent<HTMLTextAreaElement>).target.value)}
                placeholder="Describe what you want the agent to do..."
                className="mt-1"
                rows={4}
              />
            </div>

            <div>
              <Label htmlFor="parameters">Task Parameters (JSON)</Label>
              <Textarea
                id="parameters"
                value={taskParameters}
                onChange={(e) => handleParametersChange((e as React.ChangeEvent<HTMLTextAreaElement>).target.value)}
                placeholder='{"key": "value"}'
                className={cn("mt-1 font-mono text-sm", parametersError && "border-red-300")}
                rows={3}
              />
              {parametersError && (
                <p className="text-sm text-red-600 mt-1">{parametersError}</p>
              )}
              <p className="text-xs text-gray-500 mt-1">
                Optional: Provide additional parameters as JSON
              </p>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t">
              <Button variant="secondary" onClick={handleClose}>
                Cancel
              </Button>
              <Button 
                onClick={handleExecute}
                disabled={!taskDescription.trim() || !!parametersError || isLoading}
              >
                {isLoading ? 'Starting...' : 'Execute Agent'}
              </Button>
            </div>
          </div>
        )}

        {step === 'executing' && execution && (
          <div className="space-y-4">
            {/* Status Header */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-2">
                {getStatusIcon(execution.status)}
                <span className="text-sm font-medium">
                  {execution.current_step || 'Processing...'}
                </span>
              </div>
              {getStatusBadge(execution.status)}
            </div>

            {/* Progress Bar */}
            <div>
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Progress</span>
                <span>{execution.progress_percentage}%</span>
              </div>
              <Progress value={execution.progress_percentage} className="h-2" />
            </div>

            {/* Task Details */}
            <div>
              <h3 className="text-sm font-medium text-gray-900 mb-2">Task</h3>
              <p className="text-sm text-gray-700">{execution.task_description}</p>
            </div>

            {/* Execution Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {execution.tokens_used.toLocaleString()}
                </div>
                <div className="text-xs text-gray-600">Tokens Used</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {formatCost(execution.cost_cents)}
                </div>
                <div className="text-xs text-gray-600">Cost</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {execution.tool_calls_count}
                </div>
                <div className="text-xs text-gray-600">Tool Calls</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {formatDuration(execution.execution_time_ms)}
                </div>
                <div className="text-xs text-gray-600">Duration</div>
              </div>
            </div>

            {/* Error Details */}
            {execution.error_details && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <h4 className="text-sm font-medium text-red-900 mb-1">Error</h4>
                <p className="text-sm text-red-700">{execution.error_details}</p>
              </div>
            )}

            <div className="flex justify-end space-x-3 pt-4 border-t">
              <Button variant="secondary" onClick={handleClose}>
                Close
              </Button>
              {(execution.status === 'completed' || execution.status === 'failed') && (
                <Button onClick={() => setStep('results')}>
                  View Results
                </Button>
              )}
            </div>
          </div>
        )}

        {step === 'results' && execution && (
          <div className="space-y-4">
            {/* Results Header */}
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center space-x-2">
                {getStatusIcon(execution.status)}
                <span className="text-sm font-medium">Execution Results</span>
              </div>
              {getStatusBadge(execution.status)}
            </div>

            {/* Execution Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-3 border border-gray-200 rounded-lg">
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {formatDuration(execution.execution_time_ms)}
                </div>
                <div className="text-xs text-gray-600">Total Duration</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {execution.tokens_used.toLocaleString()}
                </div>
                <div className="text-xs text-gray-600">Tokens Used</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {formatCost(execution.cost_cents)}
                </div>
                <div className="text-xs text-gray-600">Total Cost</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">
                  {execution.tool_calls_count}
                </div>
                <div className="text-xs text-gray-600">Tool Calls</div>
              </div>
            </div>

            {/* Results Content */}
            <div>
              <h3 className="text-sm font-medium text-gray-900 mb-3">Results</h3>
              <div className="p-4 border border-gray-200 rounded-lg">
                {execution.status === 'completed' ? (
                  renderResultData(execution.result_data)
                ) : execution.error_details ? (
                  <div className="text-red-700">
                    <h4 className="font-medium mb-2">Error Details</h4>
                    <p className="text-sm">{execution.error_details}</p>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No results available</p>
                )}
              </div>
            </div>

            {/* Output Artifacts */}
            {execution.output_artifacts.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-3">Output Files</h3>
                <div className="space-y-2">
                  {execution.output_artifacts.map((artifact, index) => (
                    <div key={index} className="flex items-center justify-between p-2 border border-gray-200 rounded">
                      <div className="flex items-center space-x-2">
                        <FileText className="h-4 w-4 text-gray-500" />
                        <span className="text-sm">{artifact}</span>
                      </div>
                      <Button variant="ghost" size="sm">
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end space-x-3 pt-4 border-t">
              <Button variant="secondary" onClick={handleClose}>
                Close
              </Button>
              <Button onClick={() => setStep('configure')}>
                Run Again
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}