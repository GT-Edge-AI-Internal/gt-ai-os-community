/**
 * GT 2.0 Authentication Service
 * 
 * Handles JWT token management, user authentication, and tenant isolation.
 */

export interface User {
  email: string;
  full_name: string;
  user_id: string;
  tenant_domain: string;
  role: 'admin' | 'developer' | 'analyst' | 'student';
  is_active: boolean;
  created_at: string;
}

export interface TenantInfo {
  domain: string;
  name: string;
  id: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  tenant: TenantInfo;
}

// TFA Response types (minimal - session data stored server-side)
export interface TFASetupResponse {
  requires_tfa: true;
  tfa_configured: false;
  // Session data (QR code, manual key, etc.) fetched via /tfa/session-data using HTTP-only cookie
}

export interface TFAVerificationResponse {
  requires_tfa: true;
  tfa_configured: true;
  // Session data fetched via /tfa/session-data using HTTP-only cookie
}

// Union type for login responses
export type LoginResult = LoginResponse | TFASetupResponse | TFAVerificationResponse;

// Type guard functions
export function isTFAResponse(data: any): data is TFASetupResponse | TFAVerificationResponse {
  return data && data.requires_tfa === true;
}

export function isTFASetupResponse(data: any): data is TFASetupResponse {
  return data && data.requires_tfa === true && data.tfa_configured === false;
}

export function isTFAVerificationResponse(data: any): data is TFAVerificationResponse {
  return data && data.requires_tfa === true && data.tfa_configured === true;
}

// GT 2.0 Single Token Key - Elegant Simplicity
const TOKEN_KEY = 'gt2_token';
const USER_KEY = 'gt2_user';
const TENANT_KEY = 'gt2_tenant';

/**
 * Get stored authentication token
 */
export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  const token = localStorage.getItem(TOKEN_KEY);
  console.log('getAuthToken - retrieved token:', token ? 'EXISTS' : 'NULL');
  return token;
}

/**
 * Store authentication token
 */
export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Remove authentication token
 */
export function removeAuthToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(TENANT_KEY);
}

/**
 * Get stored user information
 */
export function getUser(): User | null {
  if (typeof window === 'undefined') return null;
  const userStr = localStorage.getItem(USER_KEY);
  return userStr ? JSON.parse(userStr) : null;
}

/**
 * Store user information
 */
export function setUser(user: User): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * Get stored tenant information
 */
export function getTenantInfo(): TenantInfo | null {
  if (typeof window === 'undefined') return null;
  const tenantStr = localStorage.getItem(TENANT_KEY);
  
  // Check for invalid JSON strings
  if (!tenantStr || tenantStr === 'undefined' || tenantStr === 'null') {
    // GT 2.0: Set default tenant for development
    const defaultTenant = {
      domain: 'test-company',
      name: 'Test Company'
    };
    setTenantInfo(defaultTenant);
    return defaultTenant;
  }
  
  try {
    return JSON.parse(tenantStr);
  } catch (error) {
    console.warn('Failed to parse tenant info from localStorage:', error);
    // Clear invalid data
    localStorage.removeItem(TENANT_KEY);
    
    // GT 2.0: Set default tenant for development
    const defaultTenant = {
      domain: 'test-company',
      name: 'Test Company'
    };
    setTenantInfo(defaultTenant);
    return defaultTenant;
  }
}

/**
 * Store tenant information
 */
export function setTenantInfo(tenant: TenantInfo): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TENANT_KEY, JSON.stringify(tenant));
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  const token = getAuthToken();
  const user = getUser();
  return !!(token && user);
}

/**
 * Parse JWT token payload (without verification)
 */
export function parseTokenPayload(token: string): any {
  try {
    // Validate input
    if (!token || typeof token !== 'string') {
      console.warn('parseTokenPayload: Invalid token (null or not string)');
      return null;
    }

    const parts = token.split('.');
    if (parts.length !== 3) {
      console.warn('parseTokenPayload: Invalid JWT format (not 3 parts)');
      return null;
    }

    const payload = parts[1];
    if (!payload) {
      console.warn('parseTokenPayload: Missing payload section');
      return null;
    }

    // Add padding if needed for proper base64 decoding
    const paddedPayload = payload + '='.repeat((4 - payload.length % 4) % 4);
    const decoded = atob(paddedPayload);
    return JSON.parse(decoded);
  } catch (error) {
    console.error('Failed to parse JWT payload:', error);
    return null;
  }
}

