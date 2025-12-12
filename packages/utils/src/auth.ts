// Authentication and Authorization Utilities
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';
import crypto from 'crypto';
import { JWTPayload, Capability } from '@gt2/types';

// JWT Configuration
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '24h';

/**
 * Generate a cryptographic hash for capability verification
 */
export function generateCapabilityHash(capabilities: Capability[]): string {
  const capabilityString = JSON.stringify(capabilities, Object.keys(capabilities).sort());
  return crypto.createHmac('sha256', JWT_SECRET).update(capabilityString).digest('hex');
}

/**
 * Verify capability hash to ensure JWT hasn't been tampered with
 */
export function verifyCapabilityHash(capabilities: Capability[], hash: string): boolean {
  const expectedHash = generateCapabilityHash(capabilities);
  return crypto.timingSafeEqual(Buffer.from(hash), Buffer.from(expectedHash));
}

/**
 * Create a capability-based JWT token
 */
export function createJWT(payload: Omit<JWTPayload, 'capability_hash' | 'exp' | 'iat'>): string {
  const capability_hash = generateCapabilityHash(payload.capabilities);
  const fullPayload: JWTPayload = {
    ...payload,
    capability_hash,
    exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60), // 24 hours
    iat: Math.floor(Date.now() / 1000)
  };

  return jwt.sign(fullPayload, JWT_SECRET, { algorithm: 'HS256' });
}

/**
 * Verify and decode a JWT token
 */
export function verifyJWT(token: string): JWTPayload | null {
  try {
    const decoded = jwt.verify(token, JWT_SECRET) as JWTPayload;
    
    // Verify capability hash to ensure token hasn't been tampered with
    if (!verifyCapabilityHash(decoded.capabilities, decoded.capability_hash)) {
      throw new Error('Invalid capability hash');
    }

    return decoded;
  } catch (error) {
    return null;
  }
}

/**
 * Check if user has required capability
 *
 * Supports wildcard matching for resources:
 * - "*" matches all resources
 * - "documents/*" matches all resources starting with "documents/"
 * - "documents/read" matches only exact resource "documents/read"
 */
export function hasCapability(
  userCapabilities: Capability[],
  resource: string,
  action: string
): boolean {
  return userCapabilities.some(cap => {
    // Check if capability matches resource (support wildcards)
    let resourceMatch = false;

    if (cap.resource === '*') {
      // Wildcard matches everything
      resourceMatch = true;
    } else if (cap.resource === resource) {
      // Exact match
      resourceMatch = true;
    } else if (cap.resource.endsWith('/*')) {
      // Prefix wildcard: "documents/*" matches "documents/read", "documents/write", etc.
      const prefix = cap.resource.slice(0, -1); // Remove trailing "*", keep "/"
      resourceMatch = resource.startsWith(prefix);
    } else if (cap.resource.endsWith('*')) {
      // Trailing wildcard: "documents*" matches "documents", "documents/read", etc.
      const prefix = cap.resource.slice(0, -1); // Remove trailing "*"
      resourceMatch = resource.startsWith(prefix);
    }

    // Check if capability includes required action
    const actionMatch = cap.actions.includes('*') || cap.actions.includes(action);

    // Check constraints if present
    if (cap.constraints) {
      // Check validity period
      if (cap.constraints.valid_until) {
        const validUntil = new Date(cap.constraints.valid_until);
        if (new Date() > validUntil) {
          return false;
        }
      }

      // Additional constraint checks can be added here
    }

    return resourceMatch && actionMatch;
  });
}

/**
 * Hash password for storage
 */
export async function hashPassword(password: string): Promise<string> {
  const salt = await bcrypt.genSalt(12);
  return bcrypt.hash(password, salt);
}

/**
 * Verify password against hash
 */
export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

/**
 * Generate secure random token
 */
export function generateSecureToken(length: number = 32): string {
  return crypto.randomBytes(length).toString('hex');
}

/**
 * Create tenant-scoped capabilities
 */
export function createTenantCapabilities(
  tenantDomain: string,
  userType: 'tenant_admin' | 'tenant_user'
): Capability[] {
  const baseResource = `tenant:${tenantDomain}`;
  
  if (userType === 'tenant_admin') {
    return [
      {
        resource: `${baseResource}:*`,
        actions: ['read', 'write', 'admin'],
        constraints: {}
      },
      {
        resource: 'ai_resource:*',
        actions: ['use'],
        constraints: {
          usage_limits: {
            max_requests_per_hour: 1000,
            max_tokens_per_request: 4000
          }
        }
      }
    ];
  } else {
    return [
      {
        resource: `${baseResource}:conversations`,
        actions: ['read', 'write'],
        constraints: {}
      },
      {
        resource: `${baseResource}:documents`,
        actions: ['read', 'write'],
        constraints: {}
      },
      {
        resource: 'ai_resource:*',
        actions: ['use'],
        constraints: {
          usage_limits: {
            max_requests_per_hour: 100,
            max_tokens_per_request: 4000
          }
        }
      }
    ];
  }
}

/**
 * Create super admin capabilities
 */
export function createSuperAdminCapabilities(): Capability[] {
  return [
    {
      resource: '*',
      actions: ['*'],
      constraints: {}
    }
  ];
}

/**
 * Extract Bearer token from Authorization header
 */
export function extractBearerToken(authHeader?: string): string | null {
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }
  return authHeader.substring(7);
}

/**
 * Check if JWT token is expired
 */
export function isTokenExpired(token: JWTPayload): boolean {
  return Date.now() >= token.exp * 1000;
}