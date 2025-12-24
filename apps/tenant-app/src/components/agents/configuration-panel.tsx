/**
 * @deprecated This component is deprecated. Use AgentConfigurationPanel from agent-configuration-panel.tsx instead.
 *
 * This legacy component lacks team sharing integration and should not be used for new development.
 * It is kept for reference only and may be removed in a future version.
 */

'use client';

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AgentAvatar } from './agent-avatar';
import {
  Settings, User, Brain, Database, Shield, Wrench, 
  Plus, X, Upload, AlertTriangle, Eye, EyeOff,
  Info, Check, Save, RefreshCw
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { slideUp, staggerContainer, staggerItem, scaleOnHover } from '@/lib/animations/gt-animations';
import { useEnhancedAgentStore } from '@/stores/agent-enhanced-store';
import type { PersonalityType, EnhancedAgent, AgentCategory, Visibility, DatasetConnection } from '@/stores/agent-enhanced-store';

interface ConfigurationPanelProps {
  agent?: EnhancedAgent;
  isOpen: boolean;
  onClose: () => void;
  onSave: (agent: Partial<EnhancedAgent>) => Promise<void>;
  mode?: 'create' | 'edit' | 'fork';
  className?: string;
}

const categories: Array<{ value: AgentCategory; label: string; description: string }> = [
  { value: 'general', label: 'General', description: 'All-purpose agent for various tasks' },
  { value: 'coding', label: 'Coding', description: 'Programming and development assistance' },
  { value: 'writing', label: 'Writing', description: 'Content creation and editing' },
  { value: 'analysis', label: 'Analysis', description: 'Data analysis and insights' },
  { value: 'creative', label: 'Creative', description: 'Creative projects and brainstorming' },
  { value: 'research', label: 'Research', description: 'Research and fact-checking' },
  { value: 'business', label: 'Business', description: 'Business strategy and operations' },
  { value: 'education', label: 'Education', description: 'Teaching and learning assistance' },
  { value: 'custom', label: 'Custom', description: 'Custom category defined by you' }
];

const personalities: Array<{ value: PersonalityType; label: string; description: string }> = [
  { value: 'minimal', label: 'Minimal', description: 'Clean, straightforward, and focused' },
  { value: 'organic', label: 'Organic', description: 'Flowing, adaptive, and natural' },
  { value: 'geometric', label: 'Geometric', description: 'Structured, precise, and methodical' },
  { value: 'technical', label: 'Technical', description: 'Data-driven, analytical, and systematic' }
];

const safetyOptions = [
  { value: 'hate_speech', label: 'Hate Speech', description: 'Filter harmful or discriminatory content' },
  { value: 'violence', label: 'Violence', description: 'Block violent or harmful instructions' },
  { value: 'self_harm', label: 'Self-harm', description: 'Prevent self-harm related content' },
  { value: 'harassment', label: 'Harassment', description: 'Block harassment or bullying' },
  { value: 'illegal_activities', label: 'Illegal Activities', description: 'Prevent illegal instruction requests' },
  { value: 'adult_content', label: 'Adult Content', description: 'Filter mature or explicit content' },
  { value: 'misinformation', label: 'Misinformation', description: 'Prevent spread of false information' }
];

const modelOptions = [
  { value: 'gpt-4o', label: 'GPT-4o', description: 'Latest and most capable model' },
  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo', description: 'Fast and efficient reasoning' },
  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo', description: 'Quick responses, lower cost' },
  { value: 'claude-3-opus', label: 'Claude 3 Opus', description: 'Excellent for complex analysis' },
  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet', description: 'Balanced performance' },
  { value: 'llama-3-70b', label: 'Llama 3 70B', description: 'Open source alternative' }
];

export function ConfigurationPanel({
  agent,
  isOpen,
  onClose,
  onSave,
  mode = 'create',
  className
}: ConfigurationPanelProps) {
  const [activeTab, setActiveTab] = useState('basic');
  const [isSaving, setIsSaving] = useState(false);
  
  // Helper function to get value from input event
  const getValue = (e: any) => (e as React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>).target.value;
  const [formData, setFormData] = useState<Partial<EnhancedAgent>>(() => {
    if (agent) {
      return { ...agent };
    }
    
    return {
      name: '',
      description: '',
      disclaimer: '',
      category: 'general' as AgentCategory,
      visibility: 'private' as Visibility,
      personalityType: 'minimal' as PersonalityType,
      modelId: 'gpt-4o',
      systemPrompt: '',
      datasetConnection: 'all' as DatasetConnection,
      selectedDatasetIds: [],
      examplePrompts: [],
      safetyFlags: [],
      requireModeration: false,
      blockedTerms: [],
      enabledCapabilities: [],
      mcpIntegrationIds: [],
      canFork: true,
      featured: false,
      tags: [],
      modelParameters: {
        maxHistoryItems: 10,
        maxChunks: 10,
        maxTokens: 4096,
        trimRatio: 75,
        temperature: 0.7,
        topP: 0.9,
        frequencyPenalty: 0.0,
        presencePenalty: 0.0,
      }
    };
  });
  
  const [examplePromptInput, setExamplePromptInput] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [blockedTermInput, setBlockedTermInput] = useState('');

  const handleInputChange = useCallback((field: string, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  }, []);

  const handleModelParameterChange = useCallback((param: string, value: number) => {
    setFormData(prev => ({
      ...prev,
      modelParameters: {
        ...prev.modelParameters!,
        [param]: value
      }
    }));
  }, []);

  const handleSafetyFlagToggle = useCallback((flag: string, enabled: boolean) => {
    setFormData(prev => ({
      ...prev,
      safetyFlags: enabled 
        ? [...(prev.safetyFlags || []), flag]
        : (prev.safetyFlags || []).filter(f => f !== flag)
    }));
  }, []);

  const handleAddExamplePrompt = useCallback(() => {
    if (examplePromptInput.trim()) {
      setFormData(prev => ({
        ...prev,
        examplePrompts: [
          ...(prev.examplePrompts || []),
          { text: examplePromptInput.trim(), category: prev.category || 'general' }
        ]
      }));
      setExamplePromptInput('');
    }
  }, [examplePromptInput]);

  const handleAddTag = useCallback(() => {
    if (tagInput.trim() && !(formData.tags || []).includes(tagInput.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...(prev.tags || []), tagInput.trim()]
      }));
      setTagInput('');
    }
  }, [tagInput, formData.tags]);

  const handleAddBlockedTerm = useCallback(() => {
    if (blockedTermInput.trim() && !(formData.blockedTerms || []).includes(blockedTermInput.trim())) {
      setFormData(prev => ({
        ...prev,
        blockedTerms: [...(prev.blockedTerms || []), blockedTermInput.trim()]
      }));
      setBlockedTermInput('');
    }
  }, [blockedTermInput, formData.blockedTerms]);

  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      await onSave(formData);
      onClose();
    } catch (error) {
      console.error('Failed to save agent:', error);
    } finally {
      setIsSaving(false);
    }
  }, [formData, onSave, onClose]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          
          {/* Panel */}
          <motion.div
            className={cn(
              "fixed right-0 top-0 h-full w-full max-w-4xl bg-gt-white dark:bg-gray-900 shadow-2xl z-50 overflow-hidden",
              className
            )}
            variants={slideUp}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {mode === 'create' ? 'Create Agent' : 
                   mode === 'fork' ? 'Fork Agent' : 'Edit Agent'}
                </h2>
                <p className="text-gray-600 dark:text-gray-400 mt-1">
                  Configure your AI agent's personality, capabilities, and behavior
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={onClose}
                  disabled={isSaving}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={isSaving || !formData.name?.trim()}
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
                      {mode === 'create' ? 'Create' : 'Save'} Agent
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Content */}
            <div className="flex h-[calc(100%-88px)]">
              {/* Tabs */}
              <Tabs value={activeTab} onValueChange={setActiveTab} className="flex w-full">
                <TabsList className="flex flex-col h-full w-60 bg-gray-50 dark:bg-gray-800 rounded-none border-r border-gray-200 dark:border-gray-700 p-2">
                  <TabsTrigger value="basic" className="w-full justify-start gap-3 mb-1">
                    <User className="w-4 h-4" />
                    Basic Info
                  </TabsTrigger>
                  <TabsTrigger value="personality" className="w-full justify-start gap-3 mb-1">
                    <Brain className="w-4 h-4" />
                    Personality
                  </TabsTrigger>
                  <TabsTrigger value="model" className="w-full justify-start gap-3 mb-1">
                    <Settings className="w-4 h-4" />
                    Model & Prompt
                  </TabsTrigger>
                  <TabsTrigger value="datasets" className="w-full justify-start gap-3 mb-1">
                    <Database className="w-4 h-4" />
                    Datasets
                  </TabsTrigger>
                  <TabsTrigger value="safety" className="w-full justify-start gap-3 mb-1">
                    <Shield className="w-4 h-4" />
                    Safety & Moderation
                  </TabsTrigger>
                  <TabsTrigger value="advanced" className="w-full justify-start gap-3">
                    <Wrench className="w-4 h-4" />
                    Advanced
                  </TabsTrigger>
                </TabsList>

                <div className="flex-1 p-6 overflow-y-auto">
                  <motion.div
                    variants={staggerContainer}
                    initial="initial"
                    animate="animate"
                    className="max-w-2xl mx-auto space-y-6"
                  >
                    {/* Basic Info Tab */}
                    <TabsContent value="basic" className="mt-0">
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
                                onChange={(e) => handleInputChange('name', getValue(e))}
                                placeholder="Enter agent name"
                                className="text-lg"
                              />
                            </div>
                            
                            <div className="space-y-2">
                              <Label htmlFor="description">Description *</Label>
                              <Textarea
                                id="description"
                                value={formData.description || ''}
                                onChange={(e) => handleInputChange('description', getValue(e))}
                                placeholder="Describe what this agent does and how it can help users"
                                rows={3}
                              />
                            </div>
                            
                            <div className="space-y-2">
                              <Label htmlFor="disclaimer">Disclaimer (Optional)</Label>
                              <Textarea
                                id="disclaimer"
                                value={formData.disclaimer || ''}
                                onChange={(e) => handleInputChange('disclaimer', getValue(e))}
                                placeholder="Any important limitations or warnings users should know"
                                rows={2}
                              />
                            </div>
                            
                            <div className="grid grid-cols-2 gap-4">
                              <div className="space-y-2">
                                <Label htmlFor="category">Category</Label>
                                <Select
                                  value={formData.category}
                                  onValueChange={(value) => handleInputChange('category', value)}
                                >
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {categories.map((cat) => (
                                      <SelectItem key={cat.value} value={cat.value}>
                                        <div>
                                          <div className="font-medium">{cat.label}</div>
                                          <div className="text-xs text-gray-500">{cat.description}</div>
                                        </div>
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                              
                              <div className="space-y-2">
                                <Label htmlFor="visibility">Visibility</Label>
                                <Select
                                  value={formData.visibility}
                                  onValueChange={(value) => handleInputChange('visibility', value as Visibility)}
                                >
                                  <SelectTrigger>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="private">
                                      <div className="flex items-center gap-2">
                                        <EyeOff className="w-4 h-4" />
                                        Private - Only you can see this
                                      </div>
                                    </SelectItem>
                                    <SelectItem value="team">
                                      <div className="flex items-center gap-2">
                                        <Eye className="w-4 h-4" />
                                        Team - Your team can access this
                                      </div>
                                    </SelectItem>
                                    <SelectItem value="public">
                                      <div className="flex items-center gap-2">
                                        <Eye className="w-4 h-4" />
                                        Public - Everyone in organization can see
                                      </div>
                                    </SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                            
                            <div className="flex items-center justify-between">
                              <div className="space-y-1">
                                <Label>Featured Agent</Label>
                                <p className="text-sm text-gray-600">Show this agent prominently in the gallery</p>
                              </div>
                              <Switch
                                checked={formData.featured || false}
                                onCheckedChange={(checked) => handleInputChange('featured', checked)}
                              />
                            </div>
                            
                            <div className="flex items-center justify-between">
                              <div className="space-y-1">
                                <Label>Allow Forking</Label>
                                <p className="text-sm text-gray-600">Let others create copies of this agent</p>
                              </div>
                              <Switch
                                checked={formData.canFork !== false}
                                onCheckedChange={(checked) => handleInputChange('canFork', checked)}
                              />
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </TabsContent>

                    {/* Personality Tab */}
                    <TabsContent value="personality" className="mt-0">
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <CardTitle>Personality & Avatar</CardTitle>
                            <CardDescription>
                              Choose how your agent looks and behaves
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-6">
                            <div className="text-center">
                              <AgentAvatar
                                personality={formData.personalityType || 'minimal'}
                                state="idle"
                                size="large"
                                confidence={1}
                                customImageUrl={formData.customAvatarUrl}
                              />
                              <div className="mt-4 space-y-2">
                                <Label>Custom Avatar (Optional)</Label>
                                <div className="flex gap-2">
                                  <Input
                                    value={formData.customAvatarUrl || ''}
                                    onChange={(e) => handleInputChange('customAvatarUrl', getValue(e))}
                                    placeholder="Image URL or upload custom avatar"
                                  />
                                  <Button variant="secondary" size="sm">
                                    <Upload className="w-4 h-4" />
                                  </Button>
                                </div>
                              </div>
                            </div>
                            
                            <div className="space-y-4">
                              <Label>Personality Type</Label>
                              <div className="grid grid-cols-2 gap-3">
                                {personalities.map((personality) => (
                                  <motion.div
                                    key={personality.value}
                                    variants={scaleOnHover}
                                    whileHover="hover"
                                    whileTap="tap"
                                    className={cn(
                                      "p-4 border-2 rounded-lg cursor-pointer transition-all",
                                      formData.personalityType === personality.value
                                        ? "border-gt-green bg-gt-green/10"
                                        : "border-gray-200 hover:border-gray-300"
                                    )}
                                    onClick={() => handleInputChange('personalityType', personality.value)}
                                  >
                                    <div className="flex items-center gap-3">
                                      <AgentAvatar
                                        personality={personality.value}
                                        state="idle"
                                        size="small"
                                      />
                                      <div>
                                        <h4 className="font-medium">{personality.label}</h4>
                                        <p className="text-sm text-gray-600">{personality.description}</p>
                                      </div>
                                    </div>
                                  </motion.div>
                                ))}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </TabsContent>

                    {/* Model & Prompt Tab */}
                    <TabsContent value="model" className="mt-0">
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <CardTitle>AI Model Selection</CardTitle>
                            <CardDescription>
                              Choose the AI model and configure generation parameters
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-2">
                              <Label htmlFor="model">AI Model</Label>
                              <Select
                                value={formData.modelId}
                                onValueChange={(value) => handleInputChange('modelId', value)}
                              >
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {modelOptions.map((model) => (
                                    <SelectItem key={model.value} value={model.value}>
                                      <div>
                                        <div className="font-medium">{model.label}</div>
                                        <div className="text-xs text-gray-500">{model.description}</div>
                                      </div>
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                            
                            <div className="space-y-2">
                              <Label htmlFor="system-prompt">System Prompt</Label>
                              <Textarea
                                id="system-prompt"
                                value={formData.systemPrompt || ''}
                                onChange={(e) => handleInputChange('systemPrompt', getValue(e))}
                                placeholder="Define the agent's role, personality, and behavioral guidelines"
                                rows={6}
                                className="font-mono text-sm"
                              />
                            </div>
                            
                            <div className="grid grid-cols-2 gap-4">
                              <div className="space-y-2">
                                <Label>Temperature: {formData.modelParameters?.temperature || 0.7}</Label>
                                <Slider
                                  value={[formData.modelParameters?.temperature || 0.7]}
                                  onValueChange={([value]) => handleModelParameterChange('temperature', value)}
                                  max={2}
                                  min={0}
                                  step={0.1}
                                  className="w-full"
                                />
                                <p className="text-xs text-gray-600">Controls creativity vs consistency</p>
                              </div>
                              
                              <div className="space-y-2">
                                <Label>Max Tokens: {formData.modelParameters?.maxTokens || 4096}</Label>
                                <Slider
                                  value={[formData.modelParameters?.maxTokens || 4096]}
                                  onValueChange={([value]) => handleModelParameterChange('maxTokens', value)}
                                  max={8192}
                                  min={256}
                                  step={256}
                                  className="w-full"
                                />
                                <p className="text-xs text-gray-600">Maximum response length</p>
                              </div>
                            </div>
                            
                            <div className="grid grid-cols-2 gap-4">
                              <div className="space-y-2">
                                <Label>Top P: {formData.modelParameters?.topP || 0.9}</Label>
                                <Slider
                                  value={[formData.modelParameters?.topP || 0.9]}
                                  onValueChange={([value]) => handleModelParameterChange('topP', value)}
                                  max={1}
                                  min={0}
                                  step={0.1}
                                  className="w-full"
                                />
                              </div>
                              
                              <div className="space-y-2">
                                <Label>History Items: {formData.modelParameters?.maxHistoryItems || 10}</Label>
                                <Slider
                                  value={[formData.modelParameters?.maxHistoryItems || 10]}
                                  onValueChange={([value]) => handleModelParameterChange('maxHistoryItems', value)}
                                  max={50}
                                  min={1}
                                  step={1}
                                  className="w-full"
                                />
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                        
                        <Card>
                          <CardHeader>
                            <CardTitle>Example Prompts</CardTitle>
                            <CardDescription>
                              Add example prompts to help users understand what your agent can do
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="flex gap-2">
                              <Input
                                value={examplePromptInput}
                                onChange={(e) => setExamplePromptInput(getValue(e))}
                                placeholder="Enter an example prompt"
                                onKeyPress={(e) => e.key === 'Enter' && handleAddExamplePrompt()}
                              />
                              <Button onClick={handleAddExamplePrompt} disabled={!examplePromptInput.trim()}>
                                <Plus className="w-4 h-4" />
                              </Button>
                            </div>
                            
                            <div className="space-y-2">
                              {(formData.examplePrompts || []).map((prompt, index) => (
                                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                                  <span className="text-sm">{prompt.text}</span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                      setFormData(prev => ({
                                        ...prev,
                                        examplePrompts: prev.examplePrompts?.filter((_, i) => i !== index) || []
                                      }));
                                    }}
                                  >
                                    <X className="w-4 h-4" />
                                  </Button>
                                </div>
                              ))}
                              {(formData.examplePrompts || []).length === 0 && (
                                <p className="text-gray-500 text-sm text-center py-4">
                                  No example prompts added yet
                                </p>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </TabsContent>

                    {/* Datasets Tab */}
                    <TabsContent value="datasets" className="mt-0">
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <CardTitle>RAG Dataset Connection</CardTitle>
                            <CardDescription>
                              Configure which knowledge bases your agent can access
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="space-y-3">
                              <div className="flex items-center space-x-2">
                                <input
                                  type="radio"
                                  id="all-datasets"
                                  name="dataset-connection"
                                  checked={formData.datasetConnection === 'all'}
                                  onChange={() => handleInputChange('datasetConnection', 'all')}
                                />
                                <Label htmlFor="all-datasets" className="flex-1">
                                  <div>
                                    <div className="font-medium">All Datasets</div>
                                    <div className="text-sm text-gray-600">Access all available knowledge bases</div>
                                  </div>
                                </Label>
                              </div>
                              
                              <div className="flex items-center space-x-2">
                                <input
                                  type="radio"
                                  id="selected-datasets"
                                  name="dataset-connection"
                                  checked={formData.datasetConnection === 'selected'}
                                  onChange={() => handleInputChange('datasetConnection', 'selected')}
                                />
                                <Label htmlFor="selected-datasets" className="flex-1">
                                  <div>
                                    <div className="font-medium">Selected Datasets</div>
                                    <div className="text-sm text-gray-600">Choose specific knowledge bases</div>
                                  </div>
                                </Label>
                              </div>
                              
                              <div className="flex items-center space-x-2">
                                <input
                                  type="radio"
                                  id="no-datasets"
                                  name="dataset-connection"
                                  checked={formData.datasetConnection === 'none'}
                                  onChange={() => handleInputChange('datasetConnection', 'none')}
                                />
                                <Label htmlFor="no-datasets" className="flex-1">
                                  <div>
                                    <div className="font-medium">No RAG</div>
                                    <div className="text-sm text-gray-600">Use only the model's training data</div>
                                  </div>
                                </Label>
                              </div>
                            </div>
                            
                            {formData.datasetConnection === 'selected' && (
                              <Card className="mt-4">
                                <CardContent className="p-4">
                                  <Label className="text-sm font-medium">Available Datasets</Label>
                                  <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
                                    {/* Mock dataset list - would come from API */}
                                    {['Company Knowledge Base', 'Product Documentation', 'Customer Support FAQ', 'Technical Specifications'].map((dataset, index) => (
                                      <div key={index} className="flex items-center space-x-2">
                                        <input
                                          type="checkbox"
                                          id={`dataset-${index}`}
                                          checked={(formData.selectedDatasetIds || []).includes(`dataset-${index}`)}
                                          onChange={(e) => {
                                            const newIds = e.target.checked
                                              ? [...(formData.selectedDatasetIds || []), `dataset-${index}`]
                                              : (formData.selectedDatasetIds || []).filter(id => id !== `dataset-${index}`);
                                            handleInputChange('selectedDatasetIds', newIds);
                                          }}
                                        />
                                        <Label htmlFor={`dataset-${index}`} className="text-sm">
                                          {dataset}
                                        </Label>
                                      </div>
                                    ))}
                                  </div>
                                </CardContent>
                              </Card>
                            )}
                          </CardContent>
                        </Card>
                      </motion.div>
                    </TabsContent>

                    {/* Safety Tab */}
                    <TabsContent value="safety" className="mt-0">
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <CardTitle>Safety Filters</CardTitle>
                            <CardDescription>
                              Configure content filters and safety measures
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="flex items-center justify-between">
                              <div className="space-y-1">
                                <Label>Require Moderation</Label>
                                <p className="text-sm text-gray-600">All responses will be reviewed before delivery</p>
                              </div>
                              <Switch
                                checked={formData.requireModeration || false}
                                onCheckedChange={(checked) => handleInputChange('requireModeration', checked)}
                              />
                            </div>
                            
                            <div className="space-y-3">
                              <Label>Content Filters</Label>
                              {safetyOptions.map((option) => (
                                <div key={option.value} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                                  <div>
                                    <Label className="font-medium">{option.label}</Label>
                                    <p className="text-sm text-gray-600">{option.description}</p>
                                  </div>
                                  <Switch
                                    checked={(formData.safetyFlags || []).includes(option.value)}
                                    onCheckedChange={(checked) => handleSafetyFlagToggle(option.value, checked)}
                                  />
                                </div>
                              ))}
                            </div>
                          </CardContent>
                        </Card>
                        
                        <Card>
                          <CardHeader>
                            <CardTitle>Blocked Terms</CardTitle>
                            <CardDescription>
                              Add specific words or phrases to block
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="flex gap-2">
                              <Input
                                value={blockedTermInput}
                                onChange={(e) => setBlockedTermInput(getValue(e))}
                                placeholder="Enter term to block"
                                onKeyPress={(e) => e.key === 'Enter' && handleAddBlockedTerm()}
                              />
                              <Button onClick={handleAddBlockedTerm} disabled={!blockedTermInput.trim()}>
                                <Plus className="w-4 h-4" />
                              </Button>
                            </div>
                            
                            <div className="flex flex-wrap gap-2">
                              {(formData.blockedTerms || []).map((term, index) => (
                                <Badge key={index} variant="destructive" className="text-sm">
                                  {term}
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="ml-1 h-4 w-4 p-0 hover:bg-transparent"
                                    onClick={() => {
                                      setFormData(prev => ({
                                        ...prev,
                                        blockedTerms: prev.blockedTerms?.filter((_, i) => i !== index) || []
                                      }));
                                    }}
                                  >
                                    <X className="w-3 h-3" />
                                  </Button>
                                </Badge>
                              ))}
                              {(formData.blockedTerms || []).length === 0 && (
                                <p className="text-gray-500 text-sm">No blocked terms configured</p>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </TabsContent>

                    {/* Advanced Tab */}
                    <TabsContent value="advanced" className="mt-0">
                      <motion.div variants={staggerItem} className="space-y-6">
                        <Card>
                          <CardHeader>
                            <CardTitle>Tags & Organization</CardTitle>
                            <CardDescription>
                              Add tags to help organize and discover your agent
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="flex gap-2">
                              <Input
                                value={tagInput}
                                onChange={(e) => setTagInput(getValue(e))}
                                placeholder="Add a tag"
                                onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
                              />
                              <Button onClick={handleAddTag} disabled={!tagInput.trim()}>
                                <Plus className="w-4 h-4" />
                              </Button>
                            </div>
                            
                            <div className="flex flex-wrap gap-2">
                              {(formData.tags || []).map((tag, index) => (
                                <Badge key={index} variant="secondary">
                                  #{tag}
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="ml-1 h-4 w-4 p-0 hover:bg-transparent"
                                    onClick={() => {
                                      setFormData(prev => ({
                                        ...prev,
                                        tags: prev.tags?.filter((_, i) => i !== index) || []
                                      }));
                                    }}
                                  >
                                    <X className="w-3 h-3" />
                                  </Button>
                                </Badge>
                              ))}
                              {(formData.tags || []).length === 0 && (
                                <p className="text-gray-500 text-sm">No tags added yet</p>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                        
                        <Card>
                          <CardHeader>
                            <CardTitle>MCP Integrations</CardTitle>
                            <CardDescription>
                              Enable external tools and capabilities via Model Context Protocol
                            </CardDescription>
                          </CardHeader>
                          <CardContent>
                            <div className="text-center py-8 text-gray-500">
                              <Wrench className="w-12 h-12 mx-auto mb-4 opacity-50" />
                              <p>MCP integrations will be available in a future update</p>
                            </div>
                          </CardContent>
                        </Card>
                        
                        {mode === 'edit' && (
                          <Card>
                            <CardHeader>
                              <CardTitle className="text-red-600">Danger Zone</CardTitle>
                              <CardDescription>
                                Irreversible actions that affect your agent
                              </CardDescription>
                            </CardHeader>
                            <CardContent>
                              <div className="flex items-center justify-between p-4 border border-red-200 rounded-lg bg-red-50">
                                <div>
                                  <Label className="text-red-800 font-medium">Delete Agent</Label>
                                  <p className="text-sm text-red-600">This action cannot be undone</p>
                                </div>
                                <Button variant="danger" size="sm">
                                  Delete
                                </Button>
                              </div>
                            </CardContent>
                          </Card>
                        )}
                      </motion.div>
                    </TabsContent>
                  </motion.div>
                </div>
              </Tabs>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}