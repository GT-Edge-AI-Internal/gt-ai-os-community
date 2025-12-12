'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Mic, Square, Database, X, Brain, Upload, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { toast } from '@/components/ui/use-toast';
import { EasyButtons } from './easy-buttons';
import type { EnhancedAgent } from '@/services/agents-enhanced';

interface ContextSource {
  id: string;
  name: string;
  type: 'document' | 'dataset';
  chunks?: number;
  description?: string;
  selected: boolean;
}

interface ConversationFile {
  id: string;
  original_filename: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
}

interface ChatInputProps {
  onSendMessage: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
  selectedContexts?: ContextSource[];
  onClearContext?: () => void;
  onFileUpload?: (files: File[]) => Promise<void>;
  conversationId?: string;
  currentAgent?: EnhancedAgent | null;
  processingFiles?: ConversationFile[];
}

export function ChatInput({
  onSendMessage,
  disabled = false,
  placeholder = "Ask me anything...",
  selectedContexts = [],
  onClearContext,
  onFileUpload,
  conversationId,
  currentAgent,
  processingFiles = []
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      // Reset height to allow shrinking
      textareaRef.current.style.height = '44px';
      // Calculate new height based on content
      const newHeight = Math.min(textareaRef.current.scrollHeight, 300);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [message]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!message.trim() || disabled) {
      return;
    }

    onSendMessage(message.trim());
    setMessage('');
    
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileUpload = () => {
    if (fileInputRef.current && !isFileAttachmentDisabled) {
      fileInputRef.current.click();
    }
  };

  // Check if file attachment should be disabled based on model
  // currentAgent can be from different sources: EnhancedAgent (model_id) or Agent (model)
  const agentModel = currentAgent?.model_id || (currentAgent as any)?.model;
  const isFileAttachmentDisabled = agentModel?.toLowerCase().includes('compound');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !onFileUpload) return;

    const fileArray = Array.from(files);
    
    // Validate file types
    const supportedTypes = ['.pdf', '.docx', '.txt', '.md', '.csv', '.json'];
    const invalidFiles = fileArray.filter(file => {
      const extension = '.' + file.name.split('.').pop()?.toLowerCase();
      return !supportedTypes.includes(extension);
    });

    if (invalidFiles.length > 0) {
      toast({
        title: "Unsupported file types",
        description: `${invalidFiles.map(f => f.name).join(', ')} are not supported. Please use: ${supportedTypes.join(', ')}`,
        variant: "destructive"
      });
      return;
    }

    // Check file sizes (10MB limit per file)
    const maxSize = 10 * 1024 * 1024; // 10MB
    const oversizedFiles = fileArray.filter(file => file.size > maxSize);

    if (oversizedFiles.length > 0) {
      toast({
        title: "Files too large",
        description: `${oversizedFiles.map(f => f.name).join(', ')} exceed the 10MB limit`,
        variant: "destructive"
      });
      return;
    }

    setIsUploading(true);
    
    try {
      await onFileUpload(fileArray);
      toast({
        title: "Files uploaded successfully",
        description: `${fileArray.length} file${fileArray.length !== 1 ? 's' : ''} uploaded and processing...`
      });
      
      // Clear the input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error) {
      console.error('File upload error:', error);
      toast({
        title: "Upload failed",
        description: "There was an error uploading your files. Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsUploading(false);
    }
  };

  const toggleRecording = () => {
    // TODO: Implement voice recording
    setIsRecording(!isRecording);
    console.log('Voice recording not implemented yet');
  };

  const handleEasyPromptClick = (prompt: string) => {
    setMessage(prompt);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  return (
    <div className="w-full">
      {/* Disclaimer Display */}
      {currentAgent?.disclaimer && (
        <div className="mb-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-start space-x-2">
            <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-yellow-800">{currentAgent.disclaimer}</p>
          </div>
        </div>
      )}

      {/* Easy Buttons Display */}
      {currentAgent?.easy_prompts && currentAgent.easy_prompts.length > 0 && !message && (
        <div className="mb-3">
          <EasyButtons
            prompts={currentAgent.easy_prompts}
            onPromptClick={handleEasyPromptClick}
          />
        </div>
      )}

      {/* Context Sources Display */}
      {selectedContexts.length > 0 && (
        <div className="mb-3 p-3 bg-gt-green/5 border border-gt-green/20 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <Brain className="h-4 w-4 text-gt-green" />
              <span className="text-sm font-medium text-gt-gray-900">
                Using {selectedContexts.length} context source{selectedContexts.length !== 1 ? 's' : ''}
              </span>
            </div>
            {onClearContext && (
              <button
                type="button"
                onClick={onClearContext}
                className="text-gt-gray-400 hover:text-gt-gray-600 transition-colors"
                title="Clear context"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {selectedContexts.map((source) => (
              <span
                key={source.id}
                className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800"
              >
                {source.type === 'dataset' ? 'Dataset' : 'Document'}: {source.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Processing Files Display */}
      {processingFiles.length > 0 && (
        <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <Upload className="h-4 w-4 text-amber-600 animate-pulse" />
            <span className="text-sm font-medium text-amber-800">
              Processing {processingFiles.length} file{processingFiles.length !== 1 ? 's' : ''}...
            </span>
          </div>
          <div className="mt-2 space-y-1">
            {processingFiles.map((file) => (
              <div key={file.id} className="flex items-center space-x-2 text-xs text-amber-700">
                <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></div>
                <span>{file.original_filename}</span>
                <span className="capitalize">({file.processing_status})</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-xs text-amber-700">
            Please wait for file processing to complete before sending messages.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="relative flex items-end space-x-3">
          {/* File Upload Button */}
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={handleFileUpload}
                  disabled={disabled || isFileAttachmentDisabled}
                  className={cn(
                    'p-3 rounded-lg transition-colors flex-shrink-0',
                    disabled || isFileAttachmentDisabled
                      ? 'text-gt-gray-300 cursor-not-allowed'
                      : 'text-gt-gray-500 hover:text-gt-gray-700 hover:bg-gt-gray-100'
                  )}
                >
                  <Paperclip className="w-5 h-5" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" sideOffset={8}>
                <p className="text-sm">Convert XLSX files to CSV before uploading for best results</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {/* Text Input */}
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage((e as React.ChangeEvent<HTMLTextAreaElement>).target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              rows={1}
              style={{ overflowY: 'hidden' }}
              className={cn(
                'chat-input w-full pr-12 min-h-[44px] max-h-[300px]',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
            />

            {/* Character Count */}
            {message.length > 0 && (
              <div className="absolute bottom-2 right-14 text-xs text-gt-gray-400">
                {message.length}
              </div>
            )}
          </div>

          {/* Voice Recording Button */}
          <button
            type="button"
            onClick={toggleRecording}
            disabled={disabled}
            className={cn(
              'p-3 rounded-lg transition-colors flex-shrink-0',
              isRecording
                ? 'text-red-600 bg-red-50 hover:bg-red-100'
                : disabled
                ? 'text-gt-gray-300 cursor-not-allowed'
                : 'text-gt-gray-500 hover:text-gt-gray-700 hover:bg-gt-gray-100'
            )}
            title={isRecording ? 'Stop recording' : 'Voice input'}
          >
            {isRecording ? (
              <Square className="w-5 h-5" />
            ) : (
              <Mic className="w-5 h-5" />
            )}
          </button>

          {/* Send Button */}
          <Button
            type="submit"
            variant="primary"
            disabled={disabled || !message.trim()}
            className="p-3 flex-shrink-0"
          >
            <Send className="w-5 h-5" />
          </Button>
        </div>

        {/* Recording Indicator */}
        {isRecording && (
          <div className="mt-2 flex items-center justify-center space-x-2 text-red-600 text-sm">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
            <span>Recording... Click the microphone to stop</span>
          </div>
        )}

        {/* Input Suggestions */}
        <div className="mt-3 flex flex-wrap gap-2">
          {!message && (
            <>
              <button
                type="button"
                onClick={() => setMessage('Help me analyze this document...')}
                disabled={disabled}
                className="px-3 py-1.5 text-xs text-gt-gray-600 bg-gt-gray-50 hover:bg-gt-gray-100 rounded-full transition-colors"
              >
                📄 Analyze document
              </button>
              <button
                type="button"
                onClick={() => setMessage('What can you help me with today?')}
                disabled={disabled}
                className="px-3 py-1.5 text-xs text-gt-gray-600 bg-gt-gray-50 hover:bg-gt-gray-100 rounded-full transition-colors"
              >
                💡 What can you do?
              </button>
              <button
                type="button"
                onClick={() => setMessage('Help me write a professional email...')}
                disabled={disabled}
                className="px-3 py-1.5 text-xs text-gt-gray-600 bg-gt-gray-50 hover:bg-gt-gray-100 rounded-full transition-colors"
              >
                ✉️ Write email
              </button>
              <button
                type="button"
                onClick={() => setMessage('Summarize the key points from...')}
                disabled={disabled}
                className="px-3 py-1.5 text-xs text-gt-gray-600 bg-gt-gray-50 hover:bg-gt-gray-100 rounded-full transition-colors"
              >
                📋 Summarize
              </button>
            </>
          )}
        </div>
      </form>

      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        multiple
        accept=".pdf,.docx,.txt,.md,.csv,.json"
        className="hidden"
      />

      {/* Input Tips */}
      <div className="mt-2 text-xs text-gt-gray-400 text-center">
        <span>Press Enter to send, Shift + Enter for new line</span>
        <span className="mx-2">•</span>
        <span>Powered by GT 2.0 Enterprise AI</span>
      </div>
    </div>
  );
}