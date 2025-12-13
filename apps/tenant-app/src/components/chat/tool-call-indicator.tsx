/**
 * GT 2.0 Tool Call Indicator Component
 *
 * Displays active tool calls with real-time status updates.
 * Shows tool name, parameters, execution state, and results.
 */

import React from 'react';
import { motion } from 'framer-motion';
import {
  Wrench,
  Loader2,
  CheckCircle,
  XCircle,
  Search,
  Database,
  Globe,
  FileText,
  MessageSquare,
  Terminal,
  Code,
  AlertCircle
} from 'lucide-react';

export interface ToolCall {
  id: string;
  name: string;
  description?: string;
  parameters?: Record<string, any>;
  status: 'pending' | 'executing' | 'completed' | 'failed';
  result?: any;
  error?: string;
  startTime?: Date;
  endTime?: Date;
}

interface ToolCallIndicatorProps {
  toolCall: ToolCall;
  isCompact?: boolean;
  showParameters?: boolean;
  showResult?: boolean;
  onRetry?: (toolCall: ToolCall) => void;
}

const ToolCallIndicator: React.FC<ToolCallIndicatorProps> = ({
  toolCall,
  isCompact = false,
  showParameters = true,
  showResult = true,
  onRetry
}) => {
  const getToolIcon = (toolName: string) => {
    const name = toolName.toLowerCase();

    if (name.includes('search')) return <Search className="w-4 h-4" />;
    if (name.includes('database') || name.includes('sql')) return <Database className="w-4 h-4" />;
    if (name.includes('web') || name.includes('brave')) return <Globe className="w-4 h-4" />;
    if (name.includes('file') || name.includes('document')) return <FileText className="w-4 h-4" />;
    if (name.includes('conversation') || name.includes('chat')) return <MessageSquare className="w-4 h-4" />;
    if (name.includes('execute') || name.includes('run')) return <Terminal className="w-4 h-4" />;
    if (name.includes('code')) return <Code className="w-4 h-4" />;

    return <Wrench className="w-4 h-4" />;
  };

  const getStatusIcon = () => {
    switch (toolCall.status) {
      case 'pending':
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
      case 'executing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
    }
  };

  const getStatusText = () => {
    switch (toolCall.status) {
      case 'pending':
        return 'Queued';
      case 'executing':
        return 'Executing...';
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
    }
  };

  const getExecutionTime = () => {
    if (!toolCall.startTime) return null;
    const end = toolCall.endTime || new Date();
    const duration = end.getTime() - toolCall.startTime.getTime();
    return duration < 1000 ? `${duration}ms` : `${(duration / 1000).toFixed(1)}s`;
  };

  const formatParameterValue = (value: any): string => {
    if (typeof value === 'string') {
      return value.length > 50 ? `${value.substring(0, 50)}...` : value;
    }
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  const formatResult = (result: any): string => {
    if (typeof result === 'string') {
      return result;
    }
    if (typeof result === 'object') {
      return JSON.stringify(result, null, 2);
    }
    return String(result);
  };

  if (isCompact) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="inline-flex items-center space-x-2 px-2 py-1 bg-gray-100 rounded-lg text-sm"
      >
        {getToolIcon(toolCall.name)}
        <span className="font-medium">{toolCall.name}</span>
        {getStatusIcon()}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`
        border rounded-lg p-4 mb-3
        ${toolCall.status === 'executing' ? 'border-blue-300 bg-blue-50' : ''}
        ${toolCall.status === 'completed' ? 'border-green-300 bg-green-50' : ''}
        ${toolCall.status === 'failed' ? 'border-red-300 bg-red-50' : ''}
        ${toolCall.status === 'pending' ? 'border-gray-300 bg-gray-50' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className={`
            p-2 rounded-lg
            ${toolCall.status === 'executing' ? 'bg-blue-100' : ''}
            ${toolCall.status === 'completed' ? 'bg-green-100' : ''}
            ${toolCall.status === 'failed' ? 'bg-red-100' : ''}
            ${toolCall.status === 'pending' ? 'bg-gray-100' : ''}
          `}>
            {getToolIcon(toolCall.name)}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h4 className="font-semibold text-gray-900">{toolCall.name}</h4>
              {getStatusIcon()}
            </div>
            {toolCall.description && (
              <p className="text-sm text-gray-600 mt-0.5">{toolCall.description}</p>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-3 text-sm">
          <span className={`
            font-medium
            ${toolCall.status === 'executing' ? 'text-blue-600' : ''}
            ${toolCall.status === 'completed' ? 'text-green-600' : ''}
            ${toolCall.status === 'failed' ? 'text-red-600' : ''}
            ${toolCall.status === 'pending' ? 'text-gray-600' : ''}
          `}>
            {getStatusText()}
          </span>
          {getExecutionTime() && (
            <span className="text-gray-500">{getExecutionTime()}</span>
          )}
        </div>
      </div>

      {/* Parameters */}
      {showParameters && toolCall.parameters && Object.keys(toolCall.parameters).length > 0 && (
        <div className="mb-3">
          <h5 className="text-sm font-medium text-gray-700 mb-2">Parameters:</h5>
          <div className="bg-gt-white rounded p-2 space-y-1">
            {Object.entries(toolCall.parameters).map(([key, value]) => (
              <div key={key} className="flex items-start text-sm">
                <span className="font-mono text-gray-600 mr-2">{key}:</span>
                <span className="text-gray-800 break-all font-mono text-xs">
                  {formatParameterValue(value)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {showResult && toolCall.status === 'completed' && toolCall.result && (
        <div className="mt-3">
          <h5 className="text-sm font-medium text-gray-700 mb-2">Result:</h5>
          <div className="bg-gt-white rounded p-2 max-h-40 overflow-auto">
            <pre className="text-xs text-gray-800 whitespace-pre-wrap">
              {formatResult(toolCall.result)}
            </pre>
          </div>
        </div>
      )}

      {/* Error */}
      {toolCall.status === 'failed' && toolCall.error && (
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <h5 className="text-sm font-medium text-red-700 mb-2">Error:</h5>
            {onRetry && (
              <button
                onClick={() => onRetry(toolCall)}
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
              >
                Retry
              </button>
            )}
          </div>
          <div className="bg-red-100 rounded p-2">
            <p className="text-sm text-red-800">{toolCall.error}</p>
          </div>
        </div>
      )}

      {/* Executing Animation */}
      {toolCall.status === 'executing' && (
        <motion.div
          className="mt-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className="flex items-center space-x-2">
            <div className="flex space-x-1">
              <motion.div
                className="w-2 h-2 bg-blue-500 rounded-full"
                animate={{ scale: [1, 1.5, 1] }}
                transition={{ duration: 0.6, repeat: Infinity }}
              />
              <motion.div
                className="w-2 h-2 bg-blue-500 rounded-full"
                animate={{ scale: [1, 1.5, 1] }}
                transition={{ duration: 0.6, delay: 0.2, repeat: Infinity }}
              />
              <motion.div
                className="w-2 h-2 bg-blue-500 rounded-full"
                animate={{ scale: [1, 1.5, 1] }}
                transition={{ duration: 0.6, delay: 0.4, repeat: Infinity }}
              />
            </div>
            <span className="text-sm text-blue-600">Processing...</span>
          </div>
        </motion.div>
      )}
    </motion.div>
  );
};

export default ToolCallIndicator;