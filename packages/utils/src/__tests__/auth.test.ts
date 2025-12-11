/**
 * Unit tests for authentication utilities
 */
import {
  generateCapabilityHash,
  verifyCapabilityHash,
  createJWT,
  verifyJWT,
  hasCapability,
  hashPassword,
  verifyPassword,
  generateSecureToken,
  createTenantCapabilities,
  createSuperAdminCapabilities,
  extractBearerToken,
  isTokenExpired
} from '../auth';
import { Capability } from '@gt2/types';

describe('Authentication Utilities', () => {
  describe('Capability Hash Functions', () => {
    const testCapabilities: Capability[] = [
      {
        resource: 'tenant:test:*',
        actions: ['read', 'write'],
        constraints: {}
      }
    ];

    test('generateCapabilityHash creates consistent hash', () => {
      const hash1 = generateCapabilityHash(testCapabilities);
      const hash2 = generateCapabilityHash(testCapabilities);
      
      expect(hash1).toBe(hash2);
      expect(typeof hash1).toBe('string');
      expect(hash1.length).toBeGreaterThan(0);
    });

    test('verifyCapabilityHash validates correct hash', () => {
      const hash = generateCapabilityHash(testCapabilities);
      const isValid = verifyCapabilityHash(testCapabilities, hash);
      
      expect(isValid).toBe(true);
    });

    test('verifyCapabilityHash rejects incorrect hash', () => {
      const isValid = verifyCapabilityHash(testCapabilities, 'incorrect-hash');
      
      expect(isValid).toBe(false);
    });

    test('capability hash changes with different capabilities', () => {
      const capabilities1: Capability[] = [
        { resource: 'tenant:test1:*', actions: ['read'], constraints: {} }
      ];
      const capabilities2: Capability[] = [
        { resource: 'tenant:test2:*', actions: ['write'], constraints: {} }
      ];

      const hash1 = generateCapabilityHash(capabilities1);
      const hash2 = generateCapabilityHash(capabilities2);

      expect(hash1).not.toBe(hash2);
    });
  });

  describe('JWT Functions', () => {
    const testPayload = {
      sub: 'test@example.com',
      tenant_id: '123',
      user_type: 'tenant_user' as const,
      capabilities: [
        {
          resource: 'tenant:test:*',
          actions: ['read', 'write'],
          constraints: {}
        }
      ]
    };

    test('createJWT generates valid token', () => {
      const token = createJWT(testPayload);
      
      expect(typeof token).toBe('string');
      expect(token.split('.')).toHaveLength(3); // JWT has 3 parts
    });

    test('verifyJWT validates correct token', () => {
      const token = createJWT(testPayload);
      const decoded = verifyJWT(token);
      
      expect(decoded).toBeTruthy();
      expect(decoded?.sub).toBe(testPayload.sub);
      expect(decoded?.tenant_id).toBe(testPayload.tenant_id);
      expect(decoded?.user_type).toBe(testPayload.user_type);
    });

    test('verifyJWT rejects invalid token', () => {
      const decoded = verifyJWT('invalid.token.here');
      
      expect(decoded).toBeNull();
    });

    test('verifyJWT rejects tampered token', () => {
      const token = createJWT(testPayload);
      const tamperedToken = token.slice(0, -10) + 'tampered123';
      const decoded = verifyJWT(tamperedToken);
      
      expect(decoded).toBeNull();
    });

    test('isTokenExpired detects expired tokens', () => {
      const expiredPayload = {
        ...testPayload,
        exp: Math.floor(Date.now() / 1000) - 3600, // 1 hour ago
        iat: Math.floor(Date.now() / 1000) - 7200  // 2 hours ago
      };
      
      expect(isTokenExpired(expiredPayload as any)).toBe(true);
    });

    test('isTokenExpired allows valid tokens', () => {
      const validPayload = {
        ...testPayload,
        exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour from now
        iat: Math.floor(Date.now() / 1000)         // Now
      };
      
      expect(isTokenExpired(validPayload as any)).toBe(false);
    });
  });

  describe('Capability Authorization', () => {
    const userCapabilities: Capability[] = [
      {
        resource: 'tenant:acme:*',
        actions: ['read', 'write'],
        constraints: {}
      },
      {
        resource: 'ai_resource:*',
        actions: ['use'],
        constraints: {
          usage_limits: {
            max_requests_per_hour: 100
          }
        }
      }
    ];

    test('hasCapability grants access for exact match', () => {
      const hasAccess = hasCapability(userCapabilities, 'tenant:acme:conversations', 'read');
      expect(hasAccess).toBe(true);
    });

    test('hasCapability grants access for wildcard match', () => {
      const hasAccess = hasCapability(userCapabilities, 'ai_resource:groq', 'use');
      expect(hasAccess).toBe(true);
    });

    test('hasCapability denies access for unauthorized resource', () => {
      const hasAccess = hasCapability(userCapabilities, 'tenant:other:*', 'read');
      expect(hasAccess).toBe(false);
    });

    test('hasCapability denies access for unauthorized action', () => {
      const hasAccess = hasCapability(userCapabilities, 'tenant:acme:*', 'admin');
      expect(hasAccess).toBe(false);
    });

    test('hasCapability respects time constraints', () => {
      const expiredCapabilities: Capability[] = [
        {
          resource: 'tenant:test:*',
          actions: ['read'],
          constraints: {
            valid_until: new Date(Date.now() - 3600000).toISOString() // 1 hour ago
          }
        }
      ];

      const hasAccess = hasCapability(expiredCapabilities, 'tenant:test:*', 'read');
      expect(hasAccess).toBe(false);
    });
  });

  describe('Password Functions', () => {
    const testPassword = 'TestPassword123!';

    test('hashPassword creates valid hash', async () => {
      const hash = await hashPassword(testPassword);
      
      expect(typeof hash).toBe('string');
      expect(hash).not.toBe(testPassword);
      expect(hash.startsWith('$2b$')).toBe(true); // bcrypt hash format
    });

    test('verifyPassword validates correct password', async () => {
      const hash = await hashPassword(testPassword);
      const isValid = await verifyPassword(testPassword, hash);
      
      expect(isValid).toBe(true);
    });

    test('verifyPassword rejects incorrect password', async () => {
      const hash = await hashPassword(testPassword);
      const isValid = await verifyPassword('WrongPassword', hash);
      
      expect(isValid).toBe(false);
    });

    test('different passwords create different hashes', async () => {
      const hash1 = await hashPassword('Password1');
      const hash2 = await hashPassword('Password2');
      
      expect(hash1).not.toBe(hash2);
    });
  });

  describe('Utility Functions', () => {
    test('generateSecureToken creates token of correct length', () => {
      const token = generateSecureToken(16);
      
      expect(typeof token).toBe('string');
      expect(token.length).toBe(32); // Hex encoding doubles the length
    });

    test('generateSecureToken creates different tokens', () => {
      const token1 = generateSecureToken();
      const token2 = generateSecureToken();
      
      expect(token1).not.toBe(token2);
    });

    test('extractBearerToken extracts token correctly', () => {
      const token = extractBearerToken('Bearer abc123token');
      expect(token).toBe('abc123token');
    });

    test('extractBearerToken returns null for invalid format', () => {
      expect(extractBearerToken('Invalid format')).toBeNull();
      expect(extractBearerToken('Bearer')).toBeNull();
      expect(extractBearerToken('')).toBeNull();
      expect(extractBearerToken(undefined)).toBeNull();
    });
  });

  describe('Capability Template Functions', () => {
    test('createTenantCapabilities for admin user', () => {
      const capabilities = createTenantCapabilities('acme', 'tenant_admin');
      
      expect(capabilities).toHaveLength(2);
      expect(capabilities[0].resource).toBe('tenant:acme:*');
      expect(capabilities[0].actions).toContain('admin');
      expect(capabilities[1].resource).toBe('ai_resource:*');
    });

    test('createTenantCapabilities for regular user', () => {
      const capabilities = createTenantCapabilities('acme', 'tenant_user');
      
      expect(capabilities).toHaveLength(3);
      expect(capabilities[0].resource).toBe('tenant:acme:conversations');
      expect(capabilities[0].actions).not.toContain('admin');
      expect(capabilities[1].resource).toBe('tenant:acme:documents');
    });

    test('createSuperAdminCapabilities grants full access', () => {
      const capabilities = createSuperAdminCapabilities();
      
      expect(capabilities).toHaveLength(1);
      expect(capabilities[0].resource).toBe('*');
      expect(capabilities[0].actions).toEqual(['*']);
    });
  });
});