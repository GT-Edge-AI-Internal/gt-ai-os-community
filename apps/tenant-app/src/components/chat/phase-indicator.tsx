'use client';

import { useEffect, useState } from 'react';
import { AgenticPhase } from '@/types';
import { cn } from '@/lib/utils';
import {
  Brain,
  Lightbulb,
  Cog,
  Network,
  Search,
  MessageSquare,
  CheckCircle,
  Clock
} from 'lucide-react';

interface PhaseIndicatorProps {
  currentPhase: AgenticPhase;
  phaseStartTime?: Date;
  totalPhases?: number;
  completedPhases?: number;
  taskComplexity?: 'simple' | 'moderate' | 'complex';
  className?: string;
}

interface PhaseConfig {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  description: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

const phaseConfigs: Record<AgenticPhase, PhaseConfig> = {
  idle: {
    icon: MessageSquare,
    label: 'Ready',
    description: 'Ready to assist',
    color: 'text-gt-gray-500',
    bgColor: 'bg-gt-gray-100',
    borderColor: 'border-gt-gray-200'
  },
  thinking: {
    icon: Brain,
    label: 'Thinking',
    description: 'Analyzing your request',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200'
  },
  planning: {
    icon: Lightbulb,
    label: 'Planning',
    description: 'Developing strategy',
    color: 'text-amber-600',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200'
  },
  tool_execution: {
    icon: Cog,
    label: 'Executing',
    description: 'Running tools and searches',
    color: 'text-gt-green',
    bgColor: 'bg-gt-green/10',
    borderColor: 'border-gt-green/30'
  },
  subagent_orchestration: {
    icon: Network,
    label: 'Orchestrating',
    description: 'Coordinating multiple agents',
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200'
  },
  source_retrieval: {
    icon: Search,
    label: 'Searching',
    description: 'Retrieving relevant information',
    color: 'text-indigo-600',
    bgColor: 'bg-indigo-50',
    borderColor: 'border-indigo-200'
  },
  responding: {
    icon: MessageSquare,
    label: 'Responding',
    description: 'Generating response',
    color: 'text-gt-green',
    bgColor: 'bg-gt-green/10',
    borderColor: 'border-gt-green/30'
  },
  completed: {
    icon: CheckCircle,
    label: 'Complete',
    description: 'Task completed',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200'
  }
};

const phaseOrder: AgenticPhase[] = [
  'thinking',
  'planning',
  'source_retrieval',
  'tool_execution',
  'subagent_orchestration',
  'responding',
  'completed'
];

export function PhaseIndicator({
  currentPhase,
  phaseStartTime,
  totalPhases,
  completedPhases = 0,
  taskComplexity = 'simple',
  className
}: PhaseIndicatorProps) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const config = phaseConfigs[currentPhase];

  // Update elapsed time
  useEffect(() => {
    if (!phaseStartTime || currentPhase === 'idle' || currentPhase === 'completed') {
      return;
    }

    const timer = setInterval(() => {
      const now = new Date();
      const elapsed = (now.getTime() - phaseStartTime.getTime()) / 1000;
      setElapsedTime(elapsed);
    }, 100);

    return () => clearInterval(timer);
  }, [phaseStartTime, currentPhase]);

  const formatTime = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const getComplexityIcon = () => {
    switch (taskComplexity) {
      case 'simple':
        return '●';
      case 'moderate':
        return '●●';
      case 'complex':
        return '●●●';
      default:
        return '●';
    }
  };

  // Don't show the indicator if idle
  if (currentPhase === 'idle') {
    return null;
  }

  return (
    <div className={cn('flex items-center space-x-4 p-4 bg-white border rounded-lg', className)}>
      {/* Phase Icon and Status */}
      <div className={cn('flex items-center space-x-3', config.bgColor, 'rounded-full px-4 py-2', config.borderColor, 'border')}>
        <div className={cn('relative', config.color)}>
          <config.icon className="w-5 h-5" />
          {/* Pulse animation for active phases */}
          {currentPhase !== 'completed' && currentPhase !== 'idle' && (
            <div className={cn('absolute inset-0 rounded-full animate-ping', config.bgColor, 'opacity-75')} />
          )}
        </div>

        <div className="flex flex-col">
          <div className="flex items-center space-x-2">
            <span className={cn('text-sm font-medium', config.color)}>
              {config.label}
            </span>
            {/* Complexity indicator */}
            <span className="text-xs text-gt-gray-400" title={`${taskComplexity} task`}>
              {getComplexityIcon()}
            </span>
          </div>
          <span className="text-xs text-gt-gray-500">
            {config.description}
          </span>
        </div>
      </div>

      {/* Timer */}
      {elapsedTime > 0 && currentPhase !== 'completed' && (
        <div className="flex items-center space-x-1 text-xs text-gt-gray-500">
          <Clock className="w-3 h-3" />
          <span className="font-mono">{formatTime(elapsedTime)}</span>
        </div>
      )}

      {/* Progress indicator for multi-phase tasks */}
      {totalPhases && totalPhases > 1 && (
        <div className="flex items-center space-x-2">
          <div className="text-xs text-gt-gray-500">
            {completedPhases}/{totalPhases} phases
          </div>
          <div className="w-20 h-1.5 bg-gt-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gt-green transition-all duration-300 ease-out"
              style={{ width: `${(completedPhases / totalPhases) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Mini phase timeline for complex tasks */}
      {taskComplexity === 'complex' && (
        <div className="flex items-center space-x-1">
          {phaseOrder.map((phase, index) => {
            const phaseConfig = phaseConfigs[phase];
            const isPast = phaseOrder.indexOf(currentPhase) > index;
            const isCurrent = phase === currentPhase;
            const isFuture = phaseOrder.indexOf(currentPhase) < index;

            return (
              <div
                key={phase}
                className={cn(
                  'w-2 h-2 rounded-full transition-all duration-200',
                  isPast && 'bg-green-400',
                  // Remove opacity suffix from bg color (e.g., bg-blue-500/10 -> bg-blue-500)
                  isCurrent && phaseConfig.bgColor.replace(/\/\d+$/, ''),
                  isCurrent && 'ring-2 ring-offset-1',
                  // Convert border color to ring color and remove opacity suffix
                  isCurrent && phaseConfig.borderColor.replace('border-', 'ring-').replace(/\/\d+$/, ''),
                  isFuture && 'bg-gt-gray-200'
                )}
                title={phaseConfig.label}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// Compact version for use in message lists or small spaces
export function CompactPhaseIndicator({
  currentPhase,
  elapsedTime
}: {
  currentPhase: AgenticPhase;
  elapsedTime?: number;
}) {
  const config = phaseConfigs[currentPhase];

  if (currentPhase === 'idle') {
    return null;
  }

  return (
    <div className="flex items-center space-x-2 text-xs">
      <div className={cn('flex items-center space-x-1', config.color)}>
        <config.icon className="w-3 h-3" />
        <span>{config.label}</span>
      </div>
      {elapsedTime && elapsedTime > 0 && (
        <span className="text-gt-gray-400 font-mono">
          {elapsedTime < 60 ? `${elapsedTime.toFixed(1)}s` : `${Math.floor(elapsedTime / 60)}m`}
        </span>
      )}
    </div>
  );
}