/**
 * GT 2.0 Conversation Service
 * 
 * API client for chat conversation management and WebSocket messaging.
 */

import { api } from './api';

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'agent' | 'system';
  content: string;
  metadata?: {
    context_sources?: string[];
    agent_id?: string;
    model?: string;
    token_count?: number;
    processing_time_ms?: number;
  };
  created_at: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  agent_id: string;
  title: string;
  model_id: string;
  message_count: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  last_message_at?: string;
}

export interface CreateConversationRequest {
  agent_id: string;
  title?: string;
}

export interface SendMessageRequest {
  content: string;
  context_sources?: string[];
  stream?: boolean;
}

export interface StreamingResponse {
  delta: string;
  done: boolean;
  metadata?: {
    model?: string;
    token_count?: number;
    processing_time_ms?: number;
  };
}

/**
 * List user's conversations
 */
export async function listConversations(params?: {
  agent_id?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.agent_id) searchParams.set('agent_id', params.agent_id);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return api.get<{
    conversations: Conversation[];
    total: number;
    limit: number;
    offset: number;
  }>(`/api/v1/conversations${query ? `?${query}` : ''}`);
}

/**
 * Create new conversation
 */
export async function createConversation(request: CreateConversationRequest) {
  return api.post<Conversation>('/api/v1/conversations', request);
}

/**
 * Get specific conversation
 */
export async function getConversation(conversationId: string, includeMessages: boolean = false) {
  const params = includeMessages ? '?include_messages=true' : '';
  return api.get<{
    conversation: Conversation;
    messages?: Message[];
  }>(`/api/v1/conversations/${conversationId}${params}`);
}

/**
 * Delete conversation
 */
export async function deleteConversation(conversationId: string) {
  return api.delete(`/api/v1/conversations/${conversationId}`);
}

/**
 * Archive/unarchive conversation
 */
export async function toggleConversationArchive(conversationId: string, isArchived: boolean) {
  return api.put<Conversation>(`/api/v1/conversations/${conversationId}`, {
    is_archived: isArchived
  });
}

/**
 * Update conversation title
 */
export async function updateConversationTitle(conversationId: string, title: string) {
  return api.put<Conversation>(`/api/v1/conversations/${conversationId}`, { title });
}

/**
 * Get conversation messages
 */
export async function getConversationMessages(
  conversationId: string,
  params?: {
    limit?: number;
    offset?: number;
  }
) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return api.get<{
    messages: Message[];
    total: number;
    limit: number;
    offset: number;
  }>(`/api/v1/conversations/${conversationId}/messages${query ? `?${query}` : ''}`);
}

/**
 * Send message to conversation (non-streaming)
 */
export async function sendMessage(conversationId: string, request: SendMessageRequest) {
  return api.post<Message>(`/api/v1/conversations/${conversationId}/messages`, {
    ...request,
    stream: false
  });
}

/**
 * WebSocket connection for real-time chat
 */
export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private conversationId: string;
  private onMessage: (message: StreamingResponse) => void;
  private onError: (error: string) => void;
  private onOpen: () => void;
  private onClose: () => void;

  constructor(
    conversationId: string,
    callbacks: {
      onMessage: (message: StreamingResponse) => void;
      onError: (error: string) => void;
      onOpen: () => void;
      onClose: () => void;
    }
  ) {
    this.conversationId = conversationId;
    this.onMessage = callbacks.onMessage;
    this.onError = callbacks.onError;
    this.onOpen = callbacks.onOpen;
    this.onClose = callbacks.onClose;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/chat/${this.conversationId}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.onOpen();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (error) {
        this.onError('Failed to parse WebSocket message');
      }
    };

    this.ws.onerror = () => {
      this.onError('WebSocket connection error');
    };

    this.ws.onclose = () => {
      this.onClose();
    };
  }

  sendMessage(request: SendMessageRequest) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'send_message',
        ...request,
        stream: true
      }));
    } else {
      this.onError('WebSocket not connected');
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

/**
 * Create WebSocket connection for conversation
 */
export function createChatWebSocket(
  conversationId: string,
  callbacks: {
    onMessage: (message: StreamingResponse) => void;
    onError: (error: string) => void;
    onOpen: () => void;
    onClose: () => void;
  }
): ChatWebSocket {
  return new ChatWebSocket(conversationId, callbacks);
}