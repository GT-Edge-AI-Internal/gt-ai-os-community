'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, Users, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import type { Team } from '@/services';

interface TeamEditModalProps {
  open: boolean;
  team: Team | null;
  onOpenChange: (open: boolean) => void;
  onUpdateTeam: (teamId: string, updates: UpdateTeamData) => Promise<void>;
  loading?: boolean;
}

export interface UpdateTeamData {
  name?: string;
  description?: string;
}

export function TeamEditModal({
  open,
  team,
  onOpenChange,
  onUpdateTeam,
  loading = false
}: TeamEditModalProps) {
  const [formData, setFormData] = useState<UpdateTeamData>({
    name: '',
    description: ''
  });

  // Load team data when modal opens or team changes
  useEffect(() => {
    if (open && team) {
      setFormData({
        name: team.name,
        description: team.description || ''
      });
    }
  }, [open, team]);

  const resetForm = () => {
    setFormData({
      name: '',
      description: ''
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!team || !formData.name?.trim()) return;

    try {
      await onUpdateTeam(team.id, formData);
      resetForm();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to update team:', error);
    }
  };

  const handleClose = () => {
    resetForm();
    onOpenChange(false);
  };

  if (!open || !team) return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[999]"
            onClick={handleClose}
          />

          {/* Panel */}
          <motion.div
            className="fixed right-0 top-0 h-screen w-full max-w-2xl bg-white shadow-2xl z-[1000] overflow-y-auto"
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
                  <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                    <Edit3 className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">Edit Team</h2>
                    <p className="text-sm text-gray-600">Update team information</p>
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

            {/* Form */}
            <form
              onSubmit={handleSubmit}
              onClick={(e) => e.stopPropagation()}
              className="p-6 space-y-6"
            >
              {/* Basic Information */}
              <div className="space-y-4">
                <div>
                  <Label htmlFor="name" className="text-sm font-medium">
                    Team Name *
                  </Label>
                  <input
                    id="name"
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Engineering Team"
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
                    onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe the purpose of this team..."
                    rows={3}
                    className="mt-1"
                  />
                </div>
              </div>

              {/* Team Stats */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <Users className="w-5 h-5 text-gray-600 flex-shrink-0" />
                  <div className="text-sm text-gray-900">
                    <p className="font-medium">
                      {team.member_count} {team.member_count === 1 ? 'member' : 'members'}
                    </p>
                    <p className="text-gray-600 text-xs">
                      Created {new Date(team.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </div>

              {/* Form Actions */}
              <div className="flex justify-end gap-3 pt-4 border-t">
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
                  disabled={loading || !formData.name?.trim()}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {loading ? 'Saving...' : 'Save Changes'}
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
