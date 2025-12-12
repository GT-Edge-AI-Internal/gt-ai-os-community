'use client';

import { useState } from 'react';
import { ToolExecution } from '@/types';
import { cn } from '@/lib/utils';
import {
  Search,
  Database,
  MessageCircle,
  Globe,
  Settings,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Play,
  Loader2
} from 'lucide-react';

interface ToolExecutionPanelProps {
  tools: ToolExecution[];
  className?: string;
  compact?: boolean;
}

interface ToolConfig {
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  description: string;
}

const toolConfigs: Record<string, ToolConfig> = {
  search_datasets: {
    icon: Database,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    description: 'Searching through uploaded documents and datasets'
  },
  web_search: {
    icon: Globe,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    description: 'Searching the web for information'
  },
  default: {
    icon: Settings,
    color: 'text-gt-gray-600',
    bgColor: 'bg-gt-gray-50',
    description: 'Executing tool'
  }
};

const statusConfigs = {
  pending: {
    icon: Clock,
    color: 'text-gt-gray-500',
    label: 'Queued'
  },
  running: {
    icon: Loader2,
    color: 'text-blue-600',
    label: 'Running',
    animate: 'animate-spin'
  },
  completed: {
    icon: CheckCircle,
    color: 'text-green-600',
    label: 'Completed'
  },
  failed: {
    icon: XCircle,
    color: 'text-red-600',
    label: 'Failed'
  }
};

