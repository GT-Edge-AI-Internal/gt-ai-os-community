/**
 * GT 2.0 Team Collaboration Service
 *
 * API client for team management, member management, and resource sharing.
 * Supports two-tier permission model:
 * - Tier 1 (Team-level): 'read' or 'share' - set by team owner
 * - Tier 2 (Resource-level): 'read' or 'edit' - set per-user by resource sharer
 */

import { api } from './api';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

export interface Team {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  owner_id: string;
  is_owner: boolean;
  can_manage: boolean;
  user_permission?: 'read' | 'share';  // Current user's team permission (null if owner)
  member_count: number;
  shared_resource_count: number;
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  user_id: string;
  user_email: string;
  user_name: string;
  team_permission: 'read' | 'share' | 'manager';
  resource_permissions: Record<string, 'read' | 'edit'>;
  is_owner: boolean;
  is_observable: boolean;
  observable_consent_status: 'none' | 'pending' | 'approved' | 'revoked';
  observable_consent_at?: string;
  status: 'pending' | 'accepted' | 'declined';
  invited_at?: string;
  responded_at?: string;
  joined_at: string;
}

export interface SharedResource {
  resource_type: 'agent' | 'dataset';
  resource_id: string;
  resource_name: string;
  resource_owner: string;
  user_permissions: Record<string, 'read' | 'edit'>;
}

export interface TeamListResponse {
  data: Team[];
  total: number;
}

export interface TeamResponse {
  data: Team;
}

export interface MemberListResponse {
  data: TeamMember[];
  total: number;
}

export interface MemberResponse {
  data: TeamMember;
}

export interface SharedResourcesResponse {
  data: SharedResource[];
  total: number;
}

// Invitation types
export interface TeamInvitation {
  id: string;
  team_id: string;
  team_name: string;
  team_description?: string;
  owner_name: string;
  owner_email: string;
  team_permission: 'read' | 'share' | 'manager';
  invited_at: string;
}

export interface InvitationListResponse {
  data: TeamInvitation[];
  total: number;
}

// Request types
export interface CreateTeamRequest {
  name: string;
  description?: string;
}

export interface UpdateTeamRequest {
  name?: string;
  description?: string;
}

export interface AddMemberRequest {
  user_email: string;
  team_permission: 'read' | 'share' | 'manager';
}

export interface UpdateMemberPermissionRequest {
  team_permission: 'read' | 'share' | 'manager';
}

export interface ShareResourceRequest {
  resource_type: 'agent' | 'dataset';
  resource_id: string;
  user_permissions: Record<string, 'read' | 'edit'>;
}

// ============================================================================
// TEAM CRUD OPERATIONS
// ============================================================================

/**
 * List all teams where the current user is owner or member
 */
export async function listTeams() {
  return api.get<TeamListResponse>('/api/v1/teams');
}

/**
 * Get team details by ID
 */
export async function getTeam(teamId: string) {
  return api.get<TeamResponse>(`/api/v1/teams/${teamId}`);
}

/**
 * Create a new team (current user becomes owner)
 */
export async function createTeam(request: CreateTeamRequest) {
  return api.post<TeamResponse>('/api/v1/teams', request);
}

/**
 * Update team name/description
 * Requires: Team ownership or admin/developer role
 */
export async function updateTeam(teamId: string, request: UpdateTeamRequest) {
  return api.put<TeamResponse>(`/api/v1/teams/${teamId}`, request);
}

/**
 * Delete a team and all its memberships
 * Requires: Team ownership or admin/developer role
 */
export async function deleteTeam(teamId: string) {
  return api.delete<void>(`/api/v1/teams/${teamId}`);
}

// ============================================================================
// TEAM MEMBER OPERATIONS
// ============================================================================

/**
 * List all members of a team with their permissions
 */
export async function listTeamMembers(teamId: string) {
  return api.get<MemberListResponse>(`/api/v1/teams/${teamId}/members`);
}

/**
 * Add a user to the team with specified permission
 * Requires: Team ownership or admin/developer role
 */
export async function addTeamMember(teamId: string, request: AddMemberRequest) {
  return api.post<MemberResponse>(`/api/v1/teams/${teamId}/members`, request);
}

/**
 * Update a team member's permission level
 * Requires: Team ownership or admin/developer role
 */
