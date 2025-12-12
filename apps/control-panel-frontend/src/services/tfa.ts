/**
 * Two-Factor Authentication Service
 *
 * Handles all TFA-related API calls to the Control Panel backend.
 */

import {
  TFAEnableResponse,
  TFAVerifySetupResponse,
  TFADisableResponse,
  TFAVerifyLoginResponse,
  TFAStatusResponse,
  TFASessionData,
} from '@/types/tfa';

// Get API URL from environment or use relative path for Next.js proxy
const getApiUrl = () => {
  if (typeof window === 'undefined') {
    // Server-side: use Docker hostname (INTERNAL_API_URL) or fallback to Docker DNS
    return process.env.INTERNAL_API_URL || 'http://control-panel-backend:8000';
  }
  // Client-side: use relative path (goes through Next.js proxy)
  return '';
};

const API_URL = getApiUrl();

/**
 * Get auth token from localStorage
 */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;

  try {
    const authStorage = localStorage.getItem('gt2-auth-storage');
    if (!authStorage) return null;

    const parsed = JSON.parse(authStorage);
    return parsed.state?.token || null;
  } catch {
    return null;
  }
}

/**
 * Get TFA session data (metadata only - no QR code) using HTTP-only session cookie
 * Called from /verify-tfa page to display setup information
 */
export async function getTFASessionData(): Promise<TFASessionData> {
  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/session-data`, {
      method: 'GET',
      credentials: 'include', // Include HTTP-only cookies
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get TFA session data');
    }

    return await response.json();
  } catch (error) {
    console.error('Get TFA session data error:', error);
    throw error;
  }
}

/**
 * Get TFA QR code as PNG blob (secure: TOTP secret never exposed to JavaScript)
 * Called from /verify-tfa page to display QR code via blob URL
 */
export async function getTFAQRCodeBlob(): Promise<string> {
  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/session-qr-code`, {
      method: 'GET',
      credentials: 'include', // Include HTTP-only cookies
    });

    if (!response.ok) {
      throw new Error('Failed to get TFA QR code');
    }

    // Get PNG blob
    const blob = await response.blob();

    // Create object URL (will be revoked on unmount)
    const blobUrl = URL.createObjectURL(blob);

    return blobUrl;
  } catch (error) {
    console.error('Get TFA QR code error:', error);
    throw error;
  }
}

/**
 * Enable TFA for current user (user-initiated from settings)
 */
export async function enableTFA(): Promise<TFAEnableResponse> {
  const token = getAuthToken();

  if (!token) {
    throw new Error('Not authenticated');
  }

  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/enable`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to enable TFA');
    }

    return await response.json();
  } catch (error) {
    console.error('Enable TFA error:', error);
    throw error;
  }
}

/**
 * Verify TFA setup code and complete setup
 */
export async function verifyTFASetup(code: string): Promise<TFAVerifySetupResponse> {
  const token = getAuthToken();

  if (!token) {
    throw new Error('Not authenticated');
  }

  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/verify-setup`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Invalid verification code');
    }

    return await response.json();
  } catch (error) {
    console.error('Verify TFA setup error:', error);
    throw error;
  }
}

/**
 * Disable TFA for current user (requires password)
 */
export async function disableTFA(password: string): Promise<TFADisableResponse> {
  const token = getAuthToken();

  if (!token) {
    throw new Error('Not authenticated');
  }

  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/disable`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to disable TFA');
    }

    return await response.json();
  } catch (error) {
    console.error('Disable TFA error:', error);
    throw error;
  }
}

/**
 * Verify TFA code during login
 * Uses HTTP-only session cookie for authentication
 */
export async function verifyTFALogin(code: string): Promise<TFAVerifyLoginResponse> {
  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/verify-login`, {
      method: 'POST',
      credentials: 'include', // Include HTTP-only cookies
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Invalid verification code');
    }

    return await response.json();
  } catch (error) {
    console.error('Verify TFA login error:', error);
    throw error;
  }
}

/**
 * Get TFA status for current user
 */
export async function getTFAStatus(): Promise<TFAStatusResponse> {
  const token = getAuthToken();

  if (!token) {
    throw new Error('Not authenticated');
  }

  try {
    const response = await fetch(`${API_URL}/api/v1/tfa/status`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      // Return default if request fails
      return {
        tfa_enabled: false,
        tfa_required: false,
        tfa_status: 'disabled',
      };
    }

    return await response.json();
  } catch (error) {
    console.error('Get TFA status error:', error);
    return {
      tfa_enabled: false,
      tfa_required: false,
      tfa_status: 'disabled',
    };
  }
}
