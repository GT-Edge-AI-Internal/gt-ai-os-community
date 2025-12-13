'use client';

import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, Database, Zap, Settings, Tag, Upload, File, Lock, Users, Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { canShareToOrganization } from '@/lib/permissions';
import { TeamShareConfiguration, type TeamShare } from '@/components/teams/team-share-configuration';
import { useTeams } from '@/hooks/use-teams';

interface DatasetCreateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateDataset: (dataset: CreateDatasetData) => Promise<void>;
  loading?: boolean;
}

export interface CreateDatasetData {
  name: string;
  description?: string;
  access_group: 'individual' | 'team' | 'organization';
  team_members?: string[];
  tags: string[];
  chunking_strategy: 'hybrid'; // Always hybrid for AI-driven optimization
  embedding_model: string;
  team_shares?: TeamShare[];
}

// BGE-M3 is the default and only embedding model for now
// In the future, this should be fetched from admin control panel configured models
const DEFAULT_EMBEDDING_MODEL = 'BAAI/bge-m3';

// Hybrid chunking with AI-driven size determination is always used
// No manual configuration needed - the system intelligently determines optimal chunk sizes
const DEFAULT_CHUNKING_STRATEGY = 'hybrid';

export function DatasetCreateModal({
  open,
  onOpenChange,
  onCreateDataset,
  loading = false
}: DatasetCreateModalProps) {
  const [formData, setFormData] = useState<CreateDatasetData>({
    name: '',
    description: '',
    access_group: 'individual',
    team_members: [],
    tags: [],
    chunking_strategy: 'hybrid',
    embedding_model: DEFAULT_EMBEDDING_MODEL
  });

  // Debug logging
  console.log('Modal render - open:', open, 'formData:', formData);

  const [tagInput, setTagInput] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [teamShares, setTeamShares] = useState<TeamShare[]>([]);
  const { data: userTeams } = useTeams();

  const resetForm = () => {
    console.log('RESETFORM CALLED! Stack trace:', new Error().stack); // Debug log
    setFormData({
      name: '',
      description: '',
      access_group: 'individual',
      team_members: [],
      tags: [],
      chunking_strategy: 'hybrid',
      embedding_model: DEFAULT_EMBEDDING_MODEL
    });
    setTagInput('');
    setSelectedFiles([]);
    setIsDragOver(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) return;

    try {
      const dataToSubmit = {
        ...formData,
        ...(formData.access_group === 'team' && teamShares.length > 0 ? { team_shares: teamShares } : {})
      };
      await onCreateDataset(dataToSubmit);
      resetForm();
      setTeamShares([]);
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to create dataset:', error);
    }
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log('handleNameChange called!', e.target?.value); // Debug log
    const value = e.target?.value || '';
    console.log('Name changing to:', value); // Debug log
    setFormData(prev => {
      console.log('Previous formData:', prev);
      const newData = { ...prev, name: value };
      console.log('New formData:', newData);
      return newData;
    });
  };


  const handleClose = () => {
    resetForm();
    onOpenChange(false);
  };

  const addTag = () => {
    const tag = tagInput.trim();
    if (tag && !formData.tags.includes(tag) && formData.tags.length < 10) {
      setFormData(prev => ({
        ...prev,
        tags: [...prev.tags, tag]
      }));
      setTagInput('');
    }
  };

  const removeTag = (tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags.filter(tag => tag !== tagToRemove)
    }));
  };

  const handleTagInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addTag();
    }
  };


  const handleFileSelect = (files: FileList | null) => {
    if (!files) return;
    const newFiles = Array.from(files);
    setSelectedFiles(prev => [...prev, ...newFiles]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
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
            className="fixed right-0 top-0 h-screen w-full max-w-2xl bg-gt-white shadow-2xl z-[1000] overflow-y-auto"
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
            className="sticky top-0 bg-gt-white border-b border-gray-200 px-6 py-4 z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-gt-green/10 rounded-lg flex items-center justify-center">
                  <Database className="w-5 h-5 text-gt-green" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">Create Dataset</h2>
                  <p className="text-sm text-gray-600">Set up a new dataset for document storage and RAG</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClose}
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
          {/* Basic Information */}
          <div className="space-y-4">
            <div>
              <Label htmlFor="name" className="text-sm font-medium">
                Dataset Name *
              </Label>
              <input
                id="name"
                type="text"
                value={formData.name}
                onChange={handleNameChange}
                placeholder="My Knowledge Base"
                required
                autoFocus
                className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div>
              <Label htmlFor="description" className="text-sm font-medium">
                Description
              </Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target?.value || '' }))}
                placeholder="Describe what this dataset contains..."
                rows={3}
                className="mt-1"
              />
            </div>

            <div className="space-y-3">
              <Label>Access Control</Label>
              <RadioGroup
                value={formData.access_group}
                onValueChange={(value: any) => setFormData(prev => ({ ...prev, access_group: value }))}
              >
                <div className="space-y-2">
                  <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-50">
                    <RadioGroupItem value="individual" id="create-individual" />
                    <Label htmlFor="create-individual" className="flex items-center gap-2 cursor-pointer flex-1">
                      <Lock className="w-4 h-4 text-gray-600" />
                      <div>
                        <div className="font-medium">Individual</div>
                        <div className="text-sm text-gray-500">Only you can access and edit this dataset</div>
                      </div>
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-50">
                    <RadioGroupItem value="team" id="create-team" />
                    <Label htmlFor="create-team" className="flex items-center gap-2 cursor-pointer flex-1">
                      <Users className="w-4 h-4 text-blue-600" />
                      <div>
                        <div className="font-medium">Team</div>
                        <div className="text-sm text-gray-500">Share with specific teams and set permissions</div>
                      </div>
                    </Label>
                  </div>
                  {canShareToOrganization() && (
                    <div className="flex items-center space-x-2 p-2 rounded hover:bg-gray-50">
                      <RadioGroupItem value="organization" id="create-organization" />
                      <Label htmlFor="create-organization" className="flex items-center gap-2 cursor-pointer flex-1">
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
            </div>

            {/* Team Sharing Configuration */}
            {formData.access_group === 'team' && (
              <div className="mt-4 pt-4 border-t">
                <TeamShareConfiguration
                  userTeams={userTeams || []}
                  value={teamShares}
                  onChange={setTeamShares}
                />
              </div>
            )}
          </div>



          {/* Tags */}
          <div className="space-y-3">
            <Label>Tags</Label>
            <div className="space-y-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target?.value || '')}
                onKeyDown={handleTagInputKeyDown}
                placeholder="Type tags and press Enter"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500">
                You can input individual keywords, including TSV and CSV formatted text.
              </p>
            </div>
            {formData.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {formData.tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="secondary"
                    className="flex items-center gap-1"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 text-gray-500 hover:text-gray-700"
                    >
                      <X className="w-3 h-3" />
                    </button>
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
              onClick={handleClose}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading || !formData.name.trim()}
            >
              {loading 
                ? 'Creating...' 
                : selectedFiles.length > 0
                  ? `Create Dataset & Upload ${selectedFiles.length} Files`
                  : 'Create Dataset'
              }
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