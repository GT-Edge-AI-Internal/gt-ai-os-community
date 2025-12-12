/**
 * Dataset Service for GT 2.0
 * 
 * Provides CRUD operations and access control for datasets with
 * proper tenant isolation and user permissions.
 */

import { api, ApiResponse } from './api';

// Access control types
export type AccessGroup = 'individual' | 'team' | 'organization';
export type AccessFilter = 'all' | 'mine' | 'team' | 'org';

// Dataset interfaces
export interface Dataset {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  access_group: AccessGroup;
  team_members: string[];
  document_count: number;
  chunk_count: number;
  vector_count: number;
  storage_size_mb: number;
  tags: string[];
  created_at: string;
  updated_at: string;

  // Chunking configuration
  chunking_strategy?: 'hybrid' | 'semantic' | 'fixed';
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;

  // Access indicators for UI
  is_owner: boolean;
  can_edit: boolean;
  can_delete: boolean;
  can_share: boolean;
}

export interface CreateDatasetRequest {
  name: string;
  description?: string;
  access_group?: AccessGroup;
  team_members?: string[];
  tags?: string[];
}

export interface UpdateDatasetRequest {
  name?: string;
  description?: string;
  tags?: string[];
  access_group?: AccessGroup;
  team_members?: string[];
  chunking_strategy?: 'hybrid' | 'semantic' | 'fixed';
  chunk_size?: number;
  chunk_overlap?: number;
  embedding_model?: string;
}

export interface ShareDatasetRequest {
  access_group: AccessGroup;
  team_members?: string[];
}

export interface DatasetStats {
  dataset_id: string;
  name: string;
  document_count: number;
  chunk_count: number;
  vector_count: number;
  storage_size_mb: number;
  created_at: string;
  updated_at: string;
  access_group: AccessGroup;
  team_member_count: number;
  tags: string[];
}

// Dataset service class
export class DatasetService {
  
  /**
   * List datasets based on user access rights
   */
  async listDatasets(options: {
    access_filter?: AccessFilter;
    include_stats?: boolean;
  } = {}): Promise<ApiResponse<Dataset[]>> {
    const params = new URLSearchParams();
    
    if (options.access_filter) {
      params.append('access_filter', options.access_filter);
    }
    
    if (options.include_stats !== undefined) {
      params.append('include_stats', options.include_stats.toString());
    }
    
    const query = params.toString();
    const endpoint = `/api/v1/datasets/${query ? `?${query}` : ''}`;

    return api.get<Dataset[]>(endpoint);
  }

  /**
   * Get specific dataset details
   */
  async getDataset(datasetId: string): Promise<ApiResponse<Dataset>> {
    return api.get<Dataset>(`/api/v1/datasets/${datasetId}`);
  }

  /**
   * Create new dataset
   */
  async createDataset(request: CreateDatasetRequest): Promise<ApiResponse<Dataset>> {
    return api.post<Dataset>('/api/v1/datasets/', request);
  }

  /**
   * Update existing dataset (owner only)
   */
  async updateDataset(
    datasetId: string, 
    request: UpdateDatasetRequest
  ): Promise<ApiResponse<Dataset>> {
    return api.put<Dataset>(`/api/v1/datasets/${datasetId}`, request);
  }

  /**
   * Share dataset with team or organization (owner only)
   */
  async shareDataset(
    datasetId: string, 
    request: ShareDatasetRequest
  ): Promise<ApiResponse<Dataset>> {
    return api.put<Dataset>(`/api/v1/datasets/${datasetId}/share`, request);
  }

  /**
   * Delete dataset (owner only)
   */
  async deleteDataset(datasetId: string): Promise<ApiResponse<{ message: string }>> {
    return api.delete<{ message: string }>(`/api/v1/datasets/${datasetId}`);
  }

  /**
   * Add documents to dataset
   */
  async addDocumentsToDataset(
    datasetId: string, 
    documentIds: string[]
  ): Promise<ApiResponse<{
    message: string;
    dataset_id: string;
    added_documents: string[];
    failed_documents: string[];
  }>> {
    return api.post(
      `/api/v1/datasets/${datasetId}/documents`, 
      documentIds
    );
  }

