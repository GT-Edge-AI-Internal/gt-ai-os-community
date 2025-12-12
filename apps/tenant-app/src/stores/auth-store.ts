import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User } from '@/types';
import { getApiUrl, handleApiError } from '@/lib/utils';
import {
  login as loginService,
  logout as logoutService,
  getUser,
  isTokenValid,
  isTokenExpired,
  parseCapabilities,
  getAuthToken,
  setAuthToken,
  removeAuthToken,
  isTFAResponse,
  isTFASetupResponse,
  isTFAVerificationResponse
} from '@/services/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  token: string | null;
  capabilities: string[];
  // TFA state (minimal - session data stored server-side)
  requiresTfa: boolean;
  tfaConfigured: boolean;
  // Internal hydration state
  _hasHydrated: boolean;
  // Token monitoring
  tokenMonitorInterval: NodeJS.Timeout | null;
}

interface AuthActions {
  login: (email: string, password: string) => Promise<boolean>;
  logout: (reason?: 'manual' | 'expired' | 'unauthorized' | 'session_expired') => void;
  checkAuth: () => Promise<void>;
  clearError: () => void;
  updateUser: (userData: Partial<User>) => void;
  setToken: (newToken: string) => void;
  startTokenMonitor: () => void;
  stopTokenMonitor: () => void;
}

type AuthStore = AuthState & AuthActions;

const API_URL = getApiUrl();

