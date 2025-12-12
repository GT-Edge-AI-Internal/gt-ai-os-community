/**
 * Two-Factor Authentication Service
 *
 * Handles all TFA-related API calls to the backend.
 */

import { getApiUrl } from '@/lib/utils';
import { getAuthToken } from './auth';

const API_URL = getApiUrl();

export interface TFAEnableResponse {
  success: boolean;
  message: string;
  qr_code_uri: string;
  manual_entry_key: string;
}

export interface TFAVerifySetupRequest {
  code: string;
}

export interface TFAVerifySetupResponse {
  success: boolean;
  message: string;
}

export interface TFADisableRequest {
  password: string;
}

export interface TFADisableResponse {
  success: boolean;
  message: string;
}

export interface TFAVerifyLoginRequest {
  temp_token: string;
  code: string;
}

export interface TFAVerifyLoginResponse {
  success: boolean;
  access_token?: string;
  message?: string;
  // Note: user, expires_in removed - all data is in JWT claims
}

export interface TFAStatusResponse {
  tfa_enabled: boolean;
  tfa_required: boolean;
  tfa_status: string; // "disabled", "enabled", "enforced"
}

export interface TFASessionData {
  user_email: string;
  tfa_configured: boolean;
  qr_code_uri?: string;
  manual_entry_key?: string;
}

/**
 * Get TFA session data (metadata only - no QR code) using HTTP-only session cookie
 * Called from /verify-tfa page to display setup information
 */
export async function getTFASessionData(): Promise<TFASessionData> {
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/session-data`, {
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
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/session-qr-code`, {
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
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/enable`, {
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
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/verify-setup`, {
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
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/disable`, {
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
 * Uses HTTP-only session cookie for authentication (no temp_token needed)
 */
export async function verifyTFALogin(
  code: string
): Promise<TFAVerifyLoginResponse> {
  try {
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/verify-login`, {
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
    const response = await fetch(`${API_URL}/api/v1/auth/tfa/status`, {
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
