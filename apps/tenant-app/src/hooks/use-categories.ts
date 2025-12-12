/**
 * React Query hooks for Agent Categories
 *
 * Provides centralized, cached category data access with automatic
 * invalidation on mutations.
 *
 * Supports Issue #215 requirements for tenant-scoped categories
 * with permission-based editing and deletion.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getCategories,
  getCategory,
  createCategory,
  updateCategory,
  deleteCategory,
  type Category,
  type CategoryCreateRequest,
  type CategoryUpdateRequest,
} from '@/services/categories';

// ============================================================================
// QUERY KEY FACTORY
// ============================================================================

export const categoryKeys = {
  all: ['categories'] as const,
  lists: () => [...categoryKeys.all, 'list'] as const,
  list: () => [...categoryKeys.lists()] as const,
  details: () => [...categoryKeys.all, 'detail'] as const,
  detail: (id: string) => [...categoryKeys.details(), id] as const,
};

// ============================================================================
// CATEGORY QUERIES
// ============================================================================

/**
 * List all categories for the tenant
 * Returns categories with permission flags (can_edit, can_delete)
 */
export function useCategories() {
  return useQuery({
    queryKey: categoryKeys.list(),
    queryFn: async () => {
      const response = await getCategories();
      if (response.error) throw new Error(response.error);
      return response.data?.categories || [];
    },
    staleTime: 60000, // 1 minute - categories don't change often
  });
}

/**
 * Get a single category by ID
 */
export function useCategory(categoryId: string | undefined) {
  return useQuery({
    queryKey: categoryKeys.detail(categoryId || ''),
    queryFn: async () => {
      if (!categoryId) throw new Error('Category ID is required');
      const response = await getCategory(categoryId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    enabled: !!categoryId,
    staleTime: 60000, // 1 minute
  });
}

// ============================================================================
// CATEGORY MUTATIONS
// ============================================================================

/**
 * Create new category mutation
 * Invalidates category queries on success
 */
export function useCreateCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CategoryCreateRequest) => {
      const response = await createCategory(data);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all category queries to trigger refetch
      queryClient.invalidateQueries({ queryKey: categoryKeys.all });
    },
  });
}

/**
 * Update existing category mutation
 * Invalidates category queries on success
 */
export function useUpdateCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      categoryId,
      data,
    }: {
      categoryId: string;
      data: CategoryUpdateRequest;
    }) => {
      const response = await updateCategory(categoryId, data);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate all category queries
      queryClient.invalidateQueries({ queryKey: categoryKeys.all });
      // Specifically invalidate the updated category's detail query
      queryClient.invalidateQueries({ queryKey: categoryKeys.detail(variables.categoryId) });
    },
  });
}

/**
 * Delete category mutation
 * Invalidates category queries on success
 */
export function useDeleteCategory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (categoryId: string) => {
      const response = await deleteCategory(categoryId);
      if (response.error) throw new Error(response.error);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all category queries to remove deleted category from lists
      queryClient.invalidateQueries({ queryKey: categoryKeys.all });
    },
  });
}

// ============================================================================
// HELPER TYPES
// ============================================================================

export type { Category, CategoryCreateRequest, CategoryUpdateRequest };
