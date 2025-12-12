/**
 * Enhanced Agent Service for GT 2.0
 * 
 * Comprehensive agent management with enterprise features, access control,
 * personality types, and advanced capabilities.
 */

import { api, ApiResponse } from './api';

// Core types
export type PersonalityType = 'geometric' | 'organic' | 'minimal' | 'technical';
export type Visibility = 'private' | 'team' | 'organization' | 'public';
export type DatasetConnection = 'none' | 'all' | 'selected';
// AgentCategory is now dynamic (loaded from API) - use string type
// Default categories: general, coding, writing, analysis, creative, research, business, education
// Custom categories can be created by users
export type AgentCategory = string;
export type AccessFilter = 'all' | 'mine' | 'team' | 'org' | 'public';

// Enhanced agent interface
export interface EnhancedAgent {
  id: string;
  team_id: string;
  name: string;
  description: string;
  disclaimer: string;
  category: AgentCategory;
  custom_category?: string;
  visibility: Visibility;
  featured: boolean;
  personality_type: PersonalityType;
  personality_profile: PersonalityProfile;
  custom_avatar_url?: string;
  model_id: string;
  system_prompt: string;
  model_parameters: ModelParameters;
  dataset_connection: DatasetConnection;
  selected_dataset_ids: string[];
  require_moderation: boolean;
  blocked_terms: string[];
  enabled_capabilities: string[];
  mcp_integration_ids: string[];
  tool_configurations: Record<string, any>;
  owner_id: string;
  owner_name?: string;  // Full name of the agent creator
  collaborator_ids: string[];
  can_fork: boolean;
  parent_agent_id?: string;
  version: number;
  usage_count: number;
  average_rating?: number;
  tags: string[];
  example_prompts: string[];
  easy_prompts?: string[] | null;  // Quick-access prompts (max 10)
  safety_flags: string[];
  created_at: string;
  updated_at: string;
  published_at?: string;
  last_used_at?: string;
  
  // Access indicators for UI
  is_owner: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_share: boolean;

  // Team sharing configuration
  team_shares?: Array<{
    team_id: string;
    team_name: string;
    user_permissions: Record<string, 'read' | 'edit'>;
  }>;
}

export interface PersonalityProfile {
  colors: {
    primary: string;
    secondary: string;
    accent: string;
    background: string;
  };
  animation: {
    style: string;
    duration: number;
    easing: string;
  };
  visual: {
    shapes: string[];
    patterns: string[];
    effects: string[];
  };
  interaction: {
    greeting_style: string;
    conversation_tone: string;
    response_style: string;
  };
}

export interface ModelParameters {
  max_history_items: number;
  max_chunks: number;
  // max_tokens removed - now determined by model configuration
  trim_ratio: number;
  temperature: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
}

export interface ExamplePrompt {
  text: string;
  category: string;
  expected_behavior?: string;
}

// Request/Response types
export interface CreateEnhancedAgentRequest {
  name: string;
  description?: string;
  category?: AgentCategory;
  custom_category?: string;
  visibility?: Visibility;
  personality_type?: PersonalityType;
  model_id?: string;
  system_prompt?: string;
  model_parameters?: Partial<ModelParameters>;
  dataset_connection?: DatasetConnection;
  selected_dataset_ids?: string[];
  require_moderation?: boolean;
  blocked_terms?: string[];
  enabled_capabilities?: string[];
  tags?: string[];
  example_prompts?: ExamplePrompt[];
  // Legacy fields removed - use team_shares instead for team collaboration
}

export interface UpdateEnhancedAgentRequest {
  name?: string;
  description?: string;
  category?: AgentCategory;
  visibility?: Visibility;
  personality_type?: PersonalityType;
  system_prompt?: string;
  model_parameters?: Partial<ModelParameters>;
  dataset_connection?: DatasetConnection;
  selected_dataset_ids?: string[];
  tags?: string[];
  example_prompts?: ExamplePrompt[];
  disclaimer?: string;
  easy_prompts?: string[];
  team_shares?: Array<{
    team_id: string;
    user_permissions: Record<string, 'read' | 'edit'>;
  }>;
}

export interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  category: AgentCategory;
  personality_type: PersonalityType;
  model_id: string;
  system_prompt: string;
  capabilities: string[];
  example_prompts: ExamplePrompt[];
  model_parameters: ModelParameters;
  tags: string[];
}

export interface ForkAgentRequest {
  new_name: string;
}

export interface CategoryInfo {
  value: string;
  label: string;
  description: string;
  count?: number;
}

// Enhanced Agent Service
export class EnhancedAgentService {

