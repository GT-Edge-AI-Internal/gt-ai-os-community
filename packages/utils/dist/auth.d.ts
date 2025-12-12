import { JWTPayload, Capability } from '@gt2/types';
/**
 * Generate a cryptographic hash for capability verification
 */
export declare function generateCapabilityHash(capabilities: Capability[]): string;
/**
 * Verify capability hash to ensure JWT hasn't been tampered with
 */
export declare function verifyCapabilityHash(capabilities: Capability[], hash: string): boolean;
/**
 * Create a capability-based JWT token
 */
export declare function createJWT(payload: Omit<JWTPayload, 'capability_hash' | 'exp' | 'iat'>): string;
/**
 * Verify and decode a JWT token
 */
export declare function verifyJWT(token: string): JWTPayload | null;
/**
 * Check if user has required capability
 */
export declare function hasCapability(userCapabilities: Capability[], resource: string, action: string): boolean;
/**
 * Hash password for storage
 */
export declare function hashPassword(password: string): Promise<string>;
/**
 * Verify password against hash
 */
export declare function verifyPassword(password: string, hash: string): Promise<boolean>;
/**
 * Generate secure random token
 */
export declare function generateSecureToken(length?: number): string;
/**
 * Create tenant-scoped capabilities
 */
export declare function createTenantCapabilities(tenantDomain: string, userType: 'tenant_admin' | 'tenant_user'): Capability[];
/**
 * Create super admin capabilities
 */
export declare function createSuperAdminCapabilities(): Capability[];
/**
 * Extract Bearer token from Authorization header
 */
export declare function extractBearerToken(authHeader?: string): string | null;
/**
 * Check if JWT token is expired
 */
export declare function isTokenExpired(token: JWTPayload): boolean;