  /**
   * Get detailed dataset statistics
   */
  async getDatasetStats(datasetId: string): Promise<ApiResponse<DatasetStats>> {
    return api.get<DatasetStats>(`/api/v1/datasets/${datasetId}/stats`);
  }

  /**
   * Get datasets filtered by access level
   */
  async getMyDatasets(): Promise<ApiResponse<Dataset[]>> {
    return this.listDatasets({ access_filter: 'mine' });
  }

  async getTeamDatasets(): Promise<ApiResponse<Dataset[]>> {
    return this.listDatasets({ access_filter: 'team' });
  }

  async getOrgDatasets(): Promise<ApiResponse<Dataset[]>> {
    return this.listDatasets({ access_filter: 'org' });
  }

  /**
   * Search datasets by name or description
   */
  async searchDatasets(query: string, accessFilter?: AccessFilter): Promise<ApiResponse<Dataset[]>> {
    const allDatasets = await this.listDatasets({ access_filter: accessFilter });
    
    if (!allDatasets.data) {
      return allDatasets;
    }

    const filtered = allDatasets.data.filter(dataset =>
      dataset.name.toLowerCase().includes(query.toLowerCase()) ||
      dataset.description?.toLowerCase().includes(query.toLowerCase()) ||
      dataset.tags.some(tag => tag.toLowerCase().includes(query.toLowerCase()))
    );

    return {
      data: filtered,
      status: allDatasets.status
    };
  }

  /**
   * Get datasets by tag
   */
  async getDatasetsByTag(tag: string, accessFilter?: AccessFilter): Promise<ApiResponse<Dataset[]>> {
    const allDatasets = await this.listDatasets({ access_filter: accessFilter });
    
    if (!allDatasets.data) {
      return allDatasets;
    }

    const filtered = allDatasets.data.filter(dataset =>
      dataset.tags.some(t => t.toLowerCase() === tag.toLowerCase())
    );

    return {
      data: filtered,
      status: allDatasets.status
    };
  }

  /**
   * Get user's dataset statistics summary
   */
  async getUserDatasetSummary(): Promise<ApiResponse<{
    total_datasets: number;
    owned_datasets: number;
    team_datasets: number;
    org_datasets: number;
    total_documents: number;
    total_storage_mb: number;
  }>> {
    // Call the new complete summary endpoint
    return api.get('/api/v1/datasets/summary/complete');
  }

  /**
   * Get AI-generated summary for a specific dataset
   */
  async getDatasetSummary(
    datasetId: string,
    forceRegenerate: boolean = false
  ): Promise<ApiResponse<{
    summary: string;
    key_topics: string[];
    document_types: Record<string, number>;
    total_documents: number;
    total_chunks: number;
    common_themes: string[];
    search_optimization_tips: string[];
    generated_at?: string;
  }>> {
    const params = forceRegenerate ? '?force_regenerate=true' : '';
    return api.get(`/api/v1/datasets/${datasetId}/summary${params}`);
  }
}

// Singleton instance
export const datasetService = new DatasetService();

// Convenience exports with proper binding
export const listDatasets = datasetService.listDatasets.bind(datasetService);
export const getDataset = datasetService.getDataset.bind(datasetService);
export const createDataset = datasetService.createDataset.bind(datasetService);
export const updateDataset = datasetService.updateDataset.bind(datasetService);
export const shareDataset = datasetService.shareDataset.bind(datasetService);
export const deleteDataset = datasetService.deleteDataset.bind(datasetService);
export const addDocumentsToDataset = datasetService.addDocumentsToDataset.bind(datasetService);
export const getDatasetStats = datasetService.getDatasetStats.bind(datasetService);
export const getMyDatasets = datasetService.getMyDatasets.bind(datasetService);
export const getTeamDatasets = datasetService.getTeamDatasets.bind(datasetService);
export const getOrgDatasets = datasetService.getOrgDatasets.bind(datasetService);
export const searchDatasets = datasetService.searchDatasets.bind(datasetService);
export const getDatasetsByTag = datasetService.getDatasetsByTag.bind(datasetService);
export const getUserDatasetSummary = datasetService.getUserDatasetSummary.bind(datasetService);
export const getDatasetSummary = datasetService.getDatasetSummary.bind(datasetService);