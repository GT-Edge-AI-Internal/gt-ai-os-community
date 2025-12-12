'use client';

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, Database, Tag, Users, Lock, Globe, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type { AccessGroup, Dataset } from '@/services';
import { canShareToOrganization } from '@/lib/permissions';
import { TeamShareConfiguration, type TeamShare } from '@/components/teams/team-share-configuration';
import { useTeams } from '@/hooks/use-teams';
import { getUser } from '@/services/auth';

interface DatasetEditModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdateDataset: (datasetId: string, data: UpdateDatasetData) => Promise<void>;
  dataset: Dataset | null;
  loading?: boolean;
}

export interface UpdateDatasetData {
  name: string;
  description?: string;
  tags: string[];
  access_group?: AccessGroup;
  team_members?: string[];
  chunking_strategy?: 'hybrid' | 'semantic' | 'fixed';
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;
  team_shares?: TeamShare[];
}

export function DatasetEditModal({
  open,
  onOpenChange,
  onUpdateDataset,
  dataset,
  loading = false
}: DatasetEditModalProps) {
  const [formData, setFormData] = useState<UpdateDatasetData>({
    name: '',
    description: '',
    tags: [],
    access_group: 'individual',
    team_members: [],
    chunking_strategy: 'hybrid',
    chunk_size: 512,
    chunk_overlap: 50,
    embedding_model: 'BAAI/bge-m3'
  });

  const [tagInput, setTagInput] = useState('');
  const [teamMemberInput, setTeamMemberInput] = useState('');
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const tagInputRef = useRef<HTMLInputElement>(null);
  const teamMemberInputRef = useRef<HTMLInputElement>(null);
  const [teamShares, setTeamShares] = useState<TeamShare[]>([]);
  const [originalTeamShares, setOriginalTeamShares] = useState<TeamShare[]>([]);
  const { data: userTeams } = useTeams();

  // Determine if current user is owner (can modify visibility and sharing)
  const isOwner = dataset?.is_owner || false;

  // Initialize form data when dataset prop changes
  useEffect(() => {
    console.log('DatasetEditModal - Dataset prop received:', dataset);
    console.log('DatasetEditModal - Modal open state:', open);

    if (dataset && open) {
      console.log('DatasetEditModal - Setting form data with:', {
        name: dataset.name,
        description: dataset.description,
        tags: dataset.tags,
        access_group: dataset.access_group,
        team_members: dataset.team_members
      });

      setFormData({
        name: dataset.name,
        description: dataset.description || '',
        tags: [...dataset.tags],
        access_group: dataset.access_group || 'individual',
        team_members: dataset.team_members || [],
        chunking_strategy: dataset.chunking_strategy || 'hybrid',
        chunk_size: dataset.chunk_size || 512,
        chunk_overlap: dataset.chunk_overlap || 50,
        embedding_model: dataset.embedding_model || 'BAAI/bge-m3'
      });

      // Initialize team shares from dataset
      const initialTeamShares = dataset.team_shares || [];
      setTeamShares(initialTeamShares);
      setOriginalTeamShares(initialTeamShares);

      console.log('DatasetEditModal - Form data set successfully');
    }
  }, [dataset, open]);

  // Reset form when modal closes
  useEffect(() => {
    if (!open) {
      setFormData({
        name: '',
        description: '',
        tags: [],
        access_group: 'individual',
        team_members: [],
        chunking_strategy: 'hybrid',
        chunk_size: 512,
        chunk_overlap: 50,
        embedding_model: 'BAAI/bge-m3'
      });
      setTagInput('');
      setTeamMemberInput('');
      setShowAdvancedSettings(false);
    }
  }, [open]);

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, name: e.target?.value || '' });
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setFormData({ ...formData, description: e.target?.value || '' });
  };

  const handleAccessGroupChange = (value: AccessGroup) => {
    setFormData({ ...formData, access_group: value });
    // Clear team members if switching away from team access
    if (value !== 'team') {
      setFormData({ ...formData, access_group: value, team_members: [] });
    }
  };

  const handleTagInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTagInput(e.target?.value || '');
  };

  const handleTagInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
      e.preventDefault();
      addTag();
    }
  };

  const addTag = () => {
    const tag = tagInput.trim();
    if (tag && !formData.tags.includes(tag)) {
      setFormData({ ...formData, tags: [...formData.tags, tag] });
    }
    setTagInput('');
  };

  const removeTag = (tagToRemove: string) => {
    setFormData({
      ...formData,
      tags: formData.tags.filter(tag => tag !== tagToRemove)
    });
  };

  const handleTeamMemberInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTeamMemberInput(e.target?.value || '');
  };

  const handleTeamMemberInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === 'Tab') {
      e.preventDefault();
      addTeamMember();
    }
  };

  const addTeamMember = () => {
    const email = teamMemberInput.trim().toLowerCase();
    // Basic email validation
    if (email && email.includes('@') && !formData.team_members?.includes(email)) {
      setFormData({
        ...formData,
        team_members: [...(formData.team_members || []), email]
      });
    }
    setTeamMemberInput('');
  };

  const removeTeamMember = (emailToRemove: string) => {
    setFormData({
      ...formData,
      team_members: formData.team_members?.filter(email => email !== emailToRemove) || []
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dataset || !formData.name.trim()) return;

    try {
      // Detect if team_shares has changed (to avoid overwriting fine-grained permissions)
      const teamSharesChanged = JSON.stringify(teamShares) !== JSON.stringify(originalTeamShares);

      // Only include team_shares if access_group is 'team' AND it has changed
      const shouldIncludeTeamShares = formData.access_group === 'team' && teamSharesChanged;

      await onUpdateDataset(dataset.id, {
        name: formData.name.trim(),
        description: formData.description?.trim() || undefined,
        tags: formData.tags,
        access_group: formData.access_group,
        team_members: formData.access_group === 'team' ? formData.team_members : undefined,
        chunking_strategy: formData.chunking_strategy,
        chunk_size: formData.chunk_size,
        chunk_overlap: formData.chunk_overlap,
        embedding_model: formData.embedding_model,
        ...(shouldIncludeTeamShares ? { team_shares: teamShares } : {})
      });
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to update dataset:', error);
    }
  };

  const getAccessIcon = (accessGroup: AccessGroup) => {
    switch (accessGroup) {
      case 'individual': return <Lock className="w-4 h-4" />;
      case 'team': return <Users className="w-4 h-4" />;
      case 'organization': return <Globe className="w-4 h-4" />;
    }
  };

  if (!open) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[999]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                onOpenChange(false);
              }
            }}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            className="fixed right-0 top-0 h-screen w-full max-w-2xl bg-white shadow-2xl z-[1000] overflow-y-auto"
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
          <div
            className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center">
                  <Database className="w-5 h-5 text-gt-green" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">Edit Dataset</h2>
                  <p className="text-sm text-gray-600">Modify dataset properties and settings</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onOpenChange(false)}
                className="p-1 h-auto"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
          </div>

        <form
          onSubmit={handleSubmit}
          onClick={(e) => e.stopPropagation()}
          className="p-6 space-y-6"
        >

          {/* Dataset Name */}
          <div className="space-y-2">
            <Label htmlFor="dataset-name">Dataset Name *</Label>
            <input
              id="dataset-name"
              type="text"
              value={formData.name}
              onChange={handleNameChange}
              placeholder="Enter dataset name"
              disabled={loading}
              className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              required
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="dataset-description">Description</Label>
            <Textarea
              id="dataset-description"
              value={formData.description}
              onChange={handleDescriptionChange}
              placeholder="Describe what this dataset contains and how it will be used"
              disabled={loading}
              className="min-h-[80px] resize-none"
            />
          </div>

          {/* Access Control */}
          <div className="space-y-3">
            <Label>Access Control</Label>
            <RadioGroup
              value={formData.access_group}
              onValueChange={(value) => handleAccessGroupChange(value as AccessGroup)}
              disabled={!isOwner}
            >
              <div className="space-y-2">
                <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-50">
                  <RadioGroupItem value="individual" id="individual" />
                  <Label htmlFor="individual" className="flex items-center gap-2 cursor-pointer flex-1">
                    <Lock className="w-4 h-4 text-gray-600" />
                    <div>
                      <div className="font-medium">Individual</div>
                      <div className="text-sm text-gray-500">Only you can access and edit this dataset</div>
                    </div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-50">
                  <RadioGroupItem value="team" id="team" />
                  <Label htmlFor="team" className="flex items-center gap-2 cursor-pointer flex-1">
                    <Users className="w-4 h-4 text-blue-600" />
                    <div>
                      <div className="font-medium">Team</div>
                      <div className="text-sm text-gray-500">Share with specific teams and set permissions</div>
                    </div>
                  </Label>
                </div>
                {canShareToOrganization() && (
                  <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-50">
                    <RadioGroupItem value="organization" id="organization" />
                    <Label htmlFor="organization" className="flex items-center gap-2 cursor-pointer flex-1">
                      <Globe className="w-4 h-4 text-green-600" />
                      <div>
                        <div className="font-medium">Organization</div>
                        <div className="text-sm text-gray-500">All users can read, only admins can edit</div>
                      </div>
                    </Label>
                  </div>
                )}
              </div>
            </RadioGroup>

            {/* Team Sharing Configuration */}
            {formData.access_group === 'team' && (
              <div className="mt-4 pt-4 border-t">
                {!isOwner && (
                  <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
                    <p className="text-sm text-blue-800">
                      Only the resource owner can modify visibility and team sharing settings.
                    </p>
                  </div>
                )}
                <TeamShareConfiguration
                  userTeams={userTeams || []}
                  value={teamShares}
                  onChange={setTeamShares}
                  disabled={!isOwner}
                />
              </div>
            )}
          </div>

          {/* Tags */}
          <div className="space-y-3">
            <Label>Tags</Label>

            {/* Tag Input */}
            <div className="space-y-2">
              <input
                ref={tagInputRef}
                type="text"
                value={tagInput}
                onChange={handleTagInputChange}
                onKeyDown={handleTagInputKeyDown}
                onBlur={addTag}
                placeholder="Type tags and press Enter"
                disabled={loading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              />
              <p className="text-xs text-gray-500">
                You can input individual keywords, including TSV and CSV formatted text.
              </p>
            </div>

            {/* Current Tags */}
            {formData.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {formData.tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="secondary"
                    className="flex items-center gap-1 cursor-pointer hover:bg-gray-200"
                    onClick={() => removeTag(tag)}
                  >
                    <Tag className="w-3 h-3" />
                    {tag}
                    <X className="w-3 h-3 hover:text-red-500" />
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-6 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading || !formData.name.trim()}
            >
              {loading ? 'Updating...' : 'Update Dataset'}
            </Button>
          </div>
        </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}