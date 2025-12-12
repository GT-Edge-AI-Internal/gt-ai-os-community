/**
 * GT 2.0 Subagent Activity Component
 *
 * Displays real-time subagent execution status during complex task handling.
 * Shows parallel execution, task delegation, and orchestration visualization.
 */

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Cpu,
  Search,
  Code,
  FileText,
  Sparkles,
  GitBranch,
  Activity
} from 'lucide-react';

interface SubagentExecution {
  id: string;
  type: 'research' | 'planning' | 'implementation' | 'validation' | 'synthesis' | 'analyst';
  task: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  startTime?: Date;
  endTime?: Date;
  dependsOn?: string[];
  results?: any;
  error?: string;
}

interface SubagentActivityProps {
  executionId?: string;
  complexity?: 'simple' | 'tool_assisted' | 'multi_step' | 'research' | 'implementation' | 'complex';
  strategy?: 'sequential' | 'parallel' | 'pipeline';
  subagents: SubagentExecution[];
  isActive: boolean;
  onSubagentClick?: (subagent: SubagentExecution) => void;
}

const SubagentActivity: React.FC<SubagentActivityProps> = ({
  executionId,
  complexity = 'simple',
  strategy = 'sequential',
  subagents,
  isActive,
  onSubagentClick
}) => {
  const [expanded, setExpanded] = useState(isActive);
  const [selectedSubagent, setSelectedSubagent] = useState<string | null>(null);

  useEffect(() => {
    setExpanded(isActive);
  }, [isActive]);

  const getSubagentIcon = (type: SubagentExecution['type']) => {
    switch (type) {
      case 'research':
        return <Search className="w-4 h-4" />;
      case 'planning':
        return <GitBranch className="w-4 h-4" />;
      case 'implementation':
        return <Code className="w-4 h-4" />;
      case 'validation':
        return <CheckCircle className="w-4 h-4" />;
      case 'synthesis':
        return <Sparkles className="w-4 h-4" />;
      case 'analyst':
        return <FileText className="w-4 h-4" />;
      default:
        return <Cpu className="w-4 h-4" />;
    }
  };

  const getStatusIcon = (status: SubagentExecution['status']) => {
    switch (status) {
      case 'pending':
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getComplexityColor = () => {
    switch (complexity) {
      case 'simple':
        return 'bg-green-100 text-green-800';
      case 'tool_assisted':
        return 'bg-blue-100 text-blue-800';
      case 'multi_step':
        return 'bg-purple-100 text-purple-800';
      case 'research':
        return 'bg-indigo-100 text-indigo-800';
      case 'implementation':
        return 'bg-orange-100 text-orange-800';
      case 'complex':
        return 'bg-red-100 text-red-800';
    }
  };

  const getStrategyIcon = () => {
    switch (strategy) {
      case 'parallel':
        return <Activity className="w-4 h-4" />;
      case 'pipeline':
        return <ChevronRight className="w-4 h-4" />;
      default:
        return <GitBranch className="w-4 h-4" />;
    }
  };

  const calculateExecutionTime = (subagent: SubagentExecution) => {
    if (!subagent.startTime) return null;
    const end = subagent.endTime || new Date();
    const duration = end.getTime() - subagent.startTime.getTime();
    return `${(duration / 1000).toFixed(1)}s`;
  };

  // Group subagents by execution phase for parallel visualization
  const groupedSubagents = subagents.reduce((acc, subagent) => {
    const phase = subagent.dependsOn?.length || 0;
    if (!acc[phase]) acc[phase] = [];
    acc[phase].push(subagent);
    return acc;
  }, {} as Record<number, SubagentExecution[]>);

  return (
    <div className="bg-gray-50 rounded-lg p-3 mb-4">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center space-x-3">
          <motion.div
            animate={{ rotate: expanded ? 90 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronRight className="w-5 h-5 text-gray-500" />
          </motion.div>

          <div className="flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-indigo-500" />
            <span className="font-medium text-gray-900">
              Subagent Orchestration
            </span>
            {isActive && (
              <span className="flex items-center space-x-1 text-sm text-blue-600">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Active</span>
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span className={`px-2 py-1 text-xs font-medium rounded-full ${getComplexityColor()}`}>
            {complexity.replace('_', ' ')}
          </span>
          <div className="flex items-center space-x-1 text-sm text-gray-500">
            {getStrategyIcon()}
            <span>{strategy}</span>
          </div>
          <span className="text-sm text-gray-500">
            {subagents.filter(s => s.status === 'completed').length}/{subagents.length} completed
          </span>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="mt-4 overflow-hidden"
          >
            {/* Execution Timeline */}
            <div className="space-y-3">
              {Object.entries(groupedSubagents)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([phase, phaseSubagents]) => (
                  <div key={phase} className="relative">
                    {Number(phase) > 0 && (
                      <div className="absolute -top-2 left-6 w-0.5 h-2 bg-gray-300" />
                    )}

                    <div className="flex items-start space-x-2">
                      <div className="text-xs text-gray-500 w-12 pt-1">
                        Phase {Number(phase) + 1}
                      </div>

                      <div className="flex-1">
                        <div className={`grid gap-2 ${phaseSubagents.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                          {phaseSubagents.map((subagent) => (
                            <motion.div
                              key={subagent.id}
                              initial={{ scale: 0.9, opacity: 0 }}
                              animate={{ scale: 1, opacity: 1 }}
                              transition={{ duration: 0.2 }}
                              className={`
                                bg-white border rounded-lg p-3 cursor-pointer transition-all
                                ${selectedSubagent === subagent.id ? 'border-indigo-500 shadow-md' : 'border-gray-200 hover:border-gray-300'}
                              `}
                              onClick={() => {
                                setSelectedSubagent(subagent.id);
                                onSubagentClick?.(subagent);
                              }}
                            >
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center space-x-2">
                                  {getSubagentIcon(subagent.type)}
                                  <span className="text-sm font-medium capitalize">
                                    {subagent.type}
                                  </span>
                                </div>
                                {getStatusIcon(subagent.status)}
                              </div>

                              <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                                {subagent.task}
                              </p>

                              {subagent.status === 'running' && subagent.progress !== undefined && (
                                <div className="mb-2">
                                  <div className="w-full bg-gray-200 rounded-full h-1.5">
                                    <motion.div
                                      className="bg-indigo-500 h-1.5 rounded-full"
                                      initial={{ width: 0 }}
                                      animate={{ width: `${subagent.progress}%` }}
                                      transition={{ duration: 0.5 }}
                                    />
                                  </div>
                                </div>
                              )}

                              <div className="flex items-center justify-between text-xs text-gray-500">
                                <span>{subagent.status}</span>
                                {subagent.startTime && (
                                  <span>{calculateExecutionTime(subagent)}</span>
                                )}
                              </div>

                              {subagent.error && (
                                <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-600">
                                  {subagent.error}
                                </div>
                              )}
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
            </div>

            {/* Execution Summary */}
            {!isActive && subagents.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Total Time:</span>
                    <span className="ml-2 font-medium">
                      {(() => {
                        const firstStart = Math.min(...subagents.filter(s => s.startTime).map(s => s.startTime!.getTime()));
                        const lastEnd = Math.max(...subagents.filter(s => s.endTime).map(s => s.endTime!.getTime()));
                        return `${((lastEnd - firstStart) / 1000).toFixed(1)}s`;
                      })()}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Success Rate:</span>
                    <span className="ml-2 font-medium">
                      {Math.round((subagents.filter(s => s.status === 'completed').length / subagents.length) * 100)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Execution ID:</span>
                    <span className="ml-2 font-mono text-xs">
                      {executionId?.slice(0, 8)}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default SubagentActivity;