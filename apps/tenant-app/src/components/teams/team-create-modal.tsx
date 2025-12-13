'use client';

import { useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

interface TeamCreateModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateTeam: (team: CreateTeamData) => Promise<void>;
  loading?: boolean;
}

export interface CreateTeamData {
  name: string;
  description?: string;
}

export function TeamCreateModal({
  open,
  onOpenChange,
  onCreateTeam,
  loading = false
}: TeamCreateModalProps) {
  const [formData, setFormData] = useState<CreateTeamData>({
    name: '',
    description: ''
  });

  const resetForm = () => {
    setFormData({
      name: '',
      description: ''
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) return;

    try {
      await onCreateTeam(formData);
      resetForm();
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to create team:', error);
    }
  };

  const handleClose = () => {
    resetForm();
    onOpenChange(false);
  };

  if (!open) return null;

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
            className="fixed right-0 top-0 h-screen w-full max-w-2xl bg-gt-white shadow-2xl z-[1000] overflow-y-auto"
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
                    <Users className="w-5 h-5 text-gt-green" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gt-gray-900">Create Team</h2>
                    <p className="text-sm text-gt-gray-600">Create a new team for collaboration</p>
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
                    className="mt-1 w-full px-3 py-2 border border-gt-gray-300 rounded-md bg-gt-white text-gt-gray-900 focus:outline-none focus:ring-2 focus:ring-gt-green focus:border-gt-green"
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
                  <p className="text-xs text-gt-gray-500 mt-1">
                    Optional: Explain what this team is for and who should join
                  </p>
                </div>
              </div>

              {/* Info Box */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex gap-3">
                  <Users className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-900">
                    <p className="font-medium mb-1">You will be the team owner</p>
                    <p className="text-blue-700">
                      As the owner, you can manage team members, set permissions, and share resources.
                      You can add members after creating the team.
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
                  disabled={loading || !formData.name.trim()}
                  className="bg-gt-green hover:bg-gt-green/90"
                >
                  {loading ? 'Creating...' : 'Create Team'}
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
