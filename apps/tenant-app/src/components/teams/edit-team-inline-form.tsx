'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Edit3, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import type { Team } from '@/services';

interface EditTeamInlineFormProps {
  team: Team;
  onUpdateTeam: (name: string, description: string) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

export function EditTeamInlineForm({
  team,
  onUpdateTeam,
  onCancel,
  loading = false
}: EditTeamInlineFormProps) {
  const [name, setName] = useState(team.name);
  const [description, setDescription] = useState(team.description || '');
  const [error, setError] = useState('');

  // Update form when team changes
  useEffect(() => {
    setName(team.name);
    setDescription(team.description || '');
  }, [team]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!name.trim()) {
      setError('Team name is required');
      return;
    }

    try {
      await onUpdateTeam(name.trim(), description.trim());
      onCancel(); // Close form after successful submission
    } catch (err: any) {
      setError(err.message || 'Failed to update team');
    }
  };

  const handleCancel = () => {
    setName(team.name);
    setDescription(team.description || '');
    setError('');
    onCancel();
  };

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="mb-6 border-2 border-blue-500 rounded-lg bg-blue-50 overflow-hidden"
    >
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-blue-200">
          <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
            <Edit3 className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Edit Team</h3>
            <p className="text-sm text-gray-500">Update team information</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Team Name */}
          <div className="space-y-2">
            <Label htmlFor="inline-team-name" className="text-sm font-medium">
              Team Name *
            </Label>
            <Input
              id="inline-team-name"
              type="text"
              value={name}
              onChange={(value) => setName(value)}
              placeholder="Engineering Team"
              disabled={loading}
              autoFocus
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="inline-team-description" className="text-sm font-medium">
              Description
            </Label>
            <Textarea
              id="inline-team-description"
              value={description}
              onChange={(value) => setDescription(value)}
              placeholder="Describe the purpose of this team..."
              rows={3}
              disabled={loading}
            />
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={loading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading || !name.trim()}
              className="flex-1 bg-blue-600 hover:bg-blue-700"
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </div>
    </motion.div>
  );
}