// Helper function to convert string capabilities to Capability objects
function convertCapabilities(capabilities: string[]): any[] {
  return capabilities.map(cap => {
    const [resource, action] = cap.split(':');
    return {
      resource: resource || cap,
      actions: action ? [action] : ['*'],
      constraints: {}
    };
  });
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      token: null,
      capabilities: [],
      // TFA state (minimal - session data stored server-side)
      requiresTfa: false,
      tfaConfigured: false,
      // Internal hydration state
      _hasHydrated: false,
      // Token monitoring
      tokenMonitorInterval: null,

      // Actions
      login: async (email: string, password: string): Promise<boolean> => {
        set({ isLoading: true, error: null });

        try {
          const result = await loginService({ username: email, password });

          if ('error' in result) {
            throw new Error(result.error);
          }

          // Check if TFA is required using type guard
          if (isTFAResponse(result)) {
            // TFA required - session stored server-side with HTTP-only cookie
            set({
              isLoading: false,
              requiresTfa: true,
              tfaConfigured: result.tfa_configured,
              error: null,
            });

            // Navigate to TFA verification page
            // Session data (QR code, etc.) will be fetched from server using cookie
            if (typeof window !== 'undefined') {
              window.location.href = '/verify-tfa';
            }

            return true;
          }

          // Normal login flow (no TFA)
          const { access_token, user, tenant } = result;

          // Parse capabilities from token (GT 2.0 Security Model)
          const capabilityStrings = parseCapabilities(access_token);
          const capabilities = convertCapabilities(capabilityStrings);

          // Update user object with converted capabilities
          const userWithCapabilities = { ...user, capabilities };

          set({
            user: userWithCapabilities,
            token: access_token,
            capabilities: capabilityStrings, // Store both formats for compatibility
            isAuthenticated: true,
            isLoading: false,
            error: null,
            // Clear TFA state
            requiresTfa: false,
            tfaConfigured: false,
          });

          // Token monitoring disabled - IdleTimerProvider handles session expiry
          // get().startTokenMonitor();

          // Navigation handled by login page component (prevents RSC payload errors)
          return true;
        } catch (error) {
          console.error('Login error:', error);

          let errorMessage = 'An error occurred. Please try again.';

          if (error instanceof Error) {
            errorMessage = error.message;
          } else if (typeof error === 'string') {
            errorMessage = error;
          } else if (error && typeof error === 'object') {
            // Handle various error object formats
            if (error.message) {
              errorMessage = error.message;
            } else if (error.detail) {
              errorMessage = error.detail;
            } else if (error.error) {
              errorMessage = error.error;
            } else {
              // Try to extract meaningful information from the error object
              try {
                const stringified = JSON.stringify(error);
                // Only use stringified version if it's not just "[object Object]" or "{}"
                if (stringified && stringified !== '{}' && stringified !== '[object Object]') {
                  errorMessage = stringified;
                } else {
                  // Extract any string values from the error object
                  const values = Object.values(error).filter(v => typeof v === 'string');
                  if (values.length > 0) {
                    errorMessage = values[0];
                  }
                }
              } catch (e) {
                // JSON.stringify failed, keep default message
                console.warn('Error stringification failed:', e);
              }
            }
          }

          set({
            isLoading: false,
            error: errorMessage,
            isAuthenticated: false,
            user: null,
            token: null,
            capabilities: [],
          });
          
          return false;
        }
      },

      logout: (reason?: 'manual' | 'expired' | 'unauthorized' | 'session_expired') => {
        // Stop token monitoring
        const interval = get().tokenMonitorInterval;
        if (interval) {
          clearInterval(interval);
        }

        // Use service layer logout (clears localStorage)
        logoutService();

        // Clear state including TFA state and monitor
        set({
          user: null,
          token: null,
          capabilities: [],
          isAuthenticated: false,
          error: null,
          requiresTfa: false,
          tfaConfigured: false,
          tokenMonitorInterval: null,
        });

        // Redirect to login with context (NIST/OWASP Issue #242)
        // - 'expired': Idle timeout (30 min inactivity)
        // - 'session_expired': Absolute timeout (8 hour session limit reached)
        if (typeof window !== 'undefined') {
          let params = '';
          if (reason === 'expired') {
            params = '?session_expired=true';
          } else if (reason === 'session_expired') {
            params = '?session_expired=absolute';
          }
          window.location.href = `/login${params}`;
        }
      },

      checkAuth: async (): Promise<void> => {
        set({ isLoading: true, error: null });

        try {
          // Check if token is valid
          if (!isTokenValid()) {
            // Clear localStorage when token is invalid
            removeAuthToken();
            set({ 
              isLoading: false, 
              isAuthenticated: false,
              user: null,
              token: null,
              capabilities: []
            });
            return;
          }

          // Get user and token from service layer
          const user = getUser();
          const token = getAuthToken();
          
          if (user && token) {
            const capabilityStrings = parseCapabilities(token);
            const capabilities = convertCapabilities(capabilityStrings);

            // Update user object with converted capabilities
            const userWithCapabilities = { ...user, capabilities };

            set({
              user: userWithCapabilities,
              token,
              capabilities: capabilityStrings,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });

            // Token monitoring disabled - IdleTimerProvider handles session expiry
            // get().startTokenMonitor();
          } else {
            set({
              user: null,
              token: null,
              capabilities: [],
              isAuthenticated: false,
              isLoading: false,
              error: null,
            });
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : 'Authentication check failed';
          
          // Clear invalid authentication  
          removeAuthToken();
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: errorMessage,
          });
        }
      },

      clearError: () => {
        set({ error: null });
      },

      updateUser: (userData: Partial<User>) => {
        const currentUser = get().user;
        if (currentUser) {
          set({
            user: { ...currentUser, ...userData }
          });
        }
      },

      setToken: (newToken: string) => {
        // Update token in localStorage and state
        // Used by IdleTimerProvider after successful token refresh
        setAuthToken(newToken);
        set({ token: newToken });
      },

      startTokenMonitor: () => {
        // Clear any existing monitor
        const existing = get().tokenMonitorInterval;
        if (existing) {
          clearInterval(existing);
        }

        // Check token every 30 seconds
        const interval = setInterval(() => {
          const token = get().token || getAuthToken();

          if (!token || isTokenExpired(token)) {
            get().logout('expired');
          }
        }, 30000); // 30 seconds

        set({ tokenMonitorInterval: interval });
      },

      stopTokenMonitor: () => {
        const interval = get().tokenMonitorInterval;
        if (interval) {
          clearInterval(interval);
          set({ tokenMonitorInterval: null });
        }
      },
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({
        // Only persist non-sensitive data
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        // Persist TFA state for redirect flow (no sensitive data - session in HTTP-only cookie)
        requiresTfa: state.requiresTfa,
        tfaConfigured: state.tfaConfigured,
      }),
      // Add hydration handling to prevent SSR mismatches
      skipHydration: typeof window === 'undefined',
      // Properly set hydration flag when Zustand finishes loading from localStorage
      onRehydrateStorage: () => (state) => {
        if (state) {
          state._hasHydrated = true;
        }
      }
    }
  )
);

// Helper function to get authenticated headers for API calls
export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

// Helper function to check if user has specific capability
export function hasCapability(resource: string, action: string): boolean {
  const { user } = useAuthStore.getState();
  
  if (!user || !user.capabilities) {
    return false;
  }

  return user.capabilities.some(cap => {
    // Check for exact match or wildcard
    const resourceMatch = cap.resource === resource || 
                         cap.resource === '*' || 
                         cap.resource.endsWith(':*');
    
    const actionMatch = cap.actions.includes(action) || 
                       cap.actions.includes('*');

    return resourceMatch && actionMatch;
  });
}

// Helper function to get current tenant ID
export function getCurrentTenantId(): number | null {
  const { user } = useAuthStore.getState();
  return user?.tenant_id || null;
}

// Helper function to check if user is tenant admin
export function isTenantAdmin(): boolean {
  const { user } = useAuthStore.getState();
  return user?.user_type === 'tenant_admin';
}

// Hook to check if store has finished hydrating from localStorage
export function useHasHydrated(): boolean {
  return useAuthStore((state) => state._hasHydrated);
}