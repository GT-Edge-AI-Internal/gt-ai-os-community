import { mockApi } from './mock-api';
import { isTokenExpired, getAuthToken } from '@/services/auth';

// Enable mock mode when backend is not available
const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === 'true';

// API client configuration - use relative paths, proxied by Next.js
const API_BASE_URL = '';

/**
 * Handle server-side session signals (OWASP/NIST compliance - Issue #264)
 * The server is the authoritative source of truth for session state.
 * This function processes X-Session-Warning and X-Session-Expired headers.
 */
function handleSessionHeaders(response: Response): void {
  if (typeof window === 'undefined') return;

  // Check for session expiration signal from server
  const sessionExpired = response.headers.get('X-Session-Expired');
  if (sessionExpired) {
    // Server says session is expired - dispatch event for IdleTimerProvider
    window.dispatchEvent(new CustomEvent('session-expired', {
      detail: { reason: sessionExpired }
    }));
    return;
  }

  // Check for session warning signal from server
  const sessionWarning = response.headers.get('X-Session-Warning');
  if (sessionWarning) {
    const secondsRemaining = parseInt(sessionWarning, 10);
    if (!isNaN(secondsRemaining)) {
      // Server says session is about to expire - dispatch event for IdleTimerProvider
      window.dispatchEvent(new CustomEvent('session-warning', {
        detail: { secondsRemaining }
      }));
    }
  }
}

/**
 * Handle session expired response (401 with X-Session-Expired header)
 */
function handleSessionExpiredResponse(response: Response): void {
  if (typeof window === 'undefined') return;

  const sessionExpired = response.headers.get('X-Session-Expired');
  if (response.status === 401 && sessionExpired) {
    // Clear storage and redirect to login with session expired indicator
    localStorage.removeItem('gt2_token');
    localStorage.removeItem('gt2_user');
    localStorage.removeItem('gt2_tenant');
    window.location.href = `/auth/login?session_expired=${sessionExpired}`;
  }
}

