/**
 * React Query hooks for Team Collaboration
 *
 * Provides centralized, cached team data access with automatic
 * invalidation on mutations.
 *
 * Supports:
 * - Team CRUD operations
 * - Member management
 * - Resource sharing (agents & datasets)
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listTeams,
  getTeam,
  createTeam,
  updateTeam,
  deleteTeam,
  listTeamMembers,
  addTeamMember,
  updateMemberPermission,
  removeTeamMember,
  shareResourceToTeam,
  unshareResourceFromTeam,
  listSharedResources,
  getPendingInvitations,
  acceptInvitation,
  declineInvitation,
  getTeamPendingInvitations,
  cancelInvitation,
  getPendingObservableRequests,
  approveObservableRequest,
  revokeObservableStatus,
  requestObservableStatus,
  type Team,
  type TeamMember,
  type SharedResource,
  type CreateTeamRequest,
  type UpdateTeamRequest,
  type AddMemberRequest,
  type UpdateMemberPermissionRequest,
  type ShareResourceRequest,
} from '@/services';

// ============================================================================
// QUERY KEY FACTORY
// ============================================================================

export const teamKeys = {
  all: ['teams'] as const,
  lists: () => [...teamKeys.all, 'list'] as const,
  list: () => [...teamKeys.lists()] as const,
  details: () => [...teamKeys.all, 'detail'] as const,
  detail: (id: string) => [...teamKeys.details(), id] as const,
  members: (id: string) => [...teamKeys.detail(id), 'members'] as const,
  resources: (id: string) => [...teamKeys.detail(id), 'resources'] as const,
  resourcesByType: (id: string, type: 'agent' | 'dataset') =>
    [...teamKeys.resources(id), type] as const,
};

// ============================================================================
// TEAM QUERIES
// ============================================================================

/**
 * List all teams where the current user is owner or member
 */
export function useTeams() {
  return useQuery({
    queryKey: teamKeys.list(),
    queryFn: async () => {
      const response = await listTeams();
      if (response.error) throw new Error(response.error);
      return response.data?.data || [];
    },
    staleTime: 60000, // 1 minute
  });
}

/**
 * Get team details by ID
 */
export function useTeam(teamId: string | undefined) {
  return useQuery({
    queryKey: teamKeys.detail(teamId || ''),
    queryFn: async () => {
      if (!teamId) throw new Error('Team ID is required');
      const response = await getTeam(teamId);
      if (response.error) throw new Error(response.error);
      return response.data?.data;
    },
    enabled: !!teamId,
    staleTime: 60000, // 1 minute
  });
}

/**
 * List all members of a team with their permissions
 */
export function useTeamMembers(teamId: string | undefined) {
  return useQuery({
    queryKey: teamKeys.members(teamId || ''),
    queryFn: async () => {
      if (!teamId) throw new Error('Team ID is required');
      const response = await listTeamMembers(teamId);
      if (response.error) throw new Error(response.error);
      return response.data?.data || [];
    },
    enabled: !!teamId,
    staleTime: 30000, // 30 seconds
  });
}

/**
 * List all resources shared to a team
 * Optional filter by resource type
 */
export function useSharedResources(
  teamId: string | undefined,
  resourceType?: 'agent' | 'dataset'
) {
  return useQuery({
    queryKey: resourceType
      ? teamKeys.resourcesByType(teamId || '', resourceType)
      : teamKeys.resources(teamId || ''),
    queryFn: async () => {
      if (!teamId) throw new Error('Team ID is required');
      const response = await listSharedResources(teamId, resourceType);
      if (response.error) throw new Error(response.error);
      return response.data?.data || [];
    },
    enabled: !!teamId,
    staleTime: 30000, // 30 seconds
  });
}

// ============================================================================
// TEAM MUTATIONS
// ============================================================================

/**
 * Create new team mutation
 * Invalidates all team queries on success
 */
export function useCreateTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateTeamRequest) => {
      const response = await createTeam(data);
      if (response.error) throw new Error(response.error);
      return response.data?.data;
    },
    onSuccess: () => {
      // Invalidate all team queries to trigger refetch
      queryClient.invalidateQueries({ queryKey: teamKeys.all });
    },
  });
}