/**
 * Map Control Panel user_type to Tenant role format
 *
 * Control Panel uses: super_admin, tenant_admin, tenant_user
 * Tenant uses: admin, developer, analyst, student
 *
 * This bridges the gap between authentication (Control Panel) and authorization (Tenant)
 */
export function mapControlPanelRoleToTenantRole(userType?: string): 'admin' | 'developer' | 'analyst' | 'student' {
  if (!userType) return 'student';

  const lowerType = userType.toLowerCase();

  // Both super_admin and tenant_admin map to admin role in tenant system
  if (lowerType === 'super_admin' || lowerType === 'tenant_admin') {
    return 'admin';
  }

  // Default to student for tenant_user or any other type
  return 'student';
}

/**
 * Check if token is expired
 */
export function isTokenExpired(token: string): boolean {
  const payload = parseTokenPayload(token);
  if (!payload || !payload.exp) return true;
  
  const now = Math.floor(Date.now() / 1000);
  return payload.exp < now;
}

/**
 * Check if current token is valid
 */
export function isTokenValid(): boolean {
  const token = getAuthToken();
  if (!token) return false;
  return !isTokenExpired(token);
}

/**
 * Parse capabilities from JWT token (GT 2.0 Security Model)
 */
export function parseCapabilities(token: string): string[] {
  const payload = parseTokenPayload(token);
  if (!payload) return [];

  // For super_admin users, grant all capabilities automatically
  if (payload.user_type === 'super_admin') {
    return [
      'agents:read', 'agents:create', 'agents:edit', 'agents:delete', 'agents:execute',
      'datasets:read', 'datasets:create', 'datasets:upload', 'datasets:delete',
      'conversations:read', 'conversations:create', 'conversations:delete',
      'documents:read', 'documents:upload', 'documents:delete',
      'admin:users', 'admin:tenants', 'admin:system'
    ];
  }

  // Check for capabilities in current_tenant first (enhanced JWTs from tenant backend)
  const currentTenant = payload.current_tenant || {};
  let capabilities = currentTenant.capabilities || [];

  // If no capabilities in current_tenant, check root level (Control Panel JWTs)
  if (!Array.isArray(capabilities) || capabilities.length === 0) {
    capabilities = payload.capabilities || [];
  }

  // Convert capability objects to strings if needed
  if (Array.isArray(capabilities)) {
    const parsed = capabilities.map(cap => {
      if (typeof cap === 'string') return cap;
      if (typeof cap === 'object' && cap.resource && cap.actions) {
        // Handle wildcard capabilities (super_admin)
        if (cap.resource === '*' && cap.actions.includes('*')) {
          // Return all possible capabilities for wildcard access
          return [
            'agents:read', 'agents:create', 'agents:edit', 'agents:delete', 'agents:execute',
            'datasets:read', 'datasets:create', 'datasets:upload', 'datasets:delete',
            'conversations:read', 'conversations:create', 'conversations:delete',
            'documents:read', 'documents:upload', 'documents:delete',
            'admin:users', 'admin:tenants', 'admin:system'
          ];
        }
        // Convert {resource: "agents", actions: ["read", "write"]} to ["agents:read", "agents:write"]
        return cap.actions.map((action: string) => `${cap.resource}:${action}`);
      }
      return cap;
    }).flat();

    return parsed;
  }

  return [];
}

/**
 * Check if user has specific capability
 */
export function hasCapability(capability: string): boolean {
  const token = getAuthToken();
  if (!token || !isTokenValid()) return false;
  
  const capabilities = parseCapabilities(token);
  return capabilities.includes(capability);
}

/**
 * Get current user's capabilities
 */
export function getUserCapabilities(): string[] {
  const token = getAuthToken();
  console.log('getUserCapabilities - token exists:', !!token);
  
  if (!token) {
    console.log('getUserCapabilities - no token found');
    return [];
  }
  
  if (!isTokenValid()) {
    console.log('getUserCapabilities - token is invalid/expired');
    return [];
  }
  
  const capabilities = parseCapabilities(token);
  console.log('getUserCapabilities - parsed capabilities:', capabilities);
  return capabilities;
}

/**
 * Login with username/password
 */
