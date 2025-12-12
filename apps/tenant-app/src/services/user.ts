/**
 * GT 2.0 User Service
 *
 * API client for user preferences and favorite agents management.
 */

import { api } from './api';

export interface UserPreferences {
  favorite_agent_ids?: string[];
  [key: string]: any;
}

export interface FavoriteAgentsResponse {
  favorite_agent_ids: string[];
}

export interface CustomCategory {
  name: string;
  description: string;
  created_at?: string;
}

export interface CustomCategoriesResponse {
  categories: CustomCategory[];
}

/**
 * Get current user's preferences
 */
export async function getUserPreferences() {
  return api.get<{ preferences: UserPreferences }>('/api/v1/users/me/preferences');
}

/**
 * Update current user's preferences (merges with existing)
 */
export async function updateUserPreferences(preferences: UserPreferences) {
  return api.put('/api/v1/users/me/preferences', { preferences });
}

/**
 * Get current user's favorited agent IDs
 */
export async function getFavoriteAgents() {
  return api.get<FavoriteAgentsResponse>('/api/v1/users/me/favorite-agents');
}

/**
 * Update current user's favorite agent IDs (replaces entire list)
 */
export async function updateFavoriteAgents(agent_ids: string[]) {
  return api.put('/api/v1/users/me/favorite-agents', { agent_ids });
}

/**
 * Add a single agent to user's favorites
 */
export async function addFavoriteAgent(agent_id: string) {
  return api.post('/api/v1/users/me/favorite-agents/add', { agent_id });
}

/**
 * Remove a single agent from user's favorites
 */
export async function removeFavoriteAgent(agent_id: string) {
  return api.post('/api/v1/users/me/favorite-agents/remove', { agent_id });
}

/**
 * Get current user's custom agent categories
 */
export async function getCustomCategories() {
  return api.get<CustomCategoriesResponse>('/api/v1/users/me/custom-categories');
}

/**
 * Update current user's custom agent categories (replaces entire list)
 */
export async function saveCustomCategories(categories: CustomCategory[]) {
  return api.put('/api/v1/users/me/custom-categories', { categories });
}
