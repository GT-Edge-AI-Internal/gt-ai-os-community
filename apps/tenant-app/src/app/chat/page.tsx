'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { AppLayout } from '@/components/layout/app-layout';
import { AuthGuard } from '@/components/auth/auth-guard';
import { GT2_CAPABILITIES } from '@/lib/capabilities';
import { getAuthToken, getTenantInfo, getUser } from '@/services/auth';
import { agentService } from '@/services';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import {
  MessageCircle,
  Bot,
  Zap,
  Brain,
  Paperclip,
  X,
  Plus,
  Search,
  ChevronUp,
  ChevronDown,
  Copy,
  Check,
  History,
  FileText,
  AlertCircle,
  Sparkles,
  Flag
} from 'lucide-react';
import { cn, formatDateTime } from '@/lib/utils';
import { TypingIndicator, StreamingIndicator } from '@/components/chat/typing-indicator';
import { streamChat, StreamingChatMessage, TokenUsage } from '@/services/chat-service';
import { ToolExecution, SubagentExecution, AgenticPhase } from '@/types';
import { DownloadButton } from '@/components/ui/download-button';
import { MessageRenderer } from '@/components/chat/message-renderer';
import { SubagentActivityPanel } from '@/components/chat/enhanced-subagent-activity';
import { ToolExecutionPanel } from '@/components/chat/tool-execution-panel';
import { usePageTitle } from '@/hooks/use-page-title';
import { ReportChatIssueSheet } from '@/components/chat/report-chat-issue-sheet';

// Agent interface for real agents
interface Agent {
  id: string;
  name: string;
  description: string;
  category?: string;
  personality_config?: any;
  resource_preferences?: any;
  tags?: string[];
  user_id: string;
  created_at: string;
  updated_at: string;
  disclaimer?: string;
  easy_prompts?: string[];
  model?: string;  // ✅ Add model field
  temperature?: number;  // ✅ Add temperature field
  max_tokens?: number;  // ✅ Add max_tokens field
  model_parameters?: {  // ✅ Add model_parameters fallback
    temperature?: number;
    max_tokens?: number;
  };
}

interface BudgetStatus {
  within_budget: boolean;
  current_usage_cents: number;
  budget_limit_cents: number | null;
  percentage_used: number;
  warning_level: 'normal' | 'warning' | 'critical' | 'exceeded';
  enforcement_enabled: boolean;
}

interface ConversationFile {
  id: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  uploaded_at: string;
}


interface ThinkingStep {
  title: string;
  content: string;
}

// Timer formatting utility - formats seconds to "Xm Y.Zs" or "Y.Zs"
const formatResponseTime = (seconds: number): string => {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
};

/**
 * Wrapper for fetch that handles 401 responses by triggering logout
 * TODO: Migrate to centralized API service layer (conversations.ts)
 */
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const response = await fetch(url, options);

  // Handle 401 - session expired
  if (response.status === 401) {
    console.warn('Chat API: 401 detected, triggering logout');
    if (typeof window !== 'undefined') {
      const { useAuthStore } = await import('@/stores/auth-store');
      useAuthStore.getState().logout('expired');
    }
  }

  return response;
}

interface ChatMessage {
  id: number;
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
  agents?: Agent[];
  agentReasoning?: string;
  thinking?: {
    steps: ThinkingStep[];
  };
  truncated?: boolean;  // ✅ Flag for truncated responses
  responseDuration?: number;  // Response time in seconds (session-only)
  responseStartTime?: number;  // Timestamp when response started (milliseconds)
  tokenCount?: number;  // Token count for the message
  modelUsed?: string;  // Model used to generate the response
  finishReason?: string;  // Finish reason from LLM response
  costBreakdown?: TokenUsage['cost_breakdown'];  // Compound model billing data
}

