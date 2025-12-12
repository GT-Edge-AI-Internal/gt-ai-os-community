"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * Unit tests for authentication utilities
 */
const auth_1 = require("../auth");
describe('Authentication Utilities', () => {
    describe('Capability Hash Functions', () => {
        const testCapabilities = [
            {
                resource: 'tenant:test:*',
                actions: ['read', 'write'],
                constraints: {}
            }
        ];
        test('generateCapabilityHash creates consistent hash', () => {
            const hash1 = (0, auth_1.generateCapabilityHash)(testCapabilities);
            const hash2 = (0, auth_1.generateCapabilityHash)(testCapabilities);
            expect(hash1).toBe(hash2);
            expect(typeof hash1).toBe('string');
            expect(hash1.length).toBeGreaterThan(0);
        });
        test('verifyCapabilityHash validates correct hash', () => {
            const hash = (0, auth_1.generateCapabilityHash)(testCapabilities);
            const isValid = (0, auth_1.verifyCapabilityHash)(testCapabilities, hash);
            expect(isValid).toBe(true);
        });
        test('verifyCapabilityHash rejects incorrect hash', () => {
            const isValid = (0, auth_1.verifyCapabilityHash)(testCapabilities, 'incorrect-hash');
            expect(isValid).toBe(false);
        });
        test('capability hash changes with different capabilities', () => {
            const capabilities1 = [
                { resource: 'tenant:test1:*', actions: ['read'], constraints: {} }
            ];
            const capabilities2 = [
                { resource: 'tenant:test2:*', actions: ['write'], constraints: {} }
            ];
            const hash1 = (0, auth_1.generateCapabilityHash)(capabilities1);
            const hash2 = (0, auth_1.generateCapabilityHash)(capabilities2);
            expect(hash1).not.toBe(hash2);
        });
    });
    describe('JWT Functions', () => {
        const testPayload = {
            sub: 'test@example.com',
            tenant_id: '123',
            user_type: 'tenant_user',
            capabilities: [
                {
                    resource: 'tenant:test:*',
                    actions: ['read', 'write'],
                    constraints: {}
                }
            ]
        };
        test('createJWT generates valid token', () => {
            const token = (0, auth_1.createJWT)(testPayload);
            expect(typeof token).toBe('string');
            expect(token.split('.')).toHaveLength(3); // JWT has 3 parts
        });
        test('verifyJWT validates correct token', () => {
            const token = (0, auth_1.createJWT)(testPayload);
            const decoded = (0, auth_1.verifyJWT)(token);
            expect(decoded).toBeTruthy();
            expect(decoded?.sub).toBe(testPayload.sub);
            expect(decoded?.tenant_id).toBe(testPayload.tenant_id);
            expect(decoded?.user_type).toBe(testPayload.user_type);
        });
        test('verifyJWT rejects invalid token', () => {
            const decoded = (0, auth_1.verifyJWT)('invalid.token.here');
            expect(decoded).toBeNull();
        });
        test('verifyJWT rejects tampered token', () => {
            const token = (0, auth_1.createJWT)(testPayload);
            const tamperedToken = token.slice(0, -10) + 'tampered123';
            const decoded = (0, auth_1.verifyJWT)(tamperedToken);
            expect(decoded).toBeNull();
        });
        test('isTokenExpired detects expired tokens', () => {
            const expiredPayload = {
                ...testPayload,
                exp: Math.floor(Date.now() / 1000) - 3600, // 1 hour ago
                iat: Math.floor(Date.now() / 1000) - 7200 // 2 hours ago
            };
            expect((0, auth_1.isTokenExpired)(expiredPayload)).toBe(true);
        });
        test('isTokenExpired allows valid tokens', () => {
            const validPayload = {
                ...testPayload,
                exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour from now
                iat: Math.floor(Date.now() / 1000) // Now
            };
            expect((0, auth_1.isTokenExpired)(validPayload)).toBe(false);
        });
    });
    describe('Capability Authorization', () => {
        const userCapabilities = [
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
            const hasAccess = (0, auth_1.hasCapability)(userCapabilities, 'tenant:acme:conversations', 'read');
            expect(hasAccess).toBe(true);
        });
        test('hasCapability grants access for wildcard match', () => {
            const hasAccess = (0, auth_1.hasCapability)(userCapabilities, 'ai_resource:groq', 'use');
            expect(hasAccess).toBe(true);
        });
        test('hasCapability denies access for unauthorized resource', () => {
            const hasAccess = (0, auth_1.hasCapability)(userCapabilities, 'tenant:other:*', 'read');
            expect(hasAccess).toBe(false);
        });
        test('hasCapability denies access for unauthorized action', () => {
            const hasAccess = (0, auth_1.hasCapability)(userCapabilities, 'tenant:acme:*', 'admin');
            expect(hasAccess).toBe(false);
        });
        test('hasCapability respects time constraints', () => {
            const expiredCapabilities = [
                {
                    resource: 'tenant:test:*',
                    actions: ['read'],
                    constraints: {
                        valid_until: new Date(Date.now() - 3600000).toISOString() // 1 hour ago
                    }
                }
            ];
            const hasAccess = (0, auth_1.hasCapability)(expiredCapabilities, 'tenant:test:*', 'read');
            expect(hasAccess).toBe(false);
        });
    });
    describe('Password Functions', () => {
        const testPassword = 'TestPassword123!';
        test('hashPassword creates valid hash', async () => {
            const hash = await (0, auth_1.hashPassword)(testPassword);
            expect(typeof hash).toBe('string');
            expect(hash).not.toBe(testPassword);
            expect(hash.startsWith('$2b$')).toBe(true); // bcrypt hash format
        });
        test('verifyPassword validates correct password', async () => {
            const hash = await (0, auth_1.hashPassword)(testPassword);
            const isValid = await (0, auth_1.verifyPassword)(testPassword, hash);
            expect(isValid).toBe(true);
        });
        test('verifyPassword rejects incorrect password', async () => {
            const hash = await (0, auth_1.hashPassword)(testPassword);
            const isValid = await (0, auth_1.verifyPassword)('WrongPassword', hash);
            expect(isValid).toBe(false);
        });
        test('different passwords create different hashes', async () => {
            const hash1 = await (0, auth_1.hashPassword)('Password1');
            const hash2 = await (0, auth_1.hashPassword)('Password2');
            expect(hash1).not.toBe(hash2);
        });
    });
    describe('Utility Functions', () => {
        test('generateSecureToken creates token of correct length', () => {
            const token = (0, auth_1.generateSecureToken)(16);
            expect(typeof token).toBe('string');
            expect(token.length).toBe(32); // Hex encoding doubles the length
        });
        test('generateSecureToken creates different tokens', () => {
            const token1 = (0, auth_1.generateSecureToken)();
            const token2 = (0, auth_1.generateSecureToken)();
            expect(token1).not.toBe(token2);
        });
        test('extractBearerToken extracts token correctly', () => {
            const token = (0, auth_1.extractBearerToken)('Bearer abc123token');
            expect(token).toBe('abc123token');
        });
        test('extractBearerToken returns null for invalid format', () => {
            expect((0, auth_1.extractBearerToken)('Invalid format')).toBeNull();
            expect((0, auth_1.extractBearerToken)('Bearer')).toBeNull();
            expect((0, auth_1.extractBearerToken)('')).toBeNull();
            expect((0, auth_1.extractBearerToken)(undefined)).toBeNull();
        });
    });
    describe('Capability Template Functions', () => {
        test('createTenantCapabilities for admin user', () => {
            const capabilities = (0, auth_1.createTenantCapabilities)('acme', 'tenant_admin');
            expect(capabilities).toHaveLength(2);
            expect(capabilities[0].resource).toBe('tenant:acme:*');
            expect(capabilities[0].actions).toContain('admin');
            expect(capabilities[1].resource).toBe('ai_resource:*');
        });
        test('createTenantCapabilities for regular user', () => {
            const capabilities = (0, auth_1.createTenantCapabilities)('acme', 'tenant_user');
            expect(capabilities).toHaveLength(3);
            expect(capabilities[0].resource).toBe('tenant:acme:conversations');
            expect(capabilities[0].actions).not.toContain('admin');
            expect(capabilities[1].resource).toBe('tenant:acme:documents');
        });
        test('createSuperAdminCapabilities grants full access', () => {
            const capabilities = (0, auth_1.createSuperAdminCapabilities)();
            expect(capabilities).toHaveLength(1);
            expect(capabilities[0].resource).toBe('*');
            expect(capabilities[0].actions).toEqual(['*']);
        });
    });
});
