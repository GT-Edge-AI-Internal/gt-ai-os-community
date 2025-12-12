/**
 * External Services API Client
 * Handles external web services integration with Resource Cluster
 */

import { apiClient } from '@/lib/api/client';

export interface ServiceInstance {
  id: string;
  service_type: string;
  service_name: string;
  description?: string;
  endpoint_url: string;
  status: string;
  health_status: string;
  created_by: string;
  allowed_users: string[];
  access_level: string;
  created_at: string;
  last_accessed?: string;
}

export interface ServiceType {
  type: string;
  name: string;
  description: string;
  category: string;
  features: string[];
  resource_requirements: {
    cpu: string;
    memory: string;
    storage: string;
  };
  estimated_startup_time: string;
  sso_supported: boolean;
}

export interface CreateServiceRequest {
  service_type: string;
  service_name: string;
  description?: string;
  config_overrides?: Record<string, any>;
  template_id?: string;
}

export interface EmbedConfig {
  iframe_url: string;
  sandbox_attributes: string[];
  security_policies: {
    allow: string;
    referrerpolicy: string;
    loading: string;
  };
  sso_token: string;
  expires_at: string;
}

export interface ServiceAnalytics {
  instance_id: string;
  service_type: string;
  service_name: string;
  analytics_period_days: number;
  total_sessions: number;
  total_time_hours: number;
  unique_users: number;
  average_session_duration_minutes: number;
  daily_usage: Record<string, any>;
  uptime_percentage: number;
}

export class ExternalServicesAPI {
  /**
   * Create a new external service instance
   */
  async createService(request: CreateServiceRequest): Promise<ServiceInstance> {
    try {
      const response = await apiClient.post<ServiceInstance>('/external-services/create', request);
      return response.data;
    } catch (error) {
      console.error('Failed to create service:', error);
      throw this.handleError(error);
    }
  }

  /**
   * List all external services accessible to the user
   */
  async listServices(options?: {
    service_type?: string;
    status?: string;
  }): Promise<{ services: ServiceInstance[]; total: number }> {
    try {
      const params = new URLSearchParams();
      if (options?.service_type) params.append('service_type', options.service_type);
      if (options?.status) params.append('status', options.status);

      const response = await apiClient.get<{ services: ServiceInstance[]; total: number }>(
        `/external-services/list?${params.toString()}`
      );
      return response.data;
    } catch (error) {
      console.error('Failed to list services:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Get specific external service details
   */
  async getService(instanceId: string): Promise<ServiceInstance> {
    try {
      const response = await apiClient.get<ServiceInstance>(`/external-services/${instanceId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to get service:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Stop an external service instance
   */
  async stopService(instanceId: string): Promise<{ success: boolean; message: string; stopped_at: string }> {
    try {
      const response = await apiClient.delete<{ success: boolean; message: string; stopped_at: string }>(
        `/external-services/${instanceId}`
      );
      return response.data;
    } catch (error) {
      console.error('Failed to stop service:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Get service health status
   */
  async getServiceHealth(instanceId: string): Promise<Record<string, any>> {
    try {
      const response = await apiClient.get<Record<string, any>>(`/external-services/${instanceId}/health`);
      return response.data;
    } catch (error) {
      console.error('Failed to get service health:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Get iframe embed configuration with SSO token
   */
  async getEmbedConfig(instanceId: string): Promise<EmbedConfig> {
    try {
      const response = await apiClient.post<EmbedConfig>(`/external-services/${instanceId}/embed-config`, {});
      return response.data;
    } catch (error) {
      console.error('Failed to get embed config:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Get service usage analytics
   */
  async getServiceAnalytics(instanceId: string, days: number = 30): Promise<ServiceAnalytics> {
    try {
      const response = await apiClient.get<ServiceAnalytics>(
        `/external-services/${instanceId}/analytics?days=${days}`
      );
      return response.data;
    } catch (error) {
      console.error('Failed to get service analytics:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Share service instance with other users
   */
  async shareService(
    instanceId: string, 
    shareWithEmails: string[], 
    accessLevel: string = 'read'
  ): Promise<{ success: boolean; shared_with: string[]; access_level: string; shared_at: string }> {
    try {
      const response = await apiClient.post<{
        success: boolean;
        shared_with: string[];
        access_level: string;
        shared_at: string;
      }>(`/external-services/${instanceId}/share`, {
        share_with_emails: shareWithEmails,
        access_level: accessLevel
      });
      return response.data;
    } catch (error) {
      console.error('Failed to share service:', error);
      throw this.handleError(error);
    }
  }

  /**
   * List available service templates
   */
  async listServiceTemplates(options?: {
    service_type?: string;
    category?: string;
  }): Promise<{ templates: any[]; total: number }> {
    try {
      const params = new URLSearchParams();
      if (options?.service_type) params.append('service_type', options.service_type);
      if (options?.category) params.append('category', options.category);

      const response = await apiClient.get<{ templates: any[]; total: number }>(
        `/external-services/templates/list?${params.toString()}`
      );
      return response.data;
    } catch (error) {
      console.error('Failed to list service templates:', error);
      throw this.handleError(error);
    }
  }

  /**
   * Get supported external service types and their capabilities
   */
  async getSupportedServiceTypes(): Promise<{
    supported_types: ServiceType[];
    total_types: number;
    categories: string[];
    extensible: boolean;
  }> {
    try {
      const response = await apiClient.get<{
        supported_types: ServiceType[];
        total_types: number;
        categories: string[];
        extensible: boolean;
      }>('/external-services/types/supported');
      return response.data;
    } catch (error) {
      console.error('Failed to get supported service types:', error);
      throw this.handleError(error);
    }
  }

  private handleError(error: any): Error {
    if (error.response?.data?.error) {
      return new Error(error.response.data.error.message || 'Unknown server error');
    }
    if (error.response?.data?.detail) {
      return new Error(error.response.data.detail);
    }
    if (error.message) {
      return new Error(error.message);
    }
    return new Error('An unexpected error occurred');
  }
}

// Export singleton instance
export const externalServicesAPI = new ExternalServicesAPI();