export async function updateMemberPermission(
  teamId: string,
  userId: string,
  request: UpdateMemberPermissionRequest
) {
  return api.put<MemberResponse>(
    `/api/v1/teams/${teamId}/members/${userId}`,
    request
  );
}

/**
 * Remove a user from the team
 * Requires: Team ownership or admin/developer role
 */
export async function removeTeamMember(teamId: string, userId: string) {
  return api.delete<void>(`/api/v1/teams/${teamId}/members/${userId}`);
}

// ============================================================================
// RESOURCE SHARING OPERATIONS
// ============================================================================

/**
 * Share a resource (agent/dataset) to team with per-user permissions
 * Requires: Team ownership or 'share' team permission
 */
export async function shareResourceToTeam(
  teamId: string,
  request: ShareResourceRequest
) {
  return api.post<{ message: string; success: boolean }>(
    `/api/v1/teams/${teamId}/share`,
    request
  );
}

/**
 * Remove resource sharing from team
 * Requires: Team ownership or 'share' team permission
 */
export async function unshareResourceFromTeam(
  teamId: string,
  resourceType: 'agent' | 'dataset',
  resourceId: string
) {
  return api.delete<void>(
    `/api/v1/teams/${teamId}/share/${resourceType}/${resourceId}`
  );
}

/**
 * List all resources shared to a team
 * Optional filter by resource type
 */
export async function listSharedResources(
  teamId: string,
  resourceType?: 'agent' | 'dataset'
) {
  const params = resourceType ? { resource_type: resourceType } : undefined;
  return api.get<SharedResourcesResponse>(
    `/api/v1/teams/${teamId}/resources`,
    { params }
  );
}

// ============================================================================
// INVITATION OPERATIONS
// ============================================================================

/**
 * Get current user's pending team invitations
 */
export async function getPendingInvitations() {
  return api.get<InvitationListResponse>('/api/v1/teams/invitations');
}

/**
 * Accept a team invitation
 */
export async function acceptInvitation(invitationId: string) {
  return api.post<MemberResponse>(
    `/api/v1/teams/invitations/${invitationId}/accept`
  );
}

/**
 * Decline a team invitation
 */
export async function declineInvitation(invitationId: string) {
  return api.post<void>(
    `/api/v1/teams/invitations/${invitationId}/decline`
  );
}

/**
 * Get pending invitations for a team (owner view)
 * Requires: Team ownership or admin role
 */
export async function getTeamPendingInvitations(teamId: string) {
  return api.get<InvitationListResponse>(
    `/api/v1/teams/${teamId}/invitations`
  );
}

/**
 * Cancel a pending invitation (owner only)
 * Requires: Team ownership or admin role
 */
export async function cancelInvitation(teamId: string, invitationId: string) {
  return api.delete<void>(
    `/api/v1/teams/${teamId}/invitations/${invitationId}`
  );
}

// ============================================================================
// OBSERVABLE REQUEST OPERATIONS
// ============================================================================

export interface ObservableRequest {
  team_id: string;
  team_name: string;
  requested_by_name: string;
  requested_by_email: string;
  requested_at: string;
}

/**
 * Get current user's pending Observable requests from team managers
 */
export async function getPendingObservableRequests() {
  return api.get<{ data: ObservableRequest[] }>(
    '/api/v1/teams/observable-requests'
  );
}

/**
 * Approve an Observable request for a specific team
 * This allows team managers to view your activity on the observability dashboard
 */
export async function approveObservableRequest(teamId: string) {
  return api.post<{ message: string; success: boolean }>(
    `/api/v1/teams/${teamId}/observable/approve`
  );
}

/**
 * Revoke Observable status for a team
 * Removes Observable status and prevents managers from viewing your activity
 */
export async function revokeObservableStatus(teamId: string) {
  return api.delete<void>(
    `/api/v1/teams/${teamId}/observable`
  );
}

/**
 * Request Observable status from a team member (manager/owner action)
 * Sends a request that the member must approve
 * Requires: Team ownership or manager permission
 */
export async function requestObservableStatus(teamId: string, userId: string) {
  return api.post<{ message: string; success: boolean }>(
    `/api/v1/teams/${teamId}/members/${userId}/request-observable`
  );
}
