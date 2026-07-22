'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Share2, Bot, Database, Search, Eye, Edit } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { getAuthToken } from '@/services/auth';
import type { TeamMember } from '@/services/teams';

interface Resource {
  id: string;
  name: string;
  description?: string;
  is_owner: boolean;
}

interface ShareResourceInlineFormProps {
  teamId: string;
  teamName: string;
  teamMembers: TeamMember[];
  onShareResource: (resourceType: 'agent' | 'dataset', resourceId: string, userPermissions: Record<string, 'read' | 'edit'>) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

export function ShareResourceInlineForm({
  teamId,
  teamName,
  teamMembers,
  onShareResource,
  onCancel,
  loading = false
}: ShareResourceInlineFormProps) {
  const [resourceType, setResourceType] = useState<'agent' | 'dataset'>('agent');
  const [resources, setResources] = useState<Resource[]>([]);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [userPermissions, setUserPermissions] = useState<Record<string, 'read' | 'edit'>>({});
  const [searchQuery, setSearchQuery] = useState('');
  const [loadingResources, setLoadingResources] = useState(false);
  const [error, setError] = useState('');

  // Load resources when component mounts or resource type changes
  useEffect(() => {
    loadResources();
  }, [resourceType]);

  const loadResources = async () => {
    setLoadingResources(true);
    setError('');

    try {
      const token = getAuthToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const endpoint = resourceType === 'agent' ? '/api/v1/agents' : '/api/v1/datasets/';
      const response = await fetch(endpoint, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to load ${resourceType}s`);
      }

      const data = await response.json();

      // Filter to only show resources the user owns or can manage
      const ownedResources = Array.isArray(data)
        ? data.filter((r: any) => r.is_owner || r.can_manage)
        : data.data?.filter((r: any) => r.is_owner || r.can_manage) || [];

      setResources(ownedResources);
    } catch (err: any) {
      console.error(`Error loading ${resourceType}s:`, err);
      setError(err.message || `Failed to load ${resourceType}s`);
    } finally {
      setLoadingResources(false);
    }
  };

  const handleResourceSelect = (resourceId: string) => {
    setSelectedResourceId(resourceId);
    // Reset permissions when selecting a new resource
    setUserPermissions({});
  };

  const handlePermissionChange = (userId: string, permission: 'read' | 'edit' | null) => {
    setUserPermissions(prev => {
      const newPermissions = { ...prev };
      if (permission === null) {
        delete newPermissions[userId];
      } else {
        newPermissions[userId] = permission;
      }
      return newPermissions;
    });
  };

  const handleBulkPermission = (permission: 'read' | 'edit') => {
    const newPermissions: Record<string, 'read' | 'edit'> = {};
    teamMembers.forEach(member => {
      newPermissions[member.user_id] = permission;
    });
    setUserPermissions(newPermissions);
  };

  const handleClearPermissions = () => {
    setUserPermissions({});
  };

  const handleSubmit = async () => {
    if (!selectedResourceId) {
      setError('Please select a resource to share');
      return;
    }

    if (Object.keys(userPermissions).length === 0) {
      setError('Please grant permissions to at least one team member');
      return;
    }

    setError('');

    try {
      await onShareResource(resourceType, selectedResourceId, userPermissions);
      handleReset();
      onCancel(); // Close form after successful submission
    } catch (err: any) {
      setError(err.message || 'Failed to share resource');
    }
  };

  const handleReset = () => {
    setSelectedResourceId(null);
    setUserPermissions({});
    setSearchQuery('');
    setError('');
  };

  const handleCancel = () => {
    handleReset();
    onCancel();
  };

  const filteredResources = resources.filter(resource =>
    resource.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    resource.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const selectedResource = resources.find(r => r.id === selectedResourceId);
  const permissionCount = Object.keys(userPermissions).length;

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="mb-6 border-2 border-green-500 rounded-lg bg-green-50 overflow-hidden"
    >
      <div className="p-6 space-y-4 max-h-[600px] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-green-200">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <Share2 className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Share Resource</h3>
            <p className="text-sm text-gray-500">{teamName}</p>
          </div>
        </div>

        {/* Resource Type Tabs */}
        <Tabs value={resourceType} onValueChange={(value) => setResourceType(value as 'agent' | 'dataset')}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="agent" className="flex items-center gap-2">
              <Bot className="w-4 h-4" />
              Agents
            </TabsTrigger>
            <TabsTrigger value="dataset" className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Datasets
            </TabsTrigger>
          </TabsList>

          <TabsContent value={resourceType} className="space-y-4 mt-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(value) => setSearchQuery(value)}
                placeholder={`Search ${resourceType}s...`}
                className="pl-10"
              />
            </div>

            {/* Resource List */}
            {loadingResources ? (
              <div className="text-center py-8 text-gray-500">
                Loading {resourceType}s...
              </div>
            ) : filteredResources.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                {searchQuery ? `No ${resourceType}s found matching "${searchQuery}"` : `No ${resourceType}s available to share`}
              </div>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto border rounded-lg p-2 bg-gt-white">
                {filteredResources.map(resource => (
                  <div
                    key={resource.id}
                    onClick={() => handleResourceSelect(resource.id)}
                    className={cn(
                      "p-3 rounded-lg border cursor-pointer transition-colors",
                      selectedResourceId === resource.id
                        ? "bg-green-100 border-green-300"
                        : "hover:bg-gray-50 border-gray-200"
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-medium text-sm">{resource.name}</h4>
                        {resource.description && (
                          <p className="text-xs text-gray-500 mt-1 line-clamp-1">{resource.description}</p>
                        )}
                      </div>
                      {selectedResourceId === resource.id && (
                        <Badge variant="default" className="bg-gt-green text-white ml-2">
                          Selected
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Member Permissions */}
        {selectedResource && (
          <div className="space-y-3 border-t border-green-200 pt-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">
                Set Member Permissions
                {permissionCount > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {permissionCount} member{permissionCount > 1 ? 's' : ''}
                  </Badge>
                )}
              </Label>
              {teamMembers.length === 0 && (
                <p className="text-xs text-gray-500">No team members yet. Add members first.</p>
              )}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkPermission('read')}
                  className="text-xs"
                >
                  <Eye className="w-3 h-3 mr-1" />
                  All View
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkPermission('edit')}
                  className="text-xs"
                >
                  <Edit className="w-3 h-3 mr-1" />
                  All Edit
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleClearPermissions}
                  disabled={permissionCount === 0}
                  className="text-xs"
                >
                  Clear
                </Button>
              </div>
            </div>

            <div className="space-y-2 max-h-40 overflow-y-auto border rounded-lg p-3 bg-gt-white">
              {teamMembers.map(member => {
                const hasRead = userPermissions[member.user_id] === 'read' || userPermissions[member.user_id] === 'edit';
                const hasEdit = userPermissions[member.user_id] === 'edit';

                return (
                  <div
                    key={member.user_id}
                    className="flex items-center gap-3 p-2 rounded hover:bg-gray-50"
                  >
                    <span className="flex-1 text-sm">
                      {member.user_name || member.user_email}
                    </span>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id={`inline-${member.user_id}-read`}
                          checked={hasRead}
                          onCheckedChange={(checked) =>
                            handlePermissionChange(
                              member.user_id,
                              checked ? 'read' : null
                            )
                          }
                        />
                        <label
                          htmlFor={`inline-${member.user_id}-read`}
                          className="text-xs cursor-pointer"
                        >
                          View
                        </label>
                      </div>
                      <div className="flex items-center gap-2">
                        <Checkbox
                          id={`inline-${member.user_id}-edit`}
                          checked={hasEdit}
                          onCheckedChange={(checked) =>
                            handlePermissionChange(
                              member.user_id,
                              checked ? 'edit' : hasRead ? 'read' : null
                            )
                          }
                        />
                        <label
                          htmlFor={`inline-${member.user_id}-edit`}
                          className="text-xs cursor-pointer"
                        >
                          Edit
                        </label>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

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
            type="button"
            onClick={handleSubmit}
            disabled={loading || !selectedResourceId || permissionCount === 0}
            className="flex-1 bg-gt-green hover:bg-gt-green/90"
          >
            {loading ? 'Sharing...' : 'Share Resource'}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
