'use client';

import { useState } from 'react';
import { Plus, Users, Search } from 'lucide-react';
import { AppLayout } from '@/components/layout/app-layout';
import { AuthGuard } from '@/components/auth/auth-guard';
import { GT2_CAPABILITIES } from '@/lib/capabilities';
import {
  TeamCard,
  TeamCreateModal,
  TeamEditModal,
  DeleteTeamDialog,
  LeaveTeamDialog,
  TeamManagementPanel,
  InvitationPanel,
  ObservableRequestPanel,
  type CreateTeamData,
  type UpdateTeamData
} from '@/components/teams';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { usePageTitle } from '@/hooks/use-page-title';
import {
  useTeams,
  useCreateTeam,
  useUpdateTeam,
  useDeleteTeam,
  useRemoveTeamMember
} from '@/hooks/use-teams';
import type { Team } from '@/services';
import { getAuthToken, parseTokenPayload } from '@/services/auth';

function TeamsPageContent() {
  usePageTitle('Teams');

  // Search state
  const [searchQuery, setSearchQuery] = useState('');

  // React Query hooks
  const { data: teams = [], isLoading: loading } = useTeams();
  const createTeam = useCreateTeam();
  const updateTeam = useUpdateTeam();
  const deleteTeam = useDeleteTeam();
  const removeTeamMember = useRemoveTeamMember();

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [showLeaveDialog, setShowLeaveDialog] = useState(false);
  const [showManagementPanel, setShowManagementPanel] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);

  // Filter teams by search query
  const filteredTeams = teams.filter(team =>
    team.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    team.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Calculate stats
  const ownedTeams = teams.filter(t => t.is_owner).length;
  const memberTeams = teams.filter(t => !t.is_owner).length;

  // Team action handlers
  const handleCreateTeam = async (data: CreateTeamData) => {
    try {
      await createTeam.mutateAsync(data);
      console.log('Team created successfully');
    } catch (error) {
      console.error('Failed to create team:', error);
    }
  };

  const handleEditTeam = (teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    if (team) {
      setSelectedTeam(team);
      setShowEditModal(true);
    }
  };

  const handleUpdateTeam = async (teamId: string, data: UpdateTeamData) => {
    try {
      await updateTeam.mutateAsync({ teamId, data });
      console.log('Team updated successfully');
    } catch (error) {
      console.error('Failed to update team:', error);
    }
  };

  const handleDeleteTeam = (teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    if (team) {
      setSelectedTeam(team);
      setShowDeleteDialog(true);
    }
  };

  const handleConfirmDelete = async (teamId: string) => {
    try {
      await deleteTeam.mutateAsync(teamId);
      console.log('Team deleted successfully');
    } catch (error) {
      console.error('Failed to delete team:', error);
    }
  };

  const handleManageTeam = (teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    if (team) {
      setSelectedTeam(team);
      setShowManagementPanel(true);
    }
  };

  const handleLeaveTeam = (teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    if (team) {
      setSelectedTeam(team);
      setShowLeaveDialog(true);
    }
  };

  const handleConfirmLeave = async (teamId: string) => {
    try {
      // Get user ID from JWT token
      const token = getAuthToken();
      if (!token) {
        console.error('No auth token found');
        alert('Authentication required. Please log in again.');
        return;
      }

      const payload = parseTokenPayload(token);
      if (!payload?.sub) {
        console.error('User ID not found in token');
        alert('Invalid authentication. Please log in again.');
        return;
      }

      // sub contains the user ID from the JWT
      await removeTeamMember.mutateAsync({ teamId, userId: payload.sub });
      console.log('Successfully left team');
    } catch (error: any) {
      console.error('Failed to leave team:', error);
      alert(`Failed to leave team: ${error.message || 'An error occurred'}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <Users className="w-8 h-8 text-gt-green" />
              Teams
            </h1>
            <p className="text-gray-600 mt-1">
              Collaborate and share resources with your team
            </p>
          </div>

          <Button
            onClick={() => setShowCreateModal(true)}
            className="bg-gt-green hover:bg-gt-green/90"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Team
          </Button>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Total:</span>
            <span className="font-semibold text-gray-900">{teams.length}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Owned:</span>
            <span className="font-semibold text-gt-green">{ownedTeams}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-600">Member of:</span>
            <span className="font-semibold text-blue-600">{memberTeams}</span>
          </div>
        </div>
      </div>

      {/* Pending Invitations */}
      <InvitationPanel />

      {/* Observable Requests */}
      <ObservableRequestPanel />

      {/* Search Bar */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5 z-10" />
          <Input
            type="text"
            placeholder="Search teams..."
            value={searchQuery}
            onChange={(value) => setSearchQuery(value)}
            className="pl-10"
            clearable
          />
        </div>
      </div>

      {/* Teams List */}
      {loading ? (
        <div className="bg-white rounded-lg shadow-sm border p-12 text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-gt-green border-r-transparent"></div>
          <p className="text-gray-600 mt-4">Loading teams...</p>
        </div>
      ) : filteredTeams.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border p-12 text-center">
          <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {searchQuery ? 'No teams found' : 'No teams yet'}
          </h3>
          <p className="text-gray-600 mb-6">
            {searchQuery
              ? 'Try adjusting your search query'
              : 'Create your first team to start collaborating'}
          </p>
          {!searchQuery && (
            <Button
              onClick={() => setShowCreateModal(true)}
              className="bg-gt-green hover:bg-gt-green/90"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Team
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTeams.map(team => (
            <TeamCard
              key={team.id}
              team={team}
              onManage={handleManageTeam}
              onEdit={handleEditTeam}
              onDelete={handleDeleteTeam}
              onLeave={handleLeaveTeam}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      <TeamCreateModal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        onCreateTeam={handleCreateTeam}
        loading={createTeam.isPending}
      />

      <TeamEditModal
        open={showEditModal}
        team={selectedTeam}
        onOpenChange={setShowEditModal}
        onUpdateTeam={handleUpdateTeam}
        loading={updateTeam.isPending}
      />

      <DeleteTeamDialog
        open={showDeleteDialog}
        team={selectedTeam}
        onOpenChange={setShowDeleteDialog}
        onConfirm={handleConfirmDelete}
        loading={deleteTeam.isPending}
      />

      <LeaveTeamDialog
        open={showLeaveDialog}
        team={selectedTeam}
        onOpenChange={setShowLeaveDialog}
        onConfirm={handleConfirmLeave}
        loading={removeTeamMember.isPending}
      />

      <TeamManagementPanel
        open={showManagementPanel}
        team={selectedTeam}
        onOpenChange={setShowManagementPanel}
      />
    </div>
  );
}

export default function TeamsPage() {
  return (
    <AuthGuard requiredCapabilities={[GT2_CAPABILITIES.DATASETS_READ]}>
      <AppLayout>
        <TeamsPageContent />
      </AppLayout>
    </AuthGuard>
  );
}
