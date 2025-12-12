/**
 * GT 2.0 Streaming Chat Service
 * 
 * Handles Server-Sent Events (SSE) streaming from the chat API
 * for real-time AI response display.
 */

import { getAuthToken, getTenantInfo, isTokenValid } from './auth';

export interface StreamingChatMessage {
  role: 'user' | 'agent' | 'system';
  content: string;
  name?: string;
}

export interface StreamingChatRequest {
  model: string;
  messages: StreamingChatMessage[];
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  stop?: string | string[] | null;
  stream: boolean;
  agent_id?: string;
  conversation_id?: string;

  // Search Control Extensions
  knowledge_search_enabled?: boolean;

  // RAG Extensions
  use_rag?: boolean;
  dataset_ids?: string[];
  rag_max_chunks?: number;
  rag_similarity_threshold?: number;
}

export interface StreamingChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Array<{
    index: number;
    delta: {
      content?: string;
      role?: string;
    };
    finish_reason?: string | null;
  }>;
  conversation_id?: string;
  agent_id?: string;
}

export interface TokenUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  // Compound model billing - actual costs from Groq response
  cost_breakdown?: {
    models?: Array<{model_id: string; input_tokens: number; output_tokens: number; cost_dollars: number}>;
    tools?: Array<{tool_name: string; invocations: number; cost_dollars: number}>;
    total_cost_dollars?: number;
    total_cost_cents?: number;
  };
}

export type StreamingEventHandler = {
  onStart?: () => void;
  onChunk?: (chunk: StreamingChunk) => void;
  onContent?: (content: string) => void;
  onComplete?: (fullContent: string, finishReason?: string, model?: string, usage?: TokenUsage) => void;
  onError?: (error: Error) => void;
};

class ChatService {
  private baseURL: string;
  private abortControllers: Map<string, AbortController> = new Map();

  constructor() {
    // Use relative path for browser, will be proxied by Next.js to tenant-backend via Docker network
    this.baseURL = '';
  }

  private getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Check token validity first
    if (!isTokenValid()) {
      console.warn('ChatService: Token invalid/expired, triggering logout');
      // Trigger logout immediately before attempting request
      if (typeof window !== 'undefined') {
        import('@/stores/auth-store').then(({ useAuthStore }) => {
          useAuthStore.getState().logout('expired');
        });
      }
      return headers; // Return without auth header - request will fail with 401
    }

    const token = getAuthToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    // Add tenant context
    const tenantInfo = getTenantInfo();
    if (tenantInfo?.domain) {
      headers['X-Tenant-Domain'] = tenantInfo.domain;
    }