/**
 * Update existing team mutation
 * Invalidates team queries on success
 */
export function useUpdateTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      teamId,
      data,
    }: {
      teamId: string;
      data: UpdateTeamRequest;
    }) => {
      const response = await updateTeam(teamId, data);
      if (response.error) throw new Error(response.error);
      return response.data?.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate all team queries
      queryClient.invalidateQueries({ queryKey: teamKeys.all });
      // Specifically invalidate the updated team's detail query
      queryClient.invalidateQueries({ queryKey: teamKeys.detail(variables.teamId) });
    },
  });
}

/**
 * Delete team mutation
 * Invalidates all team queries on success
 */
export function useDeleteTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (teamId: string) => {
      const response = await deleteTeam(teamId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all team queries to remove deleted team from lists
      queryClient.invalidateQueries({ queryKey: teamKeys.all });
    },
  });
}

// ============================================================================
// MEMBER MUTATIONS
// ============================================================================

/**
 * Add team member mutation
 * Invalidates team and member queries on success
 */
export function useAddTeamMember() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      teamId,
      data,
    }: {
      teamId: string;
      data: AddMemberRequest;
    }) => {
      const response = await addTeamMember(teamId, data);
      if (response.error) throw new Error(response.error);
      return response.data?.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate team list (for member counts)
      queryClient.invalidateQueries({ queryKey: teamKeys.list() });
      // Invalidate specific team detail
      queryClient.invalidateQueries({ queryKey: teamKeys.detail(variables.teamId) });
      // Invalidate members list
      queryClient.invalidateQueries({ queryKey: teamKeys.members(variables.teamId) });
    },
  });
}

/**
 * Update member permission mutation
 * Invalidates member queries on success
 */
export function useUpdateMemberPermission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      teamId,
      userId,
      data,
    }: {
      teamId: string;
      userId: string;
      data: UpdateMemberPermissionRequest;
    }) => {
      const response = await updateMemberPermission(teamId, userId, data);
      if (response.error) throw new Error(response.error);
      return response.data?.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate members list
      queryClient.invalidateQueries({ queryKey: teamKeys.members(variables.teamId) });
    },
  });
}

/**
 * Remove team member mutation
 * Invalidates team and member queries on success
 */
export function useRemoveTeamMember() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ teamId, userId }: { teamId: string; userId: string }) => {
      const response = await removeTeamMember(teamId, userId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate team list (for member counts)
      queryClient.invalidateQueries({ queryKey: teamKeys.list() });
      // Invalidate specific team detail
      queryClient.invalidateQueries({ queryKey: teamKeys.detail(variables.teamId) });
      // Invalidate members list
      queryClient.invalidateQueries({ queryKey: teamKeys.members(variables.teamId) });
    },
  });
}

// ============================================================================
// RESOURCE SHARING MUTATIONS
// ============================================================================

/**
 * Share resource to team mutation
 * Invalidates resource queries on success
 */
export function useShareResourceToTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      teamId,
      data,
    }: {
      teamId: string;
      data: ShareResourceRequest;
    }) => {
      const response = await shareResourceToTeam(teamId, data);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate shared resources list
      queryClient.invalidateQueries({ queryKey: teamKeys.resources(variables.teamId) });
      // Invalidate members list (their resource_permissions changed)
      queryClient.invalidateQueries({ queryKey: teamKeys.members(variables.teamId) });
    },
  });
}

/**
 * Unshare resource from team mutation
 * Invalidates resource queries on success
 */
export function useUnshareResourceFromTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      teamId,
      resourceType,
      resourceId,
    }: {
      teamId: string;
      resourceType: 'agent' | 'dataset';
      resourceId: string;
    }) => {
      const response = await unshareResourceFromTeam(teamId, resourceType, resourceId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate shared resources list
      queryClient.invalidateQueries({ queryKey: teamKeys.resources(variables.teamId) });
      // Invalidate members list (their resource_permissions changed)
      queryClient.invalidateQueries({ queryKey: teamKeys.members(variables.teamId) });
    },
  });
}

