/**
 * GT 2.0 Categories Service
 *
 * API client for tenant-scoped agent category management.
 * Supports Issue #215 requirements for editable/deletable categories.
 */

import { api, ApiResponse } from './api';

/**
 * Category data from the backend
 */
export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  is_default: boolean;
  created_by: string | null;
  created_by_name: string | null;
  can_edit: boolean;
  can_delete: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

/**
 * Response from listing categories
 */
export interface CategoryListResponse {
  categories: Category[];
  total: number;
}

/**
 * Request to create a new category
 */
export interface CategoryCreateRequest {
  name: string;
  description?: string;
  icon?: string;
}

/**
 * Request to update a category
 */
export interface CategoryUpdateRequest {
  name?: string;
  description?: string;
  icon?: string;
}

/**
 * Get all categories for the tenant
 */
export async function getCategories(): Promise<ApiResponse<CategoryListResponse>> {
  return api.get<CategoryListResponse>('/api/v1/categories');
}

/**
 * Get a single category by ID
 */
export async function getCategory(id: string): Promise<ApiResponse<Category>> {
  return api.get<Category>(`/api/v1/categories/${id}`);
}

/**
 * Create a new category
 */
export async function createCategory(data: CategoryCreateRequest): Promise<ApiResponse<Category>> {
  return api.post<Category>('/api/v1/categories', data);
}

/**
 * Update an existing category
 */
export async function updateCategory(id: string, data: CategoryUpdateRequest): Promise<ApiResponse<Category>> {
  return api.put<Category>(`/api/v1/categories/${id}`, data);
}

/**
 * Delete a category (soft delete)
 */
export async function deleteCategory(id: string): Promise<ApiResponse<{ message: string }>> {
  return api.delete<{ message: string }>(`/api/v1/categories/${id}`);
}