  /**
   * List agents with access control filtering
   */
  async listAgents(options: {
    access_filter?: AccessFilter;
    category?: string;
    search?: string;
    featured_only?: boolean;
    limit?: number;
    offset?: number;
    sort_by?: 'usage_count' | 'average_rating' | 'created_at' | 'recent_usage' | 'my_most_used';
    filter?: 'used_last_7_days' | 'used_last_30_days';
  } = {}): Promise<ApiResponse<EnhancedAgent[]>> {
    const params = new URLSearchParams();

    Object.entries(options).forEach(([key, value]) => {
      if (value !== undefined) {
        // Map sort_by to sort for backend compatibility
        const paramKey = key === 'sort_by' ? 'sort' : key;
        params.append(paramKey, value.toString());
      }
    });

    const query = params.toString();
    const endpoint = `/api/v1/agents${query ? `?${query}` : ''}`;

    return api.get<EnhancedAgent[]>(endpoint);
  }

  /**
   * Get specific agent with full details
   */
  async getAgent(agentId: string): Promise<ApiResponse<EnhancedAgent>> {
    return api.get<EnhancedAgent>(`/api/v1/agents/${agentId}`);
  }

  /**
   * Create new enhanced agent
   */
  async createAgent(request: CreateEnhancedAgentRequest): Promise<ApiResponse<EnhancedAgent>> {
    return api.post<EnhancedAgent>('/api/v1/agents', request);
  }

  /**
   * Update existing agent (owner only)
   */
  async updateAgent(
    agentId: string,
    request: UpdateEnhancedAgentRequest
  ): Promise<ApiResponse<EnhancedAgent>> {
    return api.put<EnhancedAgent>(`/api/v1/agents/${agentId}`, request);
  }

  /**
   * Delete agent (owner only)
   */
  async deleteAgent(agentId: string): Promise<ApiResponse<{ message: string }>> {
    return api.delete<{ message: string }>(`/api/v1/agents/${agentId}`);
  }

  /**
   * Fork an existing agent
   */
  async forkAgent(
    agentId: string,
    newName: string
  ): Promise<ApiResponse<EnhancedAgent>> {
    return api.post<EnhancedAgent>(`/api/v1/agents/${agentId}/fork`, { new_name: newName });
  }

  /**
   * Get available agent templates
   */
  async getTemplates(category?: string): Promise<ApiResponse<AgentTemplate[]>> {
    const params = new URLSearchParams();
    if (category) {
      params.append('category', category);
    }
    
    const query = params.toString();
    const endpoint = `/api/v1/agents/templates/${query ? `?${query}` : ''}`;
    
    return api.get<AgentTemplate[]>(endpoint);
  }

  /**
   * Create agent from template
   */
  async createFromTemplate(
    templateId: string,
    customization: Partial<CreateEnhancedAgentRequest>
  ): Promise<ApiResponse<EnhancedAgent>> {
    return api.post<EnhancedAgent>(`/api/v1/agents/templates/${templateId}`, customization);
  }

  /**
   * Get agent categories with counts
   */
  async getCategories(includeTeamId?: string): Promise<ApiResponse<CategoryInfo[]>> {
    const params = new URLSearchParams();
    params.append('include_counts', 'true');
    if (includeTeamId) {
      params.append('team_id', includeTeamId);
    }
    
    const query = params.toString();
    return api.get<CategoryInfo[]>(`/api/v1/agents/categories/?${query}`);
  }

  /**
   * Get public agents (legacy endpoint)
   */
  async getPublicAgents(options: {
    category?: string;
    search?: string;
    featured_only?: boolean;
    limit?: number;
    offset?: number;
    sort_by?: string;
  } = {}): Promise<ApiResponse<EnhancedAgent[]>> {
    const params = new URLSearchParams();
    
    Object.entries(options).forEach(([key, value]) => {
      if (value !== undefined) {
        params.append(key, value.toString());
      }
    });
    
    const query = params.toString();
    return api.get<EnhancedAgent[]>(`/api/v1/agents/public/?${query}`);
  }

  /**
   * Get agents filtered by access level
   */
  async getMyAgents(): Promise<ApiResponse<EnhancedAgent[]>> {
    return this.listAgents({ access_filter: 'mine' });
  }

  async getTeamAgents(): Promise<ApiResponse<EnhancedAgent[]>> {
    return this.listAgents({ access_filter: 'team' });
  }

  async getOrgAgents(): Promise<ApiResponse<EnhancedAgent[]>> {
    return this.listAgents({ access_filter: 'org' });
  }

  async getFeaturedAgents(): Promise<ApiResponse<EnhancedAgent[]>> {
    return this.listAgents({ featured_only: true });
  }

  /**
   * Search agents by name, description, or tags
   */
  async searchAgents(
    query: string,
    accessFilter?: AccessFilter,
    category?: string
  ): Promise<ApiResponse<EnhancedAgent[]>> {
    return this.listAgents({
      access_filter: accessFilter,
      search: query,
      category
    });
  }

  /**
   * Get agents by category
   */
  async getAgentsByCategory(
    category: AgentCategory,
    accessFilter?: AccessFilter
  ): Promise<ApiResponse<EnhancedAgent[]>> {
    return this.listAgents({
      access_filter: accessFilter,
      category
    });
  }

