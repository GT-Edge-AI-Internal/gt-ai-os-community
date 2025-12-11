/**
 * Access Level Display Helpers
 *
 * Provides consistent display mapping for access levels across the application.
 * Backend uses 'individual', 'team', 'organization' but UX displays 'Myself', 'Team', 'Organization'.
 */

export type AccessLevel = 'individual' | 'team' | 'organization';

/**
 * Get user-friendly display name for access level
 */
export function getAccessLevelDisplay(level: AccessLevel): string {
  const displayMap: Record<AccessLevel, string> = {
    'individual': 'Myself',
    'team': 'Team',
    'organization': 'Organization'
  };
  return displayMap[level] || level;
}

/**
 * Get access level description for UI
 */
export function getAccessLevelDescription(level: AccessLevel, context: 'agent' | 'dataset'): string {
  const descriptions: Record<AccessLevel, Record<string, string>> = {
    'individual': {
      'agent': 'Only you can access this Agent',
      'dataset': 'Only you can access this dataset'
    },
    'team': {
      'agent': 'Share with specific Team members',
      'dataset': 'Share with a group of users'
    },
    'organization': {
      'agent': 'Available to all Organization users',
      'dataset': 'This dataset is available to all users in your Organization'
    }
  };

  return descriptions[level]?.[context] || '';
}