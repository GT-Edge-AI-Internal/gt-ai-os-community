'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { AppLayout } from '@/components/layout/app-layout';
import { AgentGallery } from '@/components/agents/agent-gallery';
import { AgentQuickTile } from '@/components/agents/agent-quick-tile';
import { AuthGuard } from '@/components/auth/auth-guard';
import { GT2_CAPABILITIES } from '@/lib/capabilities';
import { agentService, type EnhancedAgent } from '@/services';
import { getFavoriteAgents, updateFavoriteAgents } from '@/services/user';
import { Bot, Plus, LayoutGrid, List, Star, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { usePageTitle } from '@/hooks/use-page-title';
import { useDebouncedValue } from '@/lib/utils';

// Dynamically import heavy modal components for better performance
const FavoriteAgentSelectorModal = dynamic(
  () => import('@/components/agents/favorite-agent-selector-modal').then(mod => ({ default: mod.FavoriteAgentSelectorModal })),
  { ssr: false }
);

const AgentBulkImportModal = dynamic(
  () => import('@/components/agents/agent-bulk-import-modal').then(mod => ({ default: mod.AgentBulkImportModal })),
  { ssr: false }
);

type ViewMode = 'quick' | 'detailed';
type SortBy = 'name' | 'created_at' | 'usage_count' | 'recent_usage' | 'my_most_used';

function AgentsPage() {
  usePageTitle('Agents');

  const [agents, setAgents] = useState<EnhancedAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const [triggerCreate, setTriggerCreate] = useState(false);

  // Quick View state - Default to 'quick' view (favorites) as landing page
  const [viewMode, setViewMode] = useState<ViewMode>('quick');
  const [favoriteAgentIds, setFavoriteAgentIds] = useState<string[]>([]);
  const [showFavoriteSelector, setShowFavoriteSelector] = useState(false);
  const [showBulkImportModal, setShowBulkImportModal] = useState(false);
  const [loadingFavorites, setLoadingFavorites] = useState(true);

  // Quick View filters
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearchQuery = useDebouncedValue(searchQuery, 300); // Performance optimization: debounce search
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedTag, setSelectedTag] = useState<string>('all');
  const [selectedCreator, setSelectedCreator] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortBy>('recent_usage'); // Default to recently used

  const loadAgents = async () => {
    setLoading(true);
    try {
      // Build query parameters for backend usage tracking
      const params: any = {};

      // Add sort parameter if using user-relative sorting
      if (sortBy === 'recent_usage' || sortBy === 'my_most_used') {
        params.sort_by = sortBy;
      }

      const res = await agentService.listAgents(params);
      console.log('📋 Agent service response:', res);
      // Backend returns wrapped in ApiResponse: {data: {data: [], total: 0, limit: 50, offset: 0}, status: 200}
      if (res && res.data && res.data.data && Array.isArray(res.data.data)) {
        console.log('📋 Found agents in res.data.data:', res.data.data);
        // Log first agent's permission flags for debugging
        if (res.data.data.length > 0) {
          const firstAgent = res.data.data[0];
          console.log('🔐 First agent permissions (RAW from backend):', {
            name: firstAgent.name,
            can_edit: firstAgent.can_edit,
            can_edit_type: typeof firstAgent.can_edit,
            can_delete: firstAgent.can_delete,
            can_delete_type: typeof firstAgent.can_delete,
            is_owner: firstAgent.is_owner,
            is_owner_type: typeof firstAgent.is_owner
          });
        }
        // Adapt backend AgentResponse to frontend EnhancedAgent interface
        const adaptedAgents = res.data.data.map((agent: any) => {
          const adapted = {
          ...agent,
          // Provide defaults for missing EnhancedAgent fields
          team_id: agent.team_id || '',
          disclaimer: agent.disclaimer || '',
          easy_prompts: agent.easy_prompts || [],
          visibility: agent.visibility || 'individual',
          featured: agent.featured || false,
          personality_type: agent.personality_type || 'minimal',
          custom_avatar_url: agent.custom_avatar_url || '',
          model_id: agent.model_id || agent.model || '',
          system_prompt: agent.system_prompt || '',
          model_parameters: agent.model_parameters || {},
          dataset_connection: agent.dataset_connection || 'all',
          selected_dataset_ids: agent.selected_dataset_ids || [],
          require_moderation: agent.require_moderation || false,
          blocked_terms: agent.blocked_terms || [],
          enabled_capabilities: agent.enabled_capabilities || [],
          mcp_integration_ids: agent.mcp_integration_ids || [],
          tool_configurations: agent.tool_configurations || {},
          collaborator_ids: agent.collaborator_ids || [],
          can_fork: agent.can_fork || true,
          parent_agent_id: agent.parent_agent_id,
          version: agent.version || 1,
          usage_count: agent.usage_count || 0,
          average_rating: agent.average_rating,
          tags: agent.tags || [],
          example_prompts: agent.example_prompts || [],
          safety_flags: agent.safety_flags || [],
          created_at: agent.created_at,
          updated_at: agent.updated_at,
          // Permission flags from backend - default to false for security
          can_edit: Boolean(agent.can_edit),
          can_delete: Boolean(agent.can_delete),
          is_owner: Boolean(agent.is_owner),
          // Creator information
          owner_name: agent.created_by_name || agent.owner_name
          };
          console.log('🔐 Adapted agent:', adapted.name, 'can_edit:', adapted.can_edit, 'can_delete:', adapted.can_delete);
          return adapted;
        });
        setAgents(adaptedAgents);
      } else if (res && res.data && Array.isArray(res.data)) {
        console.log('📋 Found agents in res.data:', res.data);
        // Map permission flags even for this path - default to false for security
        const mappedAgents = res.data.map((agent: any) => ({
          ...agent,
          can_edit: Boolean(agent.can_edit),
          can_delete: Boolean(agent.can_delete),
          is_owner: Boolean(agent.is_owner),
          owner_name: agent.created_by_name || agent.owner_name
        }));
        setAgents(mappedAgents);
      } else if (Array.isArray(res)) {
        console.log('📋 Response is array:', res);
        // Map permission flags even for this path - default to false for security
        const mappedAgents = res.map((agent: any) => ({
          ...agent,
          can_edit: Boolean(agent.can_edit),
          can_delete: Boolean(agent.can_delete),
          is_owner: Boolean(agent.is_owner)
        }));
        setAgents(mappedAgents);
      } else {
        console.log('📋 No agents found or unexpected response format:', res);
        setAgents([]);
      }
    } catch (error) {
      console.error('❌ Error loading agents:', error);
      setAgents([]);
    } finally {
      setLoading(false);
    }
  };

  const loadFavorites = async () => {
    setLoadingFavorites(true);
    try {
      const res = await getFavoriteAgents();
      if (res.data?.favorite_agent_ids && res.data.favorite_agent_ids.length > 0) {
        // User has favorites set
        setFavoriteAgentIds(res.data.favorite_agent_ids);
      } else {
        // No favorites set - mark all agents as favorites by default
        // Wait for agents to load first
        if (agents.length === 0) {
          // Agents not loaded yet, wait for them
          setLoadingFavorites(false);
          return;
        }
        const allAgentIds = agents.map(agent => agent.id);
        setFavoriteAgentIds(allAgentIds);
        // Save to backend
        if (allAgentIds.length > 0) {
          try {
            await updateFavoriteAgents(allAgentIds);
            console.log('✅ All agents marked as favorites by default');
          } catch (saveError) {
            console.error('❌ Error saving default favorites:', saveError);
          }
        }
      }
    } catch (error) {
      console.error('❌ Error loading favorite agents:', error);
    } finally {
      setLoadingFavorites(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  // Load favorites after agents are loaded, or allow empty state if no agents exist
  useEffect(() => {
    if (!loading) {
      if (agents.length > 0 && loadingFavorites) {
        loadFavorites();
      } else if (agents.length === 0 && loadingFavorites) {
        // No agents visible to this user - allow empty favorites state
        setLoadingFavorites(false);
      }
    }
  }, [agents, loading]);

  // Reload agents when sort or filter changes
  useEffect(() => {
    if (!loading) {
      loadAgents();
    }
  }, [sortBy]);

  const handleSaveFavorites = async (newFavoriteIds: string[]) => {
    try {
      const res = await updateFavoriteAgents(newFavoriteIds);
      if (res.status >= 200 && res.status < 300) {
        setFavoriteAgentIds(newFavoriteIds);
        console.log('✅ Favorite agents updated');
      } else {
        throw new Error(res.error || 'Failed to update favorites');
      }
    } catch (error) {
      console.error('❌ Error saving favorite agents:', error);
      alert('Failed to save favorite agents. Please try again.');
    }
  };

  // Get favorite agents (filtered list)
  const favoriteAgents = React.useMemo(() => {
    return agents.filter(agent => favoriteAgentIds.includes(agent.id));
  }, [agents, favoriteAgentIds]);

  // Extract unique categories, tags, and creators from agents
  const { categories, tags, creators } = React.useMemo(() => {
    const categorySet = new Set<string>();
    const tagSet = new Set<string>();
    const creatorSet = new Set<string>();

    agents.forEach(agent => {
      if (agent.category) categorySet.add(agent.category);
      agent.tags?.forEach(tag => tagSet.add(tag));
      if (agent.owner_name) creatorSet.add(agent.owner_name);
    });

    return {
      categories: Array.from(categorySet).sort(),
      tags: Array.from(tagSet).sort(),
      creators: Array.from(creatorSet).sort()
    };
  }, [agents]);

  // Filter and sort favorite agents for Quick View
  const filteredFavoriteAgents = React.useMemo(() => {
    let filtered = favoriteAgents.filter(agent => {
      const matchesSearch = !debouncedSearchQuery ||
        agent.name.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
        agent.description?.toLowerCase().includes(debouncedSearchQuery.toLowerCase());

      const matchesCategory = selectedCategory === 'all' || agent.category === selectedCategory;
      const matchesTag = selectedTag === 'all' || agent.tags?.includes(selectedTag);
      const matchesCreator = selectedCreator === 'all' || agent.owner_name === selectedCreator;

      return matchesSearch && matchesCategory && matchesTag && matchesCreator;
    });

    // Sort agents locally (only if not using backend sorting)
    if (sortBy === 'recent_usage' || sortBy === 'my_most_used') {
      // Backend already sorted, preserve order
      return filtered;
    }

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'usage_count':
          return (b.usage_count || 0) - (a.usage_count || 0);
        case 'created_at':
        default:
          return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
      }
    });

    return filtered;
  }, [favoriteAgents, debouncedSearchQuery, selectedCategory, selectedTag, selectedCreator, sortBy]);

  const handleSelectAgent = (agent: EnhancedAgent) => {
    router.push(`/chat?agent=${agent.id}`);
  };

  const handleCreateAgent = async (agentData: any) => {
    try {
      console.log('🚀 Creating agent with data:', agentData);

      // Essential fields that backend expects including model_id
      const createRequest = {
        name: agentData.name,
        description: agentData.description || "",
        category: agentData.category || agentData.agent_type || "general",
        model_id: agentData.model_id,
        temperature: agentData.temperature || agentData.model_parameters?.temperature,
        max_tokens: agentData.max_tokens || agentData.model_parameters?.max_tokens,
        prompt_template: agentData.system_prompt,
        tags: agentData.tags || [],
        selected_dataset_ids: agentData.selected_dataset_ids || [],
        visibility: agentData.visibility || "individual",
        disclaimer: agentData.disclaimer,
        easy_prompts: agentData.easy_prompts || []
      };

      console.log('📦 Sending request:', createRequest);
      
      const result = await agentService.createAgent(createRequest);
      console.log('📥 Backend result:', result);
      
      if (result.data && result.status >= 200 && result.status < 300) {
        // Refresh the agents list
        const refreshResult = await agentService.listAgents();
        if (refreshResult && refreshResult.data && refreshResult.data.data && Array.isArray(refreshResult.data.data)) {
          const adaptedAgents = refreshResult.data.data.map((agent: any) => ({
            ...agent,
            team_id: agent.team_id || '',
            disclaimer: agent.disclaimer || '',
            easy_prompts: agent.easy_prompts || [],
            visibility: agent.visibility || 'individual',
            featured: agent.featured || false,
            personality_type: agent.personality_type || 'minimal',
            custom_avatar_url: agent.custom_avatar_url || '',
            model_id: agent.model_id || agent.model || '',
            system_prompt: agent.system_prompt || '',
            model_parameters: agent.model_parameters || {},
            dataset_connection: agent.dataset_connection || 'all',
            selected_dataset_ids: agent.selected_dataset_ids || [],
            require_moderation: agent.require_moderation || false,
            blocked_terms: agent.blocked_terms || [],
            enabled_capabilities: agent.enabled_capabilities || [],
            mcp_integration_ids: agent.mcp_integration_ids || [],
            tool_configurations: agent.tool_configurations || {},
            collaborator_ids: agent.collaborator_ids || [],
            can_fork: agent.can_fork || true,
            parent_agent_id: agent.parent_agent_id,
            version: agent.version || 1,
            usage_count: agent.usage_count || 0,
            average_rating: agent.average_rating,
            tags: agent.tags || [],
            example_prompts: agent.example_prompts || [],
            safety_flags: agent.safety_flags || [],
            created_at: agent.created_at,
            updated_at: agent.updated_at,
            can_edit: agent.can_edit === true,
            can_delete: agent.can_delete === true,
            is_owner: agent.is_owner === true,
            owner_name: agent.created_by_name || agent.owner_name
          }));
          setAgents(adaptedAgents);
        } else if (refreshResult && refreshResult.data && Array.isArray(refreshResult.data)) {
          setAgents(refreshResult.data);
        } else if (Array.isArray(refreshResult)) {
          setAgents(refreshResult);
        }
        console.log('✅ Agent created successfully');
      } else {
        throw new Error(result.error || 'Failed to create agent');
      }
    } catch (error) {
      console.error('❌ Error creating agent:', error);
      throw error;
    }
  };

  const handleEditAgent = async (agentData: any) => {
    try {
      console.log('📝 Updating agent with data:', agentData);
      
      // The agentData should contain the agent ID and update fields
      const updateRequest = {
        name: agentData.name,
        description: agentData.description || "",
        category: agentData.category || agentData.agent_type || "general",
        prompt_template: agentData.system_prompt || agentData.prompt_template || "",
        model: agentData.model_id || agentData.model || "",
        temperature: agentData.model_parameters?.temperature || 0.7,
        max_tokens: agentData.model_parameters?.max_tokens || 4096,
        personality_config: agentData.personality_profile || agentData.personality_config || {},
        resource_preferences: agentData.resource_preferences || {},
        tags: agentData.tags || [],
        is_favorite: agentData.is_favorite || false,
        visibility: agentData.visibility || "individual",
        selected_dataset_ids: agentData.selected_dataset_ids || [],
        disclaimer: agentData.disclaimer,
        easy_prompts: agentData.easy_prompts || [],
        team_shares: agentData.team_shares
      };

      console.log('📦 Sending update request:', updateRequest);
      
      const result = await agentService.updateAgent(agentData.id, updateRequest);
      console.log('📥 Backend update result:', result);
      
      if (result.data && result.status >= 200 && result.status < 300) {
        // Refresh the agents list
        const refreshResult = await agentService.listAgents();
        if (refreshResult && refreshResult.data && refreshResult.data.data && Array.isArray(refreshResult.data.data)) {
          const adaptedAgents = refreshResult.data.data.map((agent: any) => ({
            ...agent,
            team_id: agent.team_id || '',
            disclaimer: agent.disclaimer || '',
            easy_prompts: agent.easy_prompts || [],
            visibility: agent.visibility || 'individual',
            featured: agent.featured || false,
            personality_type: agent.personality_type || 'minimal',
            custom_avatar_url: agent.custom_avatar_url || '',
            model_id: agent.model_id || agent.model || '',
            system_prompt: agent.system_prompt || '',
            model_parameters: agent.model_parameters || {},
            dataset_connection: agent.dataset_connection || 'all',
            selected_dataset_ids: agent.selected_dataset_ids || [],
            require_moderation: agent.require_moderation || false,
            blocked_terms: agent.blocked_terms || [],
            enabled_capabilities: agent.enabled_capabilities || [],
            mcp_integration_ids: agent.mcp_integration_ids || [],
            tool_configurations: agent.tool_configurations || {},
            collaborator_ids: agent.collaborator_ids || [],
            can_fork: agent.can_fork || true,
            parent_agent_id: agent.parent_agent_id,
            version: agent.version || 1,
            usage_count: agent.usage_count || 0,
            average_rating: agent.average_rating,
            tags: agent.tags || [],
            example_prompts: agent.example_prompts || [],
            safety_flags: agent.safety_flags || [],
            created_at: agent.created_at,
            updated_at: agent.updated_at,
            can_edit: agent.can_edit === true,
            can_delete: agent.can_delete === true,
            is_owner: agent.is_owner === true,
            owner_name: agent.created_by_name || agent.owner_name
          }));
          setAgents(adaptedAgents);
        } else if (refreshResult && refreshResult.data && Array.isArray(refreshResult.data)) {
          setAgents(refreshResult.data);
        } else if (Array.isArray(refreshResult)) {
          setAgents(refreshResult);
        }
        console.log('✅ Agent updated successfully');
      } else {
        throw new Error(result.error || 'Failed to update agent');
      }
    } catch (error) {
      console.error('❌ Error updating agent:', error);
      throw error;
    }
  };

  const handleDeleteAgent = async (agentId: string) => {
    try {
      const result = await agentService.deleteAgent(agentId);
      if (result.status >= 200 && result.status < 300) {
        // Remove from local state (archived agents are filtered out)
        setAgents(prev => prev.filter(agent => agent.id !== agentId));
        console.log('✅ Agent archived successfully');
      } else {
        throw new Error(result.error || 'Failed to archive agent');
      }
    } catch (error) {
      console.error('❌ Error archiving agent:', error);
      alert('Failed to archive agent. Please try again.');
    }
  };

  const handleDuplicateAgent = async (agent: EnhancedAgent) => {
    try {
      const newName = `${agent.name} (Copy)`;
      const result = await agentService.forkAgent(agent.id, newName);
      
      if (result.data && result.status >= 200 && result.status < 300) {
        // Refresh the agents list
        await loadAgents();
        console.log('✅ Agent duplicated successfully');
      } else {
        throw new Error(result.error || 'Failed to duplicate agent');
      }
    } catch (error) {
      console.error('❌ Error duplicating agent:', error);
      alert('Failed to duplicate agent. Please try again.');
    }
  };

  const handleViewHistory = (agent: EnhancedAgent) => {
    // Navigate to chat page with agent filter
    router.push(`/chat?agent=${agent.id}`);
  };

  const handleOpenCreateAgent = () => {
    setTriggerCreate(true);
  };


  if (loading || loadingFavorites) {
    return (
      <AppLayout>
        <div className="max-w-7xl mx-auto p-6">
          <div className="text-center py-16">
            <div className="text-lg text-gray-600">Loading agents...</div>
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                <Bot className="w-8 h-8 text-gt-green" />
                {viewMode === 'quick' ? 'Favorite Agents' : 'Agent Configuration'}
              </h1>
              {/* Removed subtitle text per issue #167 requirements */}
            </div>

            <div className="flex items-center gap-2">
              {/* Action Button (changes based on view mode) - LEFT position */}
              {viewMode === 'quick' ? (
                <Button
                  className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 focus:ring-green-500"
                  onClick={() => setShowFavoriteSelector(true)}
                >
                  <Star className="w-4 h-4 mr-2" />
                  Add Favorites
                </Button>
              ) : (
                <>
                  <Button
                    variant="outline"
                    onClick={() => setShowBulkImportModal(true)}
                    className="px-4 py-2"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Import Agent
                  </Button>
                  <Button
                    onClick={handleOpenCreateAgent}
                    className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 focus:ring-blue-500"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Create Agent
                  </Button>
                </>
              )}

              {/* View Mode Toggle - Color-coded: Blue = Configuration, Green = Navigation - RIGHT position */}
              {viewMode === 'quick' ? (
                <Button
                  onClick={() => setViewMode('detailed')}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white focus:ring-blue-500"
                >
                  <List className="w-4 h-4" />
                  Agent Configuration
                </Button>
              ) : (
                <Button
                  onClick={() => setViewMode('quick')}
                  className="flex items-center gap-2 px-4 py-2 bg-green-500 hover:bg-green-600 text-white focus:ring-green-500"
                >
                  <LayoutGrid className="w-4 h-4" />
                  Back to Favorites
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Content: Quick View or Detailed View */}
        {viewMode === 'quick' ? (
          <>
            {/* Quick View: Empty State or Agent Tiles */}
            {favoriteAgentIds.length === 0 ? (
              <div className="bg-white rounded-lg shadow-sm border p-12">
                <div className="text-center max-w-md mx-auto">
                  <Star className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    No favorites selected
                  </h3>
                  <p className="text-gray-600 mb-6">
                    Click on the button below to select your Favorite Agents from the list of agents available in the catalog.
                  </p>
                  <Button
                    onClick={() => setShowFavoriteSelector(true)}
                    className="bg-green-500 hover:bg-green-600 text-white focus:ring-green-500"
                  >
                    <Star className="w-4 h-4 mr-2" />
                    Add Favorites
                  </Button>
                </div>
              </div>
            ) : (
              <>
                {/* Search and Filters */}
                <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
                  {/* Search */}
                  <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4 z-10" />
                    <Input
                      placeholder="Search favorite agents..."
                      value={searchQuery}
                      onChange={(value: string) => setSearchQuery(value)}
                      className="pl-10"
                      clearable
                    />
                  </div>

                  {/* Filters */}
                  <div className="flex gap-2 items-center">
                    <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                      <SelectTrigger className="w-[140px]">
                        <SelectValue placeholder="Category" />
                      </SelectTrigger>
                      <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                        <SelectItem value="all">All Categories</SelectItem>
                        {categories.map(category => (
                          <SelectItem key={category} value={category}>
                            {category}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={selectedTag} onValueChange={setSelectedTag}>
                      <SelectTrigger className="w-[120px]">
                        <SelectValue placeholder="Tag" />
                      </SelectTrigger>
                      <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                        <SelectItem value="all">All Tags</SelectItem>
                        {tags.map(tag => (
                          <SelectItem key={tag} value={tag}>
                            {tag}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={selectedCreator} onValueChange={setSelectedCreator}>
                      <SelectTrigger className="w-[140px]">
                        <SelectValue placeholder="Creator" />
                      </SelectTrigger>
                      <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                        <SelectItem value="all">All Creators</SelectItem>
                        {creators.map(creator => (
                          <SelectItem key={creator} value={creator}>
                            {creator}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    <Select value={sortBy} onValueChange={(value) => setSortBy(value as SortBy)}>
                      <SelectTrigger className="w-[160px]">
                        <SelectValue placeholder="Sort by" />
                      </SelectTrigger>
                      <SelectContent className="z-[100] backdrop-blur-sm bg-white/95 border shadow-lg" position="popper" sideOffset={5}>
                        <SelectItem value="created_at">Date Created</SelectItem>
                        <SelectItem value="name">Name</SelectItem>
                        <SelectItem value="usage_count">Usage (Global)</SelectItem>
                        <SelectItem value="recent_usage">Recently Used</SelectItem>
                        <SelectItem value="my_most_used">Most Used</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Agent Tiles Grid (4 columns) */}
                {filteredFavoriteAgents.length === 0 ? (
                  <div className="text-center py-12 bg-white rounded-lg border">
                    <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">No agents found</h3>
                    <p className="text-gray-600">Try adjusting your search or filter criteria.</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
                    {filteredFavoriteAgents.map((agent) => (
                      <AgentQuickTile
                        key={agent.id}
                        agent={agent}
                        onSelect={handleSelectAgent}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          /* Detailed View: Existing AgentGallery */
          <AgentGallery
            agents={agents}
            onSelectAgent={handleSelectAgent}
            onCreateAgent={handleCreateAgent}
            onEditAgent={handleEditAgent}
            onDeleteAgent={handleDeleteAgent}
            onDuplicateAgent={handleDuplicateAgent}
            onViewHistory={handleViewHistory}
            hideHeader={true}
            className="mt-0"
            triggerCreate={triggerCreate}
            onTriggerComplete={() => setTriggerCreate(false)}
          />
        )}

        {/* Favorite Agent Selector Modal */}
        <FavoriteAgentSelectorModal
          isOpen={showFavoriteSelector}
          onClose={() => setShowFavoriteSelector(false)}
          agents={agents}
          currentFavorites={favoriteAgentIds}
          onSave={handleSaveFavorites}
        />

        {/* Bulk Import Modal */}
        <AgentBulkImportModal
          isOpen={showBulkImportModal}
          onClose={() => setShowBulkImportModal(false)}
          onImportComplete={loadAgents}
        />
      </div>
    </AppLayout>
  );
}

export default function Page() {
  return (
    <AuthGuard requiredCapabilities={[GT2_CAPABILITIES.AGENTS_READ]}>
      <AgentsPage />
    </AuthGuard>
  );
}