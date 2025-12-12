/**
 * GT 2.0 Agent Service
 * 
 * API client for AI agent management with template support.
 */

import { api } from './api';

export interface Agent {
  agent_id: string;
  name: string;
  description: string;
  template_id: string;
  category: string;
  is_favorite: boolean;
  conversation_count: number;
  icon?: string;
  last_used_at?: Date;
  system_prompt?: string;
  instructions?: string;
  capabilities?: string[];
  disclaimer?: string;
  easy_prompts?: string[];
  created_at: string;
  updated_at: string;
}

export interface AgentTemplate {
  template_id: string;
  name: string;
  description: string;
  category: string;
  system_prompt: string;
  default_instructions: string;
  capabilities: string[];
  icon: string;
  tags: string[];
  use_cases: string[];
  example_conversations: string[];
}

export interface CreateAgentRequest {
  name: string;
  description?: string;
  template_id: string;
  instructions?: string;
  capabilities?: string[];
  is_favorite?: boolean;
}

export interface UpdateAgentRequest {
  name?: string;
  description?: string;
  instructions?: string;
  capabilities?: string[];
  is_favorite?: boolean;
}

/**
 * Get all available agent templates
 */
export async function getAgentTemplates() {
  return api.get<AssistantTemplate[]>('/api/v1/agents/templates');
}

/**
 * Get specific agent template
 */
export async function getAgentTemplate(templateId: string) {
  return api.get<AgentTemplate>(`/api/v1/agents/templates/${templateId}`);
}

/**
 * List user's agents
 */
export async function listAgents(params?: {
  category?: string;
  is_favorite?: boolean;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set('category', params.category);
  if (params?.is_favorite !== undefined) searchParams.set('is_favorite', params.is_favorite.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return api.get<Agent[]>(`/api/v1/agents${query ? `?${query}` : ''}`);
}

/**
 * Get specific agent
 */
export async function getAgent(agentId: string) {
  return api.get<Agent>(`/api/v1/agents/${agentId}`);
}

/**
 * Create new agent
 */
export async function createAgent(request: CreateAgentRequest) {
  return api.post<Agent>('/api/v1/agents', request);
}

/**
 * Update existing agent
 */
export async function updateAgent(agentId: string, request: UpdateAgentRequest) {
  return api.put<Agent>(`/api/v1/agents/${agentId}`, request);
}

/**
 * Delete agent
 */
export async function deleteAgent(agentId: string) {
  return api.delete(`/api/v1/agents/${agentId}`);
}

/**
 * Toggle favorite status
 */
export async function toggleFavorite(agentId: string, is_favorite: boolean) {
  return api.put<Agent>(`/api/v1/agents/${agentId}`, { is_favorite });
}

/**
 * Get agent usage statistics
 */
export async function getAgentStats(agentId: string) {
  return api.get<{
    conversation_count: number;
    total_messages: number;
    last_used_at: string;
    average_conversation_length: number;
    most_common_topics: string[];
  }>(`/api/v1/agents/${agentId}/stats`);
}

/**
 * Get agent categories for filtering
 */
export async function getAgentCategories() {
  const response = await getAssistantTemplates();
  if (response.data) {
    const categories = [...new Set(response.data.map(t => t.category))];
    return { data: categories, status: response.status };
  }
  return response;
}

/**
 * Bulk import result interface
 */
export interface BulkImportResult {
  success_count: number;
  error_count: number;
  total_rows: number;
  created_agents: Array<{
    id: string;
    name: string;
    original_name?: string;
  }>;
  errors: Array<{
    row_number: number;
    field: string;
    message: string;
  }>;
}

/**
 * Bulk import agents from CSV
 */
export async function bulkImportAgents(
  data: { file?: File; text?: string }
): Promise<BulkImportResult> {
  if (data.text) {
    // Send CSV text using fetch to properly handle the request
    const { getAuthToken, getTenantInfo, getUser } = await import('./auth');

    const token = getAuthToken();
    const tenantInfo = getTenantInfo();
    const user = getUser();

    const tenantDomain = tenantInfo?.domain || process.env.NEXT_PUBLIC_TENANT_DOMAIN || 'test-company';
    const userId = user?.email || user?.user_id || '';

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Tenant-Domain': tenantDomain,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (userId) {
      headers['X-User-ID'] = userId;
    }

    const response = await fetch('/api/v1/agents/bulk-import', {
      method: 'POST',
      headers,
      body: JSON.stringify({ csv_text: data.text })
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Import failed' }));
      throw new Error(error.detail || 'Import failed');
    }

    return response.json();
  } else if (data.file) {
    // For file upload, use fetch directly with FormData
    const { getAuthToken, getTenantInfo, getUser } = await import('./auth');

    const token = getAuthToken();
    const tenantInfo = getTenantInfo();
    const user = getUser();

    const tenantDomain = tenantInfo?.domain || process.env.NEXT_PUBLIC_TENANT_DOMAIN || 'test-company';
    const userId = user?.email || user?.user_id || '';

    const headers: Record<string, string> = {
      'X-Tenant-Domain': tenantDomain,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (userId) {
      headers['X-User-ID'] = userId;
    }

    const formData = new FormData();
    formData.append('csv_file', data.file);

    const response = await fetch('/api/v1/agents/bulk-import', {
      method: 'POST',
      headers,
      body: formData
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Import failed' }));
      throw new Error(error.detail || 'Import failed');
    }

    return response.json();
  } else {
    throw new Error('Either file or text must be provided');
  }
}

/**
 * Export agent configuration as CSV
 */
export async function exportAgent(agentId: string, format: 'download' | 'clipboard' = 'download'): Promise<string> {
  // Import auth functions
  const { getAuthToken, getTenantInfo, getUser } = await import('./auth');

  const token = getAuthToken();
  const tenantInfo = getTenantInfo();
  const user = getUser();

  const tenantDomain = tenantInfo?.domain || process.env.NEXT_PUBLIC_TENANT_DOMAIN || 'test-company';
  const userId = user?.email || user?.user_id || '';

  const headers: Record<string, string> = {
    'X-Tenant-Domain': tenantDomain,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (userId) {
    headers['X-User-ID'] = userId;
  }

  const response = await fetch(
    `/api/v1/agents/${agentId}/export?format=${format}`,
    {
      method: 'GET',
      headers
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || 'Export failed');
  }

  if (format === 'download') {
    // Trigger browser download
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = `agent_${agentId}.csv`;
    document.body.appendChild(a);
    a.click();

    // Cleanup
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);

    return 'Downloaded';
  } else {
    // Return CSV text for clipboard
    return response.text();
  }
}