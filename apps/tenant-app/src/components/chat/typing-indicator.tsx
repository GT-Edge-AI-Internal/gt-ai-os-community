'use client';

import { useEffect, useState } from 'react';
import { Bot, Zap, Brain, Clock, Search } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TypingIndicatorProps {
  variant?: 'thinking' | 'typing' | 'connecting' | 'tool-executing';
  agentName?: string;
  className?: string;
  startTime?: Date;
  toolName?: string;
  elapsedTime?: number;
}

interface TimedTypingIndicatorProps extends TypingIndicatorProps {
  showTimer?: boolean;
  onTimeUpdate?: (seconds: number) => void;
}

const TypingDots = () => (
  <div className="flex space-x-1">
    <div className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.3s]"></div>
    <div className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:-0.15s]"></div>
    <div className="w-2 h-2 bg-current rounded-full animate-bounce"></div>
  </div>
);

const ThinkingSpinner = () => (
  <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
);

const PulsingBrain = () => (
  <Brain className="w-4 h-4 animate-pulse" />
);

const SearchingIcon = () => (
  <Search className="w-4 h-4 animate-pulse text-gt-blue" />
);

export function TypingIndicator({
  variant = 'typing',
  agentName = 'AI Assistant',
  className,
  startTime,
  toolName,
  elapsedTime = 0
}: TypingIndicatorProps) {
  const [message, setMessage] = useState('');
  const [messageIndex, setMessageIndex] = useState(0);

  const messages = {
    thinking: [
      'Thinking...',
      'Analyzing your request...',
      'Processing information...',
      'Considering the best response...',
    ],
    typing: [
      'Typing...',
      'Composing response...',
      'Almost ready...',
    ],
    connecting: [
      'Connecting...',
      'Establishing connection...',
      'Initializing AI...',
    ],
    'tool-executing': [
      'Searching documents...',
      'Looking through knowledge base...',
      'Finding relevant information...',
      'Analyzing search results...',
    ]
  };

  useEffect(() => {
    const messageArray = messages[variant];
    setMessage(messageArray[0]);

    const interval = setInterval(() => {
      setMessageIndex((prevIndex) => {
        const nextIndex = (prevIndex + 1) % messageArray.length;
        setMessage(messageArray[nextIndex]);
        return nextIndex;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [variant]);

  const formatTime = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const getIcon = () => {
    switch (variant) {
      case 'thinking':
        return <PulsingBrain />;
      case 'connecting':
        return <ThinkingSpinner />;
      case 'tool-executing':
        return <SearchingIcon />;
      case 'typing':
      default:
        return <Zap className="w-4 h-4 text-gt-green animate-pulse" />;
    }
  };

  const getAnimation = () => {
    switch (variant) {
      case 'thinking':
        return <PulsingBrain />;
      case 'connecting':
        return <ThinkingSpinner />;
      case 'tool-executing':
        return <SearchingIcon />;
      case 'typing':
      default:
        return <TypingDots />;
    }
  };

  // Custom message for tool execution with tool name
  const getDisplayMessage = () => {
    // If elapsedTime is provided, show timer instead of message
    if (elapsedTime > 0) {
      return formatTime(elapsedTime);
    }

    if (variant === 'tool-executing' && toolName) {
      const toolMessages = {
        'search_datasets': 'Searching documents...',
        'rag_server_search_datasets': 'Searching knowledge base...'
      };
      return toolMessages[toolName] || `Executing ${toolName}...`;
    }
    return message;
  };

  return (
    <div className={cn('animate-slide-up flex gap-4', className)}>
      <div className="w-8 h-8 rounded-full bg-gt-gray-100 flex items-center justify-center flex-shrink-0">
        {getIcon()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center space-x-2 mb-2">
          <span className="text-xs text-gt-gray-500">{agentName}</span>
          <span className="text-xs text-gt-gray-400">•</span>
          <span className="text-xs text-gt-gray-400">just now</span>
        </div>

        <div className="bg-gt-gray-100 rounded-2xl px-4 py-3 max-w-xs">
          <div className="flex items-center space-x-3">
            <div className="text-gt-gray-600 text-sm">
              {getAnimation()}
            </div>
            <span className={cn(
              "text-sm animate-fade-in",
              elapsedTime > 0 ? "text-gt-gray-700 font-mono" : "text-gt-gray-700"
            )}>
              {getDisplayMessage()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Enhanced typing indicator with progress bar
export function TypingIndicatorWithProgress({ 
  variant = 'typing', 
  agentName = 'AI Assistant',
  progress = 0,
  className 
}: TypingIndicatorProps & { progress?: number }) {
  return (
    <div className={cn('animate-slide-up flex gap-4', className)}>
      <div className="w-8 h-8 rounded-full bg-gt-gray-100 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-gt-green" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center space-x-2 mb-2">
          <span className="text-xs text-gt-gray-500">{agentName}</span>
          <span className="text-xs text-gt-gray-400">•</span>
          <span className="text-xs text-gt-gray-400">generating response</span>
        </div>
        
        <div className="bg-gt-gray-100 rounded-2xl px-4 py-3 max-w-md">
          <div className="flex items-center space-x-3 mb-2">
            <TypingDots />
            <span className="text-sm text-gt-gray-700">
              {variant === 'thinking' ? 'Analyzing...' : 'Generating response...'}
            </span>
          </div>
          
          {/* Progress bar */}
          {progress > 0 && (
            <div className="w-full bg-gt-gray-200 rounded-full h-1.5">
              <div 
                className="bg-gt-green h-1.5 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Streaming message indicator
export function StreamingIndicator({
  agentName = 'AI Assistant',
  currentText = '',
  className,
  elapsedTime = 0
}: {
  agentName?: string;
  currentText?: string;
  className?: string;
  elapsedTime?: number;
}) {
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setShowCursor(prev => !prev);
    }, 500);

    return () => clearInterval(interval);
  }, []);

  const formatTime = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  return (
    <div className={cn('animate-slide-up flex gap-4', className)}>
      <div className="w-8 h-8 rounded-full bg-gt-gray-100 flex items-center justify-center flex-shrink-0">
        <Bot className="w-4 h-4 text-gt-green" />
      </div>
      <div className="flex-1 min-w-0 max-w-full overflow-hidden">
        <div className="flex items-center space-x-2 mb-2">
          <span className="text-xs text-gt-gray-500">{agentName}</span>
          <span className="text-xs text-gt-gray-400">•</span>
          <span className="text-xs text-gt-gray-400">streaming</span>
        </div>

        <div className="flex items-start gap-3">
          <div className="message-agent rounded-2xl px-4 py-3 flex-1 min-w-0">
            <div className="prose prose-sm max-w-none prose-invert">
              <div className="text-white whitespace-pre-wrap">
                {currentText}
                {showCursor && (
                  <span className="inline-block w-2 h-4 bg-gt-white ml-1 animate-pulse"></span>
                )}
              </div>
            </div>
          </div>
          {elapsedTime > 0 && (
            <div className="text-xs font-mono text-gt-gray-500 bg-gt-gray-50 px-2 py-1 rounded whitespace-nowrap flex-shrink-0 mt-1">
              {formatTime(elapsedTime)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Timed typing indicator with response time display
export function TimedTypingIndicator({
  variant = 'typing',
  agentName = 'AI Assistant',
  className,
  startTime = new Date(),
  showTimer = true,
  onTimeUpdate,
  toolName
}: TimedTypingIndicatorProps) {
  const [message, setMessage] = useState('');
  const [messageIndex, setMessageIndex] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const messages = {
    thinking: [
      'Thinking...',
      'Analyzing your request...',
      'Processing information...',
      'Considering the best response...',
    ],
    typing: [
      'Typing...',
      'Composing response...',
      'Almost ready...',
    ],
    connecting: [
      'Connecting...',
      'Establishing connection...',
      'Initializing AI...',
    ],
    'tool-executing': [
      'Searching documents...',
      'Looking through knowledge base...',
      'Finding relevant information...',
      'Analyzing search results...',
    ]
  };

  // Timer effect
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      const elapsed = (now.getTime() - startTime.getTime()) / 1000;
      setElapsedSeconds(elapsed);
      
      if (onTimeUpdate) {
        onTimeUpdate(elapsed);
      }
    }, 100);

    return () => clearInterval(timer);
  }, [startTime, onTimeUpdate]);

  // Message cycling effect
  useEffect(() => {
    const messageArray = messages[variant];
    setMessage(messageArray[0]);
    
    const interval = setInterval(() => {
      setMessageIndex((prevIndex) => {
        const nextIndex = (prevIndex + 1) % messageArray.length;
        setMessage(messageArray[nextIndex]);
        return nextIndex;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [variant]);

  const formatTime = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const getIcon = () => {
    switch (variant) {
      case 'thinking':
        return <PulsingBrain />;
      case 'connecting':
        return <ThinkingSpinner />;
      case 'tool-executing':
        return <SearchingIcon />;
      case 'typing':
      default:
        return <Zap className="w-4 h-4 text-gt-green animate-pulse" />;
    }
  };

  const getAnimation = () => {
    switch (variant) {
      case 'thinking':
        return <PulsingBrain />;
      case 'connecting':
        return <ThinkingSpinner />;
      case 'tool-executing':
        return <SearchingIcon />;
      case 'typing':
      default:
        return <TypingDots />;
    }
  };

  return (
    <div className={cn('animate-slide-up', className)}>
      {/* Time per response header */}
      {showTimer && elapsedSeconds > 0 && (
        <div className="flex items-center justify-between mb-2 px-1">
          <div className="flex items-center gap-1 text-xs text-gt-gray-400">
            <Clock className="w-3 h-3" />
            <span>Time per response</span>
          </div>
          <div className="text-xs font-mono text-gt-gray-600 bg-gt-gray-50 px-2 py-1 rounded">
            {formatTime(elapsedSeconds)}
          </div>
        </div>
      )}
      
      {/* Typing indicator */}
      <div className="flex gap-4">
        <div className="w-8 h-8 rounded-full bg-gt-gray-100 flex items-center justify-center flex-shrink-0">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-xs text-gt-gray-500">{agentName}</span>
            <span className="text-xs text-gt-gray-400">•</span>
            <span className="text-xs text-gt-gray-400">
              {showTimer && elapsedSeconds > 0 ? formatTime(elapsedSeconds) : 'just now'}
            </span>
          </div>
          
          <div className="bg-gt-gray-100 rounded-2xl px-4 py-3 max-w-xs">
            <div className="flex items-center space-x-3">
              <div className="text-gt-gray-600 text-sm">
                {getAnimation()}
              </div>
              <span className="text-sm text-gt-gray-700 animate-fade-in">
                {variant === 'tool-executing' && toolName ? (
                  toolName === 'search_datasets' ? 'Searching documents...' :
                  `Executing ${toolName}...`
                ) : message}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}