  /**
   * Get user's agent statistics summary
   */
  async getUserAgentSummary(): Promise<ApiResponse<{
    total_agents: number;
    owned_agents: number;
    team_agents: number;
    org_agents: number;
    public_agents: number;
    total_usage: number;
    avg_rating: number;
    categories: Record<string, number>;
  }>> {
    const allAgents = await this.listAgents({ access_filter: 'all' });
    
    if (!allAgents.data) {
      return {
        error: allAgents.error,
        status: allAgents.status
      };
    }

    const agents = allAgents.data;
    const categoryCount: Record<string, number> = {};
    
    agents.forEach(agent => {
      categoryCount[agent.category] = (categoryCount[agent.category] || 0) + 1;
    });

    const summary = {
      total_agents: agents.length,
      owned_agents: agents.filter(a => a.is_owner).length,
      team_agents: agents.filter(a => a.visibility === 'team' && !a.is_owner).length,
      org_agents: agents.filter(a => a.visibility === 'organization' && !a.is_owner).length,
      public_agents: agents.filter(a => a.visibility === 'public' && !a.is_owner).length,
      total_usage: agents.reduce((sum, a) => sum + a.usage_count, 0),
      avg_rating: agents.filter(a => a.average_rating).reduce((sum, a, _, arr) => 
        sum + (a.average_rating || 0) / arr.length, 0),
      categories: categoryCount
    };

    return {
      data: summary,
      status: 200
    };
  }

  /**
   * Get personality profiles for different types
   */
  getPersonalityProfiles(): Record<PersonalityType, PersonalityProfile> {
    return {
      geometric: {
        colors: {
          primary: "#00FF94",
          secondary: "#0066FF", 
          accent: "#FFD700",
          background: "rgba(0, 255, 148, 0.05)"
        },
        animation: {
          style: "sharp",
          duration: 300,
          easing: "cubic-bezier(0.4, 0, 0.2, 1)"
        },
        visual: {
          shapes: ["square", "triangle", "hexagon"],
          patterns: ["grid", "lines", "dots"],
          effects: ["slide", "fade", "scale"]
        },
        interaction: {
          greeting_style: "direct",
          conversation_tone: "structured",
          response_style: "organized"
        }
      },
      organic: {
        colors: {
          primary: "#FF6B6B",
          secondary: "#4ECDC4",
          accent: "#FFE66D",
          background: "rgba(255, 107, 107, 0.05)"
        },
        animation: {
          style: "fluid",
          duration: 600,
          easing: "cubic-bezier(0.25, 0.46, 0.45, 0.94)"
        },
        visual: {
          shapes: ["circle", "ellipse", "blob"],
          patterns: ["waves", "curves", "spirals"],
          effects: ["bounce", "spring", "flow"]
        },
        interaction: {
          greeting_style: "warm",
          conversation_tone: "friendly",
          response_style: "conversational"
        }
      },
      minimal: {
        colors: {
          primary: "#333333",
          secondary: "#666666",
          accent: "#999999", 
          background: "rgba(51, 51, 51, 0.02)"
        },
        animation: {
          style: "subtle",
          duration: 200,
          easing: "ease-in-out"
        },
        visual: {
          shapes: ["line", "rectangle", "point"],
          patterns: ["minimal", "clean", "simple"],
          effects: ["fade", "opacity", "transform"]
        },
        interaction: {
          greeting_style: "concise",
          conversation_tone: "professional",
          response_style: "efficient"
        }
      },
      technical: {
        colors: {
          primary: "#0088FF",
          secondary: "#00CCFF",
          accent: "#FFFFFF",
          background: "rgba(0, 136, 255, 0.03)"
        },
        animation: {
          style: "precise",
          duration: 250,
          easing: "linear"
        },
        visual: {
          shapes: ["circuit", "connector", "node"],
          patterns: ["matrix", "grid", "network"],
          effects: ["pulse", "glow", "scan"]
        },
        interaction: {
          greeting_style: "systematic",
          conversation_tone: "analytical",
          response_style: "detailed"
        }
      }
    };
  }
}

// Singleton instance
export const enhancedAgentService = new EnhancedAgentService();

// Convenience exports
export const {
  listAgents: listEnhancedAgents,
  getAgent: getEnhancedAgent,
  createAgent: createEnhancedAgent,
  updateAgent: updateEnhancedAgent,
  deleteAgent: deleteEnhancedAgent,
  forkAgent,
  getTemplates: getAgentTemplates,
  createFromTemplate,
  getCategories: getAgentCategories,
  getPublicAgents,
  getMyAgents,
  getTeamAgents,
  getOrgAgents,
  getFeaturedAgents,
  searchAgents,
  getAgentsByCategory,
  getUserAgentSummary,
  getPersonalityProfiles
} = enhancedAgentService;