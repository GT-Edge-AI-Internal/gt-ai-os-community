import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type PersonalityType = 'geometric' | 'organic' | 'minimal' | 'technical';
export type AvatarState = 'idle' | 'thinking' | 'speaking' | 'offline' | 'success' | 'error';
export type Visibility = 'private' | 'team' | 'public';
export type DatasetConnection = 'all' | 'none' | 'selected';
// AgentCategory is now dynamic (loaded from API) - use string type
// Default categories: general, coding, writing, analysis, creative, research, business, education
// Custom categories can be created by users
export type AgentCategory = string;

interface AvatarConfig {
  primaryColor: string;
  secondaryColor: string;
  size: 'small' | 'medium' | 'large';
  showConfidence: boolean;
  customImageUrl?: string;
}

interface ModelParameters {
  maxHistoryItems: number;
  maxChunks: number;
  maxTokens: number;
  trimRatio: number;
  temperature: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
}

interface ExamplePrompt {
  text: string;
  category: string;
  expectedBehavior?: string;
}

export interface EnhancedAgent {
  id: string;
  teamId: string;
  name: string;
  description: string;
  disclaimer: string;
  category: AgentCategory;
  customCategory?: string;
  visibility: Visibility;
  featured: boolean;
  personalityType: PersonalityType;
  personalityProfile?: any;
  customAvatarUrl?: string;
  modelId: string;
  systemPrompt: string;
  modelParameters: ModelParameters;
  datasetConnection: DatasetConnection;
  selectedDatasetIds: string[];
  examplePrompts: ExamplePrompt[];
  safetyFlags: string[];
  requireModeration: boolean;
  blockedTerms: string[];
  enabledCapabilities: string[];
  mcpIntegrationIds: string[];
  toolConfigurations: Record<string, any>;
  ownerId: string;
  collaboratorIds: string[];
  canFork: boolean;
  parentAgentId?: string;
  version: number;
  usageCount: number;
  averageRating?: number;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  publishedAt?: string;
  lastUsedAt?: string;
}

interface AgentFilters {
  category?: AgentCategory;
  visibility?: Visibility;
  search?: string;
  featuredOnly?: boolean;
  tags?: string[];
  sortBy?: 'recent' | 'name' | 'usage' | 'rating';
}

interface EnhancedAgentStore {
  // State
  agents: EnhancedAgent[];
  selectedAgent: EnhancedAgent | null;
  currentAgentId: string | null;
  selectedPersonality: PersonalityType;
  avatarConfig: AvatarConfig;
  avatarState: AvatarState;
  confidenceThreshold: number;
  currentConfidence: number;
  isThinking: boolean;
  filters: AgentFilters;
  view: 'grid' | 'list';
  
  // Loading states
  isLoading: boolean;
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  
  // Error states
  error: string | null;
  
  // Actions - Agent Management
  setAgents: (agents: EnhancedAgent[]) => void;
  addAgent: (agent: EnhancedAgent) => void;
  updateAgent: (agentId: string, updates: Partial<EnhancedAgent>) => void;
  removeAgent: (agentId: string) => void;
  selectAgent: (agent: EnhancedAgent | null) => void;
  setCurrentAgent: (agentId: string | null) => void;
  
  // Actions - Personality & Avatar
  setPersonality: (type: PersonalityType) => void;
  updateAvatarConfig: (config: Partial<AvatarConfig>) => void;
  setAvatarState: (state: AvatarState) => void;
  setThinkingState: (thinking: boolean) => void;
  updateConfidence: (score: number) => void;
  setConfidenceThreshold: (threshold: number) => void;
  
  // Actions - Filtering & Search
  setFilters: (filters: Partial<AgentFilters>) => void;
  clearFilters: () => void;
  setView: (view: 'grid' | 'list') => void;
  
  // Actions - Loading States
  setLoading: (loading: boolean) => void;
  setCreating: (creating: boolean) => void;
  setUpdating: (updating: boolean) => void;
  setDeleting: (deleting: boolean) => void;
  setError: (error: string | null) => void;
  
  // Computed getters
  getFilteredAgents: () => EnhancedAgent[];
  getAgentById: (id: string) => EnhancedAgent | undefined;
  getMyAgents: (userId: string) => EnhancedAgent[];
  getPublicAgents: () => EnhancedAgent[];
  getTeamAgents: (teamId: string) => EnhancedAgent[];
  getFeaturedAgents: () => EnhancedAgent[];
  getAgentsByCategory: (category: AgentCategory) => EnhancedAgent[];
  
