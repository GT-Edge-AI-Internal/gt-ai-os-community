/**
 * GT 2.0 Permission Utilities
 * Role-based permission helpers for UI
 */

import { getUser } from '@/services/auth';

export type UserRole = 'admin' | 'developer' | 'analyst' | 'student';
export type VisibilityLevel = 'individual' | 'organization';

const ADMIN_ROLES: UserRole[] = ['admin', 'developer'];

/**
 * Get current user's role from stored user data
 */
export function getUserRole(): UserRole | null {
  const user = getUser();
  return user?.role || null;
}

/**
 * Check if user can share resources to organization level
 * Only admin and developer roles can share to organization
 */
export function canShareToOrganization(role?: UserRole | null): boolean {
  if (!role) {
    role = getUserRole();
  }
  return role ? ADMIN_ROLES.includes(role) : false;
}

/**
 * Get available visibility options for current user
 * Returns array of visibility levels the user is allowed to set
 */
export function getAvailableVisibilityOptions(): VisibilityLevel[] {
  const role = getUserRole();

  if (canShareToOrganization(role)) {
    // Admin and developer can use both visibility levels
    return ['individual', 'organization'];
  }

  // Analyst and student can only use individual
  return ['individual'];
}

/**
 * Check if user can edit a resource
 * @param resourceOwnerId - The UUID/email of the resource creator
 * @param resourceVisibility - The visibility level of the resource
 */
export function canEditResource(
  resourceOwnerId: string,
  resourceVisibility: VisibilityLevel
): boolean {
  const user = getUser();
  if (!user) return false;

  const role = getUserRole();

  // Admin and developer can edit anything
  if (role && ADMIN_ROLES.includes(role)) {
    return true;
  }

  // Owner can always edit their own resources
  if (user.email === resourceOwnerId || user.user_id === resourceOwnerId) {
    return true;
  }

  // Organization resources are read-only for non-admins who didn't create it
  return false;
}

/**
 * Check if user can delete a resource
 * @param resourceOwnerId - The UUID/email of the resource creator
 */
export function canDeleteResource(resourceOwnerId: string): boolean {
  const user = getUser();
  if (!user) return false;

  const role = getUserRole();

  // Admin and developer can delete anything
  if (role && ADMIN_ROLES.includes(role)) {
    return true;
  }

  // Owner can delete
  if (user.email === resourceOwnerId || user.user_id === resourceOwnerId) {
    return true;
  }

  return false;
}