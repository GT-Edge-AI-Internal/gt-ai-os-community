/**
 * GT 2.0 Capability Management Utilities
 * 
 * Provides capability-based authorization following GT 2.0's security model.
 */

import { getAuthToken, parseCapabilities, isTokenValid } from '@/services/auth';

// GT 2.0 Standard Capabilities
export const GT2_CAPABILITIES = {
  // Agent Management (Primary)
  AGENTS_READ: 'agents:read',
  AGENTS_CREATE: 'agents:create',
  AGENTS_EDIT: 'agents:edit',
  AGENTS_DELETE: 'agents:delete',
  AGENTS_SHARE: 'agents:share',
  AGENTS_EXECUTE: 'agents:execute',

  // Agent Management (Legacy - Maps to Agents)
  AGENTS_READ: 'agents:read',
  AGENTS_CREATE: 'agents:create',
  ASSISTANTS_EDIT: 'agents:edit',
  AGENTS_DELETE: 'agents:delete',
  ASSISTANTS_SHARE: 'agents:share',

  // Dataset Management
  DATASETS_READ: 'datasets:read',
  DATASETS_CREATE: 'datasets:create',
  DATASETS_UPLOAD: 'datasets:upload',
  DATASETS_DELETE: 'datasets:delete',
  DATASETS_SHARE: 'datasets:share',

  // Conversation Management
  CONVERSATIONS_READ: 'conversations:read',
  CONVERSATIONS_CREATE: 'conversations:create',
  CONVERSATIONS_DELETE: 'conversations:delete',

  // Document Management
  DOCUMENTS_READ: 'documents:read',
  DOCUMENTS_UPLOAD: 'documents:upload',
  DOCUMENTS_DELETE: 'documents:delete',

  // Administrative
  ADMIN_USERS: 'admin:users',
  ADMIN_TENANTS: 'admin:tenants',
  ADMIN_SYSTEM: 'admin:system'
} as const;

export type GT2Capability = typeof GT2_CAPABILITIES[keyof typeof GT2_CAPABILITIES];

/**
 * Check if user has specific capability
 */
export function hasCapability(capability: string): boolean {
  if (!isTokenValid()) return false;
  
  const token = getAuthToken();
  if (!token) return false;
  
  const capabilities = parseCapabilities(token);
  return capabilities.includes(capability);
}

/**
 * Check if user has all required capabilities
 */
export function hasAllCapabilities(requiredCapabilities: string[]): boolean {
  if (requiredCapabilities.length === 0) return true;
  
  return requiredCapabilities.every(cap => hasCapability(cap));
}

/**
 * Check if user has any of the specified capabilities
 */
export function hasAnyCapability(capabilities: string[]): boolean {
  if (capabilities.length === 0) return true;
  
  return capabilities.some(cap => hasCapability(cap));
}

/**
 * Get user's current capabilities
 */
export function getCurrentCapabilities(): string[] {
  if (!isTokenValid()) return [];
  
  const token = getAuthToken();
  if (!token) return [];
  
  return parseCapabilities(token);
}

/**
 * Check if user can perform action on resource
 */
export function canPerformAction(resource: string, action: string): boolean {
  const capability = `${resource}:${action}`;
  return hasCapability(capability);
}

/**
 * Get user's role from capabilities (GT 2.0 role inference)
 */
export function inferUserRole(): 'admin' | 'developer' | 'analyst' | 'student' | 'guest' {
  const capabilities = getCurrentCapabilities();
  
  if (capabilities.some(cap => cap.startsWith('admin:'))) {
    return 'admin';
  }
  
  if (capabilities.includes(GT2_CAPABILITIES.AGENTS_CREATE) || 
      capabilities.includes(GT2_CAPABILITIES.AGENTS_CREATE)) {
    return 'developer';
  }
  
  if (capabilities.includes(GT2_CAPABILITIES.DATASETS_CREATE) ||
      capabilities.includes(GT2_CAPABILITIES.DATASETS_UPLOAD)) {
    return 'analyst';
  }
  
  if (capabilities.includes(GT2_CAPABILITIES.CONVERSATIONS_CREATE)) {
    return 'student';
  }
  
  return 'guest';
}

/**
 * Create capability checker hook for React components
 */
export function createCapabilityChecker(requiredCapabilities: string[]) {
  return {
    hasAccess: hasAllCapabilities(requiredCapabilities),
    missingCapabilities: requiredCapabilities.filter(cap => !hasCapability(cap)),
    userCapabilities: getCurrentCapabilities()
  };
}

/**
 * Filter items based on required capabilities
 */
export function filterByCapability<T extends { requiredCapability?: string }>(
  items: T[],
  defaultCapability?: string
): T[] {
  return items.filter(item => {
    const required = item.requiredCapability || defaultCapability;
    return !required || hasCapability(required);
  });
}

export default {
  GT2_CAPABILITIES,
  hasCapability,
  hasAllCapabilities,
  hasAnyCapability,
  getCurrentCapabilities,
  canPerformAction,
  inferUserRole,
  createCapabilityChecker,
  filterByCapability
};