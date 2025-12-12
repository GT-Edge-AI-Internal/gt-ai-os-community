'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  MessageSquare, 
  Send, 
  Bot, 
  User, 
  Play, 
  Clock, 
  CheckCircle, 
  XCircle,
  AlertCircle,
  Loader2,
  Workflow,
  ArrowRight
} from 'lucide-react';
import { cn, formatTime } from '@/lib/utils';
import type { 
  Workflow,
  WorkflowSession, 
  WorkflowMessage, 
  WorkflowExecution,
  WorkflowInterfaceProps 
} from '@/types/workflow';

interface WorkflowChatInterfaceProps extends WorkflowInterfaceProps {
  session?: WorkflowSession;
  onSessionUpdate?: (session: WorkflowSession) => void;
  autoFocus?: boolean;
  placeholder?: string;
  maxHeight?: string;
}

interface MessageBubbleProps {
  message: WorkflowMessage;
  workflow: Workflow;
  execution?: WorkflowExecution;
  isLatest?: boolean;
}

function MessageBubble({ message, workflow, execution, isLatest }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  
  const getStatusIcon = () => {
    if (!execution || !isLatest) return null;
    
    switch (execution.status) {
      case 'running':
        return <Loader2 className="w-3 h-3 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="w-3 h-3 text-green-500" />;
      case 'failed':
        return <XCircle className="w-3 h-3 text-red-500" />;
      case 'pending':
        return <Clock className="w-3 h-3 text-yellow-500" />;
      default:
        return null;
    }
  };

  const getExecutionInfo = () => {
    if (!execution || !isLatest || message.role !== 'agent') return null;
    
    return (
      <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-gray-600">Execution Status:</span>
          <div className="flex items-center gap-1">
            {getStatusIcon()}
            <span className={cn(
              "capitalize font-medium",
              execution.status === 'completed' && "text-green-600",
              execution.status === 'failed' && "text-red-600",
              execution.status === 'running' && "text-blue-600",
              execution.status === 'pending' && "text-yellow-600"
            )}>
              {execution.status}
            </span>
          </div>
        </div>
        
        {execution.current_node_id && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Current Node:</span>
            <span className="text-gray-800">{execution.current_node_id}</span>
          </div>
        )}
        
        {execution.progress_percentage > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Progress:</span>
            <span className="text-gray-800">{execution.progress_percentage}%</span>
          </div>
        )}
        
        {execution.tokens_used > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Tokens Used:</span>
            <span className="text-gray-800">{execution.tokens_used.toLocaleString()}</span>
          </div>
        )}
        
        {execution.cost_cents > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-gray-600">Cost:</span>
            <span className="text-gray-800">${(execution.cost_cents / 100).toFixed(4)}</span>
          </div>
        )}
        
        {execution.error_details && (
          <div className="mt-1 p-2 bg-red-50 rounded border border-red-200">
            <div className="flex items-center gap-1 text-red-600 mb-1">
              <AlertCircle className="w-3 h-3" />
              <span className="font-medium">Error Details:</span>
            </div>
            <p className="text-red-700 text-xs">{execution.error_details}</p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={cn(
      "flex gap-3 mb-4",
      isUser ? "justify-end" : "justify-start"
    )}>
      {!isUser && !isSystem && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
          <Bot className="w-4 h-4 text-blue-600" />
        </div>
      )}
      
      <div className={cn(
        "max-w-[80%] rounded-lg px-4 py-2",
        isUser && "bg-blue-600 text-white",
        !isUser && !isSystem && "bg-gray-100 text-gray-900",
        isSystem && "bg-yellow-50 text-yellow-800 border border-yellow-200"
      )}>
        {isSystem && (
          <div className="flex items-center gap-1 mb-1">
            <Workflow className="w-3 h-3" />
            <span className="text-xs font-medium uppercase tracking-wide">System</span>
          </div>
        )}
        
        <div className="whitespace-pre-wrap">{message.content}</div>
        
        <div className="flex items-center justify-between mt-2">
          <span className={cn(
            "text-xs opacity-70",
            isUser && "text-blue-100",
            !isUser && !isSystem && "text-gray-500",
            isSystem && "text-yellow-600"
          )}>
            {formatTime(message.timestamp)}
          </span>
          
          {isLatest && !isUser && getStatusIcon()}
        </div>
        
        {getExecutionInfo()}
      </div>
      
      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
          <User className="w-4 h-4 text-white" />
        </div>
      )}
    </div>
  );
}

