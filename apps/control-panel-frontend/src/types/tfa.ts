/**
 * Two-Factor Authentication Type Definitions
 *
 * Shared types for TFA functionality across the Control Panel
 */

export type TFAStatus = 'disabled' | 'enabled' | 'enforced';

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
  code: string;
}

export interface TFAVerifyLoginResponse {
  success: boolean;
  access_token?: string;
  message?: string;
  user?: any;
  expires_in?: number;
}

export interface TFAStatusResponse {
  tfa_enabled: boolean;
  tfa_required: boolean;
  tfa_status: TFAStatus;
}

export interface TFASessionData {
  user_email: string;
  tfa_configured: boolean;
  qr_code_uri?: string;
  manual_entry_key?: string;
}

// Login response types for TFA flow detection
export interface NormalLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: any;
}

export interface TFASetupResponse {
  requires_tfa: true;
  tfa_configured: false;
  temp_token: string;
  qr_code_uri: string;
  manual_entry_key: string;
  user_email: string;
}

export interface TFAVerificationResponse {
  requires_tfa: true;
  tfa_configured: true;
  temp_token: string;
  user_email: string;
}

export type LoginResponse = NormalLoginResponse | TFASetupResponse | TFAVerificationResponse;

// Type guards for login response detection
export function isTFAResponse(response: any): response is TFASetupResponse | TFAVerificationResponse {
  return response && response.requires_tfa === true;
}

export function isTFASetupResponse(response: any): response is TFASetupResponse {
  return response && response.requires_tfa === true && response.tfa_configured === false;
}

export function isTFAVerificationResponse(response: any): response is TFAVerificationResponse {
  return response && response.requires_tfa === true && response.tfa_configured === true;
}

export function isNormalLoginResponse(response: any): response is NormalLoginResponse {
  return response && response.access_token && !response.requires_tfa;
}
