/**
 * Team Permission Helpers for GT 2.0
 *
 * Implements hierarchical team permission system:
 * - Owner: Full control (edit team, manage all members, view Observable, share resources)
 * - Manager: Limited management (manage non-owner members, view Observable, share resources, invite)
 * - Contributor: Resource sharing only (share own resources)
 * - Member: Access only (use shared resources per resource permissions)
 *
 * Separate from:
 * - Resource-level permissions (Read/Edit) - set per-resource by sharer
 * - System roles (admin/developer/analyst/student) - tenant-wide permissions
 */

export type TeamRole = 'owner' | 'manager' | 'contributor' | 'member';
export type TeamPermission = 'read' | 'share' | 'manager';  // Database values

export interface TeamMember {
  user_id: string;
  user_email: string;
  user_name: string;
  team_permission: TeamPermission;
  is_observable: boolean;
  observable_consent_status: 'none' | 'pending' | 'approved' | 'revoked';
  observable_consent_at?: string;
  status: 'pending' | 'accepted' | 'declined';
}

export interface Team {
  id: string;
  name: string;
  owner_id: string;
  is_owner: boolean;
  can_manage: boolean;
  user_permission?: TeamPermission;
  member_count: number;
}

/**
 * Map database team_permission to user-facing role.
 * Owner is determined by matching user_id with team.owner_id.
 */
export function getTeamRole(member: TeamMember | null, ownerId: string, userId: string): TeamRole {
  if (userId === ownerId) return 'owner';
  if (!member) return 'member';  // Not in team

  switch (member.team_permission) {
    case 'manager':
      return 'manager';
    case 'share':
      return 'contributor';
    case 'read':
    default:
      return 'member';
  }
}

/**
 * Map user-facing role to database team_permission value.
 * Owner is stored separately in teams.owner_id, not in team_permission.
 */
export function getTeamPermissionValue(role: TeamRole): TeamPermission {
  switch (role) {
    case 'owner':
      // Owner doesn't have a team_permission row (they're in teams.owner_id)
      // If we need to create a membership for owner, use 'manager' equivalent
      return 'manager';
    case 'manager':
      return 'manager';
    case 'contributor':
      return 'share';
    case 'member':
    default:
      return 'read';
  }
}

/**
 * Check if user can edit team details (name, description).
 * Only owner can edit team.
 */
export function canEditTeam(role: TeamRole): boolean {
  return role === 'owner';
}

/**
 * Check if user can view Observable member activity.
 * Owner and Manager can view activity of Observable members.
 */
export function canViewObservability(role: TeamRole): boolean {
  return role === 'owner' || role === 'manager';
}

/**
 * Check if user can manage members (add, remove, change roles).
 * Owner can manage all members.
 * Manager can manage non-owner members.
 */
export function canManageMembers(userRole: TeamRole, targetRole?: TeamRole): boolean {
  if (userRole === 'owner') return true;
  if (userRole === 'manager') {
    return !targetRole || targetRole !== 'owner';  // Manager cannot modify owner
  }
  return false;
}

/**
 * Check if user can share resources to team.
 * Owner, Manager, and Contributor can share.
 */
export function canShareResources(role: TeamRole): boolean {
  return ['owner', 'manager', 'contributor'].includes(role);
}

/**
 * Check if user can invite new members.
 * Owner and Manager can invite.
 */
export function canInviteMembers(role: TeamRole): boolean {
  return role === 'owner' || role === 'manager';
}

/**
 * Check if user can set a specific role on a member.
 * Owner can set any role.
 * Manager can only set Contributor or Member roles (not Owner or Manager).
 */
export function canSetRole(userRole: TeamRole, targetRole: TeamRole): boolean {
  if (userRole === 'owner') return true;
  if (userRole === 'manager') {
    return targetRole === 'contributor' || targetRole === 'member';
  }
  return false;
}

/**
 * Check if user can request Observable access from members.
 * Owner and Manager can request.
 */
export function canRequestObservable(role: TeamRole): boolean {
  return role === 'owner' || role === 'manager';
}

/**
 * Get badge variant for team role display.
 */
export function getRoleBadgeVariant(role: TeamRole): 'default' | 'secondary' | 'outline' | 'ghost' {
  const variants: Record<TeamRole, 'default' | 'secondary' | 'outline' | 'ghost'> = {
    owner: 'default',
    manager: 'secondary',
    contributor: 'outline',
    member: 'ghost'
  };
  return variants[role];
}

/**
 * Get user-friendly label for team role.
 */
export function getRoleLabel(role: TeamRole): string {
  const labels: Record<TeamRole, string> = {
    owner: 'Owner',
    manager: 'Manager',
    contributor: 'Contributor',
    member: 'Member'
  };
  return labels[role];
}

/**
 * Get role description for tooltips/help text.
 */
export function getRoleDescription(role: TeamRole): string {
  const descriptions: Record<TeamRole, string> = {
    owner: 'Full control over team, members, and settings',
    manager: 'Can manage members, view Observable activity, and share resources',
    contributor: 'Can share own resources with team',
    member: 'Can access shared resources'
  };
  return descriptions[role];
}

/**
 * Get Observable status badge variant.
 */
export function getObservableBadgeVariant(status: string): 'default' | 'secondary' | 'outline' {
  switch (status) {
    case 'approved':
      return 'default';
    case 'pending':
      return 'secondary';
    default:
      return 'outline';
  }
}

/**
 * Get Observable status label.
 */
export function getObservableLabel(status: string): string {
  switch (status) {
    case 'approved':
      return 'Observable';
    case 'pending':
      return 'Observable (Pending)';
    case 'revoked':
      return 'Observable (Revoked)';
    default:
      return '';
  }
}

/**
 * Check if member is Observable (approved status).
 */
export function isObservable(member: TeamMember): boolean {
  return member.is_observable && member.observable_consent_status === 'approved';
}

/**
 * Check if member has pending Observable request.
 */
export function hasPendingObservableRequest(member: TeamMember): boolean {
  return member.is_observable && member.observable_consent_status === 'pending';
}