interface WorkflowContextDisplayProps {
  workflow: Workflow;
  currentExecution?: WorkflowExecution;
  className?: string;
}

function WorkflowContextDisplay({ workflow, currentExecution, className }: WorkflowContextDisplayProps) {
  const getNodeName = (nodeId: string) => {
    const node = workflow.definition.nodes.find(n => n.id === nodeId);
    return node?.data.label || nodeId;
  };

  return (
    <div className={cn("border-b p-4 bg-gray-50", className)}>
      <div className="flex items-center gap-2 mb-2">
        <Workflow className="w-4 h-4 text-gray-600" />
        <span className="text-sm font-medium text-gray-900">{workflow.name}</span>
        {workflow.description && (
          <span className="text-xs text-gray-500">• {workflow.description}</span>
        )}
      </div>
      
      {currentExecution && (
        <div className="flex items-center gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-1">
            <span>Status:</span>
            <Badge 
              variant={
                currentExecution.status === 'completed' ? 'default' :
                currentExecution.status === 'failed' ? 'destructive' :
                'secondary'
              }
              className="text-xs"
            >
              {currentExecution.status}
            </Badge>
          </div>
          
          {currentExecution.current_node_id && (
            <div className="flex items-center gap-1">
              <ArrowRight className="w-3 h-3" />
              <span>Current: {getNodeName(currentExecution.current_node_id)}</span>
            </div>
          )}
          
          {currentExecution.progress_percentage > 0 && (
            <div className="flex items-center gap-1">
              <span>Progress: {currentExecution.progress_percentage}%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function WorkflowChatInterface({
  workflow,
  onExecute,
  onExecutionUpdate,
  session,
  onSessionUpdate,
  autoFocus = true,
  placeholder = "Type your message to start the workflow...",
  maxHeight = "600px",
  className
}: WorkflowChatInterfaceProps) {
  const [messages, setMessages] = useState<WorkflowMessage[]>(session?.messages || []);
  const [currentInput, setCurrentInput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentExecution, setCurrentExecution] = useState<WorkflowExecution | null>(null);
  const [sessionId, setSessionId] = useState(session?.id);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-focus input
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  // Update messages when session prop changes
  useEffect(() => {
    if (session) {
      setMessages(session.messages);
      setSessionId(session.id);
    }
  }, [session]);

  const addMessage = (role: 'user' | 'agent' | 'system', content: string, metadata?: any) => {
    const newMessage: WorkflowMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      session_id: sessionId || 'temp',
      role,
      content,
      timestamp: new Date().toISOString(),
      execution_id: currentExecution?.id,
      metadata
    };
    
    setMessages(prev => [...prev, newMessage]);
    return newMessage;
  };

  const sendMessage = async () => {
    if (!currentInput.trim() || isExecuting) return;

    const userMessage = currentInput.trim();
    setCurrentInput('');
    setIsExecuting(true);

    // Add user message
    addMessage('user', userMessage);

    try {
      // Execute workflow with the user's message as input
      const execution = await onExecute({
        message: userMessage,
        interaction_mode: 'chat',
        session_id: sessionId
      });

      setCurrentExecution(execution);

      // Simulate workflow execution progress
      if (execution.status === 'running') {
        addMessage('system', `Workflow execution started (ID: ${execution.id})`);
        
        // Poll for execution updates
        pollExecutionStatus(execution.id);
      } else if (execution.status === 'completed') {
        handleExecutionComplete(execution);
      } else if (execution.status === 'failed') {
        handleExecutionFailed(execution);
      }

    } catch (error) {
      console.error('Failed to execute workflow:', error);
      addMessage('system', `Error executing workflow: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsExecuting(false);
    }
  };

  const pollExecutionStatus = async (executionId: string) => {
    try {
      // In a real implementation, this would poll the backend API
      // For now, we'll simulate the execution completing after a delay
      setTimeout(async () => {
        // Simulate getting updated execution status
        const updatedExecution: WorkflowExecution = {
          ...currentExecution!,
          status: 'completed',
          progress_percentage: 100,
          completed_at: new Date().toISOString(),
          duration_ms: 2500,
          output_data: {
            result: "Workflow completed successfully! Here's the response from your Agent.",
            processed_message: currentInput
          },
          tokens_used: 150,
          cost_cents: 5
        };

        setCurrentExecution(updatedExecution);
        handleExecutionComplete(updatedExecution);
        
        if (onExecutionUpdate) {
          onExecutionUpdate(updatedExecution);
        }
      }, 2500);

    } catch (error) {
      console.error('Error polling execution status:', error);
      addMessage('system', 'Error monitoring workflow execution');
      setIsExecuting(false);
    }
  };

  const handleExecutionComplete = (execution: WorkflowExecution) => {
    setIsExecuting(false);
    
    // Add agent response
    const agentResponse = execution.output_data?.result || 
      "Workflow completed successfully!";
    
    addMessage('agent', agentResponse, {
      execution_id: execution.id,
      tokens_used: execution.tokens_used,
      cost_cents: execution.cost_cents
    });

    // Add system completion message
    addMessage('system', 
      `Workflow completed in ${execution.duration_ms}ms. ` +
      `Used ${execution.tokens_used} tokens (${(execution.cost_cents / 100).toFixed(4)} USD).`
    );
  };

  const handleExecutionFailed = (execution: WorkflowExecution) => {
    setIsExecuting(false);
    
    addMessage('agent', 
      `I encountered an error while processing your request: ${execution.error_details || 'Unknown error'}`
    );
    
    addMessage('system', `Workflow execution failed (ID: ${execution.id})`);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Card className={cn("flex flex-col", className)}>
      <CardHeader className="pb-0">
        <CardTitle className="flex items-center gap-2 text-lg">
          <MessageSquare className="w-5 h-5" />
          Chat with Workflow
        </CardTitle>
      </CardHeader>

      <WorkflowContextDisplay 
        workflow={workflow} 
        currentExecution={currentExecution} 
      />

      <CardContent className="flex-1 flex flex-col p-0">
        {/* Messages Area */}
        <div 
          className="flex-1 overflow-y-auto p-4 space-y-2"
          style={{ maxHeight }}
        >
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              <MessageSquare className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium mb-2">Start a conversation</p>
              <p className="text-sm">
                Send a message to begin executing this workflow. Your Agent will guide you through the process.
              </p>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  workflow={workflow}
                  execution={currentExecution}
                  isLatest={index === messages.length - 1}
                />
              ))}
              
              {isExecuting && (
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="bg-gray-100 rounded-lg px-4 py-2">
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                      <span className="text-gray-600">Processing your request...</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t p-4">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={currentInput}
              onChange={(e) => setCurrentInput((e as React.ChangeEvent<HTMLSelectElement>).target.value)}
              onKeyPress={handleKeyPress}
              placeholder={placeholder}
              disabled={isExecuting}
              className="flex-1"
            />
            <Button
              onClick={sendMessage}
              disabled={!currentInput.trim() || isExecuting}
              size="icon"
            >
              {isExecuting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
          
          {workflow.definition.nodes.length > 0 && (
            <p className="text-xs text-gray-500 mt-2">
              This workflow contains {workflow.definition.nodes.length} nodes. 
              Press Enter to send, Shift+Enter for new line.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}