// ==============================================================================
// INVITATION HOOKS
// ==============================================================================

/**
 * Get pending invitations for current user
 */
export function usePendingInvitations() {
  return useQuery({
    queryKey: ['team-invitations'],
    queryFn: async () => {
      const response = await getPendingInvitations();
      if (response.error) throw new Error(response.error);
      return response.data?.data || [];
    },
  });
}

/**
 * Accept invitation mutation
 * Invalidates teams list and invitations on success
 */
export function useAcceptInvitation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (invitationId: string) => {
      const response = await acceptInvitation(invitationId);
      if (response.error) throw new Error(response.error);
      return response.data?.data;
    },
    retry: false,  // Don't retry - invitation acceptance is idempotent
    onSuccess: () => {
      // Invalidate teams list (user is now a member)
      queryClient.invalidateQueries({ queryKey: teamKeys.all });
      // Invalidate invitations list
      queryClient.invalidateQueries({ queryKey: ['team-invitations'] });
    },
  });
}

/**
 * Decline invitation mutation
 * Invalidates invitations on success
 */
export function useDeclineInvitation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (invitationId: string) => {
      const response = await declineInvitation(invitationId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    retry: false,  // Don't retry - invitation decline is idempotent
    onSuccess: () => {
      // Invalidate invitations list
      queryClient.invalidateQueries({ queryKey: ['team-invitations'] });
    },
  });
}

/**
 * Get pending invitations for a team (owner view)
 */
export function useTeamPendingInvitations(teamId?: string) {
  return useQuery({
    queryKey: ['team-pending-invitations', teamId],
    queryFn: async () => {
      if (!teamId) return [];
      const response = await getTeamPendingInvitations(teamId);
      if (response.error) throw new Error(response.error);
      return response.data?.data || [];
    },
    enabled: !!teamId,
  });
}

/**
 * Cancel invitation mutation (owner only)
 * Invalidates team invitations on success
 */
export function useCancelInvitation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ teamId, invitationId }: { teamId: string; invitationId: string }) => {
      const response = await cancelInvitation(teamId, invitationId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate team invitations
      queryClient.invalidateQueries({ queryKey: ['team-pending-invitations', variables.teamId] });
    },
  });
}

// ============================================================================
// OBSERVABLE REQUEST HOOKS
// ============================================================================

/**
 * Get pending Observable requests for current user
 * Returns requests from team managers asking for Observable status
 */
export function usePendingObservableRequests() {
  return useQuery({
    queryKey: ['observable-requests'],
    queryFn: async () => {
      const response = await getPendingObservableRequests();
      if (response.error) throw new Error(response.error);
      return response.data?.data || [];
    },
    staleTime: 30000, // 30 seconds
  });
}

/**
 * Approve Observable request mutation
 * Allows team managers to view your activity
 * Invalidates requests list and teams list on success
 */
export function useApproveObservableRequest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (teamId: string) => {
      const response = await approveObservableRequest(teamId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate requests list
      queryClient.invalidateQueries({ queryKey: ['observable-requests'] });
      // Invalidate teams list (member observable status changed)
      queryClient.invalidateQueries({ queryKey: teamKeys.all });
    },
  });
}

/**
 * Revoke Observable status mutation
 * Removes Observable status and prevents managers from viewing your activity
 * Invalidates requests list and teams list on success
 */
export function useRevokeObservableStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (teamId: string) => {
      const response = await revokeObservableStatus(teamId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observable-requests'] });
      queryClient.invalidateQueries({ queryKey: teamKeys.all });
    },
  });
}

/**
 * Request Observable status from a team member (manager/owner action)
 * Sends a request that the member must approve
 * Invalidates team members list on success
 */
export function useRequestObservableStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ teamId, userId }: { teamId: string; userId: string }) => {
      const response = await requestObservableStatus(teamId, userId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate team members (pending request status added)
      queryClient.invalidateQueries({ queryKey: teamKeys.members(variables.teamId) });
    },
  });
}
