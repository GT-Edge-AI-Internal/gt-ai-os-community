/**
 * GT 2.0 API Service Layer
 * 
 * Centralized API client for all backend communication with proper
 * authentication, error handling, and tenant isolation.
 */

import { getAuthToken, getTenantInfo, getUser, isTokenValid } from './auth';

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
}

class ApiClient {
  private baseURL: string;
  private defaultHeaders: Record<string, string>;

  constructor() {
    // Use relative path for browser, will be proxied by Next.js to tenant-backend via Docker network
    this.baseURL = '';
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  private getAuthHeaders(): Record<string, string> {
    console.log('🔐 Getting auth headers...');

    // GT 2.0: Check token validity before using
    const tokenValid = isTokenValid();
    console.log('🔐 Token valid:', tokenValid);

    if (!tokenValid) {
      console.log('🔐 No valid token, using default headers');
      // For unauthenticated requests, still include tenant domain from environment
      const tenantDomain = process.env.NEXT_PUBLIC_TENANT_DOMAIN || 'test-company';
      return {
        ...this.defaultHeaders,
        'X-Tenant-Domain': tenantDomain,
      };
    }

    const token = getAuthToken();
    const tenantInfo = getTenantInfo();
    const user = getUser();

    // GT 2.0: Validate tenant domain is available
    const tenantDomain = tenantInfo?.domain || process.env.NEXT_PUBLIC_TENANT_DOMAIN || 'test-company';

    // GT 2.0: Get user ID from stored user info (email is used as user_id)
    const userId = user?.email || user?.user_id || '';

    if (!tenantInfo?.domain) {
      console.warn('⚠️ No tenant domain from auth context, falling back to environment variable:', tenantDomain);
    }

    if (!userId) {
      console.warn('⚠️ No user ID available from auth context');
    }

    console.log('🔐 Auth data:', {
      hasToken: !!token,
      tokenPrefix: token?.substring(0, 20) + '...',
      tenantDomain: tenantDomain,
      userId: userId,
      userEmail: user?.email,
      source: tenantInfo?.domain ? 'auth' : 'environment'
    });

    const headers: Record<string, string> = {
      ...this.defaultHeaders,
      'X-Tenant-Domain': tenantDomain,
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    if (userId) {
      headers['X-User-ID'] = userId;
    }

    return headers;
  }

  private async makeRequest<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const requestId = Math.random().toString(36).substr(2, 9);
    console.log(`🔍 [${requestId}] API Request Start: ${endpoint}`, { 
      method: options.method || 'GET',
      baseURL: this.baseURL 
    });
    
    try {
      // Get auth headers with debugging
      console.log(`🔍 [${requestId}] Getting auth headers...`);
      console.log(`🔥 DETAILED LOGGING IS ACTIVE - requestId: ${requestId}`);
      
      let headers;
      try {
        headers = this.getAuthHeaders();
        console.log(`✅ [${requestId}] Auth headers obtained successfully`);
      } catch (authError) {
        console.error(`❌ [${requestId}] Auth headers failed:`, authError);
        throw authError;
      }
      console.log(`🔐 [${requestId}] Auth Headers:`, {
        hasAuth: !!headers.Authorization,
        hasTenant: !!headers['X-Tenant-Domain'],
        authPrefix: headers.Authorization?.substring(0, 20) + '...',
        tenantDomain: headers['X-Tenant-Domain'],
        allHeaders: Object.keys(headers)
      });
      
      const fullUrl = `${this.baseURL}${endpoint}`;
      console.log(`📡 [${requestId}] Making fetch request to: ${fullUrl}`);
      console.log(`📡 [${requestId}] Request options:`, {
        method: options.method || 'GET',
        headers: Object.keys(headers)
      });
      
      let response: Response;
      try {
        console.log(`📡 [${requestId}] About to call fetch()...`);
        console.log(`📡 [${requestId}] Fetch URL: ${fullUrl}`);
        console.log(`📡 [${requestId}] Fetch options:`, {
          method: options.method,
          headers: { ...headers, ...options.headers },
          body: options.body ? `BODY: ${options.body}` : 'NO_BODY',
          fullUrl: fullUrl,
          baseURL: this.baseURL,
          endpoint: endpoint
        });
        
        // Try fetch with detailed logging
        console.log(`🌐 [${requestId}] === ATTEMPTING FETCH ===`);
        console.log(`🌐 [${requestId}] fetch(${fullUrl}, {`);
        console.log(`🌐 [${requestId}]   method: ${options.method}`);
        console.log(`🌐 [${requestId}]   headers:`, { ...headers, ...options.headers });
        console.log(`🌐 [${requestId}]   body: ${options.body || 'undefined'}`);
        console.log(`🌐 [${requestId}] })`);
        
        response = await fetch(fullUrl, {
          ...options,
          headers: {
            ...headers,
            ...options.headers,
          },
        });
        
        console.log(`✅ [${requestId}] Fetch completed successfully!`);
        console.log(`📊 [${requestId}] Response status: ${response.status}`);
        console.log(`📊 [${requestId}] Response headers:`, Object.fromEntries(response.headers.entries()));
        console.log(`📊 [${requestId}] Response URL: ${response.url}`);
      } catch (fetchError: any) {
        console.error(`❌ [${requestId}] Fetch failed:`, {
          error: fetchError,
          message: fetchError?.message,
          name: fetchError?.name,
          stack: fetchError?.stack
        });
        return {
          error: `Network request failed: ${fetchError?.message || 'Unknown fetch error'}`,
          status: 0,
        };
      }

      console.log(`📥 Response received:`, {
        status: response.status,
        ok: response.ok,
        statusText: response.statusText,
        url: response.url
      });

      const contentType = response.headers.get('content-type');
      let data: T | undefined;

      // Always try to get response text first for debugging
      let responseText: string;
      try {
        responseText = await response.text();
        console.log(`📄 Response text (${responseText?.length} chars):`, {
          contentType: contentType,
          textPreview: responseText?.substring(0, 200),
          isEmpty: !responseText,
          isUndefined: responseText === 'undefined'
        });
      } catch (textError) {
        console.error('❌ Failed to get response text:', textError);
        return {
          error: `Failed to read response: ${textError}`,
          status: response.status,
        };
      }
      
      if (contentType?.includes('application/json') && responseText) {
        if (responseText === 'undefined') {
          console.error('❌ Response text is literally "undefined"');
          return {
            error: 'Server returned "undefined" instead of valid JSON',
            status: response.status,
          };
        }
        
        try {
          data = JSON.parse(responseText);
          console.log('✅ JSON parsed successfully:', typeof data);
        } catch (jsonError) {
          console.error('❌ JSON parsing failed:', {
            error: jsonError,
            responseText: responseText,
            responseLength: responseText.length
          });
          return {
            error: `Invalid JSON response: ${jsonError}`,
            status: response.status,
          };
        }
      } else if (!responseText) {
        console.warn('⚠️ Empty response body');
        data = undefined;
      } else {
        console.log('ℹ️ Non-JSON response:', { contentType, textLength: responseText.length });
      }

      if (!response.ok) {
        // GT 2.0: Handle authentication failures gracefully
        if (response.status === 401) {
          // Use centralized logout from auth store
          if (typeof window !== 'undefined') {
            const { useAuthStore } = await import('@/stores/auth-store');
            useAuthStore.getState().logout('unauthorized');
          }
          return {
            error: 'Session expired. Please log in again.',
            status: response.status,
          };
        }

        return {
          error: (data as any)?.detail || (data as any)?.message || `HTTP ${response.status}: ${response.statusText}`,
          status: response.status,
        };
      }

      return {
        data,
        status: response.status,
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : 'Network error',
        status: 0,
      };
    }
  }

  async get<T>(endpoint: string, options?: { params?: Record<string, any> }): Promise<ApiResponse<T>> {
    let url = endpoint;
    if (options?.params) {
      const queryParams = new URLSearchParams();
      Object.entries(options.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, String(value));
        }
      });
      const queryString = queryParams.toString();
      if (queryString) {
        url = `${endpoint}?${queryString}`;
      }
    }
    return this.makeRequest<T>(url, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.makeRequest<T>(endpoint, { method: 'DELETE' });
  }

  async upload<T>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> {
    try {
      const token = await getAuthToken();
      const tenantInfo = getTenantInfo();

      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      if (tenantInfo?.domain) headers['X-Tenant-Domain'] = tenantInfo.domain;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers,
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          error: data?.detail || `Upload failed: ${response.statusText}`,
          status: response.status,
        };
      }

      return {
        data,
        status: response.status,
      };
    } catch (error) {
      return {
        error: error instanceof Error ? error.message : 'Upload error',
        status: 0,
      };
    }
  }
}

// Singleton instance
export const apiClient = new ApiClient();

// Convenience methods
export const api = {
  get: <T>(endpoint: string, options?: { params?: Record<string, any> }) => apiClient.get<T>(endpoint, options),
  post: <T>(endpoint: string, data?: any) => apiClient.post<T>(endpoint, data),
  put: <T>(endpoint: string, data?: any) => apiClient.put<T>(endpoint, data),
  delete: <T>(endpoint: string) => apiClient.delete<T>(endpoint),
  upload: <T>(endpoint: string, formData: FormData) => apiClient.upload<T>(endpoint, formData),
};