  // Actions - Utility
  resetToDefaults: () => void;
  incrementUsageCount: (agentId: string) => void;
  updateRating: (agentId: string, rating: number) => void;
}

const defaultAvatarConfig: AvatarConfig = {
  primaryColor: '#00d084',
  secondaryColor: '#ffffff',
  size: 'medium',
  showConfidence: true,
};

const defaultModelParameters: ModelParameters = {
  maxHistoryItems: 10,
  maxChunks: 10,
  maxTokens: 4096,
  trimRatio: 75,
  temperature: 0.7,
  topP: 0.9,
  frequencyPenalty: 0.0,
  presencePenalty: 0.0,
};

export const useEnhancedAgentStore = create<EnhancedAgentStore>()(
  persist(
    (set, get) => ({
      // Initial state
      agents: [],
      selectedAgent: null,
      currentAgentId: null,
      selectedPersonality: 'minimal',
      avatarConfig: defaultAvatarConfig,
      avatarState: 'idle',
      confidenceThreshold: 0.7,
      currentConfidence: 1.0,
      isThinking: false,
      filters: {},
      view: 'grid',
      
      // Loading states
      isLoading: false,
      isCreating: false,
      isUpdating: false,
      isDeleting: false,
      
      // Error states
      error: null,
      
      // Actions - Agent Management
      setAgents: (agents) => set({ agents, error: null }),
      
      addAgent: (agent) => set((state) => ({
        agents: [agent, ...state.agents],
        error: null
      })),
      
      updateAgent: (agentId, updates) => set((state) => ({
        agents: state.agents.map(a => 
          a.id === agentId ? { ...a, ...updates } : a
        ),
        selectedAgent: state.selectedAgent?.id === agentId 
          ? { ...state.selectedAgent, ...updates } 
          : state.selectedAgent,
        error: null
      })),
      
      removeAgent: (agentId) => set((state) => ({
        agents: state.agents.filter(a => a.id !== agentId),
        selectedAgent: state.selectedAgent?.id === agentId ? null : state.selectedAgent,
        currentAgentId: state.currentAgentId === agentId ? null : state.currentAgentId,
        error: null
      })),
      
      selectAgent: (agent) => set({ 
        selectedAgent: agent,
        selectedPersonality: agent?.personalityType || 'minimal',
        error: null
      }),
      
      setCurrentAgent: (agentId) => {
        const agent = agentId ? get().getAgentById(agentId) : null;
        set({ 
          currentAgentId: agentId,
          selectedAgent: agent || null,
          selectedPersonality: agent?.personalityType || 'minimal'
        });
      },
      
      // Actions - Personality & Avatar
      setPersonality: (type) => set({ 
        selectedPersonality: type,
        avatarConfig: {
          ...defaultAvatarConfig,
          primaryColor: type === 'technical' ? '#2d3748' : '#00d084',
        }
      }),
      
      updateAvatarConfig: (config) => set((state) => ({
        avatarConfig: { ...state.avatarConfig, ...config }
      })),
      
      setAvatarState: (avatarState) => set({ 
        avatarState,
        isThinking: avatarState === 'thinking'
      }),
      
      setThinkingState: (thinking) => set({ 
        isThinking: thinking,
        avatarState: thinking ? 'thinking' : 'idle'
      }),
      
      updateConfidence: (score) => set({ currentConfidence: Math.min(1, Math.max(0, score)) }),
      
      setConfidenceThreshold: (threshold) => set({ 
        confidenceThreshold: Math.min(1, Math.max(0, threshold))
      }),
      
      // Actions - Filtering & Search
      setFilters: (newFilters) => set((state) => ({
        filters: { ...state.filters, ...newFilters }
      })),
      
      clearFilters: () => set({ filters: {} }),
      
      setView: (view) => set({ view }),
      
      // Actions - Loading States
      setLoading: (isLoading) => set({ isLoading }),
      setCreating: (isCreating) => set({ isCreating }),
      setUpdating: (isUpdating) => set({ isUpdating }),
      setDeleting: (isDeleting) => set({ isDeleting }),
      setError: (error) => set({ error }),
      
      // Computed getters
      getFilteredAgents: () => {
        const state = get();
        let filtered = state.agents;
        
        if (state.filters.category) {
          filtered = filtered.filter(a => a.category === state.filters.category);
        }
        
        if (state.filters.visibility) {
          filtered = filtered.filter(a => a.visibility === state.filters.visibility);
        }
        
        if (state.filters.search) {
          const search = state.filters.search.toLowerCase();
          filtered = filtered.filter(a =>
            a.name.toLowerCase().includes(search) ||
            a.description.toLowerCase().includes(search) ||
            a.tags.some(tag => tag.toLowerCase().includes(search))
          );
        }
        
        if (state.filters.featuredOnly) {
          filtered = filtered.filter(a => a.featured);
        }
        
        if (state.filters.tags && state.filters.tags.length > 0) {
          filtered = filtered.filter(a =>
            state.filters.tags!.some(tag => a.tags.includes(tag))
          );
        }
        
        // Sort
        const sortBy = state.filters.sortBy || 'recent';
        filtered.sort((a, b) => {
          switch (sortBy) {
            case 'name':
              return a.name.localeCompare(b.name);
            case 'usage':
              return b.usageCount - a.usageCount;
            case 'rating':
              return (b.averageRating || 0) - (a.averageRating || 0);
            case 'recent':
            default:
              const aTime = new Date(a.lastUsedAt || a.updatedAt).getTime();
              const bTime = new Date(b.lastUsedAt || b.updatedAt).getTime();
              return bTime - aTime;
          }
        });
        
        return filtered;
      },
      
      getAgentById: (id) => {
        return get().agents.find(a => a.id === id);
      },
      
      getMyAgents: (userId) => {
        return get().agents.filter(a => a.ownerId === userId);
      },
      
      getPublicAgents: () => {
        return get().agents.filter(a => a.visibility === 'public');
      },
      
      getTeamAgents: (teamId) => {
        return get().agents.filter(a => a.teamId === teamId && a.visibility === 'team');
      },
      
      getFeaturedAgents: () => {
        return get().agents.filter(a => a.featured);
      },
      
      getAgentsByCategory: (category) => {
        return get().agents.filter(a => a.category === category);
      },
      
      // Actions - Utility
      resetToDefaults: () => set({
        selectedPersonality: 'minimal',
        avatarConfig: defaultAvatarConfig,
        avatarState: 'idle',
        confidenceThreshold: 0.7,
        currentConfidence: 1.0,
        isThinking: false,
        filters: {},
        view: 'grid',
        selectedAgent: null,
        error: null
      }),
      
      incrementUsageCount: (agentId) => set((state) => ({
        agents: state.agents.map(a =>
          a.id === agentId 
            ? { ...a, usageCount: a.usageCount + 1, lastUsedAt: new Date().toISOString() }
            : a
        )
      })),
      
      updateRating: (agentId, rating) => set((state) => {
        const agent = state.agents.find(a => a.id === agentId);
        if (!agent) return state;
        
        // Simple rating update - in production would need proper averaging logic
        const newRating = agent.averageRating 
          ? (agent.averageRating + rating) / 2
          : rating;
        
        return {
          agents: state.agents.map(a =>
            a.id === agentId 
              ? { ...a, averageRating: newRating }
              : a
          )
        };
      }),
    }),
    {
      name: 'enhanced-agent-store',
      partialize: (state) => ({
        selectedPersonality: state.selectedPersonality,
        avatarConfig: state.avatarConfig,
        confidenceThreshold: state.confidenceThreshold,
        filters: state.filters,
        view: state.view,
      }),
    }
  )
);

// Helper hooks for specific use cases
export const useAgentFiltering = () => {
  const { filters, setFilters, clearFilters, getFilteredAgents } = useEnhancedAgentStore();
  return { filters, setFilters, clearFilters, getFilteredAgents };
};

export const useAgentPersonality = () => {
  const { 
    selectedPersonality, 
    avatarConfig, 
    avatarState, 
    currentConfidence,
    setPersonality, 
    updateAvatarConfig, 
    setAvatarState, 
    updateConfidence 
  } = useEnhancedAgentStore();
  
  return { 
    selectedPersonality, 
    avatarConfig, 
    avatarState, 
    currentConfidence,
    setPersonality, 
    updateAvatarConfig, 
    setAvatarState, 
    updateConfidence 
  };
};

export const useCurrentAgent = () => {
  const { 
    selectedAgent, 
    currentAgentId, 
    selectAgent, 
    setCurrentAgent,
    incrementUsageCount 
  } = useEnhancedAgentStore();
  
  return { 
    selectedAgent, 
    currentAgentId, 
    selectAgent, 
    setCurrentAgent,
    incrementUsageCount 
  };
};