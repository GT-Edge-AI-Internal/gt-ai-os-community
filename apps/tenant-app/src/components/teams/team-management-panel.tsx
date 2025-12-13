'use client';

import { useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { slideLeft } from '@/lib/animations/gt-animations';
import { X, Info, Users as UsersIcon, Share2, Plus, Edit3, UserX, Shield, Trash2, ChevronDown, ChevronRight, Eye, Edit as EditIcon, User, Target } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Checkbox } from '@/components/ui/checkbox';
import { useTeamMembers, useSharedResources, useUpdateTeam, useUpdateMemberPermission, useRemoveTeamMember, useUnshareResourceFromTeam, useShareResourceToTeam, useRequestObservableStatus } from '@/hooks/use-teams';
import type { Team } from '@/services';
import { AddMemberInlineForm } from './add-member-inline-form';
import { ShareResourceInlineForm } from './share-resource-inline-form';
import { EditTeamInlineForm } from './edit-team-inline-form';
import { getAuthToken } from '@/services/auth';

interface TeamManagementPanelProps {
  open: boolean;
  team: Team | null;
  initialTab?: 'overview' | 'members' | 'resources';
  onOpenChange: (open: boolean) => void;
}

export function TeamManagementPanel({
  open,
  team,
  initialTab = 'overview',
  onOpenChange
}: TeamManagementPanelProps) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [showAddMemberForm, setShowAddMemberForm] = useState(false);
  const [showShareResourceForm, setShowShareResourceForm] = useState(false);
  const [showEditTeamForm, setShowEditTeamForm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Bulk member selection state
  const [selectedMemberIds, setSelectedMemberIds] = useState<Set<string>>(new Set());

  // Resource expansion state
  const [expandedResourceIds, setExpandedResourceIds] = useState<Set<string>>(new Set());

  // Team update mutation
  const updateTeam = useUpdateTeam();

  // Member management mutations
  const updateMemberPermission = useUpdateMemberPermission();
  const removeMember = useRemoveTeamMember();
  const requestObservable = useRequestObservableStatus();

  // Resource management mutations
  const shareResource = useShareResourceToTeam();
  const unshareResource = useUnshareResourceFromTeam();

  // Fetch members data (needed for both Members and Resources tabs)
  const { data: members = [], isLoading: membersLoading, refetch: refetchMembers } = useTeamMembers(
    team?.id
  );

  const { data: resources = [], isLoading: resourcesLoading, refetch: refetchResources } = useSharedResources(
    activeTab === 'resources' && team?.id ? team.id : undefined
  );

  const handleClose = () => {
    onOpenChange(false);
    // Reset to overview tab when closing
    setTimeout(() => setActiveTab('overview'), 300);
  };

  const handleAddMember = async (email: string, permission: 'view' | 'share' | 'manager') => {
    if (!team) return;

    setActionLoading(true);
    try {
      const token = getAuthToken();
      if (!token) throw new Error('Not authenticated');

      // Map frontend permission to backend permission
      const teamPermission = permission === 'view' ? 'read' : permission === 'share' ? 'share' : 'manager';

      const response = await fetch(`/api/v1/teams/${team.id}/members`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_email: email,
          team_permission: teamPermission
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to add member');
      }

      // Refetch members list
      await refetchMembers();
    } catch (error: any) {
      throw new Error(error.message || 'Failed to add member');
    } finally {
      setActionLoading(false);
    }
  };

  const handleShareResource = async (
    resourceType: 'agent' | 'dataset',
    resourceId: string,
    userPermissions: Record<string, 'read' | 'edit'>
  ) => {
    if (!team) return;

    setActionLoading(true);
    try {
      const token = getAuthToken();
      if (!token) throw new Error('Not authenticated');

      const response = await fetch(`/api/v1/teams/${team.id}/share`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          resource_type: resourceType,
          resource_id: resourceId,
          user_permissions: userPermissions
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to share resource');
      }

      // Refetch resources list
      await refetchResources();
    } catch (error: any) {
      throw new Error(error.message || 'Failed to share resource');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateTeam = async (name: string, description: string) => {
    if (!team) return;

    setActionLoading(true);
    try {
      await updateTeam.mutateAsync({
        teamId: team.id,
        data: { name, description }
      });
      setShowEditTeamForm(false);
    } catch (error: any) {
      throw new Error(error.message || 'Failed to update team');
    } finally {
      setActionLoading(false);
    }
  };

  // Bulk selection handlers
  const selectableMembers = members.filter(m =>
    !m.is_owner &&
    m.status === 'accepted' &&
    !(team.user_permission === 'manager' && m.team_permission === 'manager')
  ); // Can't select owner, pending invitations, or managers (if current user is a manager)
  const isAllSelected = selectableMembers.length > 0 && selectableMembers.every(m => selectedMemberIds.has(m.user_id));

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedMemberIds(new Set(selectableMembers.map(m => m.user_id)));
    } else {
      setSelectedMemberIds(new Set());
    }
  };

  const handleSelectMember = (userId: string, checked: boolean) => {
    const newSelected = new Set(selectedMemberIds);
    if (checked) {
      newSelected.add(userId);
    } else {
      newSelected.delete(userId);
    }
    setSelectedMemberIds(newSelected);
  };

  const handleBulkChangePermission = async (permission: 'read' | 'share' | 'manager') => {
    if (!team || selectedMemberIds.size === 0) return;

    setActionLoading(true);
    try {
      // Update each selected member
      await Promise.all(
        Array.from(selectedMemberIds).map(userId =>
          updateMemberPermission.mutateAsync({
            teamId: team.id,
            userId,
            data: { team_permission: permission }
          })
        )
      );
      setSelectedMemberIds(new Set());
      alert(`Successfully updated ${selectedMemberIds.size} member(s) to ${permission} permission`);
    } catch (error: any) {
      alert(`Failed to update permissions: ${error.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleBulkRemoveMembers = async () => {
    if (!team || selectedMemberIds.size === 0) return;

    const confirmed = window.confirm(
      `Are you sure you want to remove ${selectedMemberIds.size} member(s) from this team?`
    );
    if (!confirmed) return;

    setActionLoading(true);
    try {
      await Promise.all(
        Array.from(selectedMemberIds).map(userId =>
          removeMember.mutateAsync({ teamId: team.id, userId })
        )
      );
      setSelectedMemberIds(new Set());
      alert(`Successfully removed ${selectedMemberIds.size} member(s)`);
    } catch (error: any) {
      alert(`Failed to remove members: ${error.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleBulkRequestObservable = async () => {
    if (!team || selectedMemberIds.size === 0) return;

    setActionLoading(true);
    try {
      // Request Observable status for each selected member
      await Promise.all(
        Array.from(selectedMemberIds).map(userId =>
          requestObservable.mutateAsync({ teamId: team.id, userId })
        )
      );
      setSelectedMemberIds(new Set());
      alert(`Observable status requested for ${selectedMemberIds.size} member(s). They will receive a request to approve.`);
    } catch (error: any) {
      alert(`Failed to request Observable status: ${error.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnshareResource = async (resourceType: 'agent' | 'dataset', resourceId: string) => {
    if (!team) return;

    const confirmed = window.confirm(`Remove this ${resourceType} from the team? This will revoke access for all members.`);
    if (!confirmed) return;

    try {
      await unshareResource.mutateAsync({
        teamId: team.id,
        resourceType,
        resourceId
      });
    } catch (error: any) {
      alert(`Failed to unshare ${resourceType}: ${error.message}`);
    }
  };

  const toggleResourceExpansion = (resourceKey: string) => {
    setExpandedResourceIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(resourceKey)) {
        newSet.delete(resourceKey);
      } else {
        newSet.add(resourceKey);
      }
      return newSet;
    });
  };

  const handleUpdateResourcePermission = async (
    resourceType: 'agent' | 'dataset',
    resourceId: string,
    userId: string,
    currentPermissions: Record<string, 'read' | 'edit'>,
    newPermission: 'read' | 'edit' | null
  ) => {
    if (!team) return;

    try {
      // Build updated permissions object
      const updatedPermissions = { ...currentPermissions };

      if (newPermission === null) {
        // Remove permission
        delete updatedPermissions[userId];
      } else {
        // Set/update permission
        updatedPermissions[userId] = newPermission;
      }

      // If no permissions left, unshare the entire resource from the team
      if (Object.keys(updatedPermissions).length === 0) {
        await unshareResource.mutateAsync({
          teamId: team.id,
          resourceType: resourceType,
          resourceId: resourceId
        });
      } else {
        // Call share endpoint to update permissions
        await shareResource.mutateAsync({
          teamId: team.id,
          data: {
            resource_type: resourceType,
            resource_id: resourceId,
            user_permissions: updatedPermissions
          }
        });
      }
    } catch (error: any) {
      alert(`Failed to update permission: ${error.message}`);
    }
  };

  if (!open || !team) return null;

  return (
    <>
      {createPortal(
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
            className="fixed right-0 top-0 h-screen w-full max-w-4xl bg-gt-white shadow-2xl z-[1000] overflow-y-auto"
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
                  <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                    <UsersIcon className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">{team.name}</h2>
                    <p className="text-sm text-gray-600">Manage team members and resources</p>
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

            {/* Tabs */}
            <div className="p-6" onClick={(e) => e.stopPropagation()}>
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full">
                <TabsList className="grid grid-cols-3 w-full mb-6">
                  <TabsTrigger value="overview" className="flex items-center gap-2">
                    <Info className="w-4 h-4" />
                    Overview
                  </TabsTrigger>
                  <TabsTrigger value="members" className="flex items-center gap-2">
                    <UsersIcon className="w-4 h-4" />
                    Members ({team.member_count})
                  </TabsTrigger>
                  <TabsTrigger value="resources" className="flex items-center gap-2">
                    <Share2 className="w-4 h-4" />
                    Resources ({team.shared_resource_count})
                  </TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-6">
                  {/* Edit Team Button - Only for owners/admins */}
                  {team.can_manage && (
                    <div className="flex justify-end">
                      <Button
                        size="sm"
                        className={showEditTeamForm ? "bg-gray-500 hover:bg-gray-600" : "bg-blue-600 hover:bg-blue-700"}
                        onClick={() => setShowEditTeamForm(!showEditTeamForm)}
                      >
                        {showEditTeamForm ? (
                          <>
                            <X className="w-4 h-4 mr-2" />
                            Cancel
                          </>
                        ) : (
                          <>
                            <Edit3 className="w-4 h-4 mr-2" />
                            Edit Team
                          </>
                        )}
                      </Button>
                    </div>
                  )}

                  {/* Edit Team Inline Form */}
                  <AnimatePresence>
                    {showEditTeamForm && team.can_manage && (
                      <EditTeamInlineForm
                        team={team}
                        onUpdateTeam={handleUpdateTeam}
                        onCancel={() => setShowEditTeamForm(false)}
                        loading={actionLoading}
                      />
                    )}
                  </AnimatePresence>

                  <div className="bg-gray-50 rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Team Information</h3>
                    <div className="space-y-3">
                      <div>
                        <span className="text-sm text-gray-600">Name:</span>
                        <p className="text-base font-medium text-gray-900">{team.name}</p>
                      </div>
                      {team.description && (
                        <div>
                          <span className="text-sm text-gray-600">Description:</span>
                          <p className="text-base text-gray-900">{team.description}</p>
                        </div>
                      )}
                      <div>
                        <span className="text-sm text-gray-600">Created:</span>
                        <p className="text-base text-gray-900">
                          {new Date(team.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="pt-3 border-t border-gray-200">
                        <span className="text-sm text-gray-600">Owner:</span>
                        <p className="text-base font-medium text-gray-900">{team.owner_name || 'Unknown'}</p>
                        {team.owner_email && (
                          <p className="text-sm text-gray-500">{team.owner_email}</p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="flex items-center gap-3">
                        <UsersIcon className="w-8 h-8 text-blue-600" />
                        <div>
                          <p className="text-2xl font-bold text-blue-900">{team.member_count}</p>
                          <p className="text-sm text-blue-700">
                            {team.member_count === 1 ? 'Member' : 'Members'}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                      <div className="flex items-center gap-3">
                        <Share2 className="w-8 h-8 text-green-600" />
                        <div>
                          <p className="text-2xl font-bold text-green-900">{team.shared_resource_count}</p>
                          <p className="text-sm text-green-700">Shared Resources</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gt-green/10 border border-gt-green/30 rounded-lg p-4">
                    <h4 className="font-semibold text-gray-900 mb-2">Quick Actions</h4>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setActiveTab('members')}
                        className="flex items-center gap-2"
                      >
                        <UsersIcon className="w-4 h-4" />
                        Manage Members
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setActiveTab('resources')}
                        className="flex items-center gap-2"
                      >
                        <Share2 className="w-4 h-4" />
                        Manage Resources
                      </Button>
                    </div>
                  </div>
                </TabsContent>

                {/* Members Tab */}
                <TabsContent value="members">
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-semibold text-gray-900">Team Members</h3>
                      {team.can_manage && (
                        <Button
                          size="sm"
                          className={showAddMemberForm ? "bg-gray-500 hover:bg-gray-600" : "bg-gt-green hover:bg-gt-green/90"}
                          onClick={() => setShowAddMemberForm(!showAddMemberForm)}
                        >
                          {showAddMemberForm ? (
                            <>
                              <X className="w-4 h-4 mr-2" />
                              Cancel
                            </>
                          ) : (
                            <>
                              <Plus className="w-4 h-4 mr-2" />
                              Add Member
                            </>
                          )}
                        </Button>
                      )}
                    </div>

                    {/* Add Member Inline Form */}
                    <AnimatePresence>
                      {showAddMemberForm && (
                        <AddMemberInlineForm
                          teamId={team.id}
                          teamName={team.name}
                          onAddMember={handleAddMember}
                          onCancel={() => setShowAddMemberForm(false)}
                          loading={actionLoading}
                        />
                      )}
                    </AnimatePresence>

                    {membersLoading ? (
                      <div className="text-center py-12">
                        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-gt-green border-r-transparent"></div>
                        <p className="text-gray-600 mt-4">Loading members...</p>
                      </div>
                    ) : members.length === 0 ? (
                      <div className="text-center py-12 bg-gray-50 rounded-lg">
                        <UsersIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <h4 className="text-lg font-semibold text-gray-900 mb-2">No members yet</h4>
                        <p className="text-gray-600 mb-4">Add members to start collaborating</p>
                        {team.can_manage && (
                          <Button
                            size="sm"
                            className="bg-gt-green hover:bg-gt-green/90"
                            onClick={() => setShowAddMemberForm(true)}
                          >
                            <Plus className="w-4 h-4 mr-2" />
                            Add First Member
                          </Button>
                        )}
                      </div>
                    ) : (
                      <>
                        {/* Owner Section */}
                        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm font-semibold text-amber-900 mb-1">Team Owner</p>
                              <p className="font-medium text-gray-900">{team.owner_name || 'Unknown'}</p>
                              {team.owner_email && (
                                <p className="text-sm text-gray-600">{team.owner_email}</p>
                              )}
                              <p className="text-xs text-gray-500 mt-1">
                                Created: {new Date(team.created_at).toLocaleDateString()}
                              </p>
                            </div>
                            <span className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-amber-100 text-amber-800">
                              Owner
                            </span>
                          </div>
                        </div>

                        {members.filter(m => !m.is_owner).length === 0 ? (
                          <div className="text-center py-12 bg-gray-50 rounded-lg">
                            <UsersIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                            <h4 className="text-lg font-semibold text-gray-900 mb-2">No members yet</h4>
                            <p className="text-gray-600 mb-4">Add members to start collaborating</p>
                            {team.can_manage && (
                              <Button
                                size="sm"
                                className="bg-gt-green hover:bg-gt-green/90"
                                onClick={() => setShowAddMemberForm(true)}
                              >
                                <Plus className="w-4 h-4 mr-2" />
                                Add First Member
                              </Button>
                            )}
                          </div>
                        ) : (
                          <>
                            {/* Bulk Actions Bar */}
                            {(team.can_manage || team.user_permission === 'manager') && selectedMemberIds.size > 0 && (
                              <div className="bg-gt-green/10 border border-gt-green/20 rounded-lg p-4 mb-4">
                                <div className="flex items-center justify-between gap-4 flex-wrap">
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-gray-900">
                                      {selectedMemberIds.size} member{selectedMemberIds.size > 1 ? 's' : ''} selected
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => handleBulkChangePermission('read')}
                                      disabled={actionLoading}
                                      className="text-xs"
                                    >
                                      <Shield className="w-3 h-3 mr-1" />
                                      Change to Member
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => handleBulkChangePermission('share')}
                                      disabled={actionLoading}
                                      className="text-xs"
                                    >
                                      <Shield className="w-3 h-3 mr-1" />
                                      Change to Contributor
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => handleBulkChangePermission('manager')}
                                      disabled={actionLoading}
                                      className="text-xs"
                                    >
                                      <Shield className="w-3 h-3 mr-1" />
                                      Change to Manager
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={handleBulkRequestObservable}
                                      disabled={actionLoading}
                                      className="text-xs text-green-600 hover:bg-green-50 border-green-200"
                                    >
                                      <Target className="w-3 h-3 mr-1" />
                                      Request Observable
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={handleBulkRemoveMembers}
                                      disabled={actionLoading}
                                      className="text-xs text-red-600 hover:bg-red-50"
                                    >
                                      <UserX className="w-3 h-3 mr-1" />
                                      Remove Selected
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setSelectedMemberIds(new Set())}
                                      className="text-xs"
                                    >
                                      Clear Selection
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Members Table */}
                            <div className="border rounded-lg overflow-hidden">
                              <table className="w-full">
                                <thead className="bg-gray-50 border-b">
                                  <tr>
                                    {(team.can_manage || team.user_permission === 'manager') && (
                                      <th className="w-12 px-4 py-3">
                                        <Checkbox
                                          checked={isAllSelected}
                                          onCheckedChange={handleSelectAll}
                                          disabled={selectableMembers.length === 0}
                                        />
                                      </th>
                                    )}
                                    <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900">Member</th>
                                    <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900">Permission</th>
                                    <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900">Observable</th>
                                    <th className="text-left px-4 py-3 text-sm font-semibold text-gray-900">Joined</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {members.filter(m => !m.is_owner).map((member, idx) => (
                                    <tr key={member.user_id} className={idx % 2 === 0 ? 'bg-gt-white' : 'bg-gray-50'}>
                                      {(team.can_manage || team.user_permission === 'manager') && (
                                        <td className="px-4 py-3">
                                        <Checkbox
                                          checked={selectedMemberIds.has(member.user_id)}
                                          onCheckedChange={(checked) => handleSelectMember(member.user_id, checked as boolean)}
                                          disabled={
                                            member.is_owner ||
                                            member.status === 'pending' ||
                                            (team.user_permission === 'manager' && member.team_permission === 'manager')
                                          }
                                        />
                                      </td>
                                    )}
                                    <td className="px-4 py-3">
                                      <div>
                                        <div className="flex items-center gap-2">
                                          <p className="font-medium text-gray-900">{member.user_name}</p>
                                          {member.is_owner && (
                                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                                              Owner
                                            </span>
                                          )}
                                          {member.status === 'pending' && (
                                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                                              Invited
                                            </span>
                                          )}
                                        </div>
                                        <p className="text-sm text-gray-600">{member.user_email}</p>
                                      </div>
                                    </td>
                                    <td className="px-4 py-3">
                                      {member.is_owner ? (
                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                                          Owner
                                        </span>
                                      ) : (
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                          member.team_permission === 'manager'
                                            ? 'bg-gt-green/20 text-gt-green'
                                            : member.team_permission === 'share'
                                            ? 'bg-blue-100 text-blue-800'
                                            : 'bg-gray-100 text-gray-800'
                                        }`}>
                                          {member.team_permission === 'read' ? 'Member' :
                                           member.team_permission === 'share' ? 'Contributor' :
                                           'Manager'}
                                        </span>
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      {member.observable_consent_status === 'approved' ? (
                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                          Observable
                                        </span>
                                      ) : member.observable_consent_status === 'pending' ? (
                                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                          Pending
                                        </span>
                                      ) : (
                                        <span className="text-xs text-gray-400">—</span>
                                      )}
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-600">
                                      {member.joined_at
                                        ? new Date(member.joined_at).toLocaleDateString()
                                        : member.status === 'pending'
                                          ? 'Pending'
                                          : '—'
                                      }
                                    </td>
                                  </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </>
                        )}
                      </>
                    )}
                  </div>
                </TabsContent>

                {/* Resources Tab */}
                <TabsContent value="resources">
                  <div className="space-y-4">
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-semibold text-gray-900">Shared Resources</h3>
                      {(team.can_manage || team.user_permission === 'share' || team.user_permission === 'manager') ? (
                        <Button
                          size="sm"
                          className={showShareResourceForm ? "bg-gray-500 hover:bg-gray-600" : "bg-gt-green hover:bg-gt-green/90"}
                          onClick={() => setShowShareResourceForm(!showShareResourceForm)}
                        >
                          {showShareResourceForm ? (
                            <>
                              <X className="w-4 h-4 mr-2" />
                              Cancel
                            </>
                          ) : (
                            <>
                              <Plus className="w-4 h-4 mr-2" />
                              Share Resource
                            </>
                          )}
                        </Button>
                      ) : (
                        <p className="text-sm text-gray-500">Only members with share permission can share resources</p>
                      )}
                    </div>

                    {/* Share Resource Inline Form */}
                    <AnimatePresence>
                      {showShareResourceForm && (
                        <ShareResourceInlineForm
                          teamId={team.id}
                          teamName={team.name}
                          teamMembers={members}
                          onShareResource={handleShareResource}
                          onCancel={() => setShowShareResourceForm(false)}
                          loading={actionLoading}
                        />
                      )}
                    </AnimatePresence>

                    {resourcesLoading ? (
                      <div className="text-center py-12">
                        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-gt-green border-r-transparent"></div>
                        <p className="text-gray-600 mt-4">Loading resources...</p>
                      </div>
                    ) : resources.length === 0 ? (
                      <div className="text-center py-12 bg-gray-50 rounded-lg">
                        <Share2 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                        <h4 className="text-lg font-semibold text-gray-900 mb-2">No resources shared yet</h4>
                        <p className="text-gray-600 mb-4">Share agents or datasets to collaborate</p>
                        {(team.can_manage || team.user_permission === 'share') ? (
                          <Button
                            size="sm"
                            className="bg-gt-green hover:bg-gt-green/90"
                            onClick={() => setShowShareResourceForm(true)}
                          >
                            <Plus className="w-4 h-4 mr-2" />
                            Share First Resource
                          </Button>
                        ) : (
                          <p className="text-sm text-gray-500 mt-2">Only members with share permission can share resources</p>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {resources.map((resource) => {
                          const resourceKey = `${resource.resource_type}-${resource.resource_id}`;
                          const isExpanded = expandedResourceIds.has(resourceKey);

                          return (
                            <div
                              key={resourceKey}
                              className="border rounded-lg overflow-hidden hover:shadow-md transition-shadow"
                            >
                              {/* Resource Header */}
                              <div className="flex items-center justify-between p-4 bg-gt-white">
                                <div className="flex items-center gap-3 flex-1">
                                  <button
                                    onClick={() => toggleResourceExpansion(resourceKey)}
                                    className="text-gray-400 hover:text-gray-600"
                                  >
                                    {isExpanded ? (
                                      <ChevronDown className="w-5 h-5" />
                                    ) : (
                                      <ChevronRight className="w-5 h-5" />
                                    )}
                                  </button>
                                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                                    resource.resource_type === 'agent'
                                      ? 'bg-blue-100 text-blue-800'
                                      : 'bg-green-100 text-green-800'
                                  }`}>
                                    {resource.resource_type}
                                  </span>
                                  <p className="font-medium text-gray-900">{resource.resource_name}</p>
                                  <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 flex items-center gap-1">
                                    <User className="w-3 h-3" />
                                    {resource.resource_owner}
                                  </span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className="text-sm text-gray-500">
                                    {Object.keys(resource.user_permissions).length} members
                                  </span>
                                  {(team.can_manage || team.user_permission === 'manager') && (
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                      onClick={() => handleUnshareResource(resource.resource_type, resource.resource_id)}
                                      disabled={unshareResource.isPending}
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  )}
                                </div>
                              </div>

                              {/* Expanded Member Permissions */}
                              {isExpanded && (
                                <div className="border-t bg-gray-50 p-4">
                                  <h4 className="text-sm font-medium text-gray-700 mb-3">Member Permissions</h4>
                                  <div className="space-y-2">
                                    {members.filter(m => !m.is_owner).map((member) => {
                                      const hasRead = resource.user_permissions[member.user_id] === 'read' ||
                                                     resource.user_permissions[member.user_id] === 'edit';
                                      const hasEdit = resource.user_permissions[member.user_id] === 'edit';

                                      return (
                                        <div
                                          key={member.user_id}
                                          className="flex items-center justify-between p-2 bg-gt-white rounded border"
                                        >
                                          <span className="text-sm font-medium text-gray-900">
                                            {member.user_name || member.user_email}
                                          </span>
                                          <div className="flex items-center gap-4">
                                            <div className="flex items-center gap-2">
                                              <Checkbox
                                                id={`${resourceKey}-${member.user_id}-read`}
                                                checked={hasRead}
                                                onCheckedChange={(checked) =>
                                                  handleUpdateResourcePermission(
                                                    resource.resource_type,
                                                    resource.resource_id,
                                                    member.user_id,
                                                    resource.user_permissions,
                                                    checked ? 'read' : null
                                                  )
                                                }
                                                disabled={shareResource.isPending || !(team.can_manage || team.user_permission === 'manager') || hasEdit}
                                              />
                                              <label
                                                htmlFor={`${resourceKey}-${member.user_id}-read`}
                                                className="text-xs cursor-pointer flex items-center gap-1"
                                              >
                                                <Eye className="w-3 h-3" />
                                                View
                                              </label>
                                            </div>
                                            <div className="flex items-center gap-2">
                                              <Checkbox
                                                id={`${resourceKey}-${member.user_id}-edit`}
                                                checked={hasEdit}
                                                onCheckedChange={(checked) => {
                                                  // Only allow Edit if View is enabled
                                                  if (checked) {
                                                    handleUpdateResourcePermission(
                                                      resource.resource_type,
                                                      resource.resource_id,
                                                      member.user_id,
                                                      resource.user_permissions,
                                                      'edit'
                                                    );
                                                  } else {
                                                    // Unchecking Edit should revert to read only if they have any permission
                                                    const currentPermission = resource.user_permissions[member.user_id];
                                                    handleUpdateResourcePermission(
                                                      resource.resource_type,
                                                      resource.resource_id,
                                                      member.user_id,
                                                      resource.user_permissions,
                                                      currentPermission ? 'read' : null
                                                    );
                                                  }
                                                }}
                                                disabled={shareResource.isPending || !(team.can_manage || team.user_permission === 'manager') || !resource.user_permissions[member.user_id]}
                                              />
                                              <label
                                                htmlFor={`${resourceKey}-${member.user_id}-edit`}
                                                className="text-xs cursor-pointer flex items-center gap-1"
                                              >
                                                <EditIcon className="w-3 h-3" />
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
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )}
    </>
  );
}