    return headers;
  }

  async streamChatCompletion(
    request: StreamingChatRequest,
    handlers: StreamingEventHandler
  ): Promise<void> {
    const conversationId = request.conversation_id || 'default';

    // Cancel any existing stream for this conversation
    const existingController = this.abortControllers.get(conversationId);
    if (existingController) {
      existingController.abort();
    }

    const controller = new AbortController();
    this.abortControllers.set(conversationId, controller);

    try {
      const headers = this.getAuthHeaders();
      const url = `${this.baseURL}/api/v1/chat/completions`;

      console.log('🌊 Starting streaming chat completion:', {
        url,
        model: request.model,
        messageCount: request.messages.length,
        agentId: request.agent_id
      });

      handlers.onStart?.();

      // Use non-streaming response for reliability
      const requestData = { ...request, stream: false };
      

      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestData),
        signal: controller.signal,
      });

      if (!response.ok) {
        // Handle 401 - session expired
        if (response.status === 401) {
          if (typeof window !== 'undefined') {
            const { useAuthStore } = await import('@/stores/auth-store');
            useAuthStore.getState().logout('expired');
          }
          throw new Error('SESSION_EXPIRED');
        }

        // Handle 402 - Budget exceeded (Issue #234)
        if (response.status === 402) {
          let detail = 'Monthly budget limit reached. Contact your administrator.';
          try {
            const errorData = await response.json();
            detail = errorData.detail || detail;
          } catch {
            // Use default message if JSON parsing fails
          }
          const budgetError = new Error('BUDGET_EXCEEDED');
          (budgetError as any).detail = detail;
          throw budgetError;
        }

        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      // Get the complete JSON response instead of streaming
      const result = await response.json();
      console.log('🌊 Received complete response:', result);

      // Extract content, finish_reason, model, and usage from the response
      const content = result.choices?.[0]?.message?.content || '';
      const finishReason = result.choices?.[0]?.finish_reason;
      const model = result.model;
      const usage: TokenUsage | undefined = result.usage ? {
        prompt_tokens: result.usage.prompt_tokens,
        completion_tokens: result.usage.completion_tokens,
        total_tokens: result.usage.total_tokens,
        // Include cost_breakdown for Compound models (pass-through billing)
        cost_breakdown: result.cost_breakdown
      } : undefined;

      console.log('🌊 Extracted content:', content);
      console.log('🌊 Finish reason:', finishReason);
      console.log('🌊 Model:', model);
      console.log('🌊 Token usage:', usage);

      // Handle non-streaming response
      if (content) {
        // Simulate the streaming behavior for UI compatibility
        handlers.onContent?.(content);
        console.log('🌊 Complete content delivered');
      }

      // Call completion handler with all metadata
      handlers.onComplete?.(content, finishReason, model, usage);
      console.log('🌊 Non-streaming chat completed');

    } catch (error) {
      console.error('🌊 Streaming error:', error);

      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          console.log('🌊 Stream aborted by user');
          return;
        }
        handlers.onError?.(error);
      } else {
        handlers.onError?.(new Error('Unknown streaming error'));
      }
    } finally {
      // Clean up the controller for this conversation
      this.abortControllers.delete(conversationId);
    }
  }

  /**
   * Cancel the streaming request for a specific conversation
   */
  cancelStream(conversationId?: string): void {
    if (conversationId) {
      const controller = this.abortControllers.get(conversationId);
      if (controller) {
        console.log(`🌊 Canceling stream for conversation: ${conversationId}`);
        controller.abort();
        this.abortControllers.delete(conversationId);
      }
    } else {
      // Cancel all streams if no conversation ID provided
      console.log('🌊 Canceling all streams...');
      this.abortControllers.forEach((controller) => controller.abort());
      this.abortControllers.clear();
    }
  }

  /**
   * Check if a stream is currently active for a specific conversation
   */
  isStreaming(conversationId?: string): boolean {
    if (conversationId) {
      return this.abortControllers.has(conversationId);
    }
    return this.abortControllers.size > 0;
  }
}

// Export singleton instance
export const chatService = new ChatService();

// Utility function for easy streaming
export async function streamChat(
  messages: StreamingChatMessage[],
  options: {
    model?: string;
    agentId?: string;
    conversationId?: string;
    temperature?: number;
    maxTokens?: number;
    use_rag?: boolean;
    dataset_ids?: string[];
    rag_max_chunks?: number;
    rag_similarity_threshold?: number;
    onContent?: (content: string) => void;
    onComplete?: (fullContent: string) => void;
    onError?: (error: Error) => void;
  } = {}
): Promise<void> {
  // Require model to be explicitly provided - no hardcoded fallback
  if (!options.model) {
    throw new Error('Model must be specified - no default model available');
  }

  // Auto-detect knowledge search enabled based on dataset presence
  const knowledgeSearchEnabled = options.use_rag && options.dataset_ids && options.dataset_ids.length > 0;

  const request: StreamingChatRequest = {
    model: options.model,
    messages,
    temperature: options.temperature || 0.7,
    max_tokens: options.maxTokens,
    stream: false,
    agent_id: options.agentId,
    conversation_id: options.conversationId,
    // Search Control Extensions
    knowledge_search_enabled: knowledgeSearchEnabled,
    // RAG Extensions
    use_rag: options.use_rag,
    dataset_ids: options.dataset_ids,
    rag_max_chunks: options.rag_max_chunks,
    rag_similarity_threshold: options.rag_similarity_threshold,
  };

  console.log('🔧 Chat service parameters:', {
    knowledge_search_enabled: request.knowledge_search_enabled,
    use_rag: request.use_rag,
    dataset_count: request.dataset_ids?.length || 0
  });


  const handlers: StreamingEventHandler = {
    onStart: () => console.log('🌊 Chat stream started'),
    onContent: options.onContent,
    onComplete: options.onComplete,
    onError: options.onError,
  };

  await chatService.streamChatCompletion(request, handlers);
}