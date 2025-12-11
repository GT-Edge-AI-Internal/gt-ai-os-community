'use client';

import { useState, useEffect } from 'react';
import { SubagentExecution } from '@/types';
import { cn } from '@/lib/utils';
import {
  Network,
  Brain,
  Search,
  FileText,
  MessageSquare,
  Settings,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  Users
} from 'lucide-react';

interface SubagentActivityPanelProps {
  subagents: SubagentExecution[];
  orchestrationStrategy?: string;
  className?: string;
  compact?: boolean;
}

interface SubagentConfig {
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  description: string;
}

const subagentConfigs: Record<string, SubagentConfig> = {
  researcher: {
    icon: Search,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    description: 'Gathers and analyzes information'
  },
  analyst: {
    icon: Brain,
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    description: 'Processes and synthesizes data'
  },
  writer: {
    icon: FileText,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    description: 'Creates structured content'
  },
  reviewer: {
    icon: MessageSquare,
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    description: 'Quality assurance and validation'
  },
  coordinator: {
    icon: Network,
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    description: 'Orchestrates team workflow'
  },
  default: {
    icon: Settings,
    color: 'text-gt-gray-600',
    bgColor: 'bg-gt-gray-50',
    description: 'Specialized task execution'
  }
};

const statusConfigs = {
  pending: {
    icon: Clock,
    color: 'text-gt-gray-500',
    label: 'Queued',
    bgColor: 'bg-gt-gray-100'
  },
  running: {
    icon: Loader2,
    color: 'text-blue-600',
    label: 'Active',
    animate: 'animate-spin',
    bgColor: 'bg-blue-100'
  },
  completed: {
    icon: CheckCircle,
    color: 'text-green-600',
    label: 'Complete',
    bgColor: 'bg-green-100'
  },
  failed: {
    icon: XCircle,
    color: 'text-red-600',
    label: 'Failed',
    bgColor: 'bg-red-100'
  }
};

