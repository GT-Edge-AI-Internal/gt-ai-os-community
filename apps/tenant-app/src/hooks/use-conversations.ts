import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAuthToken } from '@/services/auth';

export interface Conversation {
  id: string;
  title: string;
  agent_id?: string;
  agent_name?: string;
  message_count: number;
  last_message_at: string;
  created_at: string;
}

interface ConversationsResponse {
  conversations: Conversation[];
  total: number;
}

export interface ConversationFilters {
  timeFilter?: 'all' | 'today' | 'week' | 'month';
  search?: string;
  agentId?: string;
}

export const conversationKeys = {
  all: ['conversations'] as const,
  list: (filters?: ConversationFilters) => [...conversationKeys.all, 'list', filters] as const,
  detail: (id: string) => [...conversationKeys.all, 'detail', id] as const,
};

const PAGE_SIZE = 20;

export function useConversations(filters?: ConversationFilters) {
  return useInfiniteQuery({
    queryKey: conversationKeys.list(filters),
    queryFn: async ({ pageParam = 0 }) => {
      const token = getAuthToken();
      if (!token) throw new Error('No authentication token');

      // Fetch conversations with pagination and server-side filtering
      const url = new URL('/api/v1/conversations', window.location.origin);
      url.searchParams.append('limit', PAGE_SIZE.toString());
      url.searchParams.append('offset', (pageParam * PAGE_SIZE).toString());

      // Add filters to query params
      if (filters?.timeFilter && filters.timeFilter !== 'all') {
        url.searchParams.append('time_filter', filters.timeFilter);
      }
      if (filters?.search) {
        url.searchParams.append('search', filters.search);
      }
      if (filters?.agentId) {
        url.searchParams.append('agent_id', filters.agentId);
      }

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to load conversations: ${response.status}`);
      }

      const data = await response.json();

      // Transform the data to match our interface
      const conversations: Conversation[] = data.conversations?.map((conv: any) => ({
        id: conv.id,
        title: conv.title || 'Untitled Conversation',
        agent_id: conv.agent_id,
        agent_name: conv.agent_name,
        message_count: conv.message_count || 0,
        last_message_at: conv.last_message_at || conv.created_at,
        created_at: conv.created_at
      })) || [];

      return {
        conversations,
        total: data.total || 0,
        nextPage: pageParam + 1
      };
    },
    getNextPageParam: (lastPage, allPages) => {
      const totalLoaded = allPages.reduce((sum, page) => sum + page.conversations.length, 0);
      return totalLoaded < lastPage.total ? lastPage.nextPage : undefined;
    },
    initialPageParam: 0,
    staleTime: 60000, // 60 seconds - keep cached data fresh
    gcTime: 300000, // 5 minutes - keep in cache even when unmounted
  });
}

export function useArchiveConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (conversationId: string) => {
      const token = getAuthToken();
      if (!token) throw new Error('No authentication token');

      const response = await fetch(`/api/v1/conversations/${conversationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to archive: ${response.status} ${errorText}`);
      }

      return conversationId;
    },
    onSuccess: () => {
      // Invalidate and refetch all conversation queries (all filter combinations)
      queryClient.invalidateQueries({ queryKey: conversationKeys.all });
    },
  });
}

export function useRenameConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ conversationId, title }: { conversationId: string; title: string }) => {
      const token = getAuthToken();
      if (!token) throw new Error('No authentication token');

      const url = new URL(`/api/v1/conversations/${conversationId}`, window.location.origin);
      url.searchParams.append('title', title.trim());

      const response = await fetch(url.toString(), {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to rename: ${response.status}`);
      }

      return { conversationId, title };
    },
    onSuccess: () => {
      // Invalidate and refetch all conversation queries to show updated title
      queryClient.invalidateQueries({ queryKey: conversationKeys.all });
    },
  });
}
