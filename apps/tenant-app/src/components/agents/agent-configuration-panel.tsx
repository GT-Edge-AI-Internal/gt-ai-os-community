'use client';

import React, { useState, useCallback, useRef, ChangeEvent, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Settings, User, Palette, Database, Shield, Wrench,
  Plus, X, Upload, Save, RefreshCw, Bot, AlertTriangle,
  Eye, EyeOff, Info, Check, Users, Search, Edit, Trash2
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { slideLeft, staggerContainer, staggerItem, scaleOnHover } from '@/lib/animations/gt-animations';
import { AgentAnimatedIcon } from './agent-animated-icon';
import { InfoHover } from '@/components/ui/info-hover';
import type { EnhancedAgent } from '@/services/agents-enhanced';
import { useModels } from '@/hooks/use-models';
import { getAuthToken } from '@/services/auth';
import { getAvailableVisibilityOptions, canShareToOrganization } from '@/lib/permissions';
import { useCategories, useCreateCategory, useUpdateCategory, useDeleteCategory, type Category } from '@/hooks/use-categories';
import { useTeams } from '@/hooks/use-teams';
import { TeamShareConfiguration, type TeamShare } from '@/components/teams/team-share-configuration';

interface AgentConfigurationPanelProps {
  agent?: EnhancedAgent;
  agents?: EnhancedAgent[];
  isOpen: boolean;
  onClose: () => void;
  onSave: (agent: Partial<EnhancedAgent>) => Promise<void>;
  mode?: 'create' | 'edit' | 'fork';
  className?: string;
}

// Model options now loaded dynamically from useModels hook

export function AgentConfigurationPanel({
  agent,
  agents = [],
  isOpen,
  onClose,
  onSave,
  mode = 'create',
  className
}: AgentConfigurationPanelProps) {
  // State declarations first
  const [isSaving, setIsSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewState, setPreviewState] = useState<'idle' | 'thinking' | 'speaking' | 'success'>('idle');

  // Ref to track latest models data without causing re-renders
  const modelsRef = useRef<any[]>([]);

  // Tenant-scoped categories from API (Issue #215)
  const { data: apiCategories = [], isLoading: categoriesLoading, refetch: refetchCategories } = useCategories();
  const createCategoryMutation = useCreateCategory();
  const updateCategoryMutation = useUpdateCategory();
  const deleteCategoryMutation = useDeleteCategory();

  // Refetch categories when modal opens to pick up newly imported categories
  useEffect(() => {
    if (isOpen) {
      refetchCategories();
    }
  }, [isOpen, refetchCategories]);

  // Custom category creation state
  const [customCategoryDescription, setCustomCategoryDescription] = useState('');

  // Edit category state
  const [editingCategoryId, setEditingCategoryId] = useState<string | null>(null);
  const [editCategoryInput, setEditCategoryInput] = useState('');
  const [editCategoryDescription, setEditCategoryDescription] = useState('');

  // Transform API categories into the format expected by the component
  const categories = React.useMemo(() => {
    // Map API categories to component format
    const categoryItems = apiCategories.map(cat => ({
      id: cat.id,
      value: cat.slug,
      label: cat.name,
      description: cat.description || 'Category',
      icon: cat.icon,
      isDefault: cat.is_default,
      canEdit: cat.can_edit,
      canDelete: cat.can_delete,
      createdBy: cat.created_by,
    }));

    // Sort by label
    return categoryItems.sort((a, b) => a.label.localeCompare(b.label));
  }, [apiCategories]);
  
  // Load available models dynamically
  const { models, selectOptions: modelOptions, isLoading: modelsLoading, isFallback } = useModels();

  // Update models ref whenever models change
  useEffect(() => {
    modelsRef.current = models;
    console.log('🔧 Models updated, count:', models.length);
  }, [models]);

  // Categories are now loaded via useCategories() hook - no manual loading needed

  const [formData, setFormData] = useState<Partial<EnhancedAgent> & {
    memory_type?: string;
    error_handling?: string;
    max_iterations?: number;
    timeout_seconds?: number;
    blockedTermInput?: string;
  }>(() => {
    if (agent) {
      return { ...agent };
    }
    
    return {
      name: '',
      description: '',
      disclaimer: '',
      category: 'general',
      visibility: 'individual',
      featured: false,
      // Enhanced appearance data
      custom_avatar_url: '',
      personality_type: 'minimal',
      personality_profile: {
        colors: {
          primary: '#00d084',
          secondary: '#ffffff',
          accent: '#00d084',
          background: '#ffffff'
        },
        animation: {
          style: 'subtle',
          duration: 1000,
          easing: 'ease-in-out'
        },
        visual: {
          shapes: ['circle'],
          patterns: ['solid'],
          effects: ['none']
        },
        interaction: {
          greeting_style: 'friendly',
          conversation_tone: 'professional',
          response_style: 'helpful'
        }
      },
      // Model settings - no hardcoded fallback, must be set from available models
      model_id: '',
      system_prompt: '',
      model_parameters: {
        temperature: 0.7,
        // max_tokens removed - now determined by model configuration
      },
      tags: [],
      example_prompts: [],
      easy_prompts: [],
      safety_flags: [],
      blocked_terms: [],
      selected_dataset_ids: [],
      require_moderation: false,
      enabled_capabilities: [],
      mcp_integration_ids: [],
      tool_configurations: {},
      can_fork: true,
      collaborator_ids: [],
      // Additional UI state fields
      memory_type: 'conversation',
      error_handling: 'retry',
      max_iterations: 10,
      timeout_seconds: 300,
      blockedTermInput: '',
    };
  });
  
  const [tagInput, setTagInput] = useState('');
  const [examplePromptInput, setExamplePromptInput] = useState('');
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [customCategoryInput, setCustomCategoryInput] = useState('');

  // Team sharing state
  const [teamShares, setTeamShares] = useState<TeamShare[]>([]);
  // Store original team shares to detect changes
  const [originalTeamShares, setOriginalTeamShares] = useState<TeamShare[]>([]);
  // Ref to track latest teamShares (avoids stale state in validation)
  const teamSharesRef = useRef<TeamShare[]>(teamShares);
  const { data: userTeams } = useTeams();

  // Determine if current user is owner (can modify visibility and sharing)
  const isOwner = mode === 'create' || agent?.is_owner || false;

  // Dataset management state
  const [availableDatasets, setAvailableDatasets] = useState<any[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);
  const [datasetSearchQuery, setDatasetSearchQuery] = useState('');
  const datasetsLoadedRef = useRef(false);

  // Sync max tokens input with formData
  useEffect(() => {
    if (formData.model_parameters?.max_tokens) {
      setMaxTokensInput(String(formData.model_parameters.max_tokens));
    }
  }, [formData.model_parameters?.max_tokens]);

  // Track if we've initialized the form to prevent infinite loops
  const initializedRef = useRef(false);

  // Update form data when agent prop changes
  useEffect(() => {
    if (agent) {
      console.log('🔧 Populating form with agent data:', agent);
      console.log('🔧 Agent model_id:', agent.model_id);
      console.log('🔧 Available model options:', modelOptions.map(m => m.value));
      setFormData({
        ...agent,
        // Map backend fields to UI fields
        category: agent.category || 'general',
        visibility: agent.visibility || 'individual',
        personality_type: agent.personality_type || 'minimal',
        model_id: agent.model_id || agent.model || '',
        system_prompt: agent.prompt_template || agent.system_prompt || '', // Map prompt_template to system_prompt
        model_parameters: {
          temperature: agent.temperature || 0.7,
          // max_tokens removed - now determined by model configuration
          ...agent.model_parameters // Override with existing data if available
        },
        disclaimer: agent.disclaimer || '',
        easy_prompts: agent.easy_prompts || [],
        tags: agent.tags || [],
        example_prompts: agent.example_prompts || [],
        blocked_terms: agent.blocked_terms || [],
        selected_dataset_ids: agent.selected_dataset_ids || [],
        enabled_capabilities: agent.enabled_capabilities || [],
        mcp_integration_ids: agent.mcp_integration_ids || [],
        tool_configurations: agent.tool_configurations || {},
        // Ensure personality_profile has proper structure
        personality_profile: {
          colors: {
            primary: '#00d084',
            secondary: '#ffffff',
            accent: '#00d084',
            background: '#ffffff'
          },
          animation: {
            style: 'subtle',
            duration: 1000,
            easing: 'ease-in-out'
          },
          visual: {
            shapes: ['circle'],
            patterns: ['solid'],
            effects: ['none']
          },
          ...agent.personality_profile // Override with existing data if available
        },
        // Default values for missing fields
        memory_type: 'conversation',
        error_handling: 'retry',
        max_iterations: 10,
        timeout_seconds: 300,
        blockedTermInput: '',
      });

      // Initialize team shares from existing agent data
      const initialTeamShares = agent.team_shares || [];
      setTeamShares(initialTeamShares);
      setOriginalTeamShares(initialTeamShares);
      initializedRef.current = true;
    } else if (!agent && !initializedRef.current && mode === 'create' && modelOptions.length > 0) {
      // Reset form for new agent creation only when creating AND not yet initialized AND models loaded
      console.log('🔧 Resetting form for new agent creation');

      // Use first available model for new agents
      const defaultModelId = modelOptions[0].value;

      // Get max_tokens from the default model using ref
      const currentModels = modelsRef.current;
      const defaultModel = currentModels.find(m => m.value === defaultModelId);
      console.log('🔧 New agent - default model:', defaultModelId);

      setFormData({
        name: '',
        description: '',
        disclaimer: '',
        easy_prompts: [],
        category: 'general',
        visibility: 'individual',
        featured: false,
        custom_avatar_url: '',
        personality_type: 'minimal',
        model_id: defaultModelId,
        system_prompt: '',
        model_parameters: {
          temperature: 0.7,
          // max_tokens removed - now determined by model configuration
        },
        tags: [],
        example_prompts: [],
        blocked_terms: [],
        selected_dataset_ids: [],
        require_moderation: false,
        enabled_capabilities: [],
        mcp_integration_ids: [],
        tool_configurations: {},
        can_fork: true,
        collaborator_ids: [],
        memory_type: 'conversation',
        error_handling: 'retry',
        max_iterations: 10,
        timeout_seconds: 300,
        blockedTermInput: '',
      });

      // Reset team shares for new agent
      setTeamShares([]);
      initializedRef.current = true;
    }
  }, [agent, mode]);

  // Separate effect to initialize model when models load (only for new agents)
  useEffect(() => {
    if (!agent && mode === 'create' && !initializedRef.current && modelOptions.length > 0) {
      console.log('🔧 Models loaded, setting default model for new agent');
      const defaultModelId = modelOptions[0].value;
      const currentModels = modelsRef.current;
      const defaultModel = currentModels.find(m => m.value === defaultModelId);
      setFormData(prev => ({
        ...prev,
        model_id: defaultModelId,
        model_parameters: {
          ...prev.model_parameters
          // max_tokens removed - now determined by model configuration
        }
      }));
      initializedRef.current = true;
    }
  }, [agent, mode, modelOptions.length]); // Only depend on length, not the array itself

  // Keep teamSharesRef in sync with teamShares state
  useEffect(() => {
    teamSharesRef.current = teamShares;
  }, [teamShares]);

  const handleInputChange = useCallback((field: string, value: any) => {
    // Auto-clear team shares when switching away from 'team' visibility
    if (field === 'visibility' && value !== 'team') {
      setTeamShares([]);
    }

    if (field === 'model_id') {
      console.log('🔧 Model changed to:', value);

      // Update model_id (max_tokens now determined by model configuration at runtime)
      if (value?.toLowerCase().includes('compound')) {
        setFormData(prev => ({
          ...prev,
          [field]: value,
          selected_dataset_ids: []
        }));
        return;
      }

      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
      return;
    }
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  }, []);

  const handleModelParameterChange = useCallback((param: string, value: number) => {
    setFormData(prev => ({
      ...prev,
      model_parameters: {
        ...prev.model_parameters!,
        [param]: value
      }
    }));
  }, []);

  const handleFileUpload = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    // Validate file
    if (!['image/png', 'image/jpeg', 'image/jpg'].includes(file.type)) {
      alert('Please upload a PNG or JPEG image');
      return;
    }
    
    if (file.size > 2 * 1024 * 1024) {
      alert('Image must be less than 2MB');
      return;
    }
    
    // Convert to base64
    const reader = new FileReader();
    reader.onload = (e) => {
      setFormData(prev => ({
        ...prev,
        custom_avatar_url: e.target?.result as string
      }));
    };
    reader.readAsDataURL(file);
  }, []);

  // Load available datasets with proper user access control
  const loadDatasets = useCallback(async () => {
    if (isLoadingDatasets) return;

    // Only prevent loading if already loaded AND we have datasets
    if (datasetsLoadedRef.current && availableDatasets.length > 0) return;

    setIsLoadingDatasets(true);
    try {
      const token = getAuthToken();
      if (!token) {
        console.warn('No auth token available for loading datasets');
        setAvailableDatasets([]);
        return;
      }

      console.log('Loading datasets for agent configuration...');

      const response = await fetch('/api/v1/datasets/', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
          'X-Tenant-Domain': window.location.hostname
        }
      });

      if (response.ok) {
        const datasets = await response.json();
        console.log(`✅ Successfully loaded ${datasets.length} datasets for user:`, datasets);

        // Validate dataset structure
        const validDatasets = datasets.filter(dataset => {
          const isValid = dataset && dataset.id && dataset.name;
          if (!isValid) {
            console.warn('⚠️  Invalid dataset structure:', dataset);
          }
          return isValid;
        });

        setAvailableDatasets(validDatasets);
        datasetsLoadedRef.current = true;

        if (validDatasets.length !== datasets.length) {
          console.warn(`⚠️  Filtered out ${datasets.length - validDatasets.length} invalid datasets`);
        }
      } else {
        console.error(`❌ Failed to load datasets: ${response.status} ${response.statusText}`);
        console.error(`🌐 Request URL: /api/v1/datasets/`);
        console.error(`🔑 Auth token present: ${!!token}`);

        // Try to get error details - only read the response once
        try {
          const errorText = await response.text();
          console.error('📄 Raw error response:', errorText);

          // Try to parse as JSON if possible
          try {
            const errorData = JSON.parse(errorText);
            console.error('📄 Parsed error details:', errorData);
          } catch (parseError) {
            console.error('📄 Error response is not JSON');
          }
        } catch (readError) {
          console.error('📄 Could not read error response:', readError);
        }
        setAvailableDatasets([]);
      }
    } catch (error) {
      console.error('Failed to load datasets:', error);
      setAvailableDatasets([]);
    } finally {
      setIsLoadingDatasets(false);
    }
  }, [availableDatasets.length]);

  // Load datasets when modal is opened
  useEffect(() => {
    if (isOpen && availableDatasets.length === 0) {
      loadDatasets();
    }

    // Reset when closed so it can load again when reopened
    if (!isOpen) {
      datasetsLoadedRef.current = false;
    }
  }, [isOpen, loadDatasets, availableDatasets.length]);

  // Filter datasets based on search query
  const filteredDatasets = availableDatasets.filter(dataset => {
    if (!datasetSearchQuery) return true;

    const searchLower = datasetSearchQuery.toLowerCase();
    return (
      dataset.name.toLowerCase().includes(searchLower) ||
      (dataset.description && dataset.description.toLowerCase().includes(searchLower))
    );
  });

  const handleAddTag = useCallback(() => {
    if (tagInput.trim() && !(formData.tags || []).includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...(prev.tags || []), tagInput.trim()]
      }));
      setTagInput('');
    }
  }, [tagInput, formData.tags]);

  const handleRemoveTag = useCallback((tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: (prev.tags || []).filter(tag => tag !== tagToRemove)
    }));
  }, []);

  const handleAddExamplePrompt = useCallback(() => {
    if (examplePromptInput.trim()) {
      setFormData(prev => ({
        ...prev,
        example_prompts: [
          ...(prev.example_prompts || []),
          examplePromptInput.trim()
        ]
      }));
      setExamplePromptInput('');
    }
  }, [examplePromptInput]);

  const handleCreateCustomCategory = useCallback(async () => {
    const trimmedCategory = customCategoryInput.trim();
    const trimmedDescription = customCategoryDescription.trim();

    if (trimmedCategory) {
      // Validate: not empty, not already exists (case-insensitive check)
      if (categories.find(c => c.label.toLowerCase() === trimmedCategory.toLowerCase())) {
        alert('This category already exists. Please choose a different name.');
        return;
      }

      try {
        // Create new category via API mutation
        const result = await createCategoryMutation.mutateAsync({
          name: trimmedCategory,
          description: trimmedDescription || undefined,
        });

        // Select the new category (use slug from API response)
        if (result?.slug) {
          handleInputChange('category', result.slug);
        }

        // Reset state
        setIsCreatingCategory(false);
        setCustomCategoryInput('');
        setCustomCategoryDescription('');
      } catch (error) {
        console.error('Failed to create category:', error);
        alert('Failed to create category. Please try again.');
      }
    }
  }, [customCategoryInput, customCategoryDescription, categories, createCategoryMutation, handleInputChange]);

  const handleCancelCustomCategory = useCallback(() => {
    setIsCreatingCategory(false);
    setCustomCategoryInput('');
    setCustomCategoryDescription('');
  }, []);

  const handleEditCategory = useCallback((categoryId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    const category = categories.find(c => c.id === categoryId);
    if (!category) return;

    // Enter edit mode
    setEditingCategoryId(categoryId);
    setEditCategoryInput(category.label);
    setEditCategoryDescription(category.description);
  }, [categories]);

  const handleSaveEditCategory = useCallback(async () => {
    if (!editingCategoryId) return;

    const trimmedName = editCategoryInput.trim();
    const trimmedDescription = editCategoryDescription.trim();

    if (!trimmedName) {
      alert('Category name cannot be empty');
      return;
    }

    // Get the current category being edited
    const currentCategory = categories.find(c => c.id === editingCategoryId);
    if (!currentCategory) return;

    // Check for duplicates (case-insensitive, excluding current category)
    if (categories.some(c =>
      c.label.toLowerCase() === trimmedName.toLowerCase() &&
      c.id !== editingCategoryId
    )) {
      alert('A category with this name already exists');
      return;
    }

    try {
      // Update via API mutation
      const result = await updateCategoryMutation.mutateAsync({
        categoryId: editingCategoryId,
        data: {
          name: trimmedName,
          description: trimmedDescription || undefined,
        },
      });

      // Update selected category if it was the one being edited
      if (formData.category === currentCategory.value && result?.slug) {
        handleInputChange('category', result.slug);
      }

      // Exit edit mode
      setEditingCategoryId(null);
      setEditCategoryInput('');
      setEditCategoryDescription('');
    } catch (error) {
      console.error('Failed to update category:', error);
      alert('Failed to update category. Please try again.');
    }
  }, [editingCategoryId, editCategoryInput, editCategoryDescription, categories, formData.category, updateCategoryMutation, handleInputChange]);

  const handleCancelEditCategory = useCallback(() => {
    setEditingCategoryId(null);
    setEditCategoryInput('');
    setEditCategoryDescription('');
  }, []);

  const handleDeleteCategory = useCallback(async (categoryId: string, categoryLabel: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (!confirm(`Are you sure you want to delete the "${categoryLabel}" category?`)) return;

    try {
      // Get the category being deleted
      const category = categories.find(c => c.id === categoryId);

      // Delete via API mutation
      await deleteCategoryMutation.mutateAsync(categoryId);

      // Reset category selection if deleted category was selected
      if (category && formData.category === category.value) {
        handleInputChange('category', 'general');
      }
    } catch (error) {
      console.error('Failed to delete category:', error);
      alert('Failed to delete category. Please try again.');
    }
  }, [categories, formData.category, deleteCategoryMutation, handleInputChange]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      // Validate required fields
      if (!formData.model_id) {
        alert('Please select a model for the agent.');
        setIsSaving(false);
        return;
      }

      // Remove UI-only fields from the data before saving
      const { memory_type, error_handling, max_iterations, timeout_seconds, blockedTermInput, ...agentData } = formData;

      // Validate team shares if visibility is 'team'
      if (formData.visibility === 'team') {
        // Use ref to get latest state (avoids React batching delays)
        if (teamSharesRef.current.length === 0) {
          alert('Please select at least one team when visibility is set to "Team".');
          setIsSaving(false);
          return;
        }
      }

      // Detect if team_shares has changed (to avoid overwriting fine-grained permissions)
      const teamSharesChanged = JSON.stringify(teamSharesRef.current) !== JSON.stringify(originalTeamShares);

      // Include team_shares only if:
      // 1. Creating new agent (mode === 'create'), OR
      // 2. Editing and team_shares was modified
      const shouldIncludeTeamShares =
        (mode === 'create' && formData.visibility === 'team') ||
        (mode === 'edit' && formData.visibility === 'team' && teamSharesChanged);

      const dataToSave = {
        ...agentData,
        ...(shouldIncludeTeamShares ? { team_shares: teamSharesRef.current } : {})
      };
      await onSave(dataToSave);
      onClose();
    } catch (error: any) {
      console.error('Failed to save agent:', error);

      // Extract specific error message from backend
      let errorMessage = 'Failed to save agent. Please try again.';
      if (error?.response?.data?.detail) {
        // Backend validation error (e.g., "Must select at least one team...")
        errorMessage = error.response.data.detail;
      } else if (error?.message) {
        // Network or other error
        errorMessage = `Error: ${error.message}`;
      }

      alert(errorMessage);
    } finally {
      setIsSaving(false);
    }
  }, [formData, onSave, onClose, originalTeamShares, mode]);

  const handleClose = () => {
    initializedRef.current = false; // Reset for next open
    onClose();
  };

  console.log('🎨 AgentConfigurationPanel render, isOpen:', isOpen);

  if (!isOpen) {
    return null;
  }

  if (typeof window === 'undefined') {
    return null;
  }

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="backdrop"
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[999]"
        style={{ 
          position: 'fixed',
          top: 0, 
          left: 0, 
          right: 0, 
          bottom: 0,
          margin: 0,
          padding: 0
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={handleClose}
      />
      
      <motion.div
        key="panel"
        className={cn(
          "fixed right-0 top-0 h-screen w-full max-w-4xl bg-gt-white shadow-2xl z-[1000]",
          className
        )}
        style={{ 
          position: 'fixed',
          top: 0, 
          right: 0, 
          height: '100vh',
          margin: 0,
          padding: 0
        }}
        variants={slideLeft}
        initial="initial"
        animate="animate"
        exit="exit"
      >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">
                  {mode === 'create' ? 'Create Agent' : 
                   mode === 'fork' ? 'Fork Agent' : 'Edit Agent'}
                </h2>
                <p className="text-gray-600 mt-1">
                  Configure your AI Agent's appearance, capabilities and behavior
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={handleClose}
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={
                    isSaving ||
                    !formData.name?.trim() ||
                    (formData.visibility === 'team' && teamShares.length === 0)
                  }
                  className="bg-gt-green hover:bg-gt-green/90"
                >
                  {isSaving ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      {mode === 'create' ? 'Create Agent' : 'Save Changes'}
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Content */}
            <div className="flex h-[calc(100%-88px)]">
              {/* Single Scrollable Form */}
              <div className="flex-1 p-6 overflow-y-auto">
                <div className="max-w-2xl mx-auto space-y-6">
                  {/* Basic Info Section */}
                  <div>
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <CardTitle>Basic Information</CardTitle>
                            <CardDescription>
                              Define the core identity and purpose of your agent
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="name">Agent Name *</Label>
                              <Input
                                id="name"
                                value={formData.name || ''}
                                onChange={(value) => handleInputChange('name', typeof value === 'string' ? value : value.target.value)}
                                placeholder="Enter agent name"
                                className="text-lg text-gray-900"
                              />
                            </div>
                            
                            <div className="space-y-2">
                              <Label htmlFor="description">Description *</Label>
                              <Textarea
                                id="description"
                                value={formData.description || ''}
                                onChange={(value) => handleInputChange('description', typeof value === 'string' ? value : value.target.value)}
                                placeholder="Describe what this agent does and how it can help users"
                                rows={3}
                                className="text-gray-900"
                              />
                            </div>
                            
                            <div className="grid grid-cols-2 gap-4">
                              <div className="space-y-2">
                                <Label htmlFor="category">Category</Label>
                                {editingCategoryId ? (
                                  // Edit category mode
                                  <div className="space-y-3">
                                    <div className="space-y-2">
                                      <Label>Category Name *</Label>
                                      <Input
                                        value={editCategoryInput}
                                        onChange={(value) => setEditCategoryInput(typeof value === 'string' ? value : value.target.value)}
                                        placeholder="Enter category name..."
                                        autoFocus
                                        clearable
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            handleSaveEditCategory();
                                          }
                                          if (e.key === 'Escape') {
                                            e.preventDefault();
                                            handleCancelEditCategory();
                                          }
                                        }}
                                      />
                                    </div>
                                    <div className="space-y-2">
                                      <Label>Description</Label>
                                      <Textarea
                                        value={editCategoryDescription}
                                        onChange={(value) => setEditCategoryDescription(typeof value === 'string' ? value : value.target.value)}
                                        placeholder="Describe what this category is for..."
                                        rows={2}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            handleSaveEditCategory();
                                          }
                                          if (e.key === 'Escape') {
                                            e.preventDefault();
                                            handleCancelEditCategory();
                                          }
                                        }}
                                      />
                                    </div>
                                    <div className="flex gap-2 justify-end">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleCancelEditCategory}
                                      >
                                        Cancel
                                      </Button>
                                      <Button
                                        size="sm"
                                        onClick={handleSaveEditCategory}
                                        disabled={!editCategoryInput.trim()}
                                        className="bg-gt-green hover:bg-gt-green/90"
                                      >
                                        <Save className="w-4 h-4 mr-2" />
                                        Save Changes
                                      </Button>
                                    </div>
                                    <p className="text-xs text-gray-500">
                                      Press Enter to save or Escape to cancel
                                    </p>
                                  </div>
                                ) : isCreatingCategory ? (
                                  // Custom category creation mode
                                  <div className="space-y-3">
                                    <div className="space-y-2">
                                      <Label>Category Name *</Label>
                                      <Input
                                        value={customCategoryInput}
                                        onChange={(value) => setCustomCategoryInput(typeof value === 'string' ? value : value.target.value)}
                                        placeholder="Enter custom category name..."
                                        autoFocus
                                        clearable
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            handleCreateCustomCategory();
                                          }
                                          if (e.key === 'Escape') {
                                            e.preventDefault();
                                            handleCancelCustomCategory();
                                          }
                                        }}
                                      />
                                    </div>
                                    <div className="space-y-2">
                                      <Label>Description</Label>
                                      <Textarea
                                        value={customCategoryDescription}
                                        onChange={(value) => setCustomCategoryDescription(typeof value === 'string' ? value : value.target.value)}
                                        placeholder="Describe what this category is for..."
                                        rows={2}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter' && !e.shiftKey) {
                                            e.preventDefault();
                                            handleCreateCustomCategory();
                                          }
                                          if (e.key === 'Escape') {
                                            e.preventDefault();
                                            handleCancelCustomCategory();
                                          }
                                        }}
                                      />
                                    </div>
                                    <div className="flex gap-2 justify-end">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleCancelCustomCategory}
                                      >
                                        Cancel
                                      </Button>
                                      <Button
                                        size="sm"
                                        onClick={handleCreateCustomCategory}
                                        disabled={!customCategoryInput.trim()}
                                        className="bg-gt-green hover:bg-gt-green/90"
                                      >
                                        <Plus className="w-4 h-4 mr-2" />
                                        Create Category
                                      </Button>
                                    </div>
                                    <p className="text-xs text-gray-500">
                                      Press Enter to create or Escape to cancel
                                    </p>
                                  </div>
                                ) : (
                                  // Normal select mode
                                  <Select
                                    value={formData.category}
                                    onValueChange={(value) => {
                                      if (value === '__create_new__') {
                                        setIsCreatingCategory(true);
                                      } else {
                                        handleInputChange('category', value);
                                      }
                                    }}
                                  >
                                    <SelectTrigger className="h-auto min-h-[40px] items-start py-2">
                                      <SelectValue className="whitespace-normal text-left" />
                                    </SelectTrigger>
                                    <SelectContent>
                                      {categories.map((cat) => (
                                        <SelectItem key={cat.id || cat.value} value={cat.value}>
                                          <div className="flex items-start justify-between w-full gap-2">
                                            <div className="flex-1 min-w-0">
                                              <div className="font-medium">{cat.label}</div>
                                              <div className="text-xs text-gray-600">{cat.description}</div>
                                            </div>
                                            {(cat.canEdit || cat.canDelete) && (
                                              <div className="flex gap-1 ml-2 pointer-events-auto">
                                                {cat.canEdit && (
                                                  <button
                                                    onPointerDown={(e) => {
                                                      e.stopPropagation();
                                                      e.preventDefault();
                                                      handleEditCategory(cat.id, e);
                                                    }}
                                                    className="p-1 hover:bg-blue-100 rounded text-blue-600"
                                                    title="Edit category"
                                                  >
                                                    <Edit className="w-3 h-3" />
                                                  </button>
                                                )}
                                                {cat.canDelete && (
                                                  <button
                                                    onPointerDown={(e) => {
                                                      e.stopPropagation();
                                                      e.preventDefault();
                                                      handleDeleteCategory(cat.id, cat.label, e);
                                                    }}
                                                    className="p-1 hover:bg-red-100 rounded text-red-600"
                                                    title="Delete category"
                                                  >
                                                    <Trash2 className="w-3 h-3" />
                                                  </button>
                                                )}
                                              </div>
                                            )}
                                          </div>
                                        </SelectItem>
                                      ))}
                                      {/* Separator and create new option */}
                                      <div className="border-t my-1" />
                                      <SelectItem value="__create_new__">
                                        <div className="flex items-center gap-2 text-gt-green font-medium">
                                          <Plus className="w-4 h-4" />
                                          <span>Create New Category...</span>
                                        </div>
                                      </SelectItem>
                                    </SelectContent>
                                  </Select>
                                )}
                              </div>
                              
                              <div className="space-y-2">
                                <Label htmlFor="visibility">Visibility</Label>
                                <Select
                                  value={formData.visibility}
                                  onValueChange={(value) => handleInputChange('visibility', value)}
                                  disabled={!isOwner}
                                >
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="individual">
                                      <div className="flex items-center gap-2">
                                        <EyeOff className="w-4 h-4" />
                                        <span>Individual</span>
                                      </div>
                                      <div className="text-xs text-gray-600">Only you can access and edit this agent</div>
                                    </SelectItem>
                                    <SelectItem value="team">
                                      <div className="flex items-center gap-2">
                                        <Users className="w-4 h-4" />
                                        <span>Team</span>
                                      </div>
                                      <div className="text-xs text-gray-600">Share with specific teams and set permissions</div>
                                    </SelectItem>
                                    {canShareToOrganization() && (
                                      <SelectItem value="organization">
                                        <div className="flex items-center gap-2">
                                          <Eye className="w-4 h-4" />
                                          <span>Organization</span>
                                        </div>
                                        <div className="text-xs text-gray-600">All users can read, only admins can edit</div>
                                      </SelectItem>
                                    )}
                                  </SelectContent>
                                </Select>
                              </div>

                              {/* Team Sharing Configuration */}
                              {formData.visibility === 'team' && (
                                <div className="mt-4 pt-4 border-t">
                                  <TeamShareConfiguration
                                    userTeams={userTeams || []}
                                    value={teamShares}
                                    onChange={setTeamShares}
                                    disabled={!isOwner}
                                  />

                                  {/* Validation Warning: Team visibility but no teams selected */}
                                  {isOwner && teamShares.length === 0 && (
                                    <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-md">
                                      <div className="flex items-start gap-2">
                                        <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                        </svg>
                                        <div className="flex-1">
                                          <p className="text-sm font-medium text-amber-800">Team visibility requires team selection</p>
                                          <p className="text-sm text-amber-700 mt-1">
                                            Please select at least one team to share this agent with, or change the visibility setting.
                                          </p>
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </CardContent>
                        </Card>

                        {/* Disclaimer Card */}
                        <Card>
                          <CardHeader>
                            <div className="flex items-center gap-2">
                              <CardTitle>Disclaimer</CardTitle>
                              <InfoHover content="Add a disclaimer message that will be shown to users when they start chatting with this Agent. This can include usage guidelines, limitations or important information users should know." />
                            </div>
                            <CardDescription>
                              Optional message displayed in chat interface
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="disclaimer">Disclaimer Message</Label>
                              <Textarea
                                id="disclaimer"
                                value={formData.disclaimer || ''}
                                onChange={(e) => handleInputChange('disclaimer', e.target.value)}
                                placeholder="This Agent is designed for [specific purpose]. Please note [any limitations or guidelines]..."
                                rows={3}
                                maxLength={500}
                                className="text-gray-900"
                              />
                              <div className="flex justify-between text-xs text-gray-500">
                                <span>Maximum 500 characters</span>
                                <span>{(formData.disclaimer || '').length}/500</span>
                              </div>
                            </div>
                          </CardContent>
                        </Card>

                        {/* Easy Buttons Card */}
                        <Card>
                          <CardHeader>
                            <div className="flex items-center gap-2">
                              <CardTitle>Easy Buttons</CardTitle>
                              <InfoHover content="Create up to 10 preset prompts that users can click to quickly populate the chat input. These buttons appear in the chat interface for easy access to common queries or tasks." />
                            </div>
                            <CardDescription>
                              Quick-access preset prompts (max 10)
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-3">
                              {(formData.easy_prompts || []).map((prompt, index) => (
                                <div key={index} className="flex gap-2 items-start">
                                  <Textarea
                                    value={prompt}
                                    onChange={(e) => {
                                      const newPrompts = [...(formData.easy_prompts || [])];
                                      newPrompts[index] = e.target.value;
                                      handleInputChange('easy_prompts', newPrompts);
                                    }}
                                    placeholder={`Prompt ${index + 1}`}
                                    className="flex-1 min-h-[38px]"
                                    rows={1}
                                    resizable
                                  />
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => {
                                      const newPrompts = (formData.easy_prompts || []).filter((_, i) => i !== index);
                                      handleInputChange('easy_prompts', newPrompts);
                                    }}
                                  >
                                    <X className="w-4 h-4" />
                                  </Button>
                                </div>
                              ))}

                              {(!formData.easy_prompts || formData.easy_prompts.length < 10) && (
                                <Button
                                  variant="outline"
                                  onClick={() => {
                                    const newPrompts = [...(formData.easy_prompts || []), ''];
                                    handleInputChange('easy_prompts', newPrompts);
                                  }}
                                  className="w-full"
                                >
                                  <Plus className="w-4 h-4 mr-2" />
                                  Add Easy Button
                                </Button>
                              )}

                              {formData.easy_prompts && formData.easy_prompts.length >= 10 && (
                                <p className="text-sm text-gray-500 text-center">
                                  Maximum of 10 prompts reached
                                </p>
                              )}
                            </div>
                          </CardContent>
                        </Card>

                        {/* Tags Card */}
                        <Card>
                          <CardHeader>
                            <CardTitle>Tags & Organization</CardTitle>
                            <CardDescription>
                              Add tags to help organize and find your agent
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <Label>Tags</Label>
                              <div className="flex space-x-2">
                                <Input
                                  value={tagInput}
                                  onChange={(value) => setTagInput(typeof value === 'string' ? value : value.target.value)}
                                  placeholder="Add tag"
                                  onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
                                  className="text-gray-900"
                                  clearable
                                />
                                <Button
                                  type="button"
                                  variant="secondary"
                                  size="sm"
                                  onClick={handleAddTag}
                                >
                                  <Plus className="h-4 w-4" />
                                </Button>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {(formData.tags || []).map((tag) => (
                                  <Badge key={tag} variant="secondary" className="text-xs">
                                    {tag}
                                    <button
                                      onClick={() => handleRemoveTag(tag)}
                                      className="ml-1 text-gray-500 hover:text-red-500"
                                    >
                                      <X className="h-3 w-3" />
                                    </button>
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </div>

                    {/* Model & Prompt Section */}
                    <div>
                      <motion.div variants={staggerItem} className="space-y-6">
                        {/* AI Model Selection - Now appears FIRST */}
                        <Card>
                          <CardHeader>
                            <div className="flex items-center gap-2">
                              <CardTitle>LLM Configuration</CardTitle>
                              <InfoHover content="Choose the LLM that you wish to use for your Agent" />
                            </div>
                            <CardDescription>
                              Choose the LLM that you wish to use for your agent
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between">
                                <Label htmlFor="model_id">AI Model</Label>
                                {isFallback && (
                                  <div className="flex items-center gap-1 text-xs text-amber-600">
                                    <AlertTriangle className="w-3 h-3" />
                                    Using fallback models
                                  </div>
                                )}
                              </div>
                              <Select
                                value={formData.model_id}
                                onValueChange={(value) => handleInputChange('model_id', value)}
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {modelsLoading ? (
                                    <SelectItem value="loading" disabled>
                                      <div className="font-medium">Loading models...</div>
                                    </SelectItem>
                                  ) : (
                                    modelOptions.map((model) => (
                                      <SelectItem key={model.value} value={model.value}>
                                        <div className="flex items-start justify-between w-full min-w-0">
                                          <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                              <span className="font-medium truncate">{model.label}</span>
                                            </div>
                                          </div>
                                        </div>
                                      </SelectItem>
                                    ))
                                  )}
                                </SelectContent>
                              </Select>
                              {!modelsLoading && modelOptions.length === 0 && (
                                <div className="text-sm text-gray-500 bg-gray-50 p-3 rounded-lg">
                                  <div className="flex items-center gap-2">
                                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                                    No models available. Please contact your administrator.
                                  </div>
                                </div>
                              )}

                              {/* Token Limits Display */}
                              {formData.model_id && !modelsLoading && (
                                <div className="mt-4 pt-4 border-t border-gray-200">
                                  <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                      <p className="text-xs font-semibold text-gray-600">Max Context (Input Tokens + Output Tokens)</p>
                                      <p className="text-sm font-medium text-gray-900">
                                        {(() => {
                                          const selectedModel = modelsRef.current.find(m => m.value === formData.model_id);
                                          return (selectedModel?.context_window || 'N/A').toLocaleString();
                                        })()}
                                      </p>
                                    </div>
                                    <div className="space-y-1">
                                      <p className="text-xs font-semibold text-gray-600">Max Output Tokens</p>
                                      <p className="text-sm font-medium text-gray-900">
                                        {(() => {
                                          const selectedModel = modelsRef.current.find(m => m.value === formData.model_id);
                                          return (selectedModel?.max_tokens || 'N/A').toLocaleString();
                                        })()}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Generation Parameters Subsection */}
                            <div className="mt-6 pt-6 border-t border-gray-200 space-y-3">
                              <div className="flex items-center gap-2 mb-3">
                                <h4 className="text-base font-semibold text-gray-900">Generation Parameters</h4>
                                <InfoHover content="Configure aspects of how the LLM responds to your prompt" />
                              </div>

                              {/* Temperature */}
                              <div className="space-y-3">
                                <div className="flex items-center gap-3">
                                  <Label>Temperature</Label>
                                  <Input
                                    type="number"
                                    min={0}
                                    max={2}
                                    step={0.01}
                                    value={formData.model_parameters?.temperature || 0.7}
                                    onChange={(inputValue: string) => {
                                      if (inputValue === '') return; // Allow clearing
                                      const value = parseFloat(inputValue);
                                      if (!isNaN(value) && value >= 0 && value <= 2) {
                                        handleModelParameterChange('temperature', value);
                                      }
                                    }}
                                    className="w-24 h-8 text-sm text-right ml-auto"
                                  />
                                </div>
                                <p className="text-xs text-gray-600">
                                  Controls inference response randomness: 0 = focused, 2 = creative
                                </p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>

                        {/* System Prompt - Now appears SECOND */}
                        <Card>
                          <CardHeader>
                            <div className="flex items-center gap-2">
                              <CardTitle>System Prompt</CardTitle>
                              <InfoHover content="Configure your Agent's guardrails, behavior, persona and response style" />
                            </div>
                            <CardDescription>
                              Configure your Agent's guardrails, behavior, persona and response style
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="system_prompt">System Prompt *</Label>
                              <Textarea
                                id="system_prompt"
                                value={formData.system_prompt || ''}
                                onChange={(value) => handleInputChange('system_prompt', typeof value === 'string' ? value : value.target.value)}
                                placeholder="You are a helpful AI Agent..."
                                rows={8}
                                className="font-mono text-sm text-gray-900 bg-gt-white"
                              />
                            </div>
                          </CardContent>
                        </Card>

                      </motion.div>
                    </div>

                    {/* Datasets Section */}
                    <div>
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <div className="flex items-center gap-2">
                              <CardTitle>Dataset Selection</CardTitle>
                              <InfoHover content="Select dataset(s) that your Agent can use as needed" />
                            </div>
                            <CardDescription>
                              Select dataset(s) that your Agent can use as needed
                            </CardDescription>
                            {formData.model_id?.toLowerCase().includes('compound') && (
                              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                                <div className="flex items-start space-x-2">
                                  <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                                  <p className="text-sm text-amber-800">
                                    Dataset selection is disabled because the selected model (groq/compound) does not support tool calling required for RAG functionality.
                                  </p>
                                </div>
                              </div>
                            )}
                          </CardHeader>
                          <CardContent className="space-y-6">
                            <div className="space-y-4">

                              {/* Selected datasets badges */}
                              {formData.selected_dataset_ids && formData.selected_dataset_ids.length > 0 && (
                                <div className="space-y-2">
                                  <div className="text-sm text-gray-600">
                                    {formData.selected_dataset_ids.length} dataset{formData.selected_dataset_ids.length !== 1 ? 's' : ''} selected
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {formData.selected_dataset_ids.map((datasetId) => {
                                      const dataset = availableDatasets.find(d => d.id === datasetId);
                                      return (
                                        <Badge
                                          key={datasetId}
                                          variant="secondary"
                                          className="flex items-center gap-1"
                                        >
                                          <Database className="w-3 h-3" />
                                          {dataset?.name || datasetId}
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-4 w-4 p-0 hover:bg-red-100 ml-1"
                                            onClick={() => {
                                              handleInputChange('selected_dataset_ids',
                                                formData.selected_dataset_ids?.filter(id => id !== datasetId) || []
                                              );
                                            }}
                                          >
                                            <X className="w-3 h-3" />
                                          </Button>
                                        </Badge>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}

                              {/* Dataset selection interface */}
                              <div className="border rounded-lg p-4 space-y-3">
                                {/* Search */}
                                <div className="relative">
                                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                  <input
                                    type="text"
                                    placeholder="Search datasets..."
                                    value={datasetSearchQuery}
                                    onChange={(e) => setDatasetSearchQuery(e.target.value)}
                                    className="w-full pl-10 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500"
                                  />
                                </div>

                                {/* Controls */}
                                {filteredDatasets.length > 0 && (
                                  <div className="flex items-center justify-between">
                                    <div className="flex gap-2">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={formData.model_id?.toLowerCase().includes('compound')}
                                        onClick={() => {
                                          handleInputChange('selected_dataset_ids', filteredDatasets.map(d => d.id));
                                        }}
                                      >
                                        Select All {datasetSearchQuery && `(${filteredDatasets.length})`}
                                      </Button>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        disabled={formData.model_id?.toLowerCase().includes('compound')}
                                        onClick={() => {
                                          handleInputChange('selected_dataset_ids', []);
                                        }}
                                      >
                                        Clear All
                                      </Button>
                                    </div>
                                    <div className="text-sm text-gray-600">
                                      {filteredDatasets.length} {datasetSearchQuery ? 'found' : 'available'}
                                    </div>
                                  </div>
                                )}

                                {/* Dataset list */}
                                <div className="max-h-64 overflow-y-auto space-y-2">
                                  {isLoadingDatasets ? (
                                    <div className="p-4 text-center text-sm text-gray-500">
                                      <Database className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                                      Loading datasets...
                                    </div>
                                  ) : availableDatasets.length === 0 ? (
                                    <div className="p-4 text-center text-sm text-gray-500">
                                      <Database className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                                      No datasets available
                                    </div>
                                  ) : filteredDatasets.length === 0 ? (
                                    <div className="p-4 text-center text-sm text-gray-500">
                                      <Database className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                                      No datasets match your search
                                    </div>
                                  ) : (
                                    filteredDatasets.map((dataset) => (
                                      <div
                                        key={dataset.id}
                                        className={cn(
                                          "flex items-center gap-3 p-3 border rounded-lg",
                                          formData.model_id?.toLowerCase().includes('compound')
                                            ? "opacity-50 cursor-not-allowed"
                                            : "hover:bg-gray-50 cursor-pointer"
                                        )}
                                        onClick={() => {
                                          if (formData.model_id?.toLowerCase().includes('compound')) return;
                                          const currentIds = formData.selected_dataset_ids || [];
                                          if (currentIds.includes(dataset.id)) {
                                            handleInputChange('selected_dataset_ids', currentIds.filter(id => id !== dataset.id));
                                          } else {
                                            handleInputChange('selected_dataset_ids', [...currentIds, dataset.id]);
                                          }
                                        }}
                                      >
                                        <Checkbox
                                          checked={(formData.selected_dataset_ids || []).includes(dataset.id)}
                                          disabled={formData.model_id?.toLowerCase().includes('compound')}
                                          onChange={() => {}} // Handled by parent onClick
                                        />
                                        <div className="flex-1 min-w-0">
                                          <div className="text-sm font-medium text-gray-900 truncate">
                                            {dataset.name}
                                          </div>
                                          {dataset.description && (
                                            <div className="text-xs text-gray-600 truncate">
                                              {dataset.description}
                                            </div>
                                          )}
                                          <div className="text-xs text-gray-500 mt-1">
                                            {dataset.document_count || 0} documents
                                          </div>
                                        </div>
                                      </div>
                                    ))
                                  )}
                                </div>
                              </div>
                            </div>

                          </CardContent>
                        </Card>
                      </motion.div>
                    </div>

                </div>
              </div>
            </div>
          </motion.div>

    </AnimatePresence>,
    document.body
  );
}