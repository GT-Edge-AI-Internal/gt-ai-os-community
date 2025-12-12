"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.generateCapabilityHash = generateCapabilityHash;
exports.verifyCapabilityHash = verifyCapabilityHash;
exports.createJWT = createJWT;
exports.verifyJWT = verifyJWT;
exports.hasCapability = hasCapability;
exports.hashPassword = hashPassword;
exports.verifyPassword = verifyPassword;
exports.generateSecureToken = generateSecureToken;
exports.createTenantCapabilities = createTenantCapabilities;
exports.createSuperAdminCapabilities = createSuperAdminCapabilities;
exports.extractBearerToken = extractBearerToken;
exports.isTokenExpired = isTokenExpired;
// Authentication and Authorization Utilities
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const crypto_1 = __importDefault(require("crypto"));
// JWT Configuration
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '24h';
/**
 * Generate a cryptographic hash for capability verification
 */
function generateCapabilityHash(capabilities) {
    const capabilityString = JSON.stringify(capabilities, Object.keys(capabilities).sort());
    return crypto_1.default.createHmac('sha256', JWT_SECRET).update(capabilityString).digest('hex');
}
/**
 * Verify capability hash to ensure JWT hasn't been tampered with
 */
function verifyCapabilityHash(capabilities, hash) {
    const expectedHash = generateCapabilityHash(capabilities);
    return crypto_1.default.timingSafeEqual(Buffer.from(hash), Buffer.from(expectedHash));
}
/**
 * Create a capability-based JWT token
 */
function createJWT(payload) {
    const capability_hash = generateCapabilityHash(payload.capabilities);
    const fullPayload = {
        ...payload,
        capability_hash,
        exp: Math.floor(Date.now() / 1000) + (24 * 60 * 60), // 24 hours
        iat: Math.floor(Date.now() / 1000)
    };
    return jsonwebtoken_1.default.sign(fullPayload, JWT_SECRET, { algorithm: 'HS256' });
}
/**
 * Verify and decode a JWT token
 */
function verifyJWT(token) {
    try {
        const decoded = jsonwebtoken_1.default.verify(token, JWT_SECRET);
        // Verify capability hash to ensure token hasn't been tampered with
        if (!verifyCapabilityHash(decoded.capabilities, decoded.capability_hash)) {
            throw new Error('Invalid capability hash');
        }
        return decoded;
    }
    catch (error) {
        return null;
    }
}
/**
 * Check if user has required capability
 */
function hasCapability(userCapabilities, resource, action) {
    return userCapabilities.some(cap => {
        // Check if capability matches resource (support wildcards)
        const resourceMatch = cap.resource === '*' ||
            cap.resource === resource ||
            resource.startsWith(cap.resource.replace('*', ''));
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
async function hashPassword(password) {
    const salt = await bcryptjs_1.default.genSalt(12);
    return bcryptjs_1.default.hash(password, salt);
}
/**
 * Verify password against hash
 */
async function verifyPassword(password, hash) {
    return bcryptjs_1.default.compare(password, hash);
}
/**
 * Generate secure random token
 */
function generateSecureToken(length = 32) {
    return crypto_1.default.randomBytes(length).toString('hex');
}
/**
 * Create tenant-scoped capabilities
 */
function createTenantCapabilities(tenantDomain, userType) {
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
    }
    else {
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
function createSuperAdminCapabilities() {
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
function extractBearerToken(authHeader) {
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return null;
    }
    return authHeader.substring(7);
}
/**
 * Check if JWT token is expired
 */
function isTokenExpired(token) {
    return Date.now() >= token.exp * 1000;
}