function SubagentCard({
  subagent,
  compact = false,
  showDependencies = true
}: {
  subagent: SubagentExecution;
  compact?: boolean;
  showDependencies?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const subagentConfig = subagentConfigs[subagent.type] || subagentConfigs.default;
  const statusConfig = statusConfigs[subagent.status];

  const executionTime = subagent.startTime && subagent.endTime
    ? (subagent.endTime.getTime() - subagent.startTime.getTime()) / 1000
    : subagent.startTime
    ? (new Date().getTime() - subagent.startTime.getTime()) / 1000
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
      <div className={cn(
        'flex items-center space-x-2 p-2 rounded-md border',
        subagentConfig.bgColor,
        statusConfig.bgColor
      )}>
        <subagentConfig.icon className={cn('w-4 h-4', subagentConfig.color)} />
        <span className="text-sm font-medium">{subagent.type}</span>
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
      {/* Subagent Header */}
      <div
        className={cn(
          'flex items-center justify-between p-3 cursor-pointer hover:bg-gt-gray-50 transition-colors',
          subagentConfig.bgColor
        )}
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-3">
          <div className={cn('p-1.5 rounded-md bg-white shadow-sm')}>
            <subagentConfig.icon className={cn('w-4 h-4', subagentConfig.color)} />
          </div>

          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium text-gt-gray-900">
                {subagent.type.charAt(0).toUpperCase() + subagent.type.slice(1)}
              </span>
              <div className="flex items-center space-x-1">
                <statusConfig.icon className={cn('w-3 h-3', statusConfig.color, statusConfig.animate)} />
                <span className={cn('text-xs font-medium', statusConfig.color)}>
                  {statusConfig.label}
                </span>
              </div>
            </div>
            <span className="text-xs text-gt-gray-500">
              {subagent.task}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {/* Progress bar for running subagents */}
          {subagent.status === 'running' && subagent.progress !== undefined && (
            <div className="w-20 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 transition-all duration-300 ease-out"
                style={{ width: `${subagent.progress}%` }}
              />
            </div>
          )}

          {/* Execution time */}
          {executionTime > 0 && (
            <span className="text-xs text-gt-gray-500 font-mono">
              {formatTime(executionTime)}
            </span>
          )}

          {/* Dependencies indicator */}
          {showDependencies && subagent.dependsOn && subagent.dependsOn.length > 0 && (
            <div className="flex items-center space-x-1 text-xs text-gt-gray-500">
              <ArrowRight className="w-3 h-3" />
              <span>{subagent.dependsOn.length}</span>
            </div>
          )}

          {/* Expand/collapse button */}
          {(subagent.result || subagent.error || (subagent.dependsOn && subagent.dependsOn.length > 0)) && (
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
      {expanded && (
        <div className="border-t border-gt-gray-200 bg-gt-gray-50 p-3 space-y-3">
          {/* Dependencies */}
          {subagent.dependsOn && subagent.dependsOn.length > 0 && (
            <div>
              <h5 className="text-xs font-medium text-gt-gray-700 mb-1">Dependencies:</h5>
              <div className="flex flex-wrap gap-1">
                {subagent.dependsOn.map((depId, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2 py-1 rounded-md bg-gt-gray-200 text-xs text-gt-gray-700"
                  >
                    {depId}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Result */}
          {subagent.result && (
            <div>
              <h5 className="text-xs font-medium text-gt-gray-700 mb-1">Result:</h5>
              <div className="bg-white rounded p-2 text-xs">
                {typeof subagent.result === 'string' ? (
                  <div className="text-gt-gray-600 whitespace-pre-wrap">
                    {subagent.result}
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap text-gt-gray-600 font-mono">
                    {JSON.stringify(subagent.result, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* Error */}
          {subagent.error && (
            <div>
              <h5 className="text-xs font-medium text-red-700 mb-1">Error:</h5>
              <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">
                {subagent.error}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OrchestrationFlow({ subagents }: { subagents: SubagentExecution[] }) {
  // Group subagents by their dependency level (execution phase)
  const phases = subagents.reduce((acc, subagent) => {
    const phase = subagent.dependsOn?.length || 0;
    if (!acc[phase]) acc[phase] = [];
    acc[phase].push(subagent);
    return acc;
  }, {} as Record<number, SubagentExecution[]>);

  const sortedPhases = Object.keys(phases)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="space-y-4">
      {sortedPhases.map((phase, phaseIndex) => (
        <div key={phase} className="relative">
          {/* Phase separator */}
          {phaseIndex > 0 && (
            <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
              <div className="bg-white border border-gt-gray-300 rounded-full p-1">
                <ArrowRight className="w-3 h-3 text-gt-gray-500" />
              </div>
            </div>
          )}

          {/* Phase label */}
          <div className="text-xs font-medium text-gt-gray-600 mb-2">
            Phase {phase + 1}
            {phase === 0 && ' (Initial)'}
          </div>

          {/* Subagents in this phase */}
          <div className={cn(
            'grid gap-2',
            phases[phase].length > 1 ? 'grid-cols-2' : 'grid-cols-1'
          )}>
            {phases[phase].map((subagent) => (
              <SubagentCard
                key={subagent.id}
                subagent={subagent}
                showDependencies={false}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function SubagentActivityPanel({
  subagents,
  orchestrationStrategy,
  className,
  compact = false
}: SubagentActivityPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [showFlow, setShowFlow] = useState(false);

  if (subagents.length === 0) {
    return null;
  }

  const activeSubagents = subagents.filter(s => s.status === 'running');
  const completedSubagents = subagents.filter(s => s.status === 'completed');
  const failedSubagents = subagents.filter(s => s.status === 'failed');

  const overallProgress = subagents.length > 0
    ? (completedSubagents.length / subagents.length) * 100
    : 0;

  if (compact) {
    return (
      <div className={cn('space-y-2', className)}>
        <div className="flex items-center space-x-2 text-sm text-gt-gray-600">
          <Users className="w-4 h-4" />
          <span>{subagents.length} agents</span>
          <span>•</span>
          <span>{Math.round(overallProgress)}% complete</span>
        </div>
        {subagents.slice(0, 3).map(subagent => (
          <SubagentCard key={subagent.id} subagent={subagent} compact />
        ))}
        {subagents.length > 3 && (
          <div className="text-xs text-gt-gray-500">
            ... and {subagents.length - 3} more agents
          </div>
        )}
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
          <Network className="w-4 h-4 text-purple-600" />
          <span className="font-medium text-gt-gray-900">Agent Orchestration</span>
          {orchestrationStrategy && (
            <span className="text-xs text-gt-gray-500 bg-gt-gray-100 px-2 py-0.5 rounded-full">
              {orchestrationStrategy}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-2">
          {/* Progress summary */}
          <div className="flex items-center space-x-1 text-xs text-gt-gray-500">
            {activeSubagents.length > 0 && (
              <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                {activeSubagents.length} active
              </span>
            )}
            {completedSubagents.length > 0 && (
              <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                {completedSubagents.length} complete
              </span>
            )}
            {failedSubagents.length > 0 && (
              <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                {failedSubagents.length} failed
              </span>
            )}
          </div>

          {/* Overall progress */}
          <div className="w-20 h-1.5 bg-gt-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-purple-500 transition-all duration-300 ease-out"
              style={{ width: `${overallProgress}%` }}
            />
          </div>

          <button className="text-gt-gray-400 hover:text-gt-gray-600">
            {collapsed ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronUp className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="p-3">
          {/* View toggle */}
          {subagents.some(s => s.dependsOn && s.dependsOn.length > 0) && (
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm text-gt-gray-600">
                {subagents.length} agents • {Math.round(overallProgress)}% complete
              </div>
              <button
                onClick={() => setShowFlow(!showFlow)}
                className="text-xs text-gt-gray-500 hover:text-gt-gray-700 transition-colors"
              >
                {showFlow ? 'List view' : 'Flow view'}
              </button>
            </div>
          )}

          {/* Subagent list or flow */}
          {showFlow ? (
            <OrchestrationFlow subagents={subagents} />
          ) : (
            <div className="space-y-3">
              {subagents.map(subagent => (
                <SubagentCard key={subagent.id} subagent={subagent} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}