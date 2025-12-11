/**
 * React Query hooks for Agent data fetching and mutations
 *
 * Provides centralized, cached agent data access with automatic
 * invalidation on mutations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentService, type EnhancedAgent } from '@/services';
import { getAuthToken } from '@/services/auth';

// Query key factory for consistent cache management
export const agentKeys = {
  all: ['agents'] as const,
  minimal: () => [...agentKeys.all, 'minimal'] as const,
  summary: () => [...agentKeys.all, 'summary'] as const,
  detail: (id: string) => [...agentKeys.all, 'detail', id] as const,
};

/**
 * Minimal agent data (id, name only) - for dropdowns and filters
 * Endpoint: GET /api/v1/agents/minimal
 */
export function useAgentsMinimal() {
  return useQuery({
    queryKey: agentKeys.minimal(),
    queryFn: async () => {
      const token = getAuthToken();
      if (!token) throw new Error('No authentication token');

      const response = await fetch('/api/v1/agents/minimal', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to load agents: ${response.status}`);
      }

      return response.json() as Promise<Array<{ id: string; name: string }>>;
    },
    staleTime: 60000, // 1 minute
  });
}

/**
 * Summary agent data (excludes heavy fields) - for gallery views
 * Endpoint: GET /api/v1/agents/summary
 */
export function useAgentsSummary() {
  return useQuery({
    queryKey: agentKeys.summary(),
    queryFn: async () => {
      const token = getAuthToken();
      if (!token) throw new Error('No authentication token');

      const response = await fetch('/api/v1/agents/summary', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to load agents: ${response.status}`);
      }

      const data = await response.json();

      // Handle nested response structure from backend
      if (data.data && Array.isArray(data.data)) {
        return data.data as EnhancedAgent[];
      }

      return data as EnhancedAgent[];
    },
    staleTime: 60000, // 1 minute
  });
}

/**
 * Full agent details (all fields) - for detail views and editing
 * Endpoint: GET /api/v1/agents/:id
 */
export function useAgentDetail(id: string | undefined) {
  return useQuery({
    queryKey: agentKeys.detail(id || ''),
    queryFn: async () => {
      if (!id) throw new Error('Agent ID is required');

      const token = getAuthToken();
      if (!token) throw new Error('No authentication token');

      const response = await fetch(`/api/v1/agents/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to load agent: ${response.status}`);
      }

      return response.json() as Promise<EnhancedAgent>;
    },
    enabled: !!id, // Only run query if ID is provided
    staleTime: 60000, // 1 minute
  });
}

/**
 * Create new agent mutation
 * Invalidates all agent queries on success
 */
export function useCreateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (agentData: any) => {
      const result = await agentService.createAgent(agentData);
      if (result.error) {
        throw new Error(result.error);
      }
      return result.data;
    },
    onSuccess: () => {
      // Invalidate all agent queries to trigger refetch
      queryClient.invalidateQueries({ queryKey: agentKeys.all });
    },
  });
}

/**
 * Update existing agent mutation
 * Invalidates all agent queries on success
 */
export function useUpdateAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: any }) => {
      const result = await agentService.updateAgent(id, data);
      if (result.error) {
        throw new Error(result.error);
      }
      return result.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate all agent queries
      queryClient.invalidateQueries({ queryKey: agentKeys.all });
      // Specifically invalidate the updated agent's detail query
      queryClient.invalidateQueries({ queryKey: agentKeys.detail(variables.id) });
    },
  });
}

/**
 * Delete (archive) agent mutation
 * Invalidates all agent queries on success
 */
export function useDeleteAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (agentId: string) => {
      const result = await agentService.deleteAgent(agentId);
      if (result.error) {
        throw new Error(result.error);
      }
      return result.data;
    },
    onSuccess: () => {
      // Invalidate all agent queries to remove deleted agent from lists
      queryClient.invalidateQueries({ queryKey: agentKeys.all });
    },
  });
}

/**
 * Fork (duplicate) agent mutation
 * Invalidates all agent queries on success
 */
export function useForkAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, newName }: { id: string; newName: string }) => {
      const result = await agentService.forkAgent(id, newName);
      if (result.error) {
        throw new Error(result.error);
      }
      return result.data;
    },
    onSuccess: () => {
      // Invalidate all agent queries to show new forked agent
      queryClient.invalidateQueries({ queryKey: agentKeys.all });
    },
  });
}