// Helper function for API calls
async function apiCall(endpoint: string, options: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? getAuthToken() : null;

  // Note: We no longer check client-side token expiry here as the server is authoritative
  // The server-side session validation middleware will return appropriate headers

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Process server-side session signals (Issue #264)
  handleSessionHeaders(response);

  if (!response.ok) {
    // Handle session expired responses specially
    handleSessionExpiredResponse(response);
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// API endpoints
export const api = {
  // Auth endpoints
  auth: {
    login: async (email: string, password: string) =>
      USE_MOCK_API
        ? mockApi.auth.login(email, password)
        : apiCall('/api/v1/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
          }),
    
    logout: async () =>
      USE_MOCK_API
        ? mockApi.auth.logout()
        : apiCall('/api/v1/auth/logout', { method: 'POST' }),
    
    getProfile: async () =>
      USE_MOCK_API
        ? mockApi.auth.getProfile()
        : apiCall('/api/v1/user/profile'),
  },

  // Chat/Conversation endpoints
  conversations: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.conversations.list()
        : apiCall('/api/v1/conversations'),
    
    create: async (data: any) =>
      USE_MOCK_API
        ? mockApi.conversations.create(data)
        : apiCall('/api/v1/conversations', {
            method: 'POST',
            body: JSON.stringify(data),
          }),
    
    get: async (id: string) =>
      USE_MOCK_API
        ? mockApi.conversations.get(id)
        : apiCall(`/api/v1/conversations/${id}`),
    
    getMessages: async (id: string) =>
      USE_MOCK_API
        ? mockApi.conversations.getMessages(id)
        : apiCall(`/api/v1/conversations/${id}/messages`),
    
    sendMessage: async (conversationId: string, content: string) =>
      USE_MOCK_API
        ? mockApi.conversations.sendMessage(conversationId, content)
        : apiCall(`/api/v1/conversations/${conversationId}/messages`, {
            method: 'POST',
            body: JSON.stringify({ content }),
          }),
  },

  // Agent endpoints
  agents: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.agents.list()
        : apiCall('/api/v1/agents'),
    
    create: async (data: any) =>
      USE_MOCK_API
        ? mockApi.agents.create(data)
        : apiCall('/api/v1/agents', {
            method: 'POST',
            body: JSON.stringify(data),
          }),
    
    get: async (id: string) =>
      USE_MOCK_API
        ? mockApi.agents.get(id)
        : apiCall(`/api/v1/agents/${id}`),
    
    update: async (id: string, data: any) =>
      USE_MOCK_API
        ? mockApi.agents.update(id, data)
        : apiCall(`/api/v1/agents/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
          }),
    
    delete: async (id: string) =>
      USE_MOCK_API
        ? mockApi.agents.delete(id)
        : apiCall(`/api/v1/agents/${id}`, {
            method: 'DELETE',
          }),
  },

  // Document endpoints
  documents: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.documents.list()
        : apiCall('/api/v1/documents'),
    
    upload: async (file: File) => {
      if (USE_MOCK_API) {
        return mockApi.documents.upload(file);
      }

      const token = getAuthToken();

      // Check if token exists and is expired before uploading
      if (token && isTokenExpired(token)) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('gt2_token');
          localStorage.removeItem('gt2_user');
          localStorage.removeItem('gt2_tenant');
          window.location.href = '/auth/login?session_expired=true';
        }
        throw new Error('Token expired');
      }

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/v1/documents', {
        method: 'POST',
        headers: {
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }

      return response.json();
    },
    
    delete: async (id: string) =>
      USE_MOCK_API
        ? mockApi.documents.delete(id)
        : apiCall(`/api/v1/documents/${id}`, {
            method: 'DELETE',
          }),
    
    getChunks: async (id: string) =>
      USE_MOCK_API
        ? mockApi.documents.getChunks(id)
        : apiCall(`/api/v1/documents/${id}/chunks`),
  },

  // RAG/Knowledge endpoints
  rag: {
    search: async (query: string, datasetIds?: string[]) =>
      USE_MOCK_API
        ? mockApi.rag.search(query, datasetIds)
        : apiCall('/api/v1/rag/search', {
            method: 'POST',
            body: JSON.stringify({ query, dataset_ids: datasetIds }),
          }),
    
    getDatasets: async () =>
      USE_MOCK_API
        ? mockApi.rag.getDatasets()
        : apiCall('/api/v1/rag/datasets'),
    
    createDataset: async (data: any) =>
      USE_MOCK_API
        ? mockApi.rag.createDataset(data)
        : apiCall('/api/v1/rag/datasets', {
            method: 'POST',
            body: JSON.stringify(data),
          }),
  },

  // Agent endpoints
  agents: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.agents.list()
        : apiCall('/api/v1/agents'),
    
    create: async (data: any) =>
      USE_MOCK_API
        ? mockApi.agents.create(data)
        : apiCall('/api/v1/agents', {
            method: 'POST',
            body: JSON.stringify(data),
          }),
    
    execute: async (agentId: string, task: string) =>
      USE_MOCK_API
        ? mockApi.agents.execute(agentId, task)
        : apiCall(`/api/v1/agents/${agentId}/execute`, {
            method: 'POST',
            body: JSON.stringify({ task }),
          }),
  },

  // External Services endpoints
  services: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.services.list()
        : apiCall('/api/v1/webservices'),
    
    getEmbedConfig: async (serviceId: string) =>
      USE_MOCK_API
        ? mockApi.services.getEmbedConfig(serviceId)
        : apiCall(`/api/v1/webservices/${serviceId}/embed-config`),
  },

  // Games & AI Literacy endpoints
  games: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.games.list()
        : apiCall('/api/v1/games'),
    
    startGame: async (gameType: string, options?: any) =>
      USE_MOCK_API
        ? mockApi.games.startGame(gameType, options)
        : apiCall(`/api/v1/games/${gameType}/start`, {
            method: 'POST',
            body: JSON.stringify(options || {}),
          }),
    
    makeMove: async (gameId: string, move: any) =>
      USE_MOCK_API
        ? mockApi.games.makeMove(gameId, move)
        : apiCall(`/api/v1/games/${gameId}/move`, {
            method: 'POST',
            body: JSON.stringify({ move }),
          }),
    
    getProgress: async () =>
      USE_MOCK_API
        ? mockApi.games.getProgress()
        : apiCall('/api/v1/learning/progress'),
  },

  // Projects endpoints
  projects: {
    list: async () =>
      USE_MOCK_API
        ? mockApi.projects.list()
        : apiCall('/api/v1/projects'),
    
    create: async (data: any) =>
      USE_MOCK_API
        ? mockApi.projects.create(data)
        : apiCall('/api/v1/projects', {
            method: 'POST',
            body: JSON.stringify(data),
          }),
    
    get: async (id: string) =>
      USE_MOCK_API
        ? mockApi.projects.get(id)
        : apiCall(`/api/v1/projects/${id}`),
  },

  // Settings endpoints
  settings: {
    getPreferences: async () =>
      USE_MOCK_API
        ? mockApi.settings.getPreferences()
        : apiCall('/api/v1/user/preferences'),
    
    updatePreferences: async (data: any) =>
      USE_MOCK_API
        ? mockApi.settings.updatePreferences(data)
        : apiCall('/api/v1/user/preferences', {
            method: 'PUT',
            body: JSON.stringify(data),
          }),
  },

  // Generic upload method for services
  upload: async <T>(endpoint: string, formData: FormData, options: {
    headers?: Record<string, string>;
    onUploadProgress?: (progressEvent: ProgressEvent) => void;
  } = {}): Promise<T> => {
    const token = typeof window !== 'undefined' ? getAuthToken() : null;

    // Check if token exists and is expired before uploading
    if (token && isTokenExpired(token)) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('gt2_token');
        localStorage.removeItem('gt2_user');
        localStorage.removeItem('gt2_tenant');
        window.location.href = '/auth/login?session_expired=true';
      }
      throw new Error('Token expired');
    }

    const headers: HeadersInit = {
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    };

    // Create XMLHttpRequest for upload progress tracking
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      // Setup upload progress tracking
      if (options.onUploadProgress) {
        xhr.upload.addEventListener('progress', options.onUploadProgress);
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (e) {
            reject(new Error('Invalid JSON response'));
          }
        } else {
          reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
        }
      };

      xhr.onerror = () => {
        reject(new Error('Upload failed: Network error'));
      };

      xhr.open('POST', endpoint);

      // Set headers
      Object.entries(headers).forEach(([key, value]) => {
        if (value) xhr.setRequestHeader(key, value);
      });

      xhr.send(formData);
    });
  },

  // Helper methods
  get: async <T>(endpoint: string): Promise<T> => {
    return apiCall(endpoint);
  },

  post: async <T>(endpoint: string, data: any): Promise<T> => {
    return apiCall(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  put: async <T>(endpoint: string, data: any): Promise<T> => {
    return apiCall(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete: async <T>(endpoint: string): Promise<T> => {
    return apiCall(endpoint, {
      method: 'DELETE',
    });
  },
};

export default api;