function ToolCard({ tool, compact = false }: { tool: ToolExecution; compact?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const toolConfig = toolConfigs[tool.name] || toolConfigs.default;
  const statusConfig = statusConfigs[tool.status];

  const executionTime = tool.startTime && tool.endTime
    ? (tool.endTime.getTime() - tool.startTime.getTime()) / 1000
    : tool.startTime
    ? (new Date().getTime() - tool.startTime.getTime()) / 1000
    : 0;

  const formatTime = (seconds: number) => {
    if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  if (compact) {
    return (
      <div className={cn('flex items-center space-x-2 p-2 rounded-md', toolConfig.bgColor)}>
        <toolConfig.icon className={cn('w-4 h-4', toolConfig.color)} />
        <span className="text-sm font-medium">{tool.name}</span>
        <statusConfig.icon className={cn('w-3 h-3', statusConfig.color, statusConfig.animate)} />
        {executionTime > 0 && (
          <span className="text-xs text-gt-gray-500 font-mono">
            {formatTime(executionTime)}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="border border-gt-gray-200 rounded-lg overflow-hidden">
      {/* Tool Header */}
      <div
        className={cn(
          'flex items-center justify-between p-3 cursor-pointer hover:bg-gt-gray-50 transition-colors',
          toolConfig.bgColor
        )}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-3">
          <div className={cn('p-1.5 rounded-md bg-white shadow-sm')}>
            <toolConfig.icon className={cn('w-4 h-4', toolConfig.color)} />
          </div>

          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gt-gray-900">
                {tool.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </span>
              <div className="flex items-center space-x-1">
                <statusConfig.icon className={cn('w-3 h-3', statusConfig.color, statusConfig.animate)} />
                <span className={cn('text-xs font-medium', statusConfig.color)}>
                  {statusConfig.label}
                </span>
              </div>
            </div>
            <span className="text-xs text-gt-gray-500">
              {toolConfig.description}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Progress bar for running tools */}
          {tool.status === 'running' && tool.progress !== undefined && (
            <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300 ease-out"
                style={{ width: `${tool.progress}%` }}
              />
            </div>
          )}

          {/* Execution time */}
          {executionTime > 0 && (
            <span className="text-xs text-gt-gray-500 font-mono">
              {formatTime(executionTime)}
            </span>
          )}

          {/* Expand/collapse button */}
          {(tool.arguments || tool.result || tool.error) && (
            <button className="text-gt-gray-400 hover:text-gt-gray-600">
              {expanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (tool.arguments || tool.result || tool.error) && (
        <div className="border-t border-gt-gray-200 bg-gt-gray-50 p-3 space-y-3">
          {/* Arguments */}
          {tool.arguments && Object.keys(tool.arguments).length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-gt-gray-700 mb-1">Arguments:</h5>
              <div className="bg-white rounded p-2 text-xs font-mono">
                <pre className="whitespace-pre-wrap text-gt-gray-600">
                  {JSON.stringify(tool.arguments, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* Result */}
          {tool.result && (
            <div>
              <h5 className="text-xs font-medium text-gt-gray-700 mb-1">Result:</h5>
              <div className="bg-white rounded p-2 text-xs">
                {typeof tool.result === 'string' ? (
                  <div className="text-gt-gray-600 whitespace-pre-wrap">
                    {tool.result}
                  </div>
                ) : tool.result.results ? (
                  <div className="space-y-2">
                    <div className="text-gt-gray-600">
                      Found {tool.result.results_count || tool.result.results.length} results
                    </div>
                    {tool.result.results.slice(0, 3).map((result: any, index: number) => (
                      <div key={index} className="border-l-2 border-blue-200 pl-2">
                        <div className="font-medium text-gt-gray-700">
                          {result.name || result.title || `Result ${index + 1}`}
                        </div>
                        {result.content && (
                          <div className="text-gt-gray-600 text-xs mt-1">
                            {result.content.substring(0, 100)}
                            {result.content.length > 100 && '...'}
                          </div>
                        )}
                        {result.relevance && (
                          <div className="text-xs text-gt-gray-500 mt-1">
                            Relevance: {(result.relevance * 100).toFixed(1)}%
                          </div>
                        )}
                      </div>
                    ))}
                    {tool.result.results.length > 3 && (
                      <div className="text-xs text-gt-gray-500">
                        ... and {tool.result.results.length - 3} more results
                      </div>
                    )}
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap text-gt-gray-600 font-mono">
                    {JSON.stringify(tool.result, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* Error */}
          {tool.error && (
            <div>
              <h5 className="text-xs font-medium text-red-700 mb-1">Error:</h5>
              <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">
                {tool.error}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolExecutionPanel({ tools, className, compact = false }: ToolExecutionPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  // Filter out tools that are no longer relevant
  const activeTools = tools.filter(tool =>
    tool.status === 'running' ||
    tool.status === 'pending' ||
    (tool.status === 'completed' && tool.endTime &&
     new Date().getTime() - tool.endTime.getTime() < 30000) // Show completed tools for 30 seconds
  );

  if (activeTools.length === 0) {
    return null;
  }

  const runningTools = activeTools.filter(t => t.status === 'running');
  const completedTools = activeTools.filter(t => t.status === 'completed');
  const failedTools = activeTools.filter(t => t.status === 'failed');

  if (compact) {
    return (
      <div className={cn('space-y-2', className)}>
        {activeTools.map(tool => (
          <ToolCard key={tool.id} tool={tool} compact />
        ))}
      </div>
    );
  }

  return (
    <div className={cn('bg-white border border-gt-gray-200 rounded-lg', className)}>
      {/* Panel Header */}
      <div
        className="flex items-center justify-between p-3 border-b border-gt-gray-200 cursor-pointer hover:bg-gt-gray-50"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center space-x-2">
          <Play className="w-4 h-4 text-gt-green" />
          <span className="font-medium text-gt-gray-900">Tool Execution</span>
          <div className="flex items-center space-x-1 text-xs text-gt-gray-500">
            {runningTools.length > 0 && (
              <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                {runningTools.length} running
              </span>
            )}
            {completedTools.length > 0 && (
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                {completedTools.length} completed
              </span>
            )}
            {failedTools.length > 0 && (
              <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                {failedTools.length} failed
              </span>
            )}
          </div>
        </div>

        <button className="text-gt-gray-400 hover:text-gt-gray-600">
          {collapsed ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronUp className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Tool List */}
      {!collapsed && (
        <div className="p-3 space-y-3">
          {activeTools.map(tool => (
            <ToolCard key={tool.id} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}