function ChatPage() {
  // Get URL search params for agent selection
  const searchParams = useSearchParams();
  const router = useRouter();

  // State management
  const [historySidebarOpen, setHistorySidebarOpen] = useState(false);
  const [messageInput, setMessageInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<Agent[]>([]);
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastAssistantMessageRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const [chatName, setChatName] = useState('New Chat');

  // Dataset selection removed - now handled via agent configuration only

  // Memory control state - DISABLED
  // History search functionality has been disabled
  const [isEditingChatName, setIsEditingChatName] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const conversationIdRef = useRef<string | null>(null); // Track conversation ID at message send time
  const isManualClearRef = useRef(false);

  // File upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{[key: string]: number}>({});
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [conversationFiles, setConversationFiles] = useState<ConversationFile[]>([]);
  const [isFilePanelExpanded, setIsFilePanelExpanded] = useState(true);

  // Budget status for file upload blocking (Issue #234)
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
  // Only block operations if budget is exceeded AND enforcement is enabled
  const isBudgetExceeded = budgetStatus?.warning_level === 'exceeded' && budgetStatus?.enforcement_enabled;
  // Show warning (but don't block) when budget exceeded but enforcement disabled
  const isBudgetWarning = budgetStatus?.warning_level === 'exceeded' && !budgetStatus?.enforcement_enabled;

  // React Query client for cache invalidation
  const queryClient = useQueryClient();

  // Helper functions for file display
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };


  // Enhanced chat features state
  // Agentic execution state
  const [currentPhase, setCurrentPhase] = useState<AgenticPhase>('idle');
  const [activeTools, setActiveTools] = useState<ToolExecution[]>([]);
  const [subagentActivity, setSubagentActivity] = useState<SubagentExecution[]>([]);
  const [orchestrationStrategy, setOrchestrationStrategy] = useState<string>('');

  // Dataset loading removed - datasets now managed via agent configuration only

  // Report dialog state
  const [reportDialogOpen, setReportDialogOpen] = useState(false);

  // Message pagination for performance
  const [visibleMessageCount, setVisibleMessageCount] = useState(50);
  const MESSAGE_INCREMENT = 25;

  // Auto-expand visible messages when new messages arrive
  useEffect(() => {
    if (messages.length > visibleMessageCount) {
      setVisibleMessageCount(messages.length);
    }
  }, [messages.length]);
  const [reportMessageData, setReportMessageData] = useState<{
    agentName: string;
    timestamp: string;
    conversationName: string;
    userPrompt: string;
    agentResponse: string;
    model?: string;
    temperature?: number;
    maxTokens?: number;
    tenantUrl?: string;
    tenantName?: string;
    userEmail?: string;
  } | null>(null);

  // Fetch conversation files
  const fetchConversationFiles = useCallback(async (conversationId: string) => {
    try {
      const token = getAuthToken();
      const response = await fetchWithAuth(
        `/api/v1/conversations/${conversationId}/files`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      if (response.ok) {
        const data = await response.json();
        setConversationFiles(data.files || []);
      }
    } catch (error) {
      console.error('Failed to fetch files:', error);
      setConversationFiles([]);
    }
  }, []);

  // Load conversation files when conversation changes
  useEffect(() => {
    if (currentConversationId) {
      fetchConversationFiles(currentConversationId);
    } else {
      setConversationFiles([]);
    }
  }, [currentConversationId, fetchConversationFiles]);

  // Fetch budget status for file upload blocking (Issue #234)
  useEffect(() => {
    async function fetchBudgetStatus() {
      try {
        const response = await api.get<BudgetStatus>('/api/v1/optics/budget-status');
        if (response.data) {
          setBudgetStatus(response.data);
        }
      } catch (error) {
        console.error('Failed to fetch budget status:', error);
        // Don't block uploads if budget check fails
        setBudgetStatus(null);
      }
    }

    fetchBudgetStatus();
    // Refresh budget status every 5 minutes
    const interval = setInterval(fetchBudgetStatus, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Keep conversation ID ref in sync for message context isolation
  useEffect(() => {
    conversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  // Mark conversation as read when opened
  useEffect(() => {
    if (currentConversationId) {
      // Import the store at the top and use it here
      // We'll call the markConversationAsRead action from the chat store
      const { markConversationAsRead } = require('@/stores/chat-store').useChatStore.getState();
      markConversationAsRead(currentConversationId);
    }
  }, [currentConversationId]);

  // NOTE: WebSocket connection is now initialized globally in AppLayout
  // No need for page-specific initialization

  // Poll for file processing status updates
  useEffect(() => {
    if (!currentConversationId) return;

    const hasProcessingFiles = conversationFiles.some(f =>
      f.processing_status === 'pending' || f.processing_status === 'processing'
    );

    if (!hasProcessingFiles) return;

    const pollInterval = setInterval(() => {
      fetchConversationFiles(currentConversationId);
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [currentConversationId, conversationFiles, fetchConversationFiles]);

  // Handle file removal
  const handleRemoveFile = async (fileId: string) => {
    if (!currentConversationId) return;

    // Check if conversation has started (has messages)
    if (messages.length > 0) {
      alert(
        "Files cannot be deleted after conversation has started.\n\n" +
        "This helps maintain conversation integrity and accurate context."
      );
      return;
    }

    try {
      const token = getAuthToken();
      const response = await fetchWithAuth(
        `/api/v1/conversations/${currentConversationId}/files/${fileId}`,
        {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        await fetchConversationFiles(currentConversationId);
      } else {
        const error = await response.json();
        alert(error.detail || 'Failed to delete file. Please try again.');
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert('Failed to delete file. Please try again.');
    }
  };

  // Handle file upload using simplified conversation files approach
  const handleFileUpload = async (files: FileList) => {
    if (!files.length) return;

    setIsUploading(true);

    try {
      // Create conversation if one doesn't exist yet
      let targetConversationId = currentConversationId;

      if (!targetConversationId) {
        console.log('🆕 No conversation exists, creating one for file upload...');
        targetConversationId = await createNewConversation('File upload conversation');
        if (!targetConversationId) {
          throw new Error('Failed to create conversation for file upload');
        }
        setCurrentConversationId(targetConversationId);
        console.log('🎉 Created conversation for file upload:', targetConversationId);
      }

      // Upload files directly to conversation (no dataset creation)
      const formData = new FormData();
      Array.from(files).forEach(file => {
        formData.append('files', file);
      });

      const uploadResult = await api.upload(`/api/v1/conversations/${targetConversationId}/files`, formData);

      if (uploadResult.error) {
        throw new Error(`Failed to upload files: ${uploadResult.error}`);
      }

      const uploadedFiles = uploadResult.data;
      console.log(`Successfully uploaded ${uploadedFiles.length} files to conversation:`, uploadedFiles);

      // Refresh file list to show newly uploaded files
      if (targetConversationId) {
        await fetchConversationFiles(targetConversationId);
      }

      // Clear file input to allow re-uploading same file
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

    } catch (error) {
      console.error('File upload failed:', error);
      // TODO: Show error toast
    } finally {
      setIsUploading(false);
    }
  };

  const [selectedAgent, setSelectedAgent] = useState<string>('');

  // Memoize selected agent data to avoid repeated .find() calls on every render
  const selectedAgentData = useMemo(() => {
    return selectedAgent ? availableAgents.find(a => a.id === selectedAgent) : null;
  }, [selectedAgent, availableAgents]);

  // Textarea resize state
  const [textareaHeight, setTextareaHeight] = useState(40); // min height to match Send button (h-10)
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ y: number; height: number } | null>(null);
  const [hasScrollbar, setHasScrollbar] = useState(false);

  // Textarea resize handlers
  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartRef.current = {
      y: e.clientY,
      height: textareaHeight
    };
  };

  const handleDragMove = useCallback((e: MouseEvent) => {
    if (!isDragging || !dragStartRef.current) return;

    const deltaY = dragStartRef.current.y - e.clientY; // Inverted: drag up = positive delta = increase height
    const newHeight = Math.max(40, Math.min(300, dragStartRef.current.height + deltaY));
    setTextareaHeight(newHeight);
  }, [isDragging]);

  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  // Add mouse event listeners for dragging
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleDragMove);
      document.addEventListener('mouseup', handleDragEnd);
      return () => {
        document.removeEventListener('mousemove', handleDragMove);
        document.removeEventListener('mouseup', handleDragEnd);
      };
    }
  }, [isDragging, handleDragMove, handleDragEnd]);

  // Auto-expand textarea based on content (Issue #148)
  useEffect(() => {
    if (!textareaRef.current) return;

    const minHeight = 40;
    const maxHeight = 300;

    // If empty, reset to minimum
    if (!messageInput || messageInput.trim().length === 0) {
      if (textareaHeight !== minHeight) {
        setTextareaHeight(minHeight);
      }
      return;
    }

    // Set to auto to measure actual content height
    textareaRef.current.style.height = 'auto';
    const scrollHeight = textareaRef.current.scrollHeight;

    // Restore current height
    textareaRef.current.style.height = `${textareaHeight}px`;

    // Expand if content needs more space (up to max)
    if (scrollHeight > textareaHeight && textareaHeight < maxHeight) {
      const newHeight = Math.min(maxHeight, scrollHeight);
      setTextareaHeight(newHeight);
    }
    // Shrink if content is smaller than current height
    else if (scrollHeight < textareaHeight) {
      const newHeight = Math.max(minHeight, scrollHeight);
      setTextareaHeight(newHeight);
    }
    // Stay at current height if content still fills current space or we're at max
  }, [messageInput, textareaHeight]);

  // Check if textarea has scrollbar (debounced for performance)
  useEffect(() => {
    if (!textareaRef.current) return;

    const checkScrollbar = () => {
      if (textareaRef.current) {
        const hasScroll = textareaRef.current.scrollHeight > textareaRef.current.clientHeight;
        setHasScrollbar(hasScroll);
      }
    };

    // Debounce the check to avoid running on every keystroke
    const timeoutId = setTimeout(checkScrollbar, 100);
    return () => clearTimeout(timeoutId);
  }, [textareaHeight]); // Only run when height changes, not on every input

  // Agent datasets are now handled entirely on the backend via agent configuration
  const agentDatasets: string[] = [];

  // Dataset logic simplified - managed entirely on backend via agent configuration

  // Copy functionality state
  const [copiedMessages, setCopiedMessages] = useState<Set<number>>(new Set());
  const [copiedCodeBlocks, setCopiedCodeBlocks] = useState<Set<string>>(new Set());

  // Track which message has sticky buttons
  const [stickyMessageId, setStickyMessageId] = useState<number | null>(null);
  const [stickyButtonRight, setStickyButtonRight] = useState<number>(16);
  const [stickyButtonTop, setStickyButtonTop] = useState<number>(8);
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Streaming state - conversation-specific
  const [activeStreamingConversationId, setActiveStreamingConversationId] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState<string>('');
  const [isStreamingActive, setIsStreamingActive] = useState(false);

  // Timer state for response tracking
  const [responseStartTime, setResponseStartTime] = useState<number | null>(null);
  const [elapsedTime, setElapsedTime] = useState<number>(0);

  // Update elapsed time while streaming
  useEffect(() => {
    if (!responseStartTime || !isStreamingActive) {
      return;
    }

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - responseStartTime) / 1000; // Convert to seconds
      setElapsedTime(elapsed);
    }, 100); // Update every 100ms for smooth timer

    return () => clearInterval(interval);
  }, [responseStartTime, isStreamingActive]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToLastAssistantMessage = () => {
    // Scroll to the top of the last agent message for better readability
    lastAssistantMessageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };



  // Simple copy functionality
  const copyToClipboard = async (text: string): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      console.error('Failed to copy text: ', err);
      return false;
    }
  };

  const copyMessage = async (messageId: number, content: string) => {
    const success = await copyToClipboard(content);
    if (success) {
      setCopiedMessages(prev => new Set(prev).add(messageId));
      setTimeout(() => {
        setCopiedMessages(prev => {
          const newSet = new Set(prev);
          newSet.delete(messageId);
          return newSet;
        });
      }, 2000);
    }
  };

  const copyCodeBlock = async (codeId: string, code: string) => {
    const success = await copyToClipboard(code);
    if (success) {
      setCopiedCodeBlocks(prev => new Set(prev).add(codeId));
      setTimeout(() => {
        setCopiedCodeBlocks(prev => {
          const newSet = new Set(prev);
          newSet.delete(codeId);
          return newSet;
        });
      }, 2000);
    }
  };

  // Report chat issue handler - opens dialog with report options
  const handleReportHarmful = (messageIndex: number) => {
    // Find the current agent message
    const agentMessage = messages[messageIndex];

    // Find the preceding user message
    let userMessage = null;
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        userMessage = messages[i];
        break;
      }
    }

    // Get agent details
    const agentId = agentMessage.agents?.[0]?.id || selectedAgent;
    const agent = agentId ? availableAgents.find(a => a.id === agentId) : null;
    const agentName = agentMessage.agents?.[0]?.name ||
                     (agent?.name) ||
                     'AI Agent';

    // Get agent configuration (model, temperature, max_tokens)
    const model = agent?.model || 'Not specified';
    const temperature = agent?.temperature ?? agent?.model_parameters?.temperature;
    const maxTokens = agent?.max_tokens ?? agent?.model_parameters?.max_tokens;

    // Get tenant information
    const tenantInfo = getTenantInfo();
    const tenantUrl = typeof window !== 'undefined' ? window.location.origin : undefined;
    const tenantName = tenantInfo?.name;

    // Get user information
    const user = getUser();
    const userEmail = user?.email;

    // Prepare data for report dialog
    setReportMessageData({
      agentName,
      timestamp: agentMessage.timestamp ? new Date(agentMessage.timestamp).toLocaleString() : 'Unknown',
      conversationName: chatName || 'Untitled Chat',
      userPrompt: userMessage ? userMessage.content : '[No user prompt found]',
      agentResponse: agentMessage.content,
      model,
      temperature,
      maxTokens,
      tenantUrl,
      tenantName,
      userEmail,
    });

    // Open report dialog
    setReportDialogOpen(true);
  };

  useEffect(() => {
    // Only scroll to bottom for user messages or when no agent message exists
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role === 'user') {
      scrollToBottom();
    } else {
      // For agent messages, scroll to the top of the message
      setTimeout(() => scrollToLastAssistantMessage(), 100); // Small delay to ensure DOM update
    }
  }, [messages]);

  // Scroll to agent message when streaming content changes
  useEffect(() => {
    if (isStreamingActive && streamingContent) {
      setTimeout(() => scrollToLastAssistantMessage(), 100);
    }
  }, [isStreamingActive, streamingContent]);

  // Load available agents and datasets on component mount
  useEffect(() => {
    loadAvailableAgents();
    // Dataset loading removed - datasets configured via agent settings
  }, []);

  // Handle agent selection from URL parameter
  useEffect(() => {
    const agentId = searchParams?.get('agent');
    if (agentId && availableAgents.length > 0) {
      // Verify the agent exists in available agents
      const agentExists = availableAgents.find(agent => agent.id === agentId);
      if (agentExists) {
        setSelectedAgent(agentId);
        console.log('🔗 Auto-selected agent from URL:', agentExists.name);
      }
    }
  }, [searchParams, availableAgents]);

  // Handle conversation selection from URL parameter
  useEffect(() => {
    const conversationId = searchParams?.get('conversation');
    if (conversationId && !currentConversationId && !isManualClearRef.current) {
      console.log('🔗 Auto-loading conversation from URL:', conversationId);
      handleSelectConversation(conversationId);
    }
    // Reset manual clear flag after URL change is processed
    if (!conversationId && isManualClearRef.current) {
      isManualClearRef.current = false;
    }
  }, [searchParams, currentConversationId]);

  // Update page title based on chat name
  useEffect(() => {
    document.title = `GT AI OS | Chat - ${chatName}`;
  }, [chatName]);

  // History search localStorage persistence - REMOVED (functionality disabled)

  // No auto-selection - require user to explicitly choose an agent

  // Listen for conversation selection from sidebar
  useEffect(() => {
    const handleLoadConversation = (event: CustomEvent) => {
      const { conversationId } = event.detail;
      if (conversationId) {
        handleSelectConversation(conversationId);
      }
    };

    window.addEventListener('loadConversation', handleLoadConversation as EventListener);
    return () => {
      window.removeEventListener('loadConversation', handleLoadConversation as EventListener);
    };
  }, []);

  const loadAvailableAgents = async () => {
    try {
      setAgentsLoading(true);
      
      const token = getAuthToken();
      if (!token) {
        console.error('No auth token found');
        setAgentsLoading(false);
        return;
      }

      const response = await agentService.listAgents();
      
      if (response.error) {
        throw new Error(`Failed to fetch agents: ${response.error}`);
      }

      // Handle the nested data structure from the API response
      let agents = [];
      if (response.data && response.data.data && Array.isArray(response.data.data)) {
        agents = response.data.data;
      } else if (response.data && Array.isArray(response.data)) {
        agents = response.data;
      }

      setAvailableAgents(agents);
    } catch (error) {
      console.error('Failed to load agents:', error);
      setAvailableAgents([]);
    } finally {
      setAgentsLoading(false);
    }
  };

  // Agent datasets configured via agent settings

  // Load agents only on mount - datasets load when agent is selected
  useEffect(() => {
    loadAvailableAgents();
    // Don't load datasets initially - wait for agent selection
  }, []);

  // Refetch agents when window regains focus (handles navigation back from agent creation)
  useEffect(() => {
    const handleFocus = () => {
      loadAvailableAgents();
    };

    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  // Scroll tracking for sticky buttons (optimized with RAF)
  useEffect(() => {
    let rafId: number | null = null;
    let isScheduled = false;

    const updateStickyButton = () => {
      let foundSticky = false;

      // Get header height
      const headerHeight = headerRef.current?.getBoundingClientRect().bottom || 0;

      messageRefs.current.forEach((element, messageId) => {
        if (!element) return;

        // Find the header element and message box within this message
        const headerElement = element.querySelector('.message-header');
        const messageBox = element.querySelector('.max-w-full');
        if (!headerElement || !messageBox) return;

        const headerRect = headerElement.getBoundingClientRect();
        const messageRect = element.getBoundingClientRect();
        const messageBoxRect = messageBox.getBoundingClientRect();
        const messageHeaderBottom = headerRect.bottom;
        const messageBottom = messageRect.bottom;

        // Message is sticky if message header bottom is above/at page header bottom but message is still visible
        if (messageHeaderBottom <= headerHeight && messageBottom > headerHeight && !foundSticky) {
          // Calculate right position to align with message box right edge (16px from edge)
          const buttonRightPosition = window.innerWidth - messageBoxRect.right + 16;
          // Calculate top position to match right spacing (16px from header bottom)
          const buttonTopPosition = headerHeight + 16;

          setStickyMessageId(messageId);
          setStickyButtonRight(buttonRightPosition);
          setStickyButtonTop(buttonTopPosition);
          foundSticky = true;
        }
      });

      if (!foundSticky) {
        setStickyMessageId(null);
      }

      isScheduled = false;
    };

    const handleScroll = () => {
      // Throttle with requestAnimationFrame
      if (!isScheduled) {
        isScheduled = true;
        rafId = requestAnimationFrame(updateStickyButton);
      }
    };

    // Use capture phase to catch scroll events from chat container
    window.addEventListener('scroll', handleScroll, true);
    // Also listen to resize to recalculate position
    window.addEventListener('resize', handleScroll);
    updateStickyButton(); // Initial check

    return () => {
      window.removeEventListener('scroll', handleScroll, true);
      window.removeEventListener('resize', handleScroll);
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
    };
  }, [messages]);

  // Dataset loading removed - agent datasets are handled on backend

  const createNewConversation = async (firstMessage: string) => {
    try {
      const token = getAuthToken();

      // agent_id is required according to the API, use first available agent if none selected
      const agentId = selectedAgent || (availableAgents.length > 0 ? availableAgents[0].id : null);

      if (!agentId) {
        throw new Error('No agent available for conversation');
      }

      // Build URL with required agent_id as query parameter
      const url = new URL('/api/v1/conversations', window.location.origin);
      url.searchParams.append('agent_id', agentId);
      // Don't pass title - let the backend generate "Conversation with {agent_name}" format

      console.log('🚀 Creating new conversation:', {
        url: url.toString(),
        agent_id: agentId
      });

      const response = await fetchWithAuth(url.toString(), {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      console.log('📡 Conversation creation response:', response.status, response.statusText);

      if (response.ok) {
        const conversationData = await response.json();
        console.log('✅ Conversation created successfully:', conversationData);
        setCurrentConversationId(conversationData.id);
        
        // Refresh the conversation list to show the new conversation
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent('refreshConversations'));
        }, 500);
        
        return conversationData.id;
      } else {
        const errorData = await response.text();
        console.error('❌ Failed to create conversation:', response.status, errorData);
      }
    } catch (error) {
      console.error('💥 Error creating conversation:', error);
    }
    return null;
  };

  const fetchLatestConversationId = async () => {
    try {
      const token = getAuthToken();

      const response = await fetchWithAuth('/api/v1/conversations?limit=1', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        const latestConversation = data.conversations?.[0];
        if (latestConversation) {
          setCurrentConversationId(latestConversation.id);
          setChatName(latestConversation.title || 'New Chat');
        }
      }
    } catch (error) {
      console.error('Error fetching latest conversation:', error);
    }
  };

  const saveMessageToConversation = async (message: ChatMessage, conversationId?: string) => {
    const targetConversationId = conversationId || currentConversationId;
    if (!targetConversationId) return;

    try {
      const token = getAuthToken();

      // Build request body with metadata for response time
      const messageData: any = {
        role: message.role,
        content: message.content,
        metadata: {}
      };

      // Add response time to metadata if available
      if (message.responseDuration !== undefined) {
        messageData.metadata.response_time_seconds = message.responseDuration;
      }

      // Add cost_breakdown for Compound model billing (pass-through pricing)
      if (message.costBreakdown) {
        messageData.metadata.cost_breakdown = message.costBreakdown;
      }

      // Add token tracking fields
      if (message.tokenCount !== undefined) {
        messageData.token_count = message.tokenCount;
      }
      if (message.modelUsed) {
        messageData.model_used = message.modelUsed;
      }
      if (message.finishReason) {
        messageData.finish_reason = message.finishReason;
      }

      // Send message content in request body (not URL) to support any message length
      const response = await fetchWithAuth(`/api/v1/conversations/${targetConversationId}/messages`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(messageData),
      });

      if (response.ok) {
        console.log('💾 Message saved to conversation', message.responseDuration ? `(${message.responseDuration.toFixed(1)}s)` : '');
      } else {
        const errorText = await response.text();
        console.error('❌ Failed to save message:', response.status, errorText);
      }
    } catch (error) {
      console.error('💥 Error saving message:', error);
    }
  };

  const refreshConversationTitle = async (conversationId: string) => {
    try {
      const token = getAuthToken();
      if (!token || !conversationId) return;

      const response = await fetchWithAuth(`/api/v1/conversations/${conversationId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const conversationData = await response.json();
        if (conversationData.title) {
          setChatName(conversationData.title);
          console.log('🔄 Refreshed conversation title:', conversationData.title);
          
          // Note: Sidebar refresh removed to prevent race condition with first message
          // The title update above is sufficient for the current chat display
        }
      }
    } catch (error) {
      console.error('Failed to refresh conversation title:', error);
    }
  };

  const updateConversationName = async (newName: string) => {
    if (!currentConversationId || !newName.trim()) return;

    try {
      const token = getAuthToken();

      // Build URL with title parameter (same as sidebar implementation)
      const url = new URL(`/api/v1/conversations/${currentConversationId}`, window.location.origin);
      url.searchParams.append('title', newName.trim());

      const response = await fetchWithAuth(url.toString(), {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setChatName(newName.trim());
        // Refresh the conversation list to show updated name
        window.dispatchEvent(new CustomEvent('refreshConversations'));
      }
    } catch (error) {
      console.error('Error updating conversation name:', error);
    }
  };

  const handleSelectConversation = async (conversationId: string) => {
    try {
      // Set conversation ID immediately to trigger file loading via useEffect
      setCurrentConversationId(conversationId);

      // Update URL with conversation parameter
      router.push(`/chat?conversation=${conversationId}`);

      const token = getAuthToken();

      // PERFORMANCE OPTIMIZATION: Load messages and conversation details in parallel
      // This reduces total loading time by ~40% compared to sequential loading
      const [messagesResponse, conversationResponse] = await Promise.all([
        fetchWithAuth(`/api/v1/conversations/${conversationId}/messages`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        }),
        fetchWithAuth(`/api/v1/conversations/${conversationId}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        }).catch(err => {
          console.error('Failed to load conversation details:', err);
          return null; // Return null instead of throwing to allow messages to load
        })
      ]);

      // Process messages
      if (!messagesResponse.ok) {
        throw new Error('Failed to load conversation messages');
      }

      const messagesData = await messagesResponse.json();

      // Transform API messages to ChatMessage format
      const transformedMessages: ChatMessage[] = messagesData.map((msg: any, index: number) => {
        const responseDuration = msg.metadata?.response_time_seconds;
        console.log('📥 Loading message:', {
          role: msg.role,
          hasMetadata: !!msg.metadata,
          metadata: msg.metadata,
          responseDuration
        });

        return {
          id: index + 1,
          role: msg.role as 'user' | 'agent',
          content: msg.content,
          timestamp: new Date(msg.created_at),
          // Load response time from metadata field
          responseDuration
        };
      });

      setMessages(transformedMessages);

      // Process conversation details (if successfully loaded)
      if (conversationResponse && conversationResponse.ok) {
        const conversationData = await conversationResponse.json();
        setChatName(conversationData.title || 'Untitled Chat');
        if (conversationData.agent_id) {
          setSelectedAgent(conversationData.agent_id);
        }
      }

    } catch (error) {
      console.error('Error loading conversation:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!messageInput.trim() || isStreaming || isStreamingActive) return;

    // Validate that an agent is selected before sending message
    if (!selectedAgent) {
      alert('Please select an agent before sending a message.');
      return;
    }

    const newUserMessage: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: messageInput,
      timestamp: new Date()
    };

    // Check if this is the first message BEFORE adding to messages array
    const isFirstMessage = !currentConversationId && messages.length === 0;
    
    setMessages(prev => [...prev, newUserMessage]);
    const userMessage = messageInput;
    setMessageInput('');
    setIsStreaming(true);
    setIsStreamingActive(true);
    setStreamingContent('');

    // Start response timer
    const startTime = Date.now();
    setResponseStartTime(startTime);
    setElapsedTime(0);

    try {
      // Create conversation if this is the first message
      console.log('💬 Sending message. Current conversation ID:', currentConversationId, 'Messages count:', messages.length);
      
      let activeConversationId = currentConversationId;
      
      if (isFirstMessage) {
        console.log('🆕 This is the first message, creating new conversation...');
        activeConversationId = await createNewConversation(userMessage);
        if (!activeConversationId) {
          throw new Error('Failed to create conversation');
        }
        console.log('🎉 New conversation created with ID:', activeConversationId);
      }

      // Note: User message will be saved AFTER LLM response with prompt token count

      // Get auth token using the auth service
      const token = getAuthToken();
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Prepare messages for streaming API call
      const apiMessages: StreamingChatMessage[] = [...messages, newUserMessage].map(msg => ({
        role: msg.role === 'agent' ? 'agent' : 'user',
        content: msg.content
      }));

      // Use the selected agent
      const agentId = selectedAgent || undefined;

      // Get the selected agent's model configuration - require it to be set
      const currentAgent = availableAgents.find(agent => agent.id === agentId);
      const modelToUse = currentAgent?.model;

      if (!modelToUse) {
        const errorMessage = agentId
          ? `Agent "${currentAgent?.name || agentId}" has no model configured. Please configure a model for this agent.`
          : 'No agent selected and no default model available. Please select an agent with a configured model.';

        setMessages(prev => [...prev, {
          role: 'agent',
          content: errorMessage,
          id: Date.now().toString(),
          timestamp: new Date()
        }]);
        setIsStreaming(false);
        return;
      }

      // ✅ Extract agent's configured settings with fallbacks
      const agentTemperature = currentAgent?.temperature ??
                              currentAgent?.model_parameters?.temperature ??
                              0.7;
      const agentMaxTokens = currentAgent?.max_tokens ??
                            currentAgent?.model_parameters?.max_tokens ??
                            8000;

      console.log('🌊 Starting streaming chat with:', {
        messageCount: apiMessages.length,
        agentId,
        agentModel: modelToUse,
        agentTemperature,
        agentMaxTokens,
        lastMessage: apiMessages[apiMessages.length - 1]?.content?.substring(0, 50),
        memoryEnabled: false, // History search disabled
        datasetCount: 0 // Dataset selection removed
      });

      // Set active streaming conversation ID for indicator isolation
      setActiveStreamingConversationId(activeConversationId);

      // Use streaming chat service
      await streamChat(apiMessages, {
        model: modelToUse,
        agentId,
        conversationId: activeConversationId || undefined,
        temperature: agentTemperature,  // ✅ Use agent's configured temperature
        maxTokens: agentMaxTokens,      // ✅ Use agent's configured max_tokens
        // RAG parameters - handled entirely on backend via agent configuration
        use_rag: true,  // Always enable RAG, backend will determine available datasets
        knowledge_search_enabled: true,  // Always enable knowledge search
        // dataset_ids removed - backend determines from agent config + conversation files
        rag_max_chunks: 5,
        rag_similarity_threshold: 0.7,
        // Memory control - DISABLED
        
        onContent: (content: string) => {
          console.log('🌊 Received streaming content:', content);
          setStreamingContent(prev => prev + content);
        },
        
        onComplete: async (fullContent: string, finishReason?: string, model?: string, usage?: TokenUsage) => {
          console.log('🌊 Stream completed. Full content length:', fullContent.length);
          console.log('🌊 Finish reason:', finishReason);
          console.log('🌊 Model used:', model);
          console.log('🌊 Token usage:', usage);

          // CRITICAL: Check if conversation has changed since message was sent
          if (conversationIdRef.current !== activeConversationId) {
            console.log('⚠️ Conversation switched during response. Saving to original conversation:', activeConversationId);

            // Save messages to CORRECT conversation (not current one)
            const updatedUserMessage: ChatMessage = {
              ...newUserMessage,
              tokenCount: usage?.prompt_tokens,
              modelUsed: model
            };

            const aiMessage: ChatMessage = {
              id: Date.now() + 1,
              role: 'agent',
              content: fullContent,
              timestamp: new Date(),
              agents: agentId ? availableAgents.filter(a => a.id === agentId) : undefined,
              truncated: finishReason === 'length',
              responseDuration: (Date.now() - startTime) / 1000,
              tokenCount: usage?.completion_tokens,
              modelUsed: model,
              finishReason: finishReason,
              costBreakdown: usage?.cost_breakdown  // Compound model billing data
            };

            // Save to original conversation only (don't render in current conversation)
            if (activeConversationId) {
              await saveMessageToConversation(updatedUserMessage, activeConversationId);
              await saveMessageToConversation(aiMessage, activeConversationId);
              console.log('✅ Messages saved to original conversation');
            }

            // Cleanup streaming state
            setStreamingContent('');
            setIsStreamingActive(false);
            setIsStreaming(false);
            setActiveStreamingConversationId(null);
            setResponseStartTime(null);
            setElapsedTime(0);

            // Don't add to UI state - user has switched conversations
            return;
          }

          // ✅ Warn if truncated
          if (finishReason === 'length') {
            console.warn('⚠️ Response truncated due to max_tokens limit');
          }

          // Calculate final response duration
          const endTime = Date.now();
          const duration = (endTime - startTime) / 1000; // Convert to seconds

          // IMMEDIATE cleanup - remove green streaming indicator first
          setStreamingContent('');
          setIsStreamingActive(false);
          setIsStreaming(false);
          setActiveStreamingConversationId(null);
          setResponseStartTime(null);
          setElapsedTime(0);

          // Update user message with prompt tokens (includes user message + system prompt + RAG + history)
          const updatedUserMessage: ChatMessage = {
            ...newUserMessage,
            tokenCount: usage?.prompt_tokens,  // ✅ Prompt tokens (input to LLM)
            modelUsed: model  // ✅ Model used for the request
          };

          // Add the complete AI response to messages
          const aiMessage: ChatMessage = {
            id: Date.now() + 1,
            role: 'agent',
            content: fullContent,
            timestamp: new Date(),
            agents: agentId ? availableAgents.filter(a => a.id === agentId) : undefined,
            truncated: finishReason === 'length',  // ✅ Flag truncated messages
            responseDuration: duration,  // ✅ Store response duration
            tokenCount: usage?.completion_tokens,  // ✅ Completion tokens (AI response only)
            modelUsed: model,  // ✅ Store model used
            finishReason: finishReason,  // ✅ Store finish reason
            costBreakdown: usage?.cost_breakdown  // ✅ Compound model billing data
          };

          // Add AI message to UI state (after streaming cleanup)
          setMessages(prev => {
            const updatedMessages = [...prev, aiMessage];

            // Check if this is the first AI response (after adding AI message, we should have exactly 2 messages)
            console.log(`🔄 Checking title refresh condition: activeConversationId=${activeConversationId}, updatedMessages.length=${updatedMessages.length}`);

            if (activeConversationId && updatedMessages.length === 2) {
              console.log('🔄 Refreshing conversation title after first response...');
              setTimeout(() => {
                refreshConversationTitle(activeConversationId);
              }, 1000); // Small delay to allow backend title generation to complete
            } else {
              console.log('🔄 Skipping title refresh - not first response or no conversation ID');
            }

            return updatedMessages;
          });

          // Save BOTH messages to conversation with proper token attribution
          if (activeConversationId) {
            // Save user message with prompt tokens
            await saveMessageToConversation(updatedUserMessage, activeConversationId);
            // Save AI message with completion tokens
            await saveMessageToConversation(aiMessage, activeConversationId);
          }

          // Chat completion and message saving complete
        },
        
        onError: (error: Error) => {
          console.error('🌊 Streaming error:', error);

          // Don't show error message for session expiration - logout handles redirect
          if (error.message === 'SESSION_EXPIRED') {
            console.log('Chat: Session expired, logout triggered');
            // Clean up streaming state
            setStreamingContent('');
            setIsStreamingActive(false);
            setIsStreaming(false);
            setActiveStreamingConversationId(null);
            setResponseStartTime(null);
            setElapsedTime(0);
            return; // Don't add error message, user will be redirected
          }

          // Handle budget exceeded error (Issue #234)
          if (error.message === 'BUDGET_EXCEEDED') {
            const detail = (error as any).detail || 'Monthly budget limit reached. Contact your administrator.';
            const errorMessage: ChatMessage = {
              id: Date.now() + 1,
              role: 'agent',
              content: `**Budget Limit Reached**\n\nYour organization has reached its monthly usage budget. Chat functionality is temporarily disabled until the budget is reset or increased.\n\n${detail}\n\nPlease contact your administrator for assistance.`,
              timestamp: new Date()
            };

            setMessages(prev => [...prev, errorMessage]);
            setStreamingContent('');
            setIsStreamingActive(false);
            setIsStreaming(false);
            setActiveStreamingConversationId(null);
            setResponseStartTime(null);
            setElapsedTime(0);
            return;
          }

          // Add error message for other errors
          const errorMessage: ChatMessage = {
            id: Date.now() + 1,
            role: 'agent',
            content: `Sorry, I encountered an error: ${error.message}`,
            timestamp: new Date()
          };

          setMessages(prev => [...prev, errorMessage]);
          setStreamingContent('');
          setIsStreamingActive(false);
          setIsStreaming(false);
          setActiveStreamingConversationId(null);
          setResponseStartTime(null);
          setElapsedTime(0);
        }
      });

    } catch (error) {
      console.error('Chat setup error:', error);

      // Add error message for setup failures
      const errorMessage: ChatMessage = {
        id: Date.now() + 1,
        role: 'agent',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date()
      };

      setMessages(prev => [...prev, errorMessage]);
      setStreamingContent('');
      setIsStreamingActive(false);
      setIsStreaming(false);
      setActiveStreamingConversationId(null);
      setResponseStartTime(null);
      setElapsedTime(0);
    }
  };
  // Dataset filtering removed - datasets managed via agent configuration

  return (
    <AppLayout>
      <div className="h-full flex flex-col bg-gt-white">
        {/* Header */}
        <div className="w-full px-6 py-4">
          <div className="bg-gt-white rounded-lg shadow-sm border p-6" ref={headerRef}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageCircle className="w-8 h-8 text-gt-green" />
                <div className="flex items-center gap-4">
                  <h1 className="text-2xl font-bold text-gray-900">GT Chat</h1>
                  {/* Editable Chat Name */}
                  <div className="flex items-center">
                    {isEditingChatName ? (
                      <input
                        type="text"
                        value={chatName}
                        onChange={(e) => setChatName(e.target.value)}
                        onBlur={() => {
                          setIsEditingChatName(false);
                          updateConversationName(chatName);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            setIsEditingChatName(false);
                            updateConversationName(chatName);
                          }
                        }}
                        className="px-3 py-1 text-sm border border-gt-gray-300 rounded-md bg-gt-white text-gray-900 focus:outline-none focus:ring-1 focus:ring-gt-green focus:border-gt-green w-32 sm:w-auto"
                        autoFocus
                      />
                    ) : (
                      <div
                        onClick={() => setIsEditingChatName(true)}
                        className="px-3 py-1 text-sm bg-gt-gray-50 border border-gt-gray-200 rounded-md cursor-pointer hover:bg-gt-gray-100 text-gray-700 break-words whitespace-normal flex-shrink min-w-0"
                        title={chatName}
                      >
                        {chatName}
                      </div>
                    )}
                  </div>
                </div>

                {/* Selected Agent, Datasets & Memory Display in Header */}
                {selectedAgent && (
                  <div className="flex items-center gap-1 sm:gap-2">
                    {/* Selected Agent */}
                    {selectedAgent && (
                      <div className="flex items-center gap-1 px-1 sm:px-2 py-1 bg-blue-50 border border-blue-200 rounded-md group">
                        <Bot className="w-3 h-3 flex-shrink-0" />
                        <span className="text-xs text-gt-gray-600 flex-shrink-0 hidden lg:inline">Agent:</span>
                        {(() => {
                          const agent = selectedAgentData;
                          return agent ? (
                            <span className="text-xs font-medium text-blue-700 hidden lg:inline min-w-0 truncate" title={agent.name}>{agent.name}</span>
                          ) : null;
                        })()}
                      </div>
                    )}

                    {/* Dataset status removed - datasets configured via agent settings */}

                    {/* Memory Status Display - REMOVED (no longer relevant) */}
                  </div>
                )}
              </div>
              
              <div className="flex items-center gap-3">
                {/* New Chat Button */}
                <Button
                  onClick={() => {
                    // Set flag to prevent URL-based reload
                    isManualClearRef.current = true;

                    // Keep the selected agent for new chat
                    const currentAgent = selectedAgent;

                    setMessages([]);
                    setVisibleMessageCount(50); // Reset pagination
                    // Keep the selected agent - don't clear it
                    setMessageInput('');
                    setChatName('New Chat');
                    setCurrentConversationId(null);
                    setConversationFiles([]);
                    // Clear file input to allow re-uploading same file
                    if (fileInputRef.current) {
                      fileInputRef.current.value = '';
                    }
                    setStreamingContent('');
                    setIsStreamingActive(false);
                    setIsStreaming(false);
                    setActiveStreamingConversationId(null);

                    // Update URL: remove conversation, add agent if present
                    if (currentAgent) {
                      router.push(`/chat?agent=${currentAgent}`);
                    } else {
                      router.push('/chat');
                    }
                  }}
                  className="bg-gt-green hover:bg-gt-green/90 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  New Chat
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Agentic Activity Panels */}
        <div className="px-6 space-y-4">
          {/* Subagent Activity Panel */}
          {subagentActivity.length > 0 && (
            <SubagentActivityPanel
              subagents={subagentActivity}
              orchestrationStrategy={orchestrationStrategy}
              className="w-full"
            />
          )}

          {/* Tool Execution Panel */}
          {activeTools.length > 0 && (
            <ToolExecutionPanel
              tools={activeTools}
              className="w-full"
            />
          )}
        </div>

        {/* Messages Area - Centered layout for empty state */}
        <div className="flex-1 overflow-y-auto bg-gt-white flex flex-col min-h-0">
            {messages.length === 0 ? (
              /* Empty State - Centered */
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  {!selectedAgent ? (
                    /* No Agent Selected */
                    <div className="max-w-md space-y-4">
                      <div className="w-16 h-16 mx-auto rounded-full bg-orange-100 flex items-center justify-center">
                        <Bot className="w-8 h-8 text-orange-500" />
                      </div>
                      <div>
                        <h3 className="text-lg font-medium text-gt-gray-900 mb-2">Select an Agent to Start</h3>
                        <p className="text-gt-gray-600 mb-4">
                          Choose an agent from the bot icon below to begin your conversation.
                          Each agent has different capabilities and knowledge.
                        </p>
                        <Link href="/agents">
                          <Button
                            className="bg-gt-green hover:bg-gt-green/90"
                          >
                            <Bot className="w-4 h-4 mr-2" />
                            Go to Agents Page
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ) : (
                    /* Agent Selected but No Messages */
                    <div className="max-w-2xl w-full space-y-6">
                      <div className="w-16 h-16 mx-auto rounded-full bg-gt-green/10 flex items-center justify-center">
                        <Bot className="w-8 h-8 text-gt-green" />
                      </div>
                      <div className="text-center">
                        <h3 className="text-lg font-medium text-gt-gray-900 mb-2">
                          {selectedAgentData?.name || 'Agent'}
                        </h3>
                        {selectedAgentData?.description && (
                          <p className="text-gt-gray-600">
                            {selectedAgentData?.description}
                          </p>
                        )}
                      </div>

                      {/* Easy Buttons */}
                      {(() => {
                        const currentAgent = selectedAgentData;
                        return currentAgent?.easy_prompts && currentAgent.easy_prompts.length > 0 ? (
                          <div className="space-y-2">
                            <div className="flex items-center gap-2 justify-center">
                              <Sparkles className={cn("w-4 h-4", isBudgetExceeded ? "text-gray-300" : "text-gray-500")} />
                              <span className={cn("text-sm font-medium", isBudgetExceeded ? "text-gray-400" : "text-gray-700")}>
                                {isBudgetExceeded ? "Easy Buttons (Budget Exceeded)" : "Easy Buttons"}
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-2 justify-center">
                              {currentAgent.easy_prompts.map((prompt, index) => (
                                <TooltipProvider key={index} delayDuration={0}>
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <span>
                                        <Button
                                          variant="secondary"
                                          size="sm"
                                          onClick={() => {
                                            if (!isBudgetExceeded) {
                                              setMessageInput(prompt);
                                              setTimeout(() => textareaRef.current?.focus(), 0);
                                            }
                                          }}
                                          disabled={isBudgetExceeded}
                                          className={cn(
                                            "text-sm rounded-full border transition-colors",
                                            isBudgetExceeded
                                              ? "bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed"
                                              : "bg-gt-white border-gt-gray-300 text-gt-gray-700 hover:bg-gt-green/10 hover:border-gt-green hover:text-gt-green"
                                          )}
                                        >
                                          {prompt}
                                        </Button>
                                      </span>
                                    </TooltipTrigger>
                                    {isBudgetExceeded && (
                                      <TooltipContent side="top" sideOffset={8} className="bg-gt-white text-gt-gray-900 border-gt-gray-200">
                                        <p className="text-sm">Chat disabled - budget exceeded</p>
                                      </TooltipContent>
                                    )}
                                  </Tooltip>
                                </TooltipProvider>
                              ))}
                            </div>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* Messages */
              <div className="flex-1 flex items-center justify-center">
                <div className="w-full max-w-none xl:max-w-6xl 2xl:max-w-7xl px-4 pt-2 pb-8 space-y-6 overflow-hidden">
                {/* Load More Button - Only show if there are hidden messages */}
                {messages.length > visibleMessageCount && (
                  <div className="flex justify-center pb-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setVisibleMessageCount(prev => Math.min(prev + MESSAGE_INCREMENT, messages.length))}
                      className="shadow-sm"
                    >
                      <ChevronUp className="w-4 h-4 mr-2" />
                      Load {Math.min(MESSAGE_INCREMENT, messages.length - visibleMessageCount)} earlier messages
                    </Button>
                  </div>
                )}
                {messages.slice(-visibleMessageCount).map((message, index) => (
                  <div key={message.id} className="group">
                    {message.role === 'user' ? (
                      <div className="flex gap-4 justify-end">
                        <div className="max-w-lg md:max-w-xl lg:max-w-2xl xl:max-w-3xl bg-gt-gray-50 rounded-2xl px-4 py-3 border relative group">
                          <p className="text-gt-gray-900 whitespace-pre-wrap pr-8">{message.content}</p>
                          <button
                            onClick={() => copyMessage(message.id, message.content)}
                            className="absolute top-2 right-2 !opacity-100 p-1 bg-gt-white hover:bg-gray-100 rounded text-gray-500 hover:text-gray-700 transition-all shadow-sm"
                            title="Copy message"
                          >
                            {copiedMessages.has(message.id) ? (
                              <Check className="w-3 h-3" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                        <div className="w-8 h-8 rounded-full bg-gt-green flex items-center justify-center flex-shrink-0">
                          <span className="text-white text-sm font-medium">U</span>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="flex gap-4"
                        ref={(el) => {
                          if (index === messages.length - 1) {
                            lastAssistantMessageRef.current = el;
                          }
                          if (el) {
                            messageRefs.current.set(message.id, el);
                          } else {
                            messageRefs.current.delete(message.id);
                          }
                        }}
                      >
                        <div className="w-8 h-8 rounded-full bg-gt-gray-100 flex items-center justify-center flex-shrink-0">
                          <Bot className="w-4 h-4 text-gt-green" />
                        </div>
                        <div className="flex-1 min-w-0 max-w-full overflow-hidden">
                          <div className="max-w-full bg-gt-gray-50 rounded-2xl px-4 py-3 border relative group">
                            {/* Agent name header with copy button */}
                            <div className="flex items-center justify-between mb-2 message-header">
                              <div className="text-xs text-gt-gray-500 font-medium flex items-center gap-1">
                                <span>
                                  {message.agents && message.agents.length > 0
                                    ? message.agents[0].name
                                    : selectedAgent
                                      ? selectedAgentData?.name || 'AI Assistant'
                                      : 'AI Assistant'
                                  }
                                </span>
                                {message.responseDuration && (
                                  <>
                                    <span className="text-gt-gray-400">•</span>
                                    <span className="text-gt-gray-400 font-mono">
                                      {formatResponseTime(message.responseDuration)}
                                    </span>
                                  </>
                                )}
                              </div>
                              <div className={cn(
                                "flex items-center gap-2 transition-all",
                                stickyMessageId === message.id && "fixed z-50"
                              )}
                              style={stickyMessageId === message.id ? {
                                top: `${stickyButtonTop}px`,
                                right: `${window.innerWidth - (messageRefs.current.get(message.id)?.querySelector('.max-w-full')?.getBoundingClientRect().right || 0) + 16}px`
                              } : undefined}
                              >
                                <button
                                  onClick={() => copyMessage(message.id, message.content)}
                                  className={cn(
                                    "flex items-center gap-1 px-2 py-1 bg-gt-white hover:bg-gray-100 rounded text-xs text-gray-600 hover:text-gray-800 transition-all shadow-sm",
                                    "!opacity-100"
                                  )}
                                  title="Copy message"
                                >
                                  {copiedMessages.has(message.id) ? (
                                    <>
                                      <Check className="w-3 h-3" />
                                      <span>Copied</span>
                                    </>
                                  ) : (
                                    <>
                                      <Copy className="w-3 h-3" />
                                      <span>Copy</span>
                                    </>
                                  )}
                                </button>
                                <div className="!opacity-100">
                                  <DownloadButton
                                    content={message.content}
                                    filename={`${chatName.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-${new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5)}`}
                                    title={`GT Chat Response - ${
                                      selectedAgent
                                        ? selectedAgentData?.name || 'AI Assistant'
                                        : 'AI Assistant'
                                    }`}
                                  />
                                </div>
                                <button
                                  onClick={() => handleReportHarmful(index)}
                                  className="flex items-center gap-1 px-2 py-1 bg-amber-50 hover:bg-amber-100 rounded text-xs text-amber-700 hover:text-amber-900 transition-all shadow-sm !opacity-100"
                                  title="Report chat issue"
                                >
                                  <Flag className="w-3 h-3" />
                                  <span>Report Chat Issue</span>
                                </button>
                              </div>
                            </div>
                            <MessageRenderer content={message.content} messageId={message.id} />

                            {/* ✅ Truncation Warning */}
                            {message.truncated && (
                              <div className="mt-3 flex items-start gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
                                <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                                <div className="text-sm text-amber-800">
                                  <p className="font-medium">Response truncated due to token limit</p>
                                  <p className="mt-1 text-xs">
                                    Increase <strong>LLM response token allocation</strong> in{' '}
                                    <Link
                                      href={`/agents?edit=${message.agents?.[0]?.id || selectedAgent}`}
                                      className="underline hover:text-amber-900"
                                    >
                                      agent settings
                                    </Link>
                                    {' '}for longer responses.
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {/* Typing/Streaming Indicator - Only show for active conversation */}
                {isStreamingActive && streamingContent && activeStreamingConversationId === currentConversationId ? (
                  <div ref={lastAssistantMessageRef}>
                    <StreamingIndicator
                      agentName={selectedAgent ? selectedAgentData?.name || 'AI Assistant' : 'AI Assistant'}
                      currentText={streamingContent}
                      elapsedTime={elapsedTime}
                    />
                  </div>
                ) : isStreaming && activeStreamingConversationId === currentConversationId && (
                  <div ref={lastAssistantMessageRef}>
                    <TypingIndicator
                      variant="typing"
                      agentName={selectedAgent ? selectedAgentData?.name || 'AI Assistant' : 'AI Assistant'}
                      elapsedTime={elapsedTime}
                    />
                  </div>
                )}
                
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}
        </div>

        {/* Chat Input Container - Positioned at bottom */}
        <div className="sticky bottom-0 w-full flex justify-center p-6 bg-gt-white">
          <div className="w-full max-w-3xl space-y-2">
            {/* Collapsible File Attachments Panel */}
            {conversationFiles.length > 0 && (
              <div className="bg-gt-white rounded-2xl border border-gt-gray-200 shadow-sm overflow-hidden">
                <button
                  onClick={() => setIsFilePanelExpanded(!isFilePanelExpanded)}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-gt-gray-50 transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    <Paperclip className="h-4 w-4 text-gt-green" />
                    <span className="text-sm font-medium">Attached Files ({conversationFiles.length})</span>
                    <span className="text-xs px-2 py-0.5 bg-gt-gray-200 text-gt-gray-600 rounded-full">
                      📎 Conversation-Only
                    </span>
                  </div>
                  {isFilePanelExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gt-gray-400" />
                  ) : (
                    <ChevronUp className="h-4 w-4 text-gt-gray-400" />
                  )}
                </button>

                {isFilePanelExpanded && (
                  <div className="px-4 pb-3 space-y-2 max-h-[280px] overflow-y-auto">
                    {conversationFiles.map((file) => {
                      const statusIcon = {
                        completed: '✅',
                        processing: '⚙️',
                        pending: '⏳',
                        failed: '❌'
                      }[file.processing_status] || '❓';

                      return (
                        <div key={file.id} className="flex items-start space-x-3 p-2 rounded-lg border border-gt-gray-200 bg-gt-gray-50 hover:bg-gt-white transition-colors">
                          <FileText className="h-4 w-4 mt-0.5 text-gt-gray-400" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center space-x-2">
                              <h4 className="text-sm font-medium truncate">{file.original_filename}</h4>
                              <span className="text-xs">{statusIcon}</span>
                            </div>
                            <p className="text-xs text-gt-gray-500 mt-0.5">
                              {formatBytes(file.file_size_bytes)} • {formatDateTime(file.uploaded_at)}
                            </p>
                          </div>
                          <button
                            onClick={() => handleRemoveFile(file.id)}
                            disabled={messages.length > 0}
                            className={messages.length > 0
                              ? "text-gt-gray-300 cursor-not-allowed"
                              : "text-gt-gray-400 hover:text-red-600 transition-colors"}
                            title={messages.length > 0
                              ? "Files cannot be deleted after conversation has started"
                              : "Remove file"}
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Processing Files Notification */}
            {conversationFiles.some(f => f.processing_status === 'pending' || f.processing_status === 'processing') && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 space-y-3">
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin"></div>
                  <span className="text-sm font-medium text-amber-800">
                    Processing {conversationFiles.filter(f => f.processing_status === 'pending' || f.processing_status === 'processing').length} file{conversationFiles.filter(f => f.processing_status === 'pending' || f.processing_status === 'processing').length !== 1 ? 's' : ''}...
                  </span>
                </div>
                <div className="space-y-1">
                  {conversationFiles
                    .filter(f => f.processing_status === 'pending' || f.processing_status === 'processing')
                    .map((file) => (
                      <div key={file.id} className="flex items-center space-x-2 text-xs text-amber-700">
                        <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></div>
                        <span>{file.original_filename}</span>
                        <span className="capitalize">({file.processing_status})</span>
                      </div>
                    ))}
                </div>
                <p className="text-xs text-amber-700">
                  Please wait for file processing to complete before sending messages.
                </p>
              </div>
            )}

            {/* Main Chat Input */}
            <div className="space-y-2">
              <div className="bg-gt-white rounded-2xl border border-gt-gray-200 shadow-sm p-2">
                <div className="flex items-center gap-2">
                {/* Left Action Buttons */}
                <div className="flex items-start gap-1">
                  {/* Agent Selection - Navigate to Agents Page */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      // Clear conversation state before returning to agents
                      setMessages([]);
                      setVisibleMessageCount(50); // Reset pagination
                      setCurrentConversationId(null);
                      setConversationFiles([]);
                      setStreamingContent('');
                      setIsStreamingActive(false);
                      setIsStreaming(false);
                      setActiveStreamingConversationId(null);
                      setChatName('New Chat');
                      setMessageInput('');
                      // Clear file input
                      if (fileInputRef.current) {
                        fileInputRef.current.value = '';
                      }
                      // Navigate to agents page
                      router.push('/agents');
                    }}
                    className={cn(
                      "w-9 h-9 p-0 transition-colors",
                      selectedAgent
                        ? "text-gt-green hover:text-gt-green hover:bg-gt-green/10"
                        : "text-orange-500 hover:text-orange-600 hover:bg-orange-50 animate-pulse"
                    )}
                    title={selectedAgent ? "Return to Agents page" : "Select an agent on the Agents page"}
                  >
                    <Bot className="w-4 h-4" />
                  </Button>

                  {/* Dataset selection removed - datasets configured via agent settings */}

                  {/* File Upload for Chat */}
                  <div className="relative">
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      accept=".pdf,.doc,.docx,.txt,.md,.json,.csv,.xml,.html,.rtf"
                      onChange={(e) => {
                        if (e.target.files) {
                          handleFileUpload(e.target.files);
                        }
                      }}
                      disabled={isBudgetExceeded}
                    />
                    <TooltipProvider delayDuration={0}>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className={cn(
                              "w-9 h-9 p-0",
                              (selectedAgentData?.model?.toLowerCase().includes('compound') || isBudgetExceeded)
                                ? "text-gt-gray-300 cursor-not-allowed"
                                : "text-gt-gray-600 hover:text-gt-blue hover:bg-gt-blue/10"
                            )}
                            onClick={() => fileInputRef.current?.click()}
                            disabled={isUploading || selectedAgentData?.model?.toLowerCase().includes('compound') || isBudgetExceeded}
                          >
                            {isUploading ? (
                              <div className="w-4 h-4 border-2 border-gt-gray-300 border-t-gt-blue rounded-full animate-spin" />
                            ) : (
                              <Paperclip className="w-4 h-4" />
                            )}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" sideOffset={8} className="bg-gt-white text-gt-gray-900 border-gt-gray-200">
                          <p className="text-sm">
                            {isBudgetExceeded
                              ? 'File uploads disabled - budget exceeded'
                              : 'Convert XLSX files to CSV before uploading for best results'}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>

                  {/* Memory Search Toggle - REMOVED (functionality disabled) */}

                </div>


                {/* Message Input */}
                <div className="flex-1 flex items-start">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="w-full relative group">
                          <textarea
                            ref={textareaRef}
                            value={messageInput}
                            onChange={(e) => setMessageInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSendMessage();
                              }
                            }}
                            placeholder={isBudgetExceeded ? "Chat disabled - budget exceeded" : selectedAgent ? "Message GT Chat..." : "Select an agent to start chatting..."}
                            disabled={!selectedAgent || isBudgetExceeded}
                            className={cn(
                              "w-full border border-gt-gray-300 rounded-md bg-transparent text-sm focus:outline-none py-2 px-3 mt-1 focus:border-gt-green focus:ring-1 focus:ring-gt-green",
                              isBudgetExceeded
                                ? "placeholder-gt-gray-400 cursor-not-allowed bg-gt-gray-50 text-gt-gray-400"
                                : selectedAgent
                                  ? "placeholder-gt-gray-500"
                                  : "placeholder-gt-gray-400 cursor-not-allowed"
                            )}
                            style={{
                              height: `${textareaHeight}px`,
                              resize: 'none', // Disable default resize
                              overflow: 'auto'
                            }}
                            rows={1}
                          />

                          {/* Resize handle - top right corner, positioned to avoid scrollbar */}
                          <div
                            className={cn(
                              "absolute top-0.5 w-6 h-6 cursor-nesw-resize flex items-start justify-end z-10 pt-0.5 pr-0 transition-all duration-150",
                              hasScrollbar ? "right-3" : "right-0",
                              isDragging ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                              isBudgetExceeded && "hidden"
                            )}
                            onMouseDown={handleDragStart}
                            title="Drag to resize"
                          >
                            <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 text-gt-gray-400 -rotate-90">
                              <path d="M2,14 L14,2 M7,14 L14,7 M12,14 L14,12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                            </svg>
                          </div>
                        </div>
                      </TooltipTrigger>
                      {isBudgetExceeded && (
                        <TooltipContent side="top" sideOffset={8} className="bg-gt-white text-gt-gray-900 border-gt-gray-200">
                          <p className="text-sm">Chat disabled - budget exceeded</p>
                        </TooltipContent>
                      )}
                    </Tooltip>
                  </TooltipProvider>
                </div>

                {/* Send Button */}
                <div className="flex items-start">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span>
                          <Button
                            onClick={handleSendMessage}
                            disabled={!selectedAgent || !messageInput.trim() || isStreaming || isBudgetExceeded || conversationFiles.some(f => f.processing_status === 'pending' || f.processing_status === 'processing')}
                            size="sm"
                            className="w-10 h-10 bg-gt-green hover:bg-gt-green/90 disabled:bg-gt-gray-300 rounded-md"
                          >
                            <ChevronUp className="w-5 h-5 text-white" />
                            <span className="sr-only">Send</span>
                          </Button>
                        </span>
                      </TooltipTrigger>
                      <TooltipContent side="top" sideOffset={8} className="bg-gt-white text-gt-gray-900 border-gt-gray-200">
                        <p className="text-sm">
                          {isBudgetExceeded
                            ? 'Chat disabled - budget exceeded'
                            : !selectedAgent
                              ? 'Select an agent first'
                              : 'Send message'}
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </div>
              </div>

              {/* Disclaimer below message input box */}
              {(() => {
                const currentAgent = selectedAgentData;
                return currentAgent?.disclaimer ? (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex gap-2">
                    <AlertCircle className="w-4 h-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-yellow-800">{currentAgent.disclaimer}</p>
                  </div>
                ) : null;
              })()}
            </div>
          </div>
        </div>

      </div>

      {/* Report Chat Issue Sheet */}
      {reportMessageData && (
        <ReportChatIssueSheet
          open={reportDialogOpen}
          onOpenChange={setReportDialogOpen}
          agentName={reportMessageData.agentName}
          timestamp={reportMessageData.timestamp}
          conversationName={reportMessageData.conversationName}
          userPrompt={reportMessageData.userPrompt}
          agentResponse={reportMessageData.agentResponse}
          model={reportMessageData.model}
          temperature={reportMessageData.temperature}
          maxTokens={reportMessageData.maxTokens}
          tenantUrl={reportMessageData.tenantUrl}
          tenantName={reportMessageData.tenantName}
          userEmail={reportMessageData.userEmail}
        />
      )}
    </AppLayout>
  );
}

export default function Page() {
  return (
    <AuthGuard requiredCapabilities={[GT2_CAPABILITIES.CONVERSATIONS_READ]}>
      <ChatPage />
    </AuthGuard>
  );
}