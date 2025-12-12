import { create } from 'zustand';
import { io, Socket } from 'socket.io-client';
import {
  ChatState,
  Conversation,
  Message,
  WebSocketMessage,
  AgenticPhase,
  ToolExecution,
  SubagentExecution,
  SourceRetrieval
} from '@/types';
import { getApiUrl, getWebSocketUrl, handleApiError, generateConversationTitle } from '@/lib/utils';
import { getAuthHeaders } from './auth-store';

interface ChatActions {
  // Conversation management
  loadConversations: () => Promise<void>;
  createConversation: (title?: string, systemPrompt?: string) => Promise<Conversation | null>;
  selectConversation: (conversationId: number) => Promise<void>;
  deleteConversation: (conversationId: number) => Promise<boolean>;
  updateConversationTitle: (conversationId: number, title: string) => Promise<boolean>;
  markConversationAsRead: (conversationId: string) => Promise<void>;

  // Message management
  sendMessage: (content: string, context?: { contextSources?: string[]; historySearchEnabled?: boolean }, conversationId?: number) => Promise<void>;
  loadMessages: (conversationId: number) => Promise<void>;

  // WebSocket management
  connect: () => void;
  disconnect: () => void;

  // State management
  setTyping: (isTyping: boolean) => void;
  setExecutingTools: (isExecuting: boolean, toolName?: string) => void;
  clearError: () => void;
  reset: () => void;

  // Agentic state management
  setCurrentPhase: (phase: AgenticPhase) => void;
  updateToolExecution: (toolExecution: ToolExecution) => void;
  updateSubagentActivity: (subagent: SubagentExecution) => void;
  updateSourceRetrieval: (source: SourceRetrieval) => void;
  completePhase: (phase: AgenticPhase) => void;
  resetAgenticState: () => void;
}

type ChatStore = ChatState & ChatActions;

const API_URL = getApiUrl();
const WS_URL = getWebSocketUrl();

