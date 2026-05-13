'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { UserPlus, Mail, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';

interface AddMemberInlineFormProps {
  teamId: string;
  teamName: string;
  onAddMember: (email: string, permission: 'view' | 'share' | 'manager') => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

export function AddMemberInlineForm({
  teamId,
  teamName,
  onAddMember,
  onCancel,
  loading = false
}: AddMemberInlineFormProps) {
  const [email, setEmail] = useState('');
  const [permission, setPermission] = useState<'view' | 'share' | 'manager'>('view');
  const [error, setError] = useState('');

  const validateEmail = (email: string) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError('Email is required');
      return;
    }

    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    try {
      await onAddMember(email.trim().toLowerCase(), permission);
      setEmail('');
      setPermission('view');
      setError('');
      onCancel(); // Close form after successful submission
    } catch (err: any) {
      setError(err.message || 'Failed to add member');
    }
  };

  const handleCancel = () => {
    setEmail('');
    setPermission('view');
    setError('');
    onCancel();
  };

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="mb-6 border-2 border-gt-green rounded-lg bg-gt-green/5 overflow-hidden"
    >
      <div className="p-6 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-gt-green/20">
          <div className="w-10 h-10 rounded-full bg-gt-green/20 flex items-center justify-center">
            <UserPlus className="w-5 h-5 text-gt-green" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Add Team Member</h3>
            <p className="text-sm text-gray-500">{teamName}</p>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Email Input */}
          <div className="space-y-2">
            <Label htmlFor="inline-email" className="text-sm font-medium">
              Email Address
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                id="inline-email"
                type="email"
                value={email}
                onChange={(value) => setEmail(value)}
                placeholder="member@example.com"
                className="pl-10"
                disabled={loading}
                autoFocus
                clearable
              />
            </div>
            {error && (
              <p className="text-sm text-red-600">{error}</p>
            )}
          </div>

          {/* Permission Level */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Permission Level</Label>
            <RadioGroup
              value={permission}
              onValueChange={(value) => setPermission(value as 'view' | 'share' | 'manager')}
            >
              <div className="space-y-2">
                <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gt-white cursor-pointer">
                  <RadioGroupItem value="view" id="inline-permission-view" />
                  <Label htmlFor="inline-permission-view" className="flex items-center gap-2 cursor-pointer flex-1">
                    <Shield className="w-4 h-4 text-gray-600" />
                    <div>
                      <div className="font-medium text-sm">Member</div>
                      <div className="text-xs text-gray-500">Can access shared resources</div>
                    </div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gt-white cursor-pointer">
                  <RadioGroupItem value="share" id="inline-permission-share" />
                  <Label htmlFor="inline-permission-share" className="flex items-center gap-2 cursor-pointer flex-1">
                    <Shield className="w-4 h-4 text-blue-600" />
                    <div>
                      <div className="font-medium text-sm">Contributor</div>
                      <div className="text-xs text-gray-500">Can share own resources to the team</div>
                    </div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 p-3 rounded-lg border hover:bg-gt-white cursor-pointer">
                  <RadioGroupItem value="manager" id="inline-permission-manager" />
                  <Label htmlFor="inline-permission-manager" className="flex items-center gap-2 cursor-pointer flex-1">
                    <Shield className="w-4 h-4 text-gt-green" />
                    <div>
                      <div className="font-medium text-sm">Manager</div>
                      <div className="text-xs text-gray-500">Can manage members, view Observable activity, and share resources</div>
                    </div>
                  </Label>
                </div>
              </div>
            </RadioGroup>
          </div>

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
              disabled={loading || !email.trim()}
              className="flex-1 bg-gt-green hover:bg-gt-green/90"
            >
              {loading ? 'Adding...' : 'Add Member'}
            </Button>
          </div>
        </form>
      </div>
    </motion.div>
  );
}
