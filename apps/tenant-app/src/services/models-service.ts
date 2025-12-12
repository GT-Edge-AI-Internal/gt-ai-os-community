import { api, type ApiResponse } from '@/services/api';

export interface ModelOption {
  value: string;  // model_id string for backwards compatibility
  uuid?: string;  // Database UUID for unique identification (new models have this)
  label: string;
  description: string;
  provider: string;
  model_type: string;
  max_tokens: number;
  context_window: number;
  cost_per_1k_tokens: number;
  latency_p50_ms: number;
  health_status: string;
  deployment_status: string;
}

export interface ModelsResponse {
  models: ModelOption[];
  total: number;
  tenant_domain: string;
  fallback?: boolean;
  message?: string;
  last_updated?: string;
}

class ModelsService {
  private modelCache: ModelsResponse | null = null;
  private cacheTimestamp: number = 0;
  private readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes
  private readonly MAX_RETRIES = 3;
  private readonly RETRY_DELAY = 1000; // 1 second

  /**
   * Fetch available AI models for the current tenant with caching
   */
  async getAvailableModels(): Promise<ModelsResponse> {
    // Check if we have valid cached data
    const now = Date.now();
    if (this.modelCache && (now - this.cacheTimestamp < this.CACHE_TTL)) {
      console.log('🚀 Using cached models data');
      return this.modelCache;
    }

    // Fetch fresh data with retry logic
    for (let attempt = 1; attempt <= this.MAX_RETRIES; attempt++) {
      try {
        console.log(`🔄 Fetching models from API (attempt ${attempt}/${this.MAX_RETRIES})`);
        const response = await api.get<ModelsResponse>('/api/v1/models/');
        
        if (response.data) {
          // Cache successful response
          this.modelCache = response.data;
          this.cacheTimestamp = now;
          
          console.log(`✅ Successfully fetched ${response.data.models?.length || 0} models`);
          if (response.data.fallback) {
            console.warn('⚠️ API returned fallback models:', response.data.message);
          }
          
          return response.data;
        }
        throw new Error(response.error || 'Failed to fetch models');
        
      } catch (error) {
        console.error(`❌ Attempt ${attempt} failed:`, error);
        
        if (attempt === this.MAX_RETRIES) {
          // Last attempt failed, return empty
          console.warn('🔄 All retry attempts failed, no models available');
          const emptyResponse = {
            models: [],
            total: 0,
            tenant_domain: 'unknown',
            fallback: false,
            message: 'No models available - all API requests failed'
          };
          
          // Cache empty response with shorter TTL
          this.modelCache = emptyResponse;
          this.cacheTimestamp = now - (this.CACHE_TTL * 0.8); // Shorter cache for errors
          
          return emptyResponse;
        }
        
        // Wait before retrying
        await new Promise(resolve => setTimeout(resolve, this.RETRY_DELAY * attempt));
      }
    }

    // This should never be reached, but just in case
    return {
      models: [],
      total: 0,
      tenant_domain: 'unknown',
      fallback: false,
      message: 'No models available'
    };
  }

  /**
   * Clear the models cache to force fresh data on next request
   */
  clearCache(): void {
    this.modelCache = null;
    this.cacheTimestamp = 0;
    console.log('🗑️ Models cache cleared');
  }

  /**
   * Refresh models data by clearing cache and fetching fresh data
   */
  async refreshModels(): Promise<ModelsResponse> {
    this.clearCache();
    return await this.getAvailableModels();
  }

  /**
   * Get details for a specific model
   */
  async getModelDetails(modelId: string): Promise<ModelOption> {
    try {
      const response = await api.get<{ model: ModelOption }>(`/api/v1/models/${modelId}`);
      if (response.data) {
        return response.data.model;
      }
      throw new Error(response.error || 'Failed to fetch model details');
    } catch (error) {
      console.error(`Failed to fetch model details for ${modelId}:`, error);
      throw error;
    }
  }


  /**
   * Clean model names by removing provider prefixes like "nvidia/", "groq/"
   */
  private cleanModelName(name: string): string {
    return name.replace(/^(nvidia|groq|openai|anthropic)\//, '');
  }

  /**
   * Format model options for Select components
   */
  formatForSelect(models: ModelOption[]): Array<{value: string, label: string, description: string}> {
    return models.map(model => ({
      value: model.value,
      label: this.cleanModelName(model.label),
      description: model.description
    }));
  }
}

export const modelsService = new ModelsService();