export async function login(credentials: LoginRequest): Promise<LoginResult | { error: string }> {
  try {
    // Get tenant domain from environment or use configured default
    const tenantDomain = process.env.NEXT_PUBLIC_TENANT_DOMAIN || 'test-company';

    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-Domain': tenantDomain,
      },
      body: JSON.stringify({
        email: credentials.username,
        password: credentials.password,
      }),
    });

    if (!response.ok) {
      let errorMessage = 'Login failed';

      try {
        const errorData = await response.json();

        // Extract error message from various possible formats
        if (typeof errorData === 'string') {
          errorMessage = errorData;
        } else if (errorData.detail) {
          // Handle string detail
          errorMessage = typeof errorData.detail === 'string'
            ? errorData.detail
            : 'Login failed. Please try again.';
        } else if (errorData.message) {
          // Handle message field - but use friendly message for generic errors
          if (typeof errorData.message === 'string') {
            // If it's a generic "Login failed" message, make it more specific
            if (errorData.message === 'Login failed' || errorData.message === 'login failed') {
              errorMessage = 'Invalid email or password';
            } else {
              errorMessage = errorData.message;
            }
          } else {
            errorMessage = 'Login failed. Please try again.';
          }
        } else if (errorData.error) {
          errorMessage = typeof errorData.error === 'string'
            ? errorData.error
            : 'Login failed. Please try again.';
        } else {
          // No recognized fields, use status-based message
          errorMessage = 'Login failed. Please try again.';
        }
      } catch (e) {
        // Failed to parse error response, will use status-based message below
      }

      // Override with user-friendly messages based on status code
      if (response.status === 401) {
        errorMessage = 'Invalid email or password';
      } else if (response.status === 422) {
        errorMessage = 'Please check your email and password format';
      } else if (response.status === 500) {
        // For 500 errors during login, it's likely an auth issue
        errorMessage = 'Invalid email or password';
      } else if (response.status >= 500) {
        errorMessage = 'Server error. Please try again later.';
      }

      return { error: errorMessage };
    }

    const data = await response.json();

    // Check if this is a TFA response (setup or verification required)
    if (isTFAResponse(data)) {
      // TFA required - return response for auth store to handle
      // Auth store will redirect to /verify-tfa page
      console.log('TFA required for login');
      return data;
    }

    // Normal login response - validate required fields
    if (!data.access_token) {
      return { error: 'Server returned invalid response (missing token)' };
    }

    console.log('Login successful - storing authentication data');

    // Store authentication data
    setAuthToken(data.access_token);
    setUser(data.user);
    setTenantInfo(data.tenant);

    return data;
  } catch (error) {
    console.error('Login network error:', error);
    
    if (error instanceof TypeError && error.message.includes('fetch')) {
      return { error: 'Cannot connect to server. Please check if the application is running.' };
    }
    
    return { error: error instanceof Error ? error.message : 'Network error occurred' };
  }
}

/**
 * Logout and clear stored data
 */
export function logout(): void {
  removeAuthToken();
  // Optionally call logout endpoint
  // await fetch('/api/v1/auth/logout', { method: 'POST' });
}

/**
 * Token refresh result type
 *
 * NIST/OWASP Compliant Session Management (Issue #242):
 * - success: Token refreshed, session extended
 * - absolute_timeout: 8-hour session limit reached, must re-login
 * - error: Other refresh failure
 */
export interface RefreshResult {
  success: boolean;
  error?: 'absolute_timeout' | 'expired' | 'network' | 'unknown';
}

/**
 * Refresh authentication token
 *
 * NIST/OWASP Compliant Session Management (Issue #242):
 * - Returns detailed result to distinguish between idle timeout and absolute timeout
 * - absolute_timeout: Session hit 8-hour limit, user must re-authenticate
 * - expired: Normal token expiration (idle timeout exceeded)
 */
export async function refreshToken(): Promise<RefreshResult> {
  const token = getAuthToken();
  if (!token) return { success: false, error: 'expired' };

  try {
    const response = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      // Check for absolute timeout (Issue #242)
      // Server returns 401 with X-Session-Expired: absolute header
      const sessionExpiredHeader = response.headers.get('X-Session-Expired');
      if (response.status === 401 && sessionExpiredHeader === 'absolute') {
        console.log('[Auth] Absolute session timeout reached (8 hours)');
        return { success: false, error: 'absolute_timeout' };
      }

      // Regular token expiration or other auth failure
      return { success: false, error: 'expired' };
    }

    const data = await response.json();
    setAuthToken(data.access_token);
    return { success: true };
  } catch (error) {
    console.error('[Auth] Token refresh network error:', error);
    return { success: false, error: 'network' };
  }
}

/**
 * Auto-refresh token if needed
 */
export async function ensureValidToken(): Promise<boolean> {
  const token = getAuthToken();
  if (!token) return false;

  if (isTokenExpired(token)) {
    const result = await refreshToken();
    return result.success;
  }

  return true;
}