export const useChatStore = create<ChatStore>((set, get) => {
  let socket: Socket | null = null;

  return {
    // Initial state
    currentConversation: null,
    conversations: [],
    messages: [],
    isLoading: false,
    isTyping: false,
    isExecutingTools: false,
    currentTool: undefined,
    error: null,
    connected: false,

    // Unread tracking
    unreadCounts: {},

    // Agentic state
    currentPhase: 'idle',
    phaseStartTime: undefined,
    activeTools: [],
    subagentActivity: [],
    sourceRetrieval: [],
    taskComplexity: undefined,
    orchestrationStrategy: undefined,
    totalPhases: undefined,
    completedPhases: 0,

    // Actions
    loadConversations: async () => {
      set({ isLoading: true, error: null });

      try {
        const response = await fetch(`${API_URL}/api/v1/conversations`, {
          method: 'GET',
          headers: getAuthHeaders(),
        });

        if (!response.ok) {
          throw new Error('Failed to load conversations');
        }

        const conversationsData = await response.json();
        const conversations = conversationsData.conversations || conversationsData;

        // Extract unread counts from conversations
        const unreadCounts: Record<string, number> = {};
        if (Array.isArray(conversations)) {
          conversations.forEach((conv: any) => {
            if (conv.unread_count && conv.unread_count > 0) {
              unreadCounts[conv.id] = conv.unread_count;
            }
          });
        }

        set({
          conversations,
          unreadCounts,
          isLoading: false,
          error: null
        });
      } catch (error) {
        const errorMessage = handleApiError(error);
        set({ 
          isLoading: false, 
          error: errorMessage 
        });
      }
    },

    createConversation: async (title?: string, systemPrompt?: string): Promise<Conversation | null> => {
      set({ isLoading: true, error: null });

      try {
        const response = await fetch(`${API_URL}/api/v1/conversations`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            title: title || 'New Conversation',
            system_prompt: systemPrompt,
            model_id: 'groq:llama3-70b-8192', // Default model
          }),
        });

        if (!response.ok) {
          throw new Error('Failed to create conversation');
        }

        const conversation = await response.json();
        
        set((state) => ({
          conversations: [conversation, ...state.conversations],
          currentConversation: conversation,
          messages: [],
          isLoading: false,
          error: null,
        }));

        return conversation;
      } catch (error) {
        const errorMessage = handleApiError(error);
        set({ 
          isLoading: false, 
          error: errorMessage 
        });
        return null;
      }
    },

    selectConversation: async (conversationId: number) => {
      const state = get();
      const conversation = state.conversations.find(c => c.id === conversationId);
      
      if (!conversation) {
        set({ error: 'Conversation not found' });
        return;
      }

      set({ 
        currentConversation: conversation,
        messages: [], // Clear messages, will be loaded
        isLoading: true,
        error: null 
      });

      await get().loadMessages(conversationId);
    },

    deleteConversation: async (conversationId: number): Promise<boolean> => {
      try {
        const response = await fetch(`${API_URL}/api/v1/conversations/${conversationId}`, {
          method: 'DELETE',
          headers: getAuthHeaders(),
        });

        if (!response.ok) {
          throw new Error('Failed to delete conversation');
        }

        set((state) => {
          const updatedConversations = state.conversations.filter(c => c.id !== conversationId);
          const newCurrentConversation = state.currentConversation?.id === conversationId 
            ? null 
            : state.currentConversation;
          
          return {
            conversations: updatedConversations,
            currentConversation: newCurrentConversation,
            messages: newCurrentConversation ? state.messages : [],
          };
        });

        return true;
      } catch (error) {
        const errorMessage = handleApiError(error);
        set({ error: errorMessage });
        return false;
      }
    },

    updateConversationTitle: async (conversationId: number, title: string): Promise<boolean> => {
      try {
        const response = await fetch(`${API_URL}/api/v1/conversations/${conversationId}`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ title }),
        });

        if (!response.ok) {
          throw new Error('Failed to update conversation');
        }

        const updatedConversation = await response.json();

        set((state) => ({
          conversations: state.conversations.map(c => 
            c.id === conversationId ? updatedConversation : c
          ),
          currentConversation: state.currentConversation?.id === conversationId 
            ? updatedConversation 
            : state.currentConversation,
        }));

        return true;
      } catch (error) {
        const errorMessage = handleApiError(error);
        set({ error: errorMessage });
        return false;
      }
    },

    markConversationAsRead: async (conversationId: string) => {
      const state = get();

      // Early exit if already read
      if (!state.unreadCounts[conversationId]) return;

      // Optimistic update (instant UI feedback)
      set((state) => {
        const updated = { ...state.unreadCounts };
        delete updated[conversationId];
        return { unreadCounts: updated };
      });

      try {
        const response = await fetch(`${API_URL}/api/v1/chat/conversations/${conversationId}/mark-read`, {
          method: 'POST',
          headers: getAuthHeaders(),
        });

        if (!response.ok) {
          throw new Error('Failed to mark conversation as read');
        }
      } catch (error) {
        console.error('Mark as read failed:', error);

        // Check if conversation still exists before retrying
        try {
          const convResponse = await fetch(`${API_URL}/api/v1/conversations/${conversationId}`, {
            method: 'GET',
            headers: getAuthHeaders(),
          });

          if (convResponse.ok) {
            // Conversation exists, retry after 1 second
            setTimeout(() => {
              get().markConversationAsRead(conversationId);
            }, 1000);
          } else {
            console.log('Conversation deleted, skipping retry');
          }
        } catch {
          // Failed to check conversation existence, skip retry
          console.log('Failed to verify conversation, skipping retry');
        }
      }
    },

    loadMessages: async (conversationId: number) => {
      set({ isLoading: true, error: null });

      try {
        const response = await fetch(`${API_URL}/api/v1/conversations/${conversationId}/messages`, {
          method: 'GET',
          headers: getAuthHeaders(),
        });

        if (!response.ok) {
          throw new Error('Failed to load messages');
        }

        const messages = await response.json();
        set({ 
          messages, 
          isLoading: false,
          error: null 
        });
      } catch (error) {
        const errorMessage = handleApiError(error);
        set({ 
          isLoading: false, 
          error: errorMessage 
        });
      }
    },

    sendMessage: async (content: string, context?: { contextSources?: string[]; historySearchEnabled?: boolean }, conversationId?: number) => {
      const state = get();
      let targetConversation = state.currentConversation;

      // Create new conversation if none exists
      if (!targetConversation && !conversationId) {
        const title = generateConversationTitle(content);
        targetConversation = await get().createConversation(title);
        
        if (!targetConversation) {
          return; // Error already set by createConversation
        }
      }

      const finalConversationId = conversationId || targetConversation?.id;
      
      if (!finalConversationId) {
        set({ error: 'No conversation selected' });
        return;
      }

      // Reset agentic state for new conversation
      get().resetAgenticState();

      // Add user message optimistically
      const userMessage: Message = {
        id: Date.now(), // Temporary ID
        uuid: `temp-${Date.now()}`,
        conversation_id: finalConversationId,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };

      set((state) => ({
        messages: [...state.messages, userMessage],
        isTyping: true,
        currentPhase: 'thinking',
        phaseStartTime: new Date(),
        error: null,
      }));

      try {
        // Send via WebSocket if connected
        if (socket?.connected) {
          socket.emit('message', {
            conversation_id: finalConversationId,
            content,
            type: 'user_message',
            context_sources: context?.contextSources || [],
            history_search_enabled: context?.historySearchEnabled ?? true,
          });
        } else {
          // Fallback to HTTP API
          const response = await fetch(`${API_URL}/api/v1/conversations/${finalConversationId}/messages`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
              content,
              role: 'user',
              context_sources: context?.contextSources || [],
              history_search_enabled: context?.historySearchEnabled ?? true,
            }),
          });

          if (!response.ok) {
            throw new Error('Failed to send message');
          }

          // The response will come via WebSocket or we'll poll for it
        }
      } catch (error) {
        const errorMessage = handleApiError(error);
        
        // Remove the optimistic user message on error
        set((state) => ({
          messages: state.messages.filter(m => m.id !== userMessage.id),
          isTyping: false,
          error: errorMessage,
        }));
      }
    },

    connect: (queryClient?: any) => {
      if (socket?.connected) {
        return;
      }

      // Store queryClient for React Query cache invalidation
      const qc = queryClient;

      // Get authentication token for WebSocket connection
      const token = localStorage.getItem('gt2_token');

      if (!token) {
        console.error('❌ No authentication token found, cannot connect WebSocket');
        set({
          error: 'Authentication required for real-time updates',
          connected: false
        });
        return;
      }

      console.log('🔑 Connecting with authentication token:', token ? `${token.substring(0, 20)}...` : 'NULL');
      console.log('🔌 WebSocket URL:', WS_URL);

      socket = io(WS_URL, {
        path: '/socket.io',  // Explicitly specify path (matches Next.js rewrite rule)
        transports: ['websocket', 'polling'],
        timeout: 10000,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
        // Socket will auto-connect when created - no manual connect() needed
        auth: {
          token: token  // Pass JWT token for backend authentication
        }
      });

      // Add more detailed error handling
      socket.on('connect_error', (error) => {
        console.error('❌ Socket.IO connection error:', error);
        console.error('Error message:', error.message);
        console.error('Error type:', error.type);
        console.error('Error description:', error.description);
      });

      socket.on('connect', () => {
        console.log('WebSocket connected');
        set({ connected: true });
      });

      socket.on('disconnect', () => {
        console.log('WebSocket disconnected');
        set({ connected: false });
      });

      socket.on('message', (data: WebSocketMessage) => {
        const { type, data: messageData } = data;

        switch (type) {
          case 'message':
            if (messageData.role === 'agent') {
              set((state) => ({
                messages: [...state.messages, messageData],
                isTyping: false,
                currentPhase: 'completed',
              }));
            }
            break;

          case 'typing':
            set({ isTyping: messageData.is_typing });
            break;

          case 'error':
            set({
              error: messageData.message,
              isTyping: false,
              currentPhase: 'idle',
            });
            break;

          case 'phase_start':
          case 'phase_transition':
            if (data.phase) {
              set((state) => ({
                currentPhase: data.phase!,
                phaseStartTime: new Date(),
                isTyping: data.phase !== 'idle' && data.phase !== 'completed',
              }));
            }
            break;

          case 'tool_execution':
            if (data.toolExecution) {
              const { toolExecution } = data;
              set((state) => {
                const existingIndex = state.activeTools.findIndex(t => t.id === toolExecution.id);
                const updatedTools = existingIndex >= 0
                  ? state.activeTools.map((t, i) => i === existingIndex ? toolExecution : t)
                  : [...state.activeTools, toolExecution];

                return {
                  activeTools: updatedTools,
                  isExecutingTools: updatedTools.some(t => t.status === 'running'),
                  currentTool: toolExecution.status === 'running' ? toolExecution.name : state.currentTool,
                };
              });
            }
            break;

          case 'subagent_status':
            if (data.subagentStatus) {
              const { subagentStatus } = data;
              set((state) => {
                const existingIndex = state.subagentActivity.findIndex(s => s.id === subagentStatus.id);
                const updatedSubagents = existingIndex >= 0
                  ? state.subagentActivity.map((s, i) => i === existingIndex ? subagentStatus : s)
                  : [...state.subagentActivity, subagentStatus];

                return {
                  subagentActivity: updatedSubagents,
                };
              });
            }
            break;

          case 'source_retrieval':
            if (data.sourceRetrieval) {
              const { sourceRetrieval } = data;
              set((state) => {
                const existingIndex = state.sourceRetrieval.findIndex(s => s.id === sourceRetrieval.id);
                const updatedSources = existingIndex >= 0
                  ? state.sourceRetrieval.map((s, i) => i === existingIndex ? sourceRetrieval : s)
                  : [...state.sourceRetrieval, sourceRetrieval];

                return {
                  sourceRetrieval: updatedSources,
                };
              });
            }
            break;

          case 'phase_complete':
            if (data.phase) {
              set((state) => ({
                completedPhases: (state.completedPhases || 0) + 1,
              }));
            }
            break;
        }
      });

      // Unread message tracking and conversation list updates
      socket.on('conversation:message_added', (data: {
        conversation_id: string;
        sender_id: string;
        message_id: string;
        message_count?: number;
        last_message_at?: string;
        title?: string;
      }) => {
        console.log('🔔 Received conversation:message_added event:', data);
        const state = get();
        const currentUserId = localStorage.getItem('user_id');
        console.log('🔔 Current conversation ID:', state.currentConversation?.id);
        console.log('🔔 Current user ID:', currentUserId);
        console.log('🔔 Event conversation ID:', data.conversation_id);
        console.log('🔔 Event sender ID:', data.sender_id);

        // PART 1: ALWAYS update conversation list (regardless of viewing status)
        console.log('🔔 Updating conversation list...');
        set((state) => {
          const updatedConversations = state.conversations.map(conv => {
            if (conv.id?.toString() === data.conversation_id?.toString()) {
              console.log('🔔 Found matching conversation, updating:', conv.id);
              return {
                ...conv,
                message_count: data.message_count || (conv.message_count || 0) + 1,
                last_message_at: data.last_message_at || new Date().toISOString(),
                title: data.title || conv.title, // Update title if provided
              };
            }
            return conv;
          });

          // Sort conversations: unread/recent first
          updatedConversations.sort((a, b) => {
            const aTime = new Date(a.last_message_at || a.updated_at || a.created_at).getTime();
            const bTime = new Date(b.last_message_at || b.updated_at || b.created_at).getTime();
            return bTime - aTime;
          });

          return { conversations: updatedConversations };
        });

        // Invalidate React Query cache to trigger sidebar UI refresh
        if (qc) {
          console.log('🔄 Invalidating React Query conversations cache');
          qc.invalidateQueries({ queryKey: ['conversations', 'list'] });
        }

        // PART 2: Conditionally update unread counts
        // Only increment unread for AGENT/ASSISTANT messages when user is not viewing the conversation
        // We check the message role (agent/assistant) rather than sender_id because
        // agent messages may be saved with the user's ID when posted from the frontend
        const viewing = data.conversation_id?.toString() === state.currentConversation?.id?.toString();
        const isAgentMessage = data.role === 'agent' || data.role === 'assistant';

        console.log('💬 Unread check:', {
          conversationId: data.conversation_id,
          role: data.role,
          viewing,
          isAgentMessage,
          shouldIncrement: !viewing && isAgentMessage
        });

        // Only increment unread if user is NOT viewing AND it's an agent message
        if (viewing || !isAgentMessage) {
          console.log('🔔 Skipping unread increment (viewing conversation or not an agent message)');
          return;
        }

        console.log('🔔 Incrementing unread count for conversation:', data.conversation_id);
        // Increment unread for background conversation
        set((state) => ({
          unreadCounts: {
            ...state.unreadCounts,
            [data.conversation_id]: (state.unreadCounts[data.conversation_id] || 0) + 1
          }
        }));
      });

      // Listen for mark-as-read from other devices
      socket.on('conversation:read', (data: { conversation_id: string }) => {
        set((state) => {
          const updated = { ...state.unreadCounts };
          delete updated[data.conversation_id];
          return { unreadCounts: updated };
        });

        // Invalidate React Query cache to refresh sidebar
        if (qc) {
          console.log('🔄 Invalidating React Query cache after mark-as-read');
          qc.invalidateQueries({ queryKey: ['conversations', 'list'] });
        }
      });

      // Handle reconnection: refresh unread counts
      socket.on('reconnect', async () => {
        console.log('WebSocket reconnected, refreshing conversations');
        await get().loadConversations();
      });

      socket.on('error', (error) => {
        console.error('WebSocket error:', error);
        set({
          error: 'Connection error occurred',
          connected: false,
        });
      });

      // Socket auto-connects when created (no manual connect() needed)
    },

    disconnect: () => {
      if (socket) {
        socket.disconnect();
        socket = null;
      }
      set({ connected: false });
    },

    setTyping: (isTyping: boolean) => {
      set({ isTyping });
    },

    setExecutingTools: (isExecuting: boolean, toolName?: string) => {
      set({ isExecutingTools: isExecuting, currentTool: toolName });
    },

    clearError: () => {
      set({ error: null });
    },

    reset: () => {
      get().disconnect();
      set({
        currentConversation: null,
        conversations: [],
        messages: [],
        isLoading: false,
        isTyping: false,
        isExecutingTools: false,
        currentTool: undefined,
        error: null,
        connected: false,
        // Reset agentic state
        currentPhase: 'idle',
        phaseStartTime: undefined,
        activeTools: [],
        subagentActivity: [],
        sourceRetrieval: [],
        taskComplexity: undefined,
        orchestrationStrategy: undefined,
        totalPhases: undefined,
        completedPhases: 0,
      });
    },

    // Agentic state management actions
    setCurrentPhase: (phase: AgenticPhase) => {
      set((state) => ({
        currentPhase: phase,
        phaseStartTime: new Date(),
        isTyping: phase !== 'idle' && phase !== 'completed',
      }));
    },

    updateToolExecution: (toolExecution: ToolExecution) => {
      set((state) => {
        const existingIndex = state.activeTools.findIndex(t => t.id === toolExecution.id);
        const updatedTools = existingIndex >= 0
          ? state.activeTools.map((t, i) => i === existingIndex ? toolExecution : t)
          : [...state.activeTools, toolExecution];

        return {
          activeTools: updatedTools,
          isExecutingTools: updatedTools.some(t => t.status === 'running'),
          currentTool: toolExecution.status === 'running' ? toolExecution.name : state.currentTool,
        };
      });
    },

    updateSubagentActivity: (subagent: SubagentExecution) => {
      set((state) => {
        const existingIndex = state.subagentActivity.findIndex(s => s.id === subagent.id);
        const updatedSubagents = existingIndex >= 0
          ? state.subagentActivity.map((s, i) => i === existingIndex ? subagent : s)
          : [...state.subagentActivity, subagent];

        return {
          subagentActivity: updatedSubagents,
        };
      });
    },

    updateSourceRetrieval: (source: SourceRetrieval) => {
      set((state) => {
        const existingIndex = state.sourceRetrieval.findIndex(s => s.id === source.id);
        const updatedSources = existingIndex >= 0
          ? state.sourceRetrieval.map((s, i) => i === existingIndex ? source : s)
          : [...state.sourceRetrieval, source];

        return {
          sourceRetrieval: updatedSources,
        };
      });
    },

    completePhase: (phase: AgenticPhase) => {
      set((state) => ({
        completedPhases: (state.completedPhases || 0) + 1,
      }));
    },

    resetAgenticState: () => {
      set({
        currentPhase: 'idle',
        phaseStartTime: undefined,
        activeTools: [],
        subagentActivity: [],
        sourceRetrieval: [],
        taskComplexity: undefined,
        orchestrationStrategy: undefined,
        totalPhases: undefined,
        completedPhases: 0,
        isTyping: false,
        isExecutingTools: false,
        currentTool: undefined,
      });
    },
  };
});