import axios, { AxiosInstance, AxiosError } from 'axios';
import { useAuthStore } from '@/stores/auth-store';
import toast from 'react-hot-toast';

// Determine the correct API URL based on environment
const getApiBaseUrl = () => {
  // Always use relative URLs to go through Next.js proxy
  // This ensures all requests (SSR and client-side) use the proxy
  return '';
};

// Helper function to check if JWT token is expired
const isTokenExpired = (token: string): boolean => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (!payload || !payload.exp) return true;

    const now = Math.floor(Date.now() / 1000);
    return payload.exp < now;
  } catch (error) {
    return true;
  }
};

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token and check expiry
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;

    // Check if token exists and is expired
    if (token && isTokenExpired(token)) {
      const { logout } = useAuthStore.getState();
      logout();
      toast.info('Your session has expired. Please login again.');
      window.location.href = '/auth/login';
      return Promise.reject(new Error('Token expired'));
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Handle server-side session headers (Issue #264)
 * Server is authoritative for session state - dispatch events for IdleTimerProvider
 */
function handleSessionHeaders(response: { headers: Record<string, string> }): void {
  // Check for session expired header (401 responses)
  const sessionExpired = response.headers?.['x-session-expired'];
  if (sessionExpired) {
    console.log('[API] Server session expired:', sessionExpired);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('session-expired', {
        detail: { reason: sessionExpired }
      }));
    }
    return; // Don't process warning if already expired
  }

  // Check for session warning header
  const sessionWarning = response.headers?.['x-session-warning'];
  if (sessionWarning && sessionWarning !== 'validation-unavailable') {
    const secondsRemaining = parseInt(sessionWarning, 10);
    if (!isNaN(secondsRemaining) && secondsRemaining > 0) {
      console.log('[API] Server session warning:', secondsRemaining, 'seconds remaining');
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('session-warning', {
          detail: { secondsRemaining }
        }));
      }
    }
  }
}

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    // Handle session headers on successful responses
    handleSessionHeaders(response);
    return response;
  },
  (error: AxiosError) => {
    const { response } = error;

    // Handle session headers on error responses too
    if (response) {
      handleSessionHeaders(response as unknown as { headers: Record<string, string> });
    }

    // Handle authentication errors
    if (response?.status === 401) {
      // Check if this is a session expiry (let the event handler deal with it)
      const sessionExpired = response.headers?.['x-session-expired'];
      if (sessionExpired) {
        // Event already dispatched by handleSessionHeaders, just reject
        return Promise.reject(error);
      }

      const { logout } = useAuthStore.getState();
      logout();
      toast.error('Session expired. Please login again.');
      window.location.href = '/auth/login';
      return Promise.reject(error);
    }

    // Handle forbidden errors
    if (response?.status === 403) {
      toast.error('Access denied. Insufficient permissions.');
      return Promise.reject(error);
    }

    // Handle server errors
    if (response?.status && response.status >= 500) {
      toast.error('Server error. Please try again later.');
      return Promise.reject(error);
    }

    // Handle network errors
    if (!response) {
      toast.error('Network error. Please check your connection.');
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

// API endpoints
export const authApi = {
  login: async (email: string, password: string) =>
    api.post('/api/v1/login', { email, password }),

  logout: async () =>
    api.post('/api/v1/logout'),

  me: async () =>
    api.get('/api/v1/me'),

  verifyToken: async () =>
    api.get('/api/v1/verify-token'),

  changePassword: async (currentPassword: string, newPassword: string) =>
    api.post('/api/v1/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
};

export const tenantsApi = {
  list: async (page = 1, limit = 20, search?: string, status?: string) =>
    api.get('/api/v1/tenants/', { params: { page, limit, search, status } }),

  get: async (id: number) =>
    api.get(`/api/v1/tenants/${id}/`),

  create: async (data: any) =>
    api.post('/api/v1/tenants/', data),

  update: async (id: number, data: any) =>
    api.put(`/api/v1/tenants/${id}/`, data),

  delete: async (id: number) =>
    api.delete(`/api/v1/tenants/${id}/`),

  deploy: async (id: number) =>
    api.post(`/api/v1/tenants/${id}/deploy/`),

  suspend: async (id: number) =>
    api.post(`/api/v1/tenants/${id}/suspend/`),

  activate: async (id: number) =>
    api.post(`/api/v1/tenants/${id}/activate/`),

  // Optics feature toggle
  getOpticsStatus: async (id: number) =>
    api.get(`/api/v1/tenants/${id}/optics`),

  setOpticsEnabled: async (id: number, enabled: boolean) =>
    api.put(`/api/v1/tenants/${id}/optics`, { enabled }),
};

export const usersApi = {
  list: async (page = 1, limit = 20, search?: string, tenantId?: number, userType?: string) =>
    api.get('/api/v1/users/', { params: { page, limit, search, tenant_id: tenantId, user_type: userType } }),

  get: async (id: number) =>
    api.get(`/api/v1/users/${id}/`),

  create: async (data: any) =>
    api.post('/api/v1/users/', data),

  update: async (id: number, data: any) =>
    api.put(`/api/v1/users/${id}/`, data),

  delete: async (id: number) =>
    api.delete(`/api/v1/users/${id}/`),

  activate: async (id: number) =>
    api.post(`/api/v1/users/${id}/activate/`),

  deactivate: async (id: number) =>
    api.post(`/api/v1/users/${id}/deactivate/`),

  bulkUpload: async (formData: FormData) =>
    api.post('/api/v1/users/bulk-upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }),

  bulkResetTFA: async (userIds: number[]) =>
    api.post('/api/v1/users/bulk/reset-tfa', { user_ids: userIds }),

  bulkEnforceTFA: async (userIds: number[]) =>
    api.post('/api/v1/users/bulk/enforce-tfa', { user_ids: userIds }),

  bulkDisableTFA: async (userIds: number[]) =>
    api.post('/api/v1/users/bulk/disable-tfa', { user_ids: userIds }),
};

export const resourcesApi = {
  list: async (page = 1, limit = 20) =>
    api.get('/api/v1/resources/', { params: { page, limit } }),

  get: async (id: number) =>
    api.get(`/api/v1/resources/${id}/`),

  create: async (data: any) =>
    api.post('/api/v1/resources/', data),

  update: async (id: number, data: any) =>
    api.put(`/api/v1/resources/${id}/`, data),

  delete: async (id: number) =>
    api.delete(`/api/v1/resources/${id}/`),

  testConnection: async (id: number) =>
    api.post(`/api/v1/resources/${id}/test/`),
};

export const monitoringApi = {
  systemMetrics: async () =>
    api.get('/api/v1/monitoring/system/'),

  tenantMetrics: async (tenantId?: number) =>
    api.get('/api/v1/monitoring/tenants/', { params: { tenant_id: tenantId } }),

  usageStats: async (period = '24h', tenantId?: number) =>
    api.get('/api/v1/monitoring/usage/', { params: { period, tenant_id: tenantId } }),

  alerts: async (page = 1, limit = 20) =>
    api.get('/api/v1/monitoring/alerts/', { params: { page, limit } }),
};

export const dashboardApi = {
  getMetrics: async () =>
    api.get('/api/v1/dashboard/metrics/'),
};

export const systemApi = {
  health: async () =>
    api.get('/health'),

  healthDetailed: async () =>
    api.get('/api/v1/system/health-detailed'),

  info: async () =>
    api.get('/api/v1/system/info/'),

  config: async () =>
    api.get('/api/v1/system/config/'),

  updateConfig: async (data: any) =>
    api.put('/api/v1/system/config/', data),

  // Software Update Management
  version: async () =>
    api.get('/api/v1/system/version'),

  checkUpdate: async () =>
    api.get('/api/v1/system/check-update'),

  validateUpdate: async (version: string) =>
    api.post('/api/v1/system/validate-update', { target_version: version }),

  startUpdate: async (version: string, createBackup = true) =>
    api.post('/api/v1/system/update', { target_version: version, create_backup: createBackup }),

  getUpdateStatus: async (updateId: string) =>
    api.get(`/api/v1/system/update/${updateId}/status`),

  rollback: async (updateId: string) =>
    api.post(`/api/v1/system/update/${updateId}/rollback`),

  // Backup Management
  listBackups: async () =>
    api.get('/api/v1/system/backups'),

  createBackup: async (type = 'full') =>
    api.post('/api/v1/system/backups', { backup_type: type }),

  getBackup: async (backupId: string) =>
    api.get(`/api/v1/system/backups/${backupId}`),

  deleteBackup: async (backupId: string) =>
    api.delete(`/api/v1/system/backups/${backupId}`),

  restoreBackup: async (backupId: string) =>
    api.post('/api/v1/system/restore', { backup_id: backupId }),
};

export const assistantLibraryApi = {
  listTemplates: async (page = 1, limit = 20, category?: string, status?: string) =>
    api.get('/api/v1/resource-management/templates/', { params: { page, limit, category, status } }),

  getTemplate: async (id: string) =>
    api.get(`/api/v1/resource-management/templates/${id}/`),

  createTemplate: async (data: any) =>
    api.post('/api/v1/resource-management/templates/', data),

  updateTemplate: async (id: string, data: any) =>
    api.put(`/api/v1/resource-management/templates/${id}/`, data),

  deleteTemplate: async (id: string) =>
    api.delete(`/api/v1/resource-management/templates/${id}/`),

  deployTemplate: async (templateId: string, tenantIds: string[]) =>
    api.post(`/api/v1/resource-management/templates/${templateId}/deploy/`, { tenant_ids: tenantIds }),

  getDeployments: async (templateId?: string) =>
    api.get('/api/v1/resource-management/deployments/', { params: { template_id: templateId } }),

  listAccessGroups: async () =>
    api.get('/api/v1/resource-management/access-groups/'),

  createAccessGroup: async (data: any) =>
    api.post('/api/v1/resource-management/access-groups/', data),
};

export const securityApi = {
  getSecurityEvents: async (page = 1, limit = 20, severity?: string, timeRange?: string) =>
    api.get('/api/v1/security/events/', { params: { page, limit, severity, time_range: timeRange } }),

  getAccessLogs: async (page = 1, limit = 20, timeRange?: string) =>
    api.get('/api/v1/security/access-logs/', { params: { page, limit, time_range: timeRange } }),

  getSecurityPolicies: async () =>
    api.get('/api/v1/security/policies/'),

  updateSecurityPolicy: async (id: number, data: any) =>
    api.put(`/api/v1/security/policies/${id}/`, data),

  getSecurityMetrics: async () =>
    api.get('/api/v1/security/metrics/'),

  acknowledgeEvent: async (eventId: number) =>
    api.post(`/api/v1/security/events/${eventId}/acknowledge/`),

  exportSecurityReport: async (timeRange?: string) =>
    api.get('/api/v1/security/export-report/', { params: { time_range: timeRange } }),
};


export const tfaApi = {
  enable: async () =>
    api.post('/api/v1/tfa/enable'),

  verifySetup: async (code: string) =>
    api.post('/api/v1/tfa/verify-setup', { code }),

  disable: async (password: string) =>
    api.post('/api/v1/tfa/disable', { password }),

  verifyLogin: async (code: string) =>
    api.post('/api/v1/tfa/verify-login', { code }, { withCredentials: true }),

  getStatus: async () =>
    api.get('/api/v1/tfa/status'),

  getSessionData: async () =>
    api.get('/api/v1/tfa/session-data', { withCredentials: true }),

  getQRCodeBlob: async () =>
    api.get('/api/v1/tfa/session-qr-code', {
      responseType: 'blob',
      withCredentials: true,
    }),
};

export const apiKeysApi = {
  // Get API key status for a tenant (without decryption)
  getTenantKeys: async (tenantId: number) =>
    api.get(`/api/v1/api-keys/tenant/${tenantId}`),

  // Set or update an API key
  setKey: async (data: {
    tenant_id: number;
    provider: string;
    api_key: string;
    api_secret?: string;
    enabled?: boolean;
    metadata?: Record<string, unknown>;
  }) => api.post('/api/v1/api-keys/set', data),

  // Test if an API key is valid
  testKey: async (tenantId: number, provider: string) =>
    api.post(`/api/v1/api-keys/test/${tenantId}/${provider}`),

  // Disable an API key (keeps it but marks disabled)
  disableKey: async (tenantId: number, provider: string) =>
    api.put(`/api/v1/api-keys/disable/${tenantId}/${provider}`),

  // Enable an API key
  enableKey: async (tenantId: number, provider: string, apiKey: string) =>
    api.post('/api/v1/api-keys/set', {
      tenant_id: tenantId,
      provider: provider,
      api_key: apiKey,
      enabled: true,
    }),

  // Remove an API key completely
  removeKey: async (tenantId: number, provider: string) =>
    api.delete(`/api/v1/api-keys/remove/${tenantId}/${provider}`),

  // Get supported providers list
  getProviders: async () =>
    api.get('/api/v1/api-keys/providers'